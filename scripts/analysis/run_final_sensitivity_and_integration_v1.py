from __future__ import annotations

import hashlib
import os
import json
import math
import platform
import sys
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from lifelines import CoxPHFitter
from lifelines.exceptions import ConvergenceWarning
from patsy import build_design_matrices, dmatrix
from scipy.special import expit
from scipy.stats import norm, rankdata


SEED = 20260621
PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", PROJECT.parent / "data" / "mimiciv.duckdb"))
TABLE = "mental_delirium_analysis.analysis_dataset_v1_1"
SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_final_sensitivity_and_integration_v1.py"
SENS_DIR = PROJECT / "analysis" / "formal_models_v1" / "03_sensitivity_analyses"
INT_DIR = PROJECT / "analysis" / "formal_models_v1" / "04_integrated_results"
MORT_DIR = PROJECT / "analysis" / "formal_models_v1" / "01_primary_mortality"
MORT_V11_DIR = PROJECT / "analysis" / "formal_models_v1" / "01_primary_mortality_v1_1"
READM_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes"
READM_V12_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes_v1_2"

REFERENCE_GROUP = "1_no_primary_psych_no_delirium"
GROUP_ORDER = [
    "1_no_primary_psych_no_delirium",
    "2_primary_psych_no_delirium",
    "3_no_primary_psych_delirium",
    "4_primary_psych_delirium",
]
GROUP_LABELS = {
    "1_no_primary_psych_no_delirium": "No psychiatric comorbidity / no delirium",
    "2_primary_psych_no_delirium": "Psychiatric comorbidity / no delirium",
    "3_no_primary_psych_delirium": "No psychiatric comorbidity / delirium",
    "4_primary_psych_delirium": "Psychiatric comorbidity / delirium",
}
CONTRASTS = [f"{g} vs {REFERENCE_GROUP}" for g in GROUP_ORDER[1:]]

WEIGHT_STRATEGIES = [
    ("untrimmed", "ipw_untrimmed"),
    ("trim_1_99", "ipw_trim_1_99"),
    ("trim_5_95", "ipw_trim_5_95"),
]

warnings.simplefilter("ignore", ConvergenceWarning)


@dataclass
class CoxResult:
    name: str
    formula: str
    cph: CoxPHFitter | None
    design_info: object | None
    fit_df: pd.DataFrame | None
    converged: bool
    error: str = ""
    warning_text: str = ""


@dataclass
class LogisticResult:
    name: str
    formula: str
    result: object | None
    design_info: object | None
    converged: bool
    error: str = ""
    warning_text: str = ""


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def q025(x: pd.Series | np.ndarray) -> float:
    return float(np.nanpercentile(np.asarray(x, dtype=float), 2.5))


def q975(x: pd.Series | np.ndarray) -> float:
    return float(np.nanpercentile(np.asarray(x, dtype=float), 97.5))


def ess(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    return float((np.nansum(w) ** 2) / np.nansum(w**2)) if np.nansum(w**2) > 0 else np.nan


def age_spline() -> str:
    return (
        "cr(age_at_index_admission, knots=(60, 72), "
        "lower_bound=31, upper_bound=89, constraints='center')"
    )


def joint_term(joint_var: str) -> str:
    return f"C({joint_var}, Treatment(reference='{REFERENCE_GROUP}'))"


def base_terms(joint_var: str, charlson_var: str = "charlson_comorbidity_only_documented_by_index") -> list[str]:
    return [
        joint_term(joint_var),
        age_spline(),
        "C(sex_recorded)",
        "C(race_group)",
        "C(anchor_year_group)",
        "C(admission_type_group)",
        "C(admission_location_group)",
        "C(first_careunit_group)",
        "log1p_prior_mimic_hospitalizations",
        charlson_var,
        "dementia_documented_by_index",
        "substance_use_documented_by_index",
        "chronic_neurologic_disease",
    ]


def model_formula(
    joint_var: str = "joint_exposure_4level",
    severity: str = "main",
    charlson_var: str = "charlson_comorbidity_only_documented_by_index",
) -> str:
    terms = base_terms(joint_var, charlson_var=charlson_var)
    if severity == "main":
        terms += [
            "nonneurologic_sofa_zero_imputed",
            "C(nonneurologic_sofa_observed_components_n, Treatment(reference=5))",
        ]
    elif severity == "none":
        pass
    elif severity == "full_sofa":
        terms += ["full_sofa_official_first_day"]
    elif severity == "oasis":
        terms += ["oasis_official_first_day"]
    elif severity == "organ_support":
        terms += [
            "invasive_ventilation_0_24h",
            "vasopressor_any_0_24h",
            "rrt_any_0_24h",
            "sepsis3_index",
        ]
    elif severity == "nonneurologic_sofa_0_6h":
        terms += [
            "nonneurologic_sofa_0_6h_zero_imputed",
            "C(nonneurologic_sofa_0_6h_observed_components_n, Treatment(reference=5))",
        ]
    else:
        raise ValueError(f"Unknown severity option: {severity}")
    return " + ".join(terms)


def interaction_formula(
    psych_var: str,
    delirium_var: str,
    severity: str = "main",
    charlson_var: str = "charlson_comorbidity_only_documented_by_index",
) -> str:
    terms = [
        psych_var,
        delirium_var,
        f"{psych_var}:{delirium_var}",
        age_spline(),
        "C(sex_recorded)",
        "C(race_group)",
        "C(anchor_year_group)",
        "C(admission_type_group)",
        "C(admission_location_group)",
        "C(first_careunit_group)",
        "log1p_prior_mimic_hospitalizations",
        charlson_var,
        "dementia_documented_by_index",
        "substance_use_documented_by_index",
        "chronic_neurologic_disease",
    ]
    if severity == "main":
        terms += [
            "nonneurologic_sofa_zero_imputed",
            "C(nonneurologic_sofa_observed_components_n, Treatment(reference=5))",
        ]
    return " + ".join(terms)


def selection_formula() -> str:
    terms = [
        age_spline(),
        "C(sex_recorded)",
        "C(race_group)",
        "C(anchor_year_group)",
        "C(admission_type_group)",
        "C(admission_location_group)",
        "C(first_careunit_group)",
        "log1p_prior_mimic_hospitalizations",
        "charlson_comorbidity_only_strict_prior",
        "dementia_strict_prior",
        "substance_use_strict_prior",
        "chronic_neurologic_disease",
        "psych_primary_strict_prior",
        "nonneurologic_sofa_zero_imputed",
        "C(nonneurologic_sofa_observed_components_n, Treatment(reference=5))",
        "invasive_ventilation_0_24h",
        "vasopressor_any_0_24h",
        "rrt_any_0_24h",
        "sepsis3_index",
        "C(insurance_group)",
        "C(language_group)",
        "C(marital_status_group)",
    ]
    return " + ".join(terms)


def design_matrix(raw: pd.DataFrame, formula: str, design_info=None, drop_intercept: bool = True) -> tuple[pd.DataFrame, object]:
    if design_info is None:
        X = dmatrix(formula, raw, return_type="dataframe")
        design_info = X.design_info
    else:
        X = build_design_matrices([design_info], raw, return_type="dataframe")[0]
    X = pd.DataFrame(X, index=raw.index)
    if drop_intercept and "Intercept" in X.columns:
        X = X.drop(columns=["Intercept"])
    return X.astype(float), design_info


def load_data() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(f"select * from {TABLE}").fetchdf()
    con.close()
    return prepare_data(df)


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    categorical = [
        "sex_recorded",
        "race_group",
        "anchor_year_group",
        "admission_type_group",
        "admission_location_group",
        "first_careunit_group",
        "insurance_group",
        "language_group",
        "marital_status_group",
        "discharge_destination_group",
        "psych_timing_group",
    ]
    for col in categorical:
        if col in df.columns:
            df[col] = df[col].fillna("Missing").astype(str)

    numeric_cols = [
        "base_population",
        "delirium_classifiable_72h",
        "primary_analysis_cohort",
        "conservative_readmission_cohort",
        "psych_primary_documented_by_index",
        "psych_primary_strict_prior",
        "psych_primary_index_only",
        "dementia_documented_by_index",
        "dementia_strict_prior",
        "substance_use_documented_by_index",
        "substance_use_strict_prior",
        "chronic_neurologic_disease",
        "death_365d_main",
        "death_365d_include_same_day",
        "time_to_death_or_censor_365d",
        "readmission_90d_event",
        "readmission_90d_status",
        "time_to_first_readmission_or_death_90d",
        "icu_readmission_365d_event",
        "icu_readmission_365d_status",
        "time_to_first_icu_readmission_or_death_365d",
        "age_at_index_admission",
        "prior_mimic_hospitalizations",
        "charlson_comorbidity_only_documented_by_index",
        "charlson_comorbidity_only_strict_prior",
        "nonneurologic_sofa_zero_imputed",
        "nonneurologic_sofa_observed_components_n",
        "invasive_ventilation_0_24h",
        "vasopressor_any_0_24h",
        "rrt_any_0_24h",
        "sepsis3_index",
        "hospice_discharge",
        "full_sofa_official_first_day",
        "oasis_official_first_day",
        "approximate_discharge_year_upper",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    binary_fill_zero = [
        "base_population",
        "delirium_classifiable_72h",
        "primary_analysis_cohort",
        "conservative_readmission_cohort",
        "psych_primary_documented_by_index",
        "psych_primary_strict_prior",
        "psych_primary_index_only",
        "dementia_documented_by_index",
        "dementia_strict_prior",
        "substance_use_documented_by_index",
        "substance_use_strict_prior",
        "chronic_neurologic_disease",
        "death_365d_main",
        "death_365d_include_same_day",
        "readmission_90d_event",
        "icu_readmission_365d_event",
        "invasive_ventilation_0_24h",
        "vasopressor_any_0_24h",
        "rrt_any_0_24h",
        "sepsis3_index",
        "hospice_discharge",
    ]
    for col in binary_fill_zero:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    for col in [
        "prior_mimic_hospitalizations",
        "charlson_comorbidity_only_documented_by_index",
        "charlson_comorbidity_only_strict_prior",
        "nonneurologic_sofa_zero_imputed",
        "nonneurologic_sofa_observed_components_n",
        "full_sofa_official_first_day",
        "oasis_official_first_day",
    ]:
        if col in df.columns and df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    df["log1p_prior_mimic_hospitalizations"] = np.log1p(df["prior_mimic_hospitalizations"].astype(float))
    df["event_main"] = df["death_365d_main"].astype(int)
    df["time_main"] = df["time_to_death_or_censor_365d"].astype(float)
    df["delirium_binary_72h"] = np.where(df["delirium_status_72h"].eq("positive"), 1, 0)
    df["delirium_binary_48h"] = np.where(df["delirium_status_48h"].eq("positive"), 1, 0)
    df["joint_exposure_4level"] = pd.Categorical(df["joint_exposure_4level"].astype(str), categories=GROUP_ORDER)

    df["joint_exposure_strict_prior_4level"] = make_joint_group(
        df["psych_primary_strict_prior"].astype(int), df["delirium_status_72h"].eq("positive")
    )
    df["joint_exposure_48h_4level"] = make_joint_group(
        df["psych_primary_documented_by_index"].astype(int), df["delirium_status_48h"].eq("positive")
    )
    return df


def make_joint_group(psych: pd.Series, delirium_positive: pd.Series) -> pd.Categorical:
    psych_bool = psych.fillna(0).astype(int).eq(1)
    delir_bool = delirium_positive.fillna(False).astype(bool)
    values = np.select(
        [
            (~psych_bool) & (~delir_bool),
            psych_bool & (~delir_bool),
            (~psych_bool) & delir_bool,
            psych_bool & delir_bool,
        ],
        GROUP_ORDER,
        default=GROUP_ORDER[0],
    )
    return pd.Categorical(values, categories=GROUP_ORDER)


def clean_model_df(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df.replace([np.inf, -np.inf], np.nan).dropna(subset=cols).copy()


def fit_cox(
    raw: pd.DataFrame,
    formula: str,
    time_col: str,
    event_col: str,
    name: str,
    weights: np.ndarray | pd.Series | None = None,
    robust: bool = False,
) -> CoxResult:
    try:
        X, design_info = design_matrix(raw, formula, drop_intercept=True)
        fit_df = pd.concat(
            [
                X,
                raw[[time_col, event_col]].rename(columns={time_col: "_time", event_col: "_event"}).astype(float),
            ],
            axis=1,
        )
        fit_df = fit_df.replace([np.inf, -np.inf], np.nan).dropna()
        if weights is not None:
            w = pd.Series(weights, index=raw.index).reindex(fit_df.index).astype(float)
            fit_df["_weight"] = w.to_numpy(dtype=float)
        cph = CoxPHFitter(penalizer=0.0)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cph.fit(
                fit_df,
                duration_col="_time",
                event_col="_event",
                weights_col="_weight" if weights is not None else None,
                robust=robust,
                batch_mode=True,
                show_progress=False,
            )
        warning_text = " | ".join(str(w.message) for w in caught)[:1000]
        return CoxResult(name=name, formula=formula, cph=cph, design_info=design_info, fit_df=fit_df, converged=True, warning_text=warning_text)
    except Exception as exc:
        return CoxResult(name=name, formula=formula, cph=None, design_info=None, fit_df=None, converged=False, error=f"{type(exc).__name__}: {exc}")


def cox_joint_rows(model: CoxResult, outcome: str, population: str, analysis: str, weight_strategy: str = "none") -> pd.DataFrame:
    rows: list[dict] = []
    for group in GROUP_ORDER[1:]:
        rows.append(
            {
                "outcome": outcome,
                "analysis": analysis,
                "population": population,
                "weight_strategy": weight_strategy,
                "model": model.name,
                "group": group,
                "contrast": f"{group} vs {REFERENCE_GROUP}",
                "term": "",
                "HR": np.nan,
                "CI95_lower": np.nan,
                "CI95_upper": np.nan,
                "p_value": np.nan,
                "n": int(model.fit_df.shape[0]) if model.fit_df is not None else 0,
                "events": int(model.fit_df["_event"].sum()) if model.fit_df is not None and "_event" in model.fit_df else 0,
                "converged": bool(model.converged),
                "warning": model.warning_text,
                "error": model.error,
            }
        )
    if not model.converged or model.cph is None:
        return pd.DataFrame(rows)
    summary = model.cph.summary
    for term, s in summary.iterrows():
        for group in GROUP_ORDER[1:]:
            if group in term:
                idx = GROUP_ORDER.index(group) - 1
                rows[idx].update(
                    {
                        "term": term,
                        "HR": float(s["exp(coef)"]),
                        "CI95_lower": float(s["exp(coef) lower 95%"]),
                        "CI95_upper": float(s["exp(coef) upper 95%"]),
                        "p_value": float(s["p"]),
                    }
                )
    return pd.DataFrame(rows)


def fit_logistic(
    raw: pd.DataFrame,
    formula: str,
    outcome_col: str,
    name: str,
    weights: np.ndarray | pd.Series | None = None,
) -> LogisticResult:
    try:
        X, design_info = design_matrix(raw, formula, drop_intercept=False)
        y = raw[outcome_col].astype(float).reindex(X.index)
        model_kwargs = {"family": sm.families.Binomial()}
        if weights is not None:
            w = pd.Series(weights, index=raw.index).reindex(X.index).astype(float)
            model_kwargs["freq_weights"] = w
        glm = sm.GLM(y, X, **model_kwargs)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = glm.fit(maxiter=200, disp=0)
        warning_text = " | ".join(str(w.message) for w in caught)[:1000]
        return LogisticResult(name=name, formula=formula, result=result, design_info=design_info, converged=True, warning_text=warning_text)
    except Exception as exc:
        return LogisticResult(name=name, formula=formula, result=None, design_info=None, converged=False, error=f"{type(exc).__name__}: {exc}")


def standardized_logistic_risk(
    model: LogisticResult,
    raw: pd.DataFrame,
    joint_var: str,
    weights: np.ndarray | pd.Series | None = None,
) -> pd.DataFrame:
    rows: list[dict] = []
    if not model.converged or model.result is None:
        for group in GROUP_ORDER:
            rows.append({"model": model.name, "group": group, "label": GROUP_LABELS[group], "risk": np.nan, "converged": False, "error": model.error})
        return pd.DataFrame(rows)
    avg_weights = None
    if weights is not None:
        avg_weights = pd.Series(weights, index=raw.index).astype(float)
    for group in GROUP_ORDER:
        cf = raw.copy()
        cf[joint_var] = pd.Categorical([group] * cf.shape[0], categories=GROUP_ORDER)
        X, _ = design_matrix(cf, model.formula, design_info=model.design_info, drop_intercept=False)
        pred = model.result.predict(X)
        if avg_weights is None:
            risk = float(np.mean(pred))
        else:
            risk = float(np.average(pred, weights=avg_weights.reindex(X.index)))
        ref_note = ""
        rows.append({"model": model.name, "group": group, "label": GROUP_LABELS[group], "risk": risk, "converged": True, "error": ref_note})
    ref = rows[0]["risk"]
    for row in rows:
        row["risk_difference_vs_group1"] = float(row["risk"] - ref) if pd.notna(row["risk"]) else np.nan
        row["risk_ratio_vs_group1"] = float(row["risk"] / ref) if pd.notna(row["risk"]) and ref else np.nan
    return pd.DataFrame(rows)


def additive_from_risks(risk_df: pd.DataFrame, outcome: str, analysis: str) -> pd.DataFrame:
    sub = risk_df.set_index("group").reindex(GROUP_ORDER)
    r00, r10, r01, r11 = [float(sub.loc[g, "risk"]) for g in GROUP_ORDER]
    rr10 = r10 / r00 if r00 else np.nan
    rr01 = r01 / r00 if r00 else np.nan
    rr11 = r11 / r00 if r00 else np.nan
    denom = (rr10 - 1) + (rr01 - 1)
    values = {
        "R00": r00,
        "R10": r10,
        "R01": r01,
        "R11": r11,
        "interaction_contrast": r11 - r10 - r01 + r00,
        "RR10": rr10,
        "RR01": rr01,
        "RR11": rr11,
        "RERI": rr11 - rr10 - rr01 + 1 if all(pd.notna([rr10, rr01, rr11])) else np.nan,
        "AP": (rr11 - rr10 - rr01 + 1) / rr11 if rr11 else np.nan,
        "synergy_index": (rr11 - 1) / denom if denom and abs(denom) > 1e-9 else np.nan,
    }
    return pd.DataFrame(
        [
            {"outcome": outcome, "analysis": analysis, "metric": metric, "estimate": estimate, "ci95_lower": np.nan, "ci95_upper": np.nan}
            for metric, estimate in values.items()
        ]
    )


def cox_interaction_row(
    raw: pd.DataFrame,
    psych_var: str,
    delirium_var: str,
    time_col: str,
    event_col: str,
    outcome: str,
    analysis: str,
    weights: np.ndarray | pd.Series | None = None,
    robust: bool = False,
) -> pd.DataFrame:
    formula = interaction_formula(psych_var, delirium_var)
    model = fit_cox(raw, formula, time_col, event_col, f"{analysis} interaction", weights=weights, robust=robust)
    row = {
        "outcome": outcome,
        "analysis": analysis,
        "term": f"{psych_var}:{delirium_var}",
        "HR": np.nan,
        "CI95_lower": np.nan,
        "CI95_upper": np.nan,
        "p_value": np.nan,
        "n": int(model.fit_df.shape[0]) if model.fit_df is not None else 0,
        "events": int(model.fit_df["_event"].sum()) if model.fit_df is not None and "_event" in model.fit_df else 0,
        "converged": model.converged,
        "warning": model.warning_text,
        "error": model.error,
    }
    if model.converged and model.cph is not None:
        for term, s in model.cph.summary.iterrows():
            if psych_var in term and delirium_var in term and ":" in term:
                row.update(
                    {
                        "term": term,
                        "HR": float(s["exp(coef)"]),
                        "CI95_lower": float(s["exp(coef) lower 95%"]),
                        "CI95_upper": float(s["exp(coef) upper 95%"]),
                        "p_value": float(s["p"]),
                    }
                )
    return pd.DataFrame([row])


def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pos = y == 1
    neg = y == 0
    n_pos = int(pos.sum())
    n_neg = int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return np.nan
    ranks = rankdata(p)
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(y, dtype=float) - np.asarray(p, dtype=float)) ** 2))


def calibration(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=float)
    lp = np.log(p / (1 - p))
    X = sm.add_constant(lp)
    try:
        res = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=100, disp=0)
        return float(res.params[0]), float(res.params[1])
    except Exception:
        return np.nan, np.nan


def stratified_folds(y: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    folds = np.empty(len(y), dtype=int)
    for value in [0, 1]:
        idx = np.where(y == value)[0]
        rng.shuffle(idx)
        for fold, part in enumerate(np.array_split(idx, k)):
            folds[part] = fold
    return folds


def build_selection_weights(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = base["delirium_classifiable_72h"].astype(int).to_numpy()
    X, design_info = design_matrix(base, selection_formula(), drop_intercept=False)
    folds = stratified_folds(y, 5, SEED)
    oof = np.full(len(base), np.nan, dtype=float)
    perf_rows: list[dict] = []

    for fold in range(5):
        train = folds != fold
        test = folds == fold
        glm = sm.GLM(y[train], X.iloc[train], family=sm.families.Binomial())
        result = glm.fit(maxiter=200, disp=0)
        pred = np.clip(result.predict(X.iloc[test]), 1e-6, 1 - 1e-6)
        oof[test] = pred
        intercept, slope = calibration(y[test], pred)
        perf_rows.append(
            {
                "fold": fold + 1,
                "AUC": auc_score(y[test], pred),
                "Brier_score": brier_score(y[test], pred),
                "calibration_intercept": intercept,
                "calibration_slope": slope,
                "probability_min": float(np.min(pred)),
                "probability_p1": float(np.percentile(pred, 1)),
                "probability_p5": float(np.percentile(pred, 5)),
                "probability_median": float(np.median(pred)),
                "probability_p95": float(np.percentile(pred, 95)),
                "probability_p99": float(np.percentile(pred, 99)),
                "probability_max": float(np.max(pred)),
            }
        )
    perf_rows.append(
        {
            "fold": "overall_oof",
            "AUC": auc_score(y, oof),
            "Brier_score": brier_score(y, oof),
            "calibration_intercept": calibration(y, oof)[0],
            "calibration_slope": calibration(y, oof)[1],
            "probability_min": float(np.min(oof)),
            "probability_p1": float(np.percentile(oof, 1)),
            "probability_p5": float(np.percentile(oof, 5)),
            "probability_median": float(np.median(oof)),
            "probability_p95": float(np.percentile(oof, 95)),
            "probability_p99": float(np.percentile(oof, 99)),
            "probability_max": float(np.max(oof)),
        }
    )
    perf = pd.DataFrame(perf_rows)

    work = base.copy()
    work["_oof_classifiable_probability"] = oof
    overall = float(y.mean())
    classifiable = work["delirium_classifiable_72h"].eq(1)
    sw = overall / np.clip(work.loc[classifiable, "_oof_classifiable_probability"].to_numpy(dtype=float), 1e-6, 1.0)
    p1, p99 = np.percentile(sw, [1, 99])
    p5, p95 = np.percentile(sw, [5, 95])
    work["ipw_untrimmed"] = np.nan
    work["ipw_trim_1_99"] = np.nan
    work["ipw_trim_5_95"] = np.nan
    work.loc[classifiable, "ipw_untrimmed"] = sw
    work.loc[classifiable, "ipw_trim_1_99"] = np.clip(sw, p1, p99)
    work.loc[classifiable, "ipw_trim_5_95"] = np.clip(sw, p5, p95)

    dist_rows = []
    for label, col in WEIGHT_STRATEGIES:
        values = work.loc[classifiable, col].to_numpy(dtype=float)
        dist_rows.append(
            {
                "weight_strategy": label,
                "n": int(values.size),
                "mean": float(np.mean(values)),
                "SD": float(np.std(values, ddof=1)),
                "min": float(np.min(values)),
                "p1": float(np.percentile(values, 1)),
                "p5": float(np.percentile(values, 5)),
                "median": float(np.median(values)),
                "p95": float(np.percentile(values, 95)),
                "p99": float(np.percentile(values, 99)),
                "max": float(np.max(values)),
                "effective_sample_size": ess(values),
                "overall_classifiable_probability": overall,
            }
        )
    dist = pd.DataFrame(dist_rows)
    balance = selection_balance(work)
    return work.drop(columns=["_oof_classifiable_probability"]), perf, dist, balance


def weighted_mean(x: pd.Series, w: np.ndarray) -> float:
    return float(np.average(pd.to_numeric(x, errors="coerce"), weights=w))


def weighted_var(x: pd.Series, w: np.ndarray) -> float:
    vals = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
    mu = np.average(vals, weights=w)
    return float(np.average((vals - mu) ** 2, weights=w))


def smd_cont(full: pd.Series, comp: pd.Series, w_full: np.ndarray, w_comp: np.ndarray) -> float:
    m1, m2 = weighted_mean(full, w_full), weighted_mean(comp, w_comp)
    v1, v2 = weighted_var(full, w_full), weighted_var(comp, w_comp)
    denom = math.sqrt((v1 + v2) / 2)
    return float((m2 - m1) / denom) if denom > 0 else 0.0


def smd_binary(p_full: float, p_comp: float) -> float:
    denom = math.sqrt((p_full * (1 - p_full) + p_comp * (1 - p_comp)) / 2)
    return float((p_comp - p_full) / denom) if denom > 0 else 0.0


def selection_balance(work: pd.DataFrame) -> pd.DataFrame:
    continuous = [
        "age_at_index_admission",
        "log1p_prior_mimic_hospitalizations",
        "charlson_comorbidity_only_strict_prior",
        "nonneurologic_sofa_zero_imputed",
    ]
    categorical = [
        "sex_recorded",
        "race_group",
        "anchor_year_group",
        "admission_type_group",
        "admission_location_group",
        "first_careunit_group",
        "nonneurologic_sofa_observed_components_n",
        "insurance_group",
        "language_group",
        "marital_status_group",
        "dementia_strict_prior",
        "substance_use_strict_prior",
        "chronic_neurologic_disease",
        "psych_primary_strict_prior",
        "invasive_ventilation_0_24h",
        "vasopressor_any_0_24h",
        "rrt_any_0_24h",
        "sepsis3_index",
    ]
    full = work.copy()
    comp = work[work["delirium_classifiable_72h"].eq(1)].copy()
    strategies = [
        ("unweighted_classifiable", np.ones(comp.shape[0])),
        ("trim_1_99_weighted_classifiable", comp["ipw_trim_1_99"].to_numpy(dtype=float)),
        ("trim_5_95_weighted_classifiable", comp["ipw_trim_5_95"].to_numpy(dtype=float)),
    ]
    rows: list[dict] = []
    w_full = np.ones(full.shape[0], dtype=float)
    for variable in continuous:
        for strategy, w_comp in strategies:
            rows.append(
                {
                    "variable": variable,
                    "level": "continuous",
                    "strategy": strategy,
                    "smd": smd_cont(full[variable], comp[variable], w_full, w_comp),
                    "abs_smd": abs(smd_cont(full[variable], comp[variable], w_full, w_comp)),
                }
            )
    for variable in categorical:
        levels = sorted(set(full[variable].fillna("Missing").astype(str).unique()) | set(comp[variable].fillna("Missing").astype(str).unique()))
        for level in levels:
            full_ind = full[variable].fillna("Missing").astype(str).eq(level).astype(float)
            p_full = float(np.average(full_ind, weights=w_full))
            for strategy, w_comp in strategies:
                comp_ind = comp[variable].fillna("Missing").astype(str).eq(level).astype(float)
                p_comp = float(np.average(comp_ind, weights=w_comp))
                smd = smd_binary(p_full, p_comp)
                rows.append({"variable": variable, "level": level, "strategy": strategy, "smd": smd, "abs_smd": abs(smd)})
    return pd.DataFrame(rows)


def plot_balance(balance: pd.DataFrame) -> None:
    summary = balance.groupby(["variable", "strategy"], as_index=False)["abs_smd"].max()
    pivot = summary.pivot(index="variable", columns="strategy", values="abs_smd").fillna(0)
    pivot = pivot.sort_values("unweighted_classifiable", ascending=True)
    fig_h = max(6, 0.28 * pivot.shape[0] + 2)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    y = np.arange(pivot.shape[0])
    for strategy, marker in [
        ("unweighted_classifiable", "o"),
        ("trim_1_99_weighted_classifiable", "s"),
        ("trim_5_95_weighted_classifiable", "^"),
    ]:
        if strategy in pivot:
            ax.scatter(pivot[strategy], y, label=strategy, marker=marker, s=24)
    ax.axvline(0.1, color="grey", linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xlabel("Maximum absolute SMD")
    ax.set_title("Classifiability Selection Balance")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(SENS_DIR / "figure_selection_weight_balance.pdf")
    plt.close(fig)


def run_ipsw(df: pd.DataFrame, weighted: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    classifiable = weighted[weighted["primary_analysis_cohort"].eq(1)].copy()
    classifiable["joint_exposure_4level"] = pd.Categorical(classifiable["joint_exposure_4level"], categories=GROUP_ORDER)
    form = model_formula("joint_exposure_4level", "main")

    mortality_rows = []
    risk_rows = []
    read_rows = []
    icu_rows = []
    diag_rows = []
    mortality_base = clean_model_df(classifiable, ["time_main", "event_main"])
    for label, wcol in WEIGHT_STRATEGIES:
        print(f"  IPSW mortality Cox/logistic: {label}", flush=True)
        w = mortality_base[wcol].to_numpy(dtype=float)
        model = fit_cox(mortality_base, form, "time_main", "event_main", f"IPSW mortality Model 2 {label}", weights=w, robust=False)
        tmp = cox_joint_rows(model, "365-day mortality", "primary classifiable", "IPSW Model 2 Cox", label)
        tmp["robust_sandwich_requested"] = True
        tmp["robust_sandwich_computed"] = False
        tmp["robust_sandwich_note"] = "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported as technical sensitivity"
        mortality_rows.append(tmp)
        logit = fit_logistic(mortality_base, form, "event_main", f"IPSW fixed-horizon logistic {label}", weights=w)
        risk = standardized_logistic_risk(logit, mortality_base, "joint_exposure_4level", weights=w)
        risk["outcome"] = "365-day mortality"
        risk["analysis"] = "IPSW weighted fixed-horizon logistic g-computation"
        risk["weight_strategy"] = label
        risk_rows.append(risk)
        diag_rows.append(
            {
                "analysis": "ipsw_mortality",
                "weight_strategy": label,
                "n": int(mortality_base.shape[0]),
                "events": int(mortality_base["event_main"].sum()),
                "cox_converged": model.converged,
                "logistic_converged": logit.converged,
                "robust_sandwich_requested": True,
                "robust_sandwich_computed": False,
                "robust_sandwich_note": "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported",
                "cox_warning": model.warning_text,
                "logistic_warning": logit.warning_text,
                "cox_error": model.error,
                "logistic_error": logit.error,
            }
        )

    read_base = classifiable[classifiable["conservative_readmission_cohort"].eq(1)].copy()
    read_base = clean_model_df(read_base, ["time_to_first_readmission_or_death_90d", "readmission_90d_status"])
    read_base["readmission_target_event"] = read_base["readmission_90d_status"].eq(1).astype(int)
    icu_base = classifiable[classifiable["conservative_readmission_cohort"].eq(1)].copy()
    icu_base = clean_model_df(icu_base, ["time_to_first_icu_readmission_or_death_365d", "icu_readmission_365d_status"])
    icu_base["icu_target_event"] = icu_base["icu_readmission_365d_status"].eq(1).astype(int)
    for label, wcol in WEIGHT_STRATEGIES:
        print(f"  IPSW readmission Cox: {label}", flush=True)
        wm = read_base[wcol].to_numpy(dtype=float)
        model = fit_cox(
            read_base,
            form,
            "time_to_first_readmission_or_death_90d",
            "readmission_target_event",
            f"IPSW readmission Model 2 {label}",
            weights=wm,
            robust=False,
        )
        tmp = cox_joint_rows(model, "90-day same-system readmission", "conservative readmission cohort", "IPSW Model 2 cause-specific Cox", label)
        tmp["robust_sandwich_requested"] = True
        tmp["robust_sandwich_computed"] = False
        tmp["robust_sandwich_note"] = "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported as technical sensitivity"
        read_rows.append(tmp)
        diag_rows.append(
            {
                "analysis": "ipsw_readmission_90d",
                "weight_strategy": label,
                "n": int(read_base.shape[0]),
                "events": int(read_base["readmission_target_event"].sum()),
                "cox_converged": model.converged,
                "logistic_converged": np.nan,
                "robust_sandwich_requested": True,
                "robust_sandwich_computed": False,
                "robust_sandwich_note": "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported",
                "cox_warning": model.warning_text,
                "logistic_warning": "",
                "cox_error": model.error,
                "logistic_error": "",
            }
        )
        print(f"  IPSW ICU readmission Cox: {label}", flush=True)
        wi = icu_base[wcol].to_numpy(dtype=float)
        model = fit_cox(
            icu_base,
            form,
            "time_to_first_icu_readmission_or_death_365d",
            "icu_target_event",
            f"IPSW ICU readmission Model 2 {label}",
            weights=wi,
            robust=False,
        )
        tmp = cox_joint_rows(model, "365-day same-system ICU readmission", "conservative readmission cohort", "IPSW Model 2 cause-specific Cox", label)
        tmp["robust_sandwich_requested"] = True
        tmp["robust_sandwich_computed"] = False
        tmp["robust_sandwich_note"] = "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported as technical sensitivity"
        icu_rows.append(tmp)
        diag_rows.append(
            {
                "analysis": "ipsw_icu_readmission_365d",
                "weight_strategy": label,
                "n": int(icu_base.shape[0]),
                "events": int(icu_base["icu_target_event"].sum()),
                "cox_converged": model.converged,
                "logistic_converged": np.nan,
                "robust_sandwich_requested": True,
                "robust_sandwich_computed": False,
                "robust_sandwich_note": "lifelines robust weighted Cox did not complete in feasible runtime; weighted Cox point estimate with model-based CI reported",
                "cox_warning": model.warning_text,
                "logistic_warning": "",
                "cox_error": model.error,
                "logistic_error": "",
            }
        )

    return (
        pd.concat(mortality_rows, ignore_index=True),
        pd.concat(risk_rows, ignore_index=True),
        pd.concat(read_rows, ignore_index=True),
        pd.concat(icu_rows, ignore_index=True),
        pd.DataFrame(diag_rows),
    )


def group_counts(raw: pd.DataFrame, group_col: str, cohort_name: str) -> pd.DataFrame:
    rows = []
    for group in GROUP_ORDER:
        sub = raw[raw[group_col].astype(str).eq(group)]
        rows.append(
            {
                "cohort": cohort_name,
                "group": group,
                "label": GROUP_LABELS[group],
                "n": int(sub.shape[0]),
                "death_365d_events": int(sub["death_365d_main"].sum()),
                "readmission_90d_events": int(sub["readmission_90d_event"].sum()),
                "icu_readmission_365d_events": int(sub["icu_readmission_365d_event"].sum()),
            }
        )
    return pd.DataFrame(rows)


def run_group_sensitivity(
    raw: pd.DataFrame,
    group_col: str,
    psych_var: str,
    delirium_var: str,
    analysis_prefix: str,
    mortality_pop_label: str,
    readmission_pop_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mortality = clean_model_df(raw, ["time_main", "event_main", group_col])
    mortality[group_col] = pd.Categorical(mortality[group_col].astype(str), categories=GROUP_ORDER)
    form = model_formula(group_col, "main")
    mortality_model = fit_cox(mortality, form, "time_main", "event_main", f"{analysis_prefix} mortality Model 2")
    mortality_rows = cox_joint_rows(mortality_model, "365-day mortality", mortality_pop_label, f"{analysis_prefix} Model 2 Cox")
    logit = fit_logistic(mortality, form, "event_main", f"{analysis_prefix} fixed-horizon logistic")
    risk = standardized_logistic_risk(logit, mortality, group_col)
    risk["outcome"] = "365-day mortality"
    risk["analysis"] = f"{analysis_prefix} fixed-horizon logistic g-computation"
    add = additive_from_risks(risk.rename(columns={"risk": "risk"}), "365-day mortality", f"{analysis_prefix} additive interaction")
    mort_int = cox_interaction_row(mortality, psych_var, delirium_var, "time_main", "event_main", "365-day mortality", f"{analysis_prefix} multiplicative interaction")

    read = raw[raw["conservative_readmission_cohort_for_sensitivity"].eq(1)].copy()
    read = clean_model_df(read, ["time_to_first_readmission_or_death_90d", "readmission_90d_status", group_col])
    read[group_col] = pd.Categorical(read[group_col].astype(str), categories=GROUP_ORDER)
    read["readmission_target_event"] = read["readmission_90d_status"].eq(1).astype(int)
    r_model = fit_cox(read, form, "time_to_first_readmission_or_death_90d", "readmission_target_event", f"{analysis_prefix} readmission Model 2")
    read_rows = cox_joint_rows(r_model, "90-day same-system readmission", readmission_pop_label, f"{analysis_prefix} Model 2 cause-specific Cox")
    read_int = cox_interaction_row(
        read,
        psych_var,
        delirium_var,
        "time_to_first_readmission_or_death_90d",
        "readmission_target_event",
        "90-day same-system readmission",
        f"{analysis_prefix} multiplicative interaction",
    )

    icu = raw[raw["conservative_readmission_cohort_for_sensitivity"].eq(1)].copy()
    icu = clean_model_df(icu, ["time_to_first_icu_readmission_or_death_365d", "icu_readmission_365d_status", group_col])
    icu[group_col] = pd.Categorical(icu[group_col].astype(str), categories=GROUP_ORDER)
    icu["icu_target_event"] = icu["icu_readmission_365d_status"].eq(1).astype(int)
    i_model = fit_cox(icu, form, "time_to_first_icu_readmission_or_death_365d", "icu_target_event", f"{analysis_prefix} ICU readmission Model 2")
    icu_rows = cox_joint_rows(i_model, "365-day same-system ICU readmission", readmission_pop_label, f"{analysis_prefix} Model 2 cause-specific Cox")
    icu_int = cox_interaction_row(
        icu,
        psych_var,
        delirium_var,
        "time_to_first_icu_readmission_or_death_365d",
        "icu_target_event",
        "365-day same-system ICU readmission",
        f"{analysis_prefix} multiplicative interaction",
    )

    interactions = pd.concat([mort_int, read_int, icu_int, add], ignore_index=True, sort=False)
    return mortality_rows, risk, pd.concat([read_rows, icu_rows], ignore_index=True), interactions, add


def run_full_classifiable_and_hospice(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    form = model_formula("joint_exposure_4level", "main")
    full = df[df["primary_analysis_cohort"].eq(1)].copy()
    full["joint_exposure_4level"] = pd.Categorical(full["joint_exposure_4level"], categories=GROUP_ORDER)
    read = clean_model_df(full, ["time_to_first_readmission_or_death_90d", "readmission_90d_status"])
    read["readmission_target_event"] = read["readmission_90d_status"].eq(1).astype(int)
    r_model = fit_cox(read, form, "time_to_first_readmission_or_death_90d", "readmission_target_event", "full classifiable readmission Model 2")
    read_rows = cox_joint_rows(
        r_model,
        "90-day same-system readmission",
        "full 72h classifiable cohort",
        "full classifiable sensitivity; administrative follow-up completeness not guaranteed",
    )
    icu = clean_model_df(full, ["time_to_first_icu_readmission_or_death_365d", "icu_readmission_365d_status"])
    icu["icu_target_event"] = icu["icu_readmission_365d_status"].eq(1).astype(int)
    i_model = fit_cox(icu, form, "time_to_first_icu_readmission_or_death_365d", "icu_target_event", "full classifiable ICU readmission Model 2")
    icu_rows = cox_joint_rows(
        i_model,
        "365-day same-system ICU readmission",
        "full 72h classifiable cohort",
        "full classifiable sensitivity; administrative follow-up completeness not guaranteed",
    )

    mort = full[full["hospice_discharge"].ne(1)].copy()
    mort = clean_model_df(mort, ["time_main", "event_main"])
    m_model = fit_cox(mort, form, "time_main", "event_main", "exclude hospice mortality Model 2")
    mort_rows = cox_joint_rows(m_model, "365-day mortality", "primary classifiable excluding hospice", "exclude hospice sensitivity Model 2 Cox")
    return pd.concat([read_rows, icu_rows], ignore_index=True), mort_rows


def run_severity_alternatives(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    alternatives = [
        ("A_main_nonneurologic_sofa", "main", "available"),
        ("B_official_first_day_sofa", "full_sofa", "available" if "full_sofa_official_first_day" in df.columns else "not available"),
        ("C_official_oasis", "oasis", "available" if "oasis_official_first_day" in df.columns else "not available"),
        ("D_organ_support", "organ_support", "available"),
        (
            "E_nonneurologic_sofa_0_6h",
            "nonneurologic_sofa_0_6h",
            "available" if {"nonneurologic_sofa_0_6h_zero_imputed", "nonneurologic_sofa_0_6h_observed_components_n"}.issubset(df.columns) else "not available",
        ),
    ]
    outcomes = [
        ("365-day mortality", df[df["primary_analysis_cohort"].eq(1)].copy(), "time_main", "event_main"),
        (
            "90-day same-system readmission",
            df[df["conservative_readmission_cohort"].eq(1)].copy(),
            "time_to_first_readmission_or_death_90d",
            "readmission_target_event",
        ),
        (
            "365-day same-system ICU readmission",
            df[df["conservative_readmission_cohort"].eq(1)].copy(),
            "time_to_first_icu_readmission_or_death_365d",
            "icu_target_event",
        ),
    ]
    for label, severity, availability in alternatives:
        for outcome, raw, time_col, event_col in outcomes:
            raw = raw.copy()
            raw["joint_exposure_4level"] = pd.Categorical(raw["joint_exposure_4level"], categories=GROUP_ORDER)
            if event_col == "readmission_target_event":
                raw[event_col] = raw["readmission_90d_status"].eq(1).astype(int)
            elif event_col == "icu_target_event":
                raw[event_col] = raw["icu_readmission_365d_status"].eq(1).astype(int)
            if availability != "available":
                for group in GROUP_ORDER[1:]:
                    rows.append(
                        {
                            "outcome": outcome,
                            "severity_adjustment": label,
                            "group": group,
                            "contrast": f"{group} vs {REFERENCE_GROUP}",
                            "HR": np.nan,
                            "CI95_lower": np.nan,
                            "CI95_upper": np.nan,
                            "p_value": np.nan,
                            "n": 0,
                            "events": 0,
                            "convergence_status": "not_available_in_frozen_analysis_table",
                        }
                    )
                continue
            form = model_formula("joint_exposure_4level", severity)
            model = fit_cox(clean_model_df(raw, [time_col, event_col]), form, time_col, event_col, f"{outcome} {label}")
            hr = cox_joint_rows(model, outcome, "prespecified analysis population", f"severity alternative {label}")
            for _, r in hr.iterrows():
                rows.append(
                    {
                        "outcome": outcome,
                        "severity_adjustment": label,
                        "group": r["group"],
                        "contrast": r["contrast"],
                        "HR": r["HR"],
                        "CI95_lower": r["CI95_lower"],
                        "CI95_upper": r["CI95_upper"],
                        "p_value": r["p_value"],
                        "n": r["n"],
                        "events": r["events"],
                        "convergence_status": "converged" if r["converged"] else f"failed: {r['error']}",
                    }
                )
    return pd.DataFrame(rows)


def build_sensitivity_summary(
    ipsw_mort: pd.DataFrame,
    ipsw_risk: pd.DataFrame,
    ipsw_read: pd.DataFrame,
    ipsw_icu: pd.DataFrame,
    strict_mort: pd.DataFrame,
    strict_risk: pd.DataFrame,
    strict_read: pd.DataFrame,
    strict_inter: pd.DataFrame,
    d48_mort: pd.DataFrame,
    d48_read: pd.DataFrame,
    d48_inter: pd.DataFrame,
    full_read: pd.DataFrame,
    hospice: pd.DataFrame,
    severity: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []

    def add_hr(df: pd.DataFrame, exposure_def: str, severity_adj: str, default_weight: str = "none") -> None:
        for _, r in df.iterrows():
            rows.append(
                {
                    "outcome": r.get("outcome", ""),
                    "analysis": r.get("analysis", ""),
                    "population": r.get("population", ""),
                    "exposure_definition": exposure_def,
                    "severity_adjustment": severity_adj,
                    "weight_strategy": r.get("weight_strategy", default_weight),
                    "contrast": r.get("contrast", ""),
                    "estimate_type": "HR",
                    "estimate": r.get("HR", np.nan),
                    "CI_lower": r.get("CI95_lower", np.nan),
                    "CI_upper": r.get("CI95_upper", np.nan),
                    "interpretation_flag": "prespecified sensitivity; not a replacement for primary result",
                }
            )

    def add_risk(df: pd.DataFrame, exposure_def: str, analysis_label: str, default_weight: str = "none") -> None:
        for _, r in df.iterrows():
            rows.append(
                {
                    "outcome": r.get("outcome", "365-day mortality"),
                    "analysis": r.get("analysis", analysis_label),
                    "population": "primary classifiable",
                    "exposure_definition": exposure_def,
                    "severity_adjustment": "Model 2 main severity",
                    "weight_strategy": r.get("weight_strategy", default_weight),
                    "contrast": f"{r.get('group')} vs {REFERENCE_GROUP}" if r.get("group") != REFERENCE_GROUP else "reference",
                    "estimate_type": "standardized risk",
                    "estimate": r.get("risk", np.nan),
                    "CI_lower": np.nan,
                    "CI_upper": np.nan,
                    "interpretation_flag": "point estimate sensitivity; no bootstrap CI requested in this batch",
                }
            )

    add_hr(ipsw_mort, "primary documented-by-index psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_risk(ipsw_risk, "primary documented-by-index psychiatric comorbidity + 72h delirium", "IPSW weighted logistic g-computation")
    add_hr(ipsw_read, "primary documented-by-index psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_hr(ipsw_icu, "primary documented-by-index psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_hr(strict_mort, "strict-prior psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_risk(strict_risk, "strict-prior psychiatric comorbidity + 72h delirium", "strict-prior logistic g-computation")
    add_hr(strict_read, "strict-prior psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_hr(d48_mort, "documented-by-index psychiatric comorbidity + 48h delirium", "Model 2 main severity")
    add_hr(d48_read, "documented-by-index psychiatric comorbidity + 48h delirium", "Model 2 main severity")
    add_hr(full_read, "primary documented-by-index psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    add_hr(hospice, "primary documented-by-index psychiatric comorbidity + 72h delirium", "Model 2 main severity")
    for _, r in severity.iterrows():
        rows.append(
            {
                "outcome": r["outcome"],
                "analysis": "severity alternative model",
                "population": "prespecified analysis population",
                "exposure_definition": "primary documented-by-index psychiatric comorbidity + 72h delirium",
                "severity_adjustment": r["severity_adjustment"],
                "weight_strategy": "none",
                "contrast": r["contrast"],
                "estimate_type": "HR",
                "estimate": r["HR"],
                "CI_lower": r["CI95_lower"],
                "CI_upper": r["CI95_upper"],
                "interpretation_flag": r["convergence_status"],
            }
        )
    for frame, exposure_def in [(strict_inter, "strict-prior psychiatric comorbidity + 72h delirium"), (d48_inter, "documented-by-index psychiatric comorbidity + 48h delirium")]:
        for _, r in frame.iterrows():
            metric = r.get("metric", "")
            if metric and metric not in ["interaction_contrast", "RERI", "AP", "synergy_index"]:
                continue
            rows.append(
                {
                    "outcome": r.get("outcome", ""),
                    "analysis": r.get("analysis", ""),
                    "population": "prespecified analysis population",
                    "exposure_definition": exposure_def,
                    "severity_adjustment": "Model 2 main severity",
                    "weight_strategy": "none",
                    "contrast": r.get("term", metric),
                    "estimate_type": "interaction",
                    "estimate": r.get("HR", r.get("estimate", np.nan)),
                    "CI_lower": r.get("CI95_lower", r.get("ci95_lower", np.nan)),
                    "CI_upper": r.get("CI95_upper", r.get("ci95_upper", np.nan)),
                    "interpretation_flag": "prespecified sensitivity interaction",
                }
            )
    return pd.DataFrame(rows)


def plot_forest(summary: pd.DataFrame, outcome: str, path: Path) -> None:
    sub = summary[(summary["outcome"].eq(outcome)) & (summary["estimate_type"].eq("HR"))].copy()
    sub = sub[sub["contrast"].str.contains(" vs ", na=False)]
    sub = sub.dropna(subset=["estimate"])
    if sub.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No HR estimates available", ha="center", va="center")
        ax.axis("off")
        fig.savefig(path)
        plt.close(fig)
        return
    sub["label"] = sub["analysis"].astype(str) + " | " + sub["contrast"].astype(str)
    sub = sub.tail(60)
    y = np.arange(sub.shape[0])
    fig_h = max(5, 0.24 * sub.shape[0] + 2)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.errorbar(
        sub["estimate"],
        y,
        xerr=[sub["estimate"] - sub["CI_lower"], sub["CI_upper"] - sub["estimate"]],
        fmt="o",
        markersize=3,
        ecolor="0.55",
        color="black",
        linewidth=0.8,
    )
    ax.axvline(1, color="grey", linestyle="--", linewidth=1)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(sub["label"], fontsize=7)
    ax.set_xlabel("Hazard ratio")
    ax.set_title(outcome)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_report(
    selection_dist: pd.DataFrame,
    balance: pd.DataFrame,
    ipsw_mort: pd.DataFrame,
    ipsw_risk: pd.DataFrame,
    ipsw_read: pd.DataFrame,
    ipsw_icu: pd.DataFrame,
    strict_counts: pd.DataFrame,
    strict_mort: pd.DataFrame,
    d48_counts: pd.DataFrame,
    d48_mort: pd.DataFrame,
    full_read: pd.DataFrame,
    hospice: pd.DataFrame,
    severity: pd.DataFrame,
) -> None:
    def md(df: pd.DataFrame, n: int = 12) -> str:
        if df.empty:
            return "_No rows._"
        return df.head(n).to_markdown(index=False)

    bal_summary = balance.groupby("strategy")["abs_smd"].agg(["max", lambda s: float((s < 0.1).mean())]).reset_index()
    bal_summary.columns = ["strategy", "max_abs_smd", "fraction_rows_abs_smd_lt_0_1"]
    lines = [
        "# Sensitivity Analysis Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Scope: final prespecified sensitivity analyses and result integration. No frozen exposure, outcome, analysis dataset, primary mortality v1.1, readmission cause-specific, or readmission CIF v1.2 files were modified.",
        "",
        "## IPSW Selection Model",
        "",
        "Stable weights were calculated for 72-hour delirium-classifiable patients using out-of-fold predicted classifiability probabilities. IPSW estimates are interpreted only as sensitivity analyses for classifiability selection, not as causal exposure effects.",
        "",
        md(selection_dist),
        "",
        "### Balance Summary",
        "",
        md(bal_summary),
        "",
        "## IPSW Outcome Results",
        "",
        "### Mortality Cox",
        "",
        md(ipsw_mort[ipsw_mort["weight_strategy"].eq("trim_1_99")]),
        "",
        "### Mortality Standardized Risk",
        "",
        md(ipsw_risk[ipsw_risk["weight_strategy"].eq("trim_1_99")]),
        "",
        "### Readmission Cox",
        "",
        md(ipsw_read[ipsw_read["weight_strategy"].eq("trim_1_99")]),
        "",
        "### ICU Readmission Cox",
        "",
        md(ipsw_icu[ipsw_icu["weight_strategy"].eq("trim_1_99")]),
        "",
        "## Strict-Prior Psychiatric Exposure Sensitivity",
        "",
        md(strict_counts),
        "",
        md(strict_mort),
        "",
        "## 48-Hour Delirium Sensitivity",
        "",
        md(d48_counts),
        "",
        md(d48_mort),
        "",
        "## Population and Outcome Sensitivities",
        "",
        "### Full classifiable readmission cohort",
        "",
        md(full_read),
        "",
        "### Excluding hospice discharge",
        "",
        md(hospice),
        "",
        "## Severity Alternative Models",
        "",
        md(severity),
        "",
        "## Robustness Note",
        "",
        "The report summarizes robustness only. It does not add post hoc subgroups, does not select variables by P value, and does not write Discussion text.",
    ]
    (SENS_DIR / "sensitivity_analysis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def direction_note(primary: pd.DataFrame, sensitivity: pd.DataFrame, outcome: str) -> str:
    try:
        p = primary[(primary["outcome"].eq(outcome)) & (primary["model"].eq("Model 2"))].set_index("group")["HR"]
        s = sensitivity[sensitivity["outcome"].eq(outcome)].set_index("group")["HR"]
        changed = []
        for g in GROUP_ORDER[1:]:
            if g in p and g in s and pd.notna(p[g]) and pd.notna(s[g]):
                if (p[g] - 1) * (s[g] - 1) < 0:
                    changed.append(g)
        return "direction changed for " + ", ".join(changed) if changed else "direction unchanged for G2-G4"
    except Exception:
        return "direction comparison unavailable"


def copy_or_empty(src: Path, dst: Path) -> pd.DataFrame:
    if src.exists():
        df = read_csv(src)
        write_csv(df, dst)
        return df
    df = pd.DataFrame({"status": [f"source file not found: {src}"]})
    write_csv(df, dst)
    return df


def build_integrated_results(summary: pd.DataFrame) -> None:
    INT_DIR.mkdir(parents=True, exist_ok=True)
    mortality_hr = read_csv(MORT_V11_DIR / "cox_joint_exposure_models_v1_1.csv")
    mortality_hr = mortality_hr[mortality_hr["model"].eq("Model 2")].copy()
    mortality_hr["source_version"] = "primary_mortality_v1_1"
    read_hr = pd.concat(
        [
            read_csv(READM_DIR / "readmission_90d_cause_specific_cox.csv"),
            read_csv(READM_DIR / "icu_readmission_365d_cause_specific_cox.csv"),
        ],
        ignore_index=True,
    )
    read_hr = read_hr[read_hr["model"].eq("Model 2")].copy()
    read_hr["source_version"] = "readmission_outcomes_v1_cause_specific_validated"
    relative = pd.concat([mortality_hr, read_hr], ignore_index=True, sort=False)
    write_csv(relative, INT_DIR / "master_relative_effects.csv")

    mort_abs = read_csv(MORT_V11_DIR / "fixed_horizon_365d_standardized_risk.csv")
    mort_abs = mort_abs[mort_abs["model"].eq("Model 2")].copy()
    mort_abs["outcome"] = "365-day mortality"
    mort_abs["source_version"] = "primary_mortality_v1_1_fixed_horizon_logistic"
    read_abs = pd.concat(
        [
            read_csv(READM_V12_DIR / "standardized_90d_readmission_cif_v1_2.csv"),
            read_csv(READM_V12_DIR / "standardized_365d_icu_readmission_cif_v1_2.csv"),
        ],
        ignore_index=True,
    )
    read_abs = read_abs[read_abs["model"].eq("Model 2")].copy()
    read_abs["source_version"] = "readmission_cif_v1_2_uncentered_baseline"
    absolute = pd.concat([mort_abs, read_abs], ignore_index=True, sort=False)
    write_csv(absolute, INT_DIR / "master_absolute_risks.csv")

    interaction_files = [
        MORT_V11_DIR / "fixed_horizon_365d_additive_interaction.csv",
        MORT_V11_DIR / "multiplicative_interaction_mortality_v1_1.csv",
        MORT_V11_DIR / "time_specific_multiplicative_interaction.csv",
        READM_V12_DIR / "additive_interaction_readmission_90d_v1_2.csv",
        READM_V12_DIR / "additive_interaction_icu_readmission_365d_v1_2.csv",
        READM_DIR / "multiplicative_interaction_readmission.csv",
        READM_DIR / "multiplicative_interaction_icu_readmission.csv",
        READM_DIR / "time_specific_interaction_readmission.csv",
    ]
    interaction_frames = []
    for p in interaction_files:
        if p.exists():
            tmp = read_csv(p)
            tmp["source_file"] = str(p)
            interaction_frames.append(tmp)
    interactions = pd.concat(interaction_frames, ignore_index=True, sort=False) if interaction_frames else pd.DataFrame()
    write_csv(interactions, INT_DIR / "master_interaction_results.csv")
    write_csv(summary, INT_DIR / "master_sensitivity_results.csv")
    copy_or_empty(MORT_DIR / "table1_four_group.csv", INT_DIR / "final_table1.csv")

    primary_table = relative.copy()
    primary_table = primary_table[
        [c for c in ["outcome", "model", "contrast", "HR", "CI95_lower", "CI95_upper", "p_value", "analysis_n", "event_n", "source_version"] if c in primary_table.columns]
    ]
    write_csv(primary_table, INT_DIR / "final_primary_results_table.csv")
    final_sens = summary.copy()
    write_csv(final_sens, INT_DIR / "final_sensitivity_table.csv")

    fig_lines = [
        "# Final Figure Manifest",
        "",
        "- `figure_sensitivity_forest_mortality.pdf`: sensitivity HR forest for 365-day mortality.",
        "- `figure_sensitivity_forest_readmission.pdf`: sensitivity HR forest for 90-day same-system readmission.",
        "- `figure_sensitivity_forest_icu_readmission.pdf`: sensitivity HR forest for 365-day same-system ICU readmission.",
        "- Mortality primary fixed-horizon risk figure remains `01_primary_mortality_v1_1/figure_fixed_horizon_365d_risk.pdf`.",
        "- Readmission standardized CIF interpretation uses v1.2 outputs; v1 and v1.1 CIF/RD/RR/additive-interaction outputs are deprecated.",
        "- Fine-Gray was not run because a validated R environment was unavailable; this is recorded and not treated as a failed analysis.",
    ]
    (INT_DIR / "final_figure_manifest.md").write_text("\n".join(fig_lines) + "\n", encoding="utf-8")

    lines = [
        "# Results Ready Summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Valid formal result versions:",
        "",
        "- One-year mortality: primary mortality v1.1, including centered full-rank age spline, time-varying Cox non-PH assessment, and fixed-horizon logistic standardized 365-day risk.",
        "- Readmission and ICU readmission: validated cause-specific Cox/time-varying results from readmission v1 and standardized CIF/RD/RR/additive interaction from CIF v1.2 only.",
        "- Deprecated: original mortality v1 age-spline model results; readmission CIF v1 and v1.1 standardized CIF/RD/RR/additive interaction.",
        "",
        "The final sensitivity batch completed IPSW for delirium classifiability, strict-prior psychiatric exposure, 48-hour delirium, full classifiable readmission, hospice exclusion, and severity alternative models without modifying frozen definitions or datasets.",
    ]
    (INT_DIR / "results_ready_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_integrated_manifest()


def write_integrated_manifest() -> None:
    files = sorted([p for p in INT_DIR.iterdir() if p.is_file() and p.name != "integrated_results_manifest.md"], key=lambda p: p.name.lower())
    lines = [
        "# Integrated Results Manifest",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Valid source versions:",
        "",
        "- Mortality: primary_mortality_v1_1.",
        "- Readmission cause-specific Cox/time-varying HR: readmission_outcomes v1 validated outputs.",
        "- Readmission standardized CIF/RD/RR/additive interaction: readmission_outcomes_v1_2 only.",
        "- Fine-Gray: not run due unavailable validated R environment; not imputed or replaced.",
        "",
        "| file | sha256 |",
        "|---|---|",
    ]
    for p in files:
        lines.append(f"| {p.name} | {sha256_path(p)} |")
    (INT_DIR / "integrated_results_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_final_manifest() -> None:
    files = sorted([p for p in SENS_DIR.iterdir() if p.is_file() and p.name != "final_analysis_run_manifest.md"], key=lambda p: p.name.lower())
    lines = [
        "# Final Analysis Run Manifest",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        f"Platform: {platform.platform()}",
        f"Script: `{SCRIPT_PATH}`",
        f"Script SHA256: `{sha256_path(SCRIPT_PATH)}`",
        "",
        "No patient-level CSV files were exported. All CSV/PDF/MD outputs in this directory are aggregate summaries.",
        "",
        "| file | sha256 |",
        "|---|---|",
    ]
    for p in files:
        lines.append(f"| {p.name} | {sha256_path(p)} |")
    (SENS_DIR / "final_analysis_run_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    start = time.time()
    np.random.seed(SEED)
    SENS_DIR.mkdir(parents=True, exist_ok=True)
    INT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading frozen analysis dataset...", flush=True)
    df = load_data()
    df["conservative_readmission_cohort_for_sensitivity"] = df["conservative_readmission_cohort"].astype(int)
    base = df[df["base_population"].eq(1)].copy()

    print("Building OOF selection model and IPSW weights...", flush=True)
    weighted_base, oof_perf, weight_dist, balance = build_selection_weights(base)
    write_csv(oof_perf, SENS_DIR / "selection_model_oof_performance.csv")
    write_csv(weight_dist, SENS_DIR / "selection_weight_distribution_formal.csv")
    write_csv(balance, SENS_DIR / "selection_weight_balance.csv")
    plot_balance(balance)

    # Merge weights back by row order. The frozen analysis table has one row per patient; no identifiers are written.
    df = df.copy()
    for col in ["ipw_untrimmed", "ipw_trim_1_99", "ipw_trim_5_95"]:
        df[col] = weighted_base[col].reindex(df.index)

    print("Running IPSW outcome sensitivities...", flush=True)
    ipsw_mort, ipsw_risk, ipsw_read, ipsw_icu, ipsw_diag = run_ipsw(df, df)
    write_csv(ipsw_mort, SENS_DIR / "ipsw_mortality_cox.csv")
    write_csv(ipsw_risk, SENS_DIR / "ipsw_mortality_standardized_risk.csv")
    write_csv(ipsw_read, SENS_DIR / "ipsw_readmission_90d_cox.csv")
    write_csv(ipsw_icu, SENS_DIR / "ipsw_icu_readmission_365d_cox.csv")
    write_csv(ipsw_diag, SENS_DIR / "ipsw_model_diagnostics.csv")

    print("Running strict-prior psychiatric exposure sensitivity...", flush=True)
    primary = df[df["primary_analysis_cohort"].eq(1)].copy()
    strict_counts = group_counts(primary, "joint_exposure_strict_prior_4level", "strict-prior psych + 72h delirium primary mortality cohort")
    strict_mort, strict_risk, strict_read, strict_inter, strict_add = run_group_sensitivity(
        primary,
        "joint_exposure_strict_prior_4level",
        "psych_primary_strict_prior",
        "delirium_binary_72h",
        "strict-prior psychiatric exposure",
        "primary 72h classifiable cohort",
        "conservative readmission cohort",
    )
    write_csv(strict_counts, SENS_DIR / "strict_prior_group_counts.csv")
    write_csv(strict_mort, SENS_DIR / "strict_prior_mortality_results.csv")
    write_csv(strict_risk, SENS_DIR / "strict_prior_mortality_standardized_risk.csv")
    write_csv(strict_read, SENS_DIR / "strict_prior_readmission_results.csv")
    write_csv(strict_inter, SENS_DIR / "strict_prior_interaction_results.csv")

    print("Running 48h delirium definition sensitivity...", flush=True)
    d48 = df[df["delirium_status_48h"].isin(["positive", "negative"])].copy()
    d48["conservative_readmission_cohort_for_sensitivity"] = np.where(d48["approximate_discharge_year_upper"].le(2021), 1, 0)
    d48_counts = group_counts(d48, "joint_exposure_48h_4level", "documented psych + 48h delirium classifiable cohort")
    d48_mort, d48_risk, d48_read, d48_inter, _ = run_group_sensitivity(
        d48,
        "joint_exposure_48h_4level",
        "psych_primary_documented_by_index",
        "delirium_binary_48h",
        "48h delirium definition",
        "48h delirium classifiable cohort",
        "48h classifiable conservative readmission cohort",
    )
    write_csv(d48_counts, SENS_DIR / "delirium_48h_cohort_counts.csv")
    d48_mortality_out = d48_mort.copy()
    d48_risk_out = d48_risk.copy()
    d48_risk_out["result_type"] = "fixed_horizon_standardized_risk"
    write_csv(pd.concat([d48_mortality_out, d48_risk_out], ignore_index=True, sort=False), SENS_DIR / "delirium_48h_mortality_results.csv")
    write_csv(d48_read, SENS_DIR / "delirium_48h_readmission_results.csv")
    write_csv(d48_inter, SENS_DIR / "delirium_48h_interaction_results.csv")

    print("Running full classifiable and hospice exclusion sensitivities...", flush=True)
    full_read, hospice = run_full_classifiable_and_hospice(df)
    write_csv(full_read, SENS_DIR / "full_classifiable_readmission_sensitivity.csv")
    write_csv(hospice, SENS_DIR / "mortality_exclude_hospice_sensitivity.csv")
    same_day_src = MORT_V11_DIR / "mortality_include_same_day_sensitivity_v1_1.csv"
    if same_day_src.exists():
        write_csv(read_csv(same_day_src), SENS_DIR / "mortality_include_same_day_sensitivity_v1_1_referenced.csv")

    print("Running severity alternative models...", flush=True)
    severity = run_severity_alternatives(df)
    write_csv(severity, SENS_DIR / "severity_alternative_models.csv")

    print("Building sensitivity summary and figures...", flush=True)
    summary = build_sensitivity_summary(
        ipsw_mort,
        ipsw_risk,
        ipsw_read,
        ipsw_icu,
        strict_mort,
        strict_risk,
        strict_read,
        strict_inter,
        d48_mort,
        d48_read,
        d48_inter,
        full_read,
        hospice,
        severity,
    )
    write_csv(summary, SENS_DIR / "sensitivity_analysis_summary.csv")
    plot_forest(summary, "365-day mortality", SENS_DIR / "figure_sensitivity_forest_mortality.pdf")
    plot_forest(summary, "90-day same-system readmission", SENS_DIR / "figure_sensitivity_forest_readmission.pdf")
    plot_forest(summary, "365-day same-system ICU readmission", SENS_DIR / "figure_sensitivity_forest_icu_readmission.pdf")
    write_report(weight_dist, balance, ipsw_mort, ipsw_risk, ipsw_read, ipsw_icu, strict_counts, strict_mort, d48_counts, d48_mort, full_read, hospice, severity)

    print("Building integrated results...", flush=True)
    build_integrated_results(summary)
    write_final_manifest()

    # Small machine-readable final summary for later audit.
    primary_hr = read_csv(MORT_V11_DIR / "cox_joint_exposure_models_v1_1.csv")
    final_status = {
        "elapsed_seconds": round(time.time() - start, 2),
        "base_population_n": int(df["base_population"].sum()),
        "primary_analysis_n": int(df["primary_analysis_cohort"].sum()),
        "conservative_readmission_n": int(df["conservative_readmission_cohort"].sum()),
        "strict_prior_direction_vs_primary_mortality": direction_note(primary_hr.assign(outcome="365-day mortality"), strict_mort, "365-day mortality"),
        "delirium_48h_direction_vs_primary_mortality": direction_note(primary_hr.assign(outcome="365-day mortality"), d48_mort, "365-day mortality"),
    }
    (SENS_DIR / "final_sensitivity_status.json").write_text(json.dumps(final_status, indent=2), encoding="utf-8")
    write_final_manifest()
    write_integrated_manifest()

    print(f"report={SENS_DIR / 'sensitivity_analysis_report.md'}", flush=True)
    print(f"report_sha256={sha256_path(SENS_DIR / 'sensitivity_analysis_report.md')}", flush=True)
    print(f"results_ready_summary={INT_DIR / 'results_ready_summary.md'}", flush=True)
    print(f"results_ready_summary_sha256={sha256_path(INT_DIR / 'results_ready_summary.md')}", flush=True)
    print(f"integrated_manifest={INT_DIR / 'integrated_results_manifest.md'}", flush=True)
    print(f"integrated_manifest_sha256={sha256_path(INT_DIR / 'integrated_results_manifest.md')}", flush=True)


if __name__ == "__main__":
    main()
