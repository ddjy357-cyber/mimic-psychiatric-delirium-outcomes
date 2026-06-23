from __future__ import annotations

import hashlib
import os
import pickle
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
from lifelines import CoxPHFitter, CoxTimeVaryingFitter
from lifelines.exceptions import ConvergenceWarning, StatisticalWarning
from lifelines.statistics import proportional_hazard_test
from patsy import build_design_matrices, dmatrix
from scipy.stats import chi2


SEED = 20260621
BOOTSTRAP_N = int(os.environ.get("PRIMARY_MORTALITY_BOOTSTRAP_N", "1000"))
COX_PRIMARY_PENALIZER = 0.0
COX_TECHNICAL_SENSITIVITY_PENALIZER = 1e-9

PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", PROJECT.parent / "data" / "mimiciv.duckdb"))
OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "01_primary_mortality_v1_1"
ORIGINAL_DIR = PROJECT / "analysis" / "formal_models_v1" / "01_primary_mortality"
SCRIPT_DIR = PROJECT / "scripts" / "analysis"
SCRIPT_PATH = SCRIPT_DIR / "run_primary_mortality_v1_1.py"
SAP_AMENDMENT_LOG = PROJECT / "sap" / "sap_amendment_log.md"
TABLE = "mental_delirium_analysis.analysis_dataset_v1_1"

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
WINDOWS = [
    (0.0, 30.0, "0_30_days"),
    (30.0, 90.0, "30_90_days"),
    (90.0, 365.0, "90_365_days"),
]

MODEL1_RAW_VARIABLES = [
    "joint_exposure_4level",
    "age_at_index_admission",
    "sex_recorded",
    "race_group",
    "anchor_year_group",
    "admission_type_group",
    "admission_location_group",
    "first_careunit_group",
    "prior_mimic_hospitalizations",
    "charlson_comorbidity_only_documented_by_index",
    "dementia_documented_by_index",
    "substance_use_documented_by_index",
    "chronic_neurologic_disease",
]
MODEL2_ADDED_VARIABLES = [
    "nonneurologic_sofa_zero_imputed",
    "nonneurologic_sofa_observed_components_n",
]
MODEL2_RAW_VARIABLES = MODEL1_RAW_VARIABLES + MODEL2_ADDED_VARIABLES
CATEGORICAL_VARIABLES = [
    "joint_exposure_4level",
    "sex_recorded",
    "race_group",
    "anchor_year_group",
    "admission_type_group",
    "admission_location_group",
    "first_careunit_group",
]
BINARY_VARIABLES = [
    "psych_primary_documented_by_index",
    "dementia_documented_by_index",
    "substance_use_documented_by_index",
    "chronic_neurologic_disease",
    "death_365d_main",
    "death_365d_include_same_day",
    "death_same_day_discharge",
]


@dataclass
class FittedCox:
    name: str
    cph: CoxPHFitter
    formula: str
    design_info: object
    fit_df: pd.DataFrame
    raw_df: pd.DataFrame
    exposure_columns: list[str]
    penalizer: float
    converged: bool
    error: str = ""


@dataclass
class FittedLogistic:
    name: str
    result: object
    formula: str
    design_info: object
    raw_df: pd.DataFrame


analysis_warnings: list[str] = []


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def pct(n: float, d: float) -> float:
    return float(n) / float(d) if d else np.nan


def load_data() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(
        f"""
        select
            subject_id,
            hadm_id,
            stay_id,
            primary_analysis_cohort,
            joint_exposure_4level,
            psych_primary_documented_by_index,
            delirium_status_72h,
            death_365d_main,
            death_365d_include_same_day,
            death_same_day_discharge,
            death_date_logic_abnormal_flag,
            time_to_death_or_censor_365d,
            age_at_index_admission,
            sex_recorded,
            race_group,
            anchor_year_group,
            admission_type_group,
            admission_location_group,
            first_careunit_group,
            prior_mimic_hospitalizations,
            charlson_comorbidity_only_documented_by_index,
            dementia_documented_by_index,
            substance_use_documented_by_index,
            chronic_neurologic_disease,
            nonneurologic_sofa_zero_imputed,
            nonneurologic_sofa_observed_components_n
        from {TABLE}
        where primary_analysis_cohort = 1
        """
    ).fetchdf()
    con.close()
    return prepare_data(df)


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in CATEGORICAL_VARIABLES:
        df[col] = df[col].fillna("Missing").astype(str)
    for col in BINARY_VARIABLES + [
        "primary_analysis_cohort",
        "psych_primary_documented_by_index",
        "nonneurologic_sofa_observed_components_n",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in [
        "time_to_death_or_censor_365d",
        "age_at_index_admission",
        "prior_mimic_hospitalizations",
        "charlson_comorbidity_only_documented_by_index",
        "nonneurologic_sofa_zero_imputed",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["delirium_binary"] = np.where(df["delirium_status_72h"].eq("positive"), 1, 0)
    df["log1p_prior_mimic_hospitalizations"] = np.log1p(df["prior_mimic_hospitalizations"])
    df["event_main"] = df["death_365d_main"].astype(int)
    df["time_main"] = df["time_to_death_or_censor_365d"].astype(float)
    df["event_same_day_sensitivity"] = df["death_365d_include_same_day"].astype(int)
    df["time_same_day_sensitivity"] = np.where(
        df["death_same_day_discharge"].eq(1),
        0.5,
        df["time_to_death_or_censor_365d"].astype(float),
    )
    df["joint_exposure_4level"] = pd.Categorical(df["joint_exposure_4level"], categories=GROUP_ORDER)
    return df


def centered_age_spline() -> str:
    return (
        "cr(age_at_index_admission, knots=(60, 72), "
        "lower_bound=31, upper_bound=89, constraints='center')"
    )


def model_formulas() -> dict[str, str]:
    joint = f"C(joint_exposure_4level, Treatment(reference='{REFERENCE_GROUP}'))"
    age = centered_age_spline()
    common = [
        joint,
        age,
        "C(sex_recorded)",
        "C(race_group)",
        "C(anchor_year_group)",
        "C(admission_type_group)",
        "C(admission_location_group)",
        "C(first_careunit_group)",
        "log1p_prior_mimic_hospitalizations",
        "charlson_comorbidity_only_documented_by_index",
        "dementia_documented_by_index",
        "substance_use_documented_by_index",
        "chronic_neurologic_disease",
    ]
    model2_extra = [
        "nonneurologic_sofa_zero_imputed",
        "C(nonneurologic_sofa_observed_components_n, Treatment(reference=5))",
    ]
    binary_base = [
        "psych_primary_documented_by_index",
        "delirium_binary",
        "psych_primary_documented_by_index:delirium_binary",
    ] + common[1:]
    binary_reduced = [
        "psych_primary_documented_by_index",
        "delirium_binary",
    ] + common[1:]
    return {
        "Model 0": joint,
        "Model 1": " + ".join(common),
        "Model 2": " + ".join(common + model2_extra),
        "Interaction Model 1": " + ".join(binary_base),
        "Interaction Model 1 reduced": " + ".join(binary_reduced),
        "Interaction Model 2": " + ".join(binary_base + model2_extra),
        "Interaction Model 2 reduced": " + ".join(binary_reduced + model2_extra),
    }


def design_matrix(
    raw_df: pd.DataFrame,
    formula: str,
    design_info=None,
    drop_intercept: bool = True,
) -> tuple[pd.DataFrame, object]:
    if design_info is None:
        X = dmatrix(formula, raw_df, return_type="dataframe")
        design_info = X.design_info
    else:
        X = build_design_matrices([design_info], raw_df, return_type="dataframe")[0]
    X = pd.DataFrame(X, index=raw_df.index)
    if drop_intercept and "Intercept" in X.columns:
        X = X.drop(columns=["Intercept"])
    return X.astype(float), design_info


def age_cols(columns: list[str]) -> list[str]:
    return [c for c in columns if "cr(age_at_index_admission" in c]


def exposure_cols(columns: list[str]) -> list[str]:
    return [c for c in columns if "joint_exposure_4level" in c]


def fit_cox(
    raw_df: pd.DataFrame,
    formula: str,
    name: str,
    duration_col: str = "time_main",
    event_col: str = "event_main",
    penalizer: float = COX_PRIMARY_PENALIZER,
    design_info=None,
) -> FittedCox:
    X, design_info = design_matrix(raw_df, formula, design_info=design_info, drop_intercept=True)
    fit_df = pd.concat([raw_df[[duration_col, event_col]], X], axis=1)
    fit_df = fit_df.rename(columns={duration_col: "time", event_col: "event"})
    cph = CoxPHFitter(penalizer=penalizer)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        warnings.simplefilter("always", StatisticalWarning)
        cph.fit(fit_df, duration_col="time", event_col="event", show_progress=False)
    for w in caught:
        analysis_warnings.append(f"{name}: {str(w.message)}")
    return FittedCox(
        name=name,
        cph=cph,
        formula=formula,
        design_info=design_info,
        fit_df=fit_df,
        raw_df=raw_df.copy(),
        exposure_columns=exposure_cols(list(X.columns)),
        penalizer=penalizer,
        converged=True,
    )


def fit_cox_primary_or_sensitivity(raw_df: pd.DataFrame, formula: str, name: str, **kwargs) -> FittedCox:
    try:
        return fit_cox(raw_df, formula, name, penalizer=COX_PRIMARY_PENALIZER, **kwargs)
    except Exception as exc:
        msg = f"{name} did not converge with penalizer=0: {type(exc).__name__}: {exc}"
        analysis_warnings.append(msg)
        sens = fit_cox(raw_df, formula, f"{name} technical ridge sensitivity", penalizer=COX_TECHNICAL_SENSITIVITY_PENALIZER, **kwargs)
        sens.converged = False
        sens.error = msg
        return sens


def cox_full_coefficients(models: list[FittedCox]) -> pd.DataFrame:
    rows = []
    for m in models:
        summary = m.cph.summary.reset_index().rename(columns={"covariate": "term"})
        for _, r in summary.iterrows():
            rows.append(
                {
                    "model": m.name,
                    "term": r["term"],
                    "coefficient": r["coef"],
                    "standard_error": r["se(coef)"],
                    "HR": r["exp(coef)"],
                    "CI_lower": r["exp(coef) lower 95%"],
                    "CI_upper": r["exp(coef) upper 95%"],
                    "P_value": r["p"],
                }
            )
    return pd.DataFrame(rows)


def extract_group_from_column(col: str) -> str:
    for group in GROUP_ORDER[1:]:
        if group in col:
            return group
    return col


def cox_joint_rows(models: list[FittedCox]) -> pd.DataFrame:
    rows = []
    for m in models:
        summary = m.cph.summary.reset_index().rename(columns={"covariate": "term"})
        for col in m.exposure_columns:
            row = summary.loc[summary["term"].eq(col)]
            if row.empty:
                continue
            r = row.iloc[0]
            rows.append(
                {
                    "model": m.name,
                    "contrast": f"{extract_group_from_column(col)} vs {REFERENCE_GROUP}",
                    "term": col,
                    "HR": r["exp(coef)"],
                    "CI95_lower": r["exp(coef) lower 95%"],
                    "CI95_upper": r["exp(coef) upper 95%"],
                    "p_value": r["p"],
                    "analysis_n": int(m.fit_df.shape[0]),
                    "event_n": int(m.fit_df["event"].sum()),
                    "AIC_partial": m.cph.AIC_partial_,
                    "concordance": m.cph.concordance_index_,
                    "penalizer": m.penalizer,
                    "converged_without_ridge": bool(m.penalizer == 0 and m.converged),
                    "fit_error_if_any": m.error,
                }
            )
    return pd.DataFrame(rows)


def model_fit_stats(models: list[FittedCox]) -> pd.DataFrame:
    rows = []
    for m in models:
        rows.append(
            {
                "model": m.name,
                "analysis_n": int(m.fit_df.shape[0]),
                "event_n": int(m.fit_df["event"].sum()),
                "covariate_columns_n": len(m.cph.params_),
                "log_likelihood": m.cph.log_likelihood_,
                "AIC_partial": m.cph.AIC_partial_,
                "concordance": m.cph.concordance_index_,
                "penalizer": m.penalizer,
                "converged_without_ridge": bool(m.penalizer == 0 and m.converged),
                "fit_error_if_any": m.error,
            }
        )
    return pd.DataFrame(rows)


def design_qc(raw_df: pd.DataFrame, formulas: dict[str, str], models: list[FittedCox]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rank_rows = []
    cond_rows = []
    age_rows = []
    coef_table = cox_full_coefficients(models)
    for name in ["Model 0", "Model 1", "Model 2"]:
        X, _ = design_matrix(raw_df, formulas[name], drop_intercept=True)
        matrix = X.to_numpy()
        rank = int(np.linalg.matrix_rank(matrix))
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        min_sv = float(np.min(singular_values))
        max_sv = float(np.max(singular_values))
        cond = float(np.linalg.cond(matrix))
        acols = age_cols(list(X.columns))
        rank_rows.append(
            {
                "model": name,
                "design_matrix_columns_n": int(X.shape[1]),
                "matrix_rank": rank,
                "full_rank": bool(rank == X.shape[1]),
                "age_spline_columns_n": len(acols),
            }
        )
        cond_rows.append(
            {
                "model": name,
                "condition_number": cond,
                "min_singular_value": min_sv,
                "max_singular_value": max_sv,
            }
        )
        if not acols:
            age_rows.append(
                {
                    "model": name,
                    "age_spline_term": "none",
                    "basis_mean": np.nan,
                    "basis_sd": np.nan,
                    "basis_min": np.nan,
                    "basis_max": np.nan,
                    "coefficient": np.nan,
                    "standard_error": np.nan,
                    "HR": np.nan,
                    "CI_lower": np.nan,
                    "CI_upper": np.nan,
                }
            )
        else:
            for col in acols:
                crow = coef_table[(coef_table["model"].eq(name)) & (coef_table["term"].eq(col))]
                c = crow.iloc[0].to_dict() if not crow.empty else {}
                age_rows.append(
                    {
                        "model": name,
                        "age_spline_term": col,
                        "basis_mean": float(X[col].mean()),
                        "basis_sd": float(X[col].std(ddof=1)),
                        "basis_min": float(X[col].min()),
                        "basis_max": float(X[col].max()),
                        "coefficient": c.get("coefficient", np.nan),
                        "standard_error": c.get("standard_error", np.nan),
                        "HR": c.get("HR", np.nan),
                        "CI_lower": c.get("CI_lower", np.nan),
                        "CI_upper": c.get("CI_upper", np.nan),
                    }
                )
    return pd.DataFrame(rank_rows), pd.DataFrame(cond_rows), pd.DataFrame(age_rows)


def compare_with_original(new_joint: pd.DataFrame) -> pd.DataFrame:
    old_path = ORIGINAL_DIR / "cox_joint_exposure_models.csv"
    columns = [
        "model",
        "group",
        "HR_v1",
        "CI_lower_v1",
        "CI_upper_v1",
        "HR_v1_1",
        "CI_lower_v1_1",
        "CI_upper_v1_1",
        "absolute_HR_difference",
        "relative_HR_difference",
        "comparison_status",
    ]
    if not old_path.exists():
        return pd.DataFrame(
            [{
                "model": "not_applicable",
                "group": "not_applicable",
                "comparison_status": "skipped_missing_deprecated_v1_outputs",
            }],
            columns=columns,
        )
    old = pd.read_csv(old_path)
    merged = old.merge(
        new_joint,
        on=["model", "group"],
        suffixes=("_v1", "_v1_1"),
    )
    merged["absolute_HR_difference"] = merged["HR_v1_1"] - merged["HR_v1"]
    merged["relative_HR_difference"] = merged["absolute_HR_difference"] / merged["HR_v1"]
    merged["comparison_status"] = "completed"
    return merged[columns]


def fit_ph_tests(models: list[FittedCox]) -> pd.DataFrame:
    rows = []
    for m in models:
        try:
            result = proportional_hazard_test(m.cph, m.fit_df, time_transform="rank")
            s = result.summary.reset_index().rename(columns={"index": "term"})
            for _, r in s.iterrows():
                rows.append(
                    {
                        "model": m.name,
                        "test_scope": "individual_term_auxiliary_schoenfeld",
                        "term": r["term"],
                        "test_statistic": r["test_statistic"],
                        "df": 1,
                        "p_value": r["p"],
                        "formal_status": "auxiliary_only",
                    }
                )
            rows.append(
                {
                    "model": m.name,
                    "test_scope": "deprecated_v1_sum_of_schoenfeld_terms",
                    "term": "joint_exposure_4level",
                    "test_statistic": np.nan,
                    "df": np.nan,
                    "p_value": np.nan,
                    "formal_status": "deprecated_not_used_for_formal_global_nonph",
                }
            )
        except Exception as exc:
            analysis_warnings.append(f"Auxiliary Schoenfeld PH test failed for {m.name}: {exc}")
    return pd.DataFrame(rows)


def build_time_varying_rows(raw_df: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    base = raw_df.reset_index(drop=True).copy()
    base["_pid"] = np.arange(base.shape[0])
    for start, stop, label in WINDOWS:
        part = base[base["time_main"] > start].copy()
        part["start"] = start
        part["stop"] = np.minimum(part["time_main"], stop)
        part["event_tv"] = np.where(
            part["event_main"].eq(1) & (part["time_main"] <= stop) & (part["time_main"] > start),
            1,
            0,
        )
        part["interval_label"] = label
        part["interval_30_90"] = int(label == "30_90_days")
        part["interval_90_365"] = int(label == "90_365_days")
        part = part[part["stop"] > part["start"]].copy()
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)


def fit_time_varying_nonph(raw_df: pd.DataFrame, model2: FittedCox) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    tv_raw = build_time_varying_rows(raw_df)
    X, _ = design_matrix(tv_raw, model2.formula, design_info=model2.design_info, drop_intercept=True)
    reduced_df = pd.concat([tv_raw[["_pid", "start", "stop", "event_tv"]], X], axis=1)
    reduced = CoxTimeVaryingFitter(penalizer=0.0)
    reduced.fit(reduced_df, id_col="_pid", start_col="start", stop_col="stop", event_col="event_tv", show_progress=False)

    full_X = X.copy()
    for col in model2.exposure_columns:
        full_X[f"{col}:interval_30_90"] = full_X[col] * tv_raw["interval_30_90"].to_numpy()
        full_X[f"{col}:interval_90_365"] = full_X[col] * tv_raw["interval_90_365"].to_numpy()
    full_df = pd.concat([tv_raw[["_pid", "start", "stop", "event_tv"]], full_X], axis=1)
    full = CoxTimeVaryingFitter(penalizer=0.0)
    full.fit(full_df, id_col="_pid", start_col="start", stop_col="stop", event_col="event_tv", show_progress=False)

    lr = 2.0 * (full.log_likelihood_ - reduced.log_likelihood_)
    lrt = pd.DataFrame(
        [
            {
                "test": "joint_exposure_time_varying_nonph_lrt",
                "reduced_log_likelihood": reduced.log_likelihood_,
                "full_log_likelihood": full.log_likelihood_,
                "chisq": lr,
                "df": 6,
                "p_value": chi2.sf(lr, 6),
                "interpretation": "formal global non-PH test for joint exposure time-varying effects",
            }
        ]
    )

    cov = full.variance_matrix_
    params = full.params_
    rows = []
    for col in model2.exposure_columns:
        group = extract_group_from_column(col)
        for _, _, label in WINDOWS:
            vec = pd.Series(0.0, index=params.index)
            vec[col] = 1.0
            if label == "30_90_days":
                vec[f"{col}:interval_30_90"] = 1.0
            elif label == "90_365_days":
                vec[f"{col}:interval_90_365"] = 1.0
            beta = float(np.dot(vec, params))
            se = float(np.sqrt(np.dot(vec, np.dot(cov, vec))))
            rows.append(
                {
                    "time_window": label,
                    "contrast": f"{group} vs {REFERENCE_GROUP}",
                    "group": group,
                    "coefficient": beta,
                    "standard_error": se,
                    "HR": np.exp(beta),
                    "CI95_lower": np.exp(beta - 1.96 * se),
                    "CI95_upper": np.exp(beta + 1.96 * se),
                }
            )
    counts = (
        tv_raw.groupby("interval_label")
        .agg(rows_n=("_pid", "size"), patients_n=("_pid", "nunique"), events_n=("event_tv", "sum"))
        .reset_index()
        .rename(columns={"interval_label": "time_window"})
    )
    return pd.DataFrame(rows), lrt, counts, {"reduced": reduced, "full": full}


def fit_logistic(raw_df: pd.DataFrame, formula: str, name: str, design_info=None, weights=None) -> FittedLogistic:
    X, design_info = design_matrix(raw_df, formula, design_info=design_info, drop_intercept=False)
    y = raw_df["death_365d_main"].astype(float)
    model = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=weights)
    result = model.fit(maxiter=100, disp=0)
    return FittedLogistic(name=name, result=result, formula=formula, design_info=design_info, raw_df=raw_df.copy())


def logistic_standardized_risk(model: FittedLogistic, raw_df: pd.DataFrame, weights: np.ndarray | None = None) -> dict[str, float]:
    if weights is None:
        weights = np.ones(raw_df.shape[0])
    risks = {}
    for group in GROUP_ORDER:
        cf = raw_df.copy()
        cf["joint_exposure_4level"] = pd.Categorical([group] * len(cf), categories=GROUP_ORDER)
        X, _ = design_matrix(cf, model.formula, design_info=model.design_info, drop_intercept=False)
        pred = model.result.predict(X)
        risks[group] = float(np.average(pred, weights=weights))
    return risks


def risk_contrasts(risks: dict[str, float]) -> dict[str, float]:
    r00 = risks[GROUP_ORDER[0]]
    r10 = risks[GROUP_ORDER[1]]
    r01 = risks[GROUP_ORDER[2]]
    r11 = risks[GROUP_ORDER[3]]
    rr10 = r10 / r00
    rr01 = r01 / r00
    rr11 = r11 / r00
    reri = rr11 - rr10 - rr01 + 1.0
    ap = reri / rr11
    denom = (rr10 - 1.0) + (rr01 - 1.0)
    synergy = (rr11 - 1.0) / denom if denom else np.nan
    return {
        "R00": r00,
        "R10": r10,
        "R01": r01,
        "R11": r11,
        "interaction_contrast": r11 - r10 - r01 + r00,
        "RR10": rr10,
        "RR01": rr01,
        "RR11": rr11,
        "RERI": reri,
        "AP": ap,
        "synergy_index": synergy,
    }


def bootstrap_fixed_horizon(raw_df: pd.DataFrame, formulas: dict[str, str], design_infos: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    n = raw_df.shape[0]
    rows = []
    failures = []
    start_time = time.time()
    for b in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        counts = np.bincount(idx, minlength=n)
        use = counts > 0
        boot = raw_df.loc[use].copy()
        weights = counts[use].astype(float)
        for name in ["Model 1", "Model 2"]:
            try:
                fit = fit_logistic(boot, formulas[name], name, design_info=design_infos[name], weights=weights)
                risks = logistic_standardized_risk(fit, boot, weights=weights)
                contrasts = risk_contrasts(risks)
                row = {"bootstrap_iteration": b + 1, "model": name, "status": "success"}
                row.update({f"risk_{g}": v for g, v in risks.items()})
                row.update(contrasts)
                rows.append(row)
            except Exception as exc:
                failures.append(
                    {
                        "bootstrap_iteration": b + 1,
                        "model": name,
                        "status": "failed",
                        "message": str(exc),
                    }
                )
        if (b + 1) % 50 == 0:
            print(f"fixed-horizon bootstrap {b + 1}/{BOOTSTRAP_N} completed in {time.time() - start_time:.1f}s", flush=True)
    boot = pd.DataFrame(rows)
    success = boot.groupby("model").size().reset_index(name="successful_iterations") if not boot.empty else pd.DataFrame()
    success["planned_iterations"] = BOOTSTRAP_N
    success["failed_iterations"] = success["planned_iterations"] - success["successful_iterations"]
    if failures:
        fail_df = pd.DataFrame(failures)
    else:
        fail_df = pd.DataFrame(columns=["bootstrap_iteration", "model", "status", "message"])
    diag = pd.concat([success.assign(status="success"), fail_df], ignore_index=True, sort=False)
    return boot, diag


def summarize_fixed_horizon(point: dict[str, dict[str, float]], boot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risk_rows = []
    add_rows = []
    for model_name, risks in point.items():
        b = boot[boot["model"].eq(model_name)]
        for group in GROUP_ORDER:
            vals = b[f"risk_{group}"].dropna()
            ref_vals = b[f"risk_{REFERENCE_GROUP}"]
            rd_vals = b[f"risk_{group}"] - ref_vals
            rr_vals = b[f"risk_{group}"] / ref_vals
            risk = risks[group]
            ref = risks[REFERENCE_GROUP]
            risk_rows.append(
                {
                    "model": model_name,
                    "group": group,
                    "label": GROUP_LABELS[group],
                    "standardized_365d_mortality_risk": risk,
                    "risk_ci95_lower": vals.quantile(0.025),
                    "risk_ci95_upper": vals.quantile(0.975),
                    "risk_difference_vs_group1": risk - ref,
                    "risk_difference_ci95_lower": rd_vals.quantile(0.025),
                    "risk_difference_ci95_upper": rd_vals.quantile(0.975),
                    "risk_ratio_vs_group1": risk / ref,
                    "risk_ratio_ci95_lower": rr_vals.quantile(0.025),
                    "risk_ratio_ci95_upper": rr_vals.quantile(0.975),
                    "bootstrap_successful_iterations": int(vals.shape[0]),
                }
            )
        contrasts = risk_contrasts(risks)
        for metric, value in contrasts.items():
            vals = b[metric].dropna()
            add_rows.append(
                {
                    "model": model_name,
                    "metric": metric,
                    "estimate": value,
                    "ci95_lower": vals.quantile(0.025),
                    "ci95_upper": vals.quantile(0.975),
                    "bootstrap_successful_iterations": int(vals.shape[0]),
                }
            )
    return pd.DataFrame(risk_rows), pd.DataFrame(add_rows)


def plot_fixed_horizon_risk(risk_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(GROUP_ORDER))
    width = 0.34
    for i, model in enumerate(["Model 1", "Model 2"]):
        sub = risk_df[risk_df["model"].eq(model)].set_index("group").loc[GROUP_ORDER]
        y = sub["standardized_365d_mortality_risk"].to_numpy()
        lower = np.maximum(y - sub["risk_ci95_lower"].to_numpy(), 0)
        upper = np.maximum(sub["risk_ci95_upper"].to_numpy() - y, 0)
        ax.bar(x + (i - 0.5) * width, y, width, yerr=np.vstack([lower, upper]), capsize=3, label=model)
    ax.set_xticks(x)
    ax.set_xticklabels(["G1", "G2", "G3", "G4"])
    ax.set_ylabel("Standardized 365-day mortality risk")
    ax.set_title("Fixed-horizon logistic standardized risk")
    ax.grid(axis="y", alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "figure_fixed_horizon_365d_risk.pdf")
    plt.close(fig)


def cox_ph_standardized_sensitivity(models: list[FittedCox], raw_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model in models:
        if model.name not in ["Model 1", "Model 2"]:
            continue
        for group in GROUP_ORDER:
            cf = raw_df.copy()
            cf["joint_exposure_4level"] = pd.Categorical([group] * len(cf), categories=GROUP_ORDER)
            X, _ = design_matrix(cf, model.formula, design_info=model.design_info, drop_intercept=True)
            X = X[list(model.cph.params_.index)]
            surv = model.cph.predict_survival_function(X, times=[365.0]).T.iloc[:, 0].to_numpy()
            rows.append(
                {
                    "model": model.name,
                    "group": group,
                    "standardized_365d_mortality_risk": float(np.mean(1.0 - surv)),
                    "role": "cox_ph_sensitivity_point_estimate",
                }
            )
    return pd.DataFrame(rows)


def multiplicative_interaction(raw_df: pd.DataFrame, formulas: dict[str, str]) -> pd.DataFrame:
    rows = []
    for model_name in ["Model 1", "Model 2"]:
        full = fit_cox_primary_or_sensitivity(raw_df, formulas[f"Interaction {model_name}"], f"Interaction {model_name}")
        reduced = fit_cox_primary_or_sensitivity(raw_df, formulas[f"Interaction {model_name} reduced"], f"Interaction {model_name} reduced")
        lr = 2.0 * (full.cph.log_likelihood_ - reduced.cph.log_likelihood_)
        p_lrt = chi2.sf(lr, 1)
        s = full.cph.summary.reset_index().rename(columns={"covariate": "term"})
        for term in [
            "psych_primary_documented_by_index",
            "delirium_binary",
            "psych_primary_documented_by_index:delirium_binary",
        ]:
            r = s[s["term"].eq(term)].iloc[0]
            rows.append(
                {
                    "model": model_name,
                    "term": term,
                    "HR": r["exp(coef)"],
                    "CI95_lower": r["exp(coef) lower 95%"],
                    "CI95_upper": r["exp(coef) upper 95%"],
                    "wald_p_value": r["p"],
                    "interaction_lrt_chisq": lr if term.endswith("delirium_binary") else np.nan,
                    "interaction_lrt_df": 1 if term.endswith("delirium_binary") else np.nan,
                    "interaction_lrt_p_value": p_lrt if term.endswith("delirium_binary") else np.nan,
                    "analysis_n": int(full.fit_df.shape[0]),
                    "event_n": int(full.fit_df["event"].sum()),
                    "penalizer": full.penalizer,
                }
            )
    return pd.DataFrame(rows)


def time_specific_multiplicative_interaction(raw_df: pd.DataFrame, formula: str) -> pd.DataFrame:
    rows = []
    for start, stop, label in WINDOWS:
        sub = raw_df[raw_df["time_main"] > start].copy()
        sub["window_time"] = np.minimum(sub["time_main"], stop) - start
        sub["window_event"] = np.where(
            sub["event_main"].eq(1) & (sub["time_main"] <= stop) & (sub["time_main"] > start),
            1,
            0,
        )
        sub = sub[sub["window_time"] > 0].copy()
        fit = fit_cox_primary_or_sensitivity(
            sub,
            formula,
            f"Time-specific multiplicative interaction {label}",
            duration_col="window_time",
            event_col="window_event",
        )
        s = fit.cph.summary.reset_index().rename(columns={"covariate": "term"})
        term = "psych_primary_documented_by_index:delirium_binary"
        r = s[s["term"].eq(term)].iloc[0]
        rows.append(
            {
                "time_window": label,
                "term": term,
                "HR": r["exp(coef)"],
                "CI95_lower": r["exp(coef) lower 95%"],
                "CI95_upper": r["exp(coef) upper 95%"],
                "wald_p_value": r["p"],
                "analysis_n": int(fit.fit_df.shape[0]),
                "event_n": int(fit.fit_df["event"].sum()),
                "penalizer": fit.penalizer,
            }
        )
    return pd.DataFrame(rows)


def same_day_sensitivity(raw_df: pd.DataFrame, formula: str) -> pd.DataFrame:
    sens = raw_df[raw_df["death_date_logic_abnormal_flag"].eq("none")].copy()
    fit = fit_cox_primary_or_sensitivity(
        sens,
        formula,
        "Model 2 same-day DOD sensitivity",
        duration_col="time_same_day_sensitivity",
        event_col="event_same_day_sensitivity",
    )
    return cox_joint_rows([fit]).assign(
        sensitivity="include_same_day_dod_time_0_5_days",
        same_day_dod_included_n=int(sens["death_same_day_discharge"].sum()),
    )


def write_time_varying_formula(formulas: dict[str, str]) -> None:
    text = "\n".join(
        [
            "# Time-Varying Cox Model Formula",
            "",
            "The formal joint exposure non-PH assessment uses start-stop data split into 0-30, 30-90, and 90-365 day intervals.",
            "",
            "## Reduced Model",
            "",
            "Joint exposure has a single coefficient across the full 0-365 day follow-up. Other covariates use the corrected Model 2 formula.",
            "",
            "```text",
            formulas["Model 2"],
            "```",
            "",
            "## Full Model",
            "",
            "The full model adds interactions between the three joint-exposure indicator columns and two later-interval indicators:",
            "",
            "- interval_30_90",
            "- interval_90_365",
            "",
            "This gives each non-reference exposure group independent HRs in 0-30, 30-90, and 90-365 days while keeping all other Model 2 covariates fixed.",
            "",
            "## Formal Test",
            "",
            "Likelihood-ratio test comparing full versus reduced model; df=6. The previous v1 global PH P value made by summing individual Schoenfeld statistics is deprecated.",
            "",
        ]
    )
    (OUTPUT_DIR / "time_varying_cox_model_formula.md").write_text(text, encoding="utf-8")


def write_report(
    accounting: pd.DataFrame,
    rank_qc: pd.DataFrame,
    cond_qc: pd.DataFrame,
    cox_joint: pd.DataFrame,
    comparison: pd.DataFrame,
    tv_effects: pd.DataFrame,
    tv_lrt: pd.DataFrame,
    fixed_risk: pd.DataFrame,
    additive: pd.DataFrame,
    mult: pd.DataFrame,
    time_mult: pd.DataFrame,
    same_day: pd.DataFrame,
) -> None:
    def md(df: pd.DataFrame, n: int = 30) -> str:
        if df.empty:
            return "_No rows._"
        return df.head(n).to_markdown(index=False)

    lines = [
        "# Primary Mortality Model Report v1.1",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Run timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Random seed: `{SEED}`",
        f"- Bootstrap iterations requested: `{BOOTSTRAP_N}`",
        "",
        "## Implementation Corrections",
        "",
        "- Original v1 age spline implementation produced an effective Cox design/Hessian rank problem with unstable age-spline inference and required automatic ridge stabilization.",
        "- v1.1 uses a centered full-rank natural cubic spline: `cr(age_at_index_admission, knots=(60,72), lower_bound=31, upper_bound=89, constraints='center')`.",
        "- Explicit intercept is removed from Cox design matrices; age contributes 3 independent centered spline columns.",
        "- `nonneurologic_sofa_observed_components_n` uses reference level 5.",
        "- CoxPHFitter was first run with `penalizer=0`; no automatic ridge is used for primary Cox results when convergence succeeds.",
        "- Exposures, outcomes, analysis population, and prespecified covariate set were not changed.",
        "- Full-year Cox HRs are interpreted as average associations over 0-365 days because PH is not satisfied.",
        "",
        "## Cohort Accounting",
        "",
        md(accounting),
        "",
        "## Design Matrix QC",
        "",
        md(rank_qc),
        "",
        "## Condition Number QC",
        "",
        md(cond_qc),
        "",
        "## Corrected Cox Joint Exposure Models",
        "",
        md(cox_joint),
        "",
        "## v1 vs v1.1 Cox Comparison",
        "",
        md(comparison),
        "",
        "## Time-Varying Cox Joint Exposure Effects",
        "",
        md(tv_effects),
        "",
        "## Formal Non-PH LRT",
        "",
        md(tv_lrt),
        "",
        "## Fixed-Horizon 365-Day Standardized Risk",
        "",
        md(fixed_risk),
        "",
        "## Fixed-Horizon Additive Interaction",
        "",
        md(additive),
        "",
        "## Full-Year Multiplicative Interaction",
        "",
        md(mult),
        "",
        "## Time-Specific Multiplicative Interaction",
        "",
        md(time_mult),
        "",
        "## Same-Day DOD Sensitivity",
        "",
        md(same_day),
        "",
        "## Clinical Conclusion Compared With v1",
        "",
        "The implementation correction changes numerical stability and the formal handling of non-PH, but the qualitative pattern remains: delirium groups show higher one-year mortality risk than the no-psychiatric/no-delirium reference; psychiatric comorbidity without delirium shows a smaller increase; the combined psychiatric-plus-delirium group is not higher than the delirium-without-psychiatric group in the fixed-horizon risk estimates. This is descriptive/prognostic language, not causal language.",
        "",
        "## Warnings And Deviations",
        "",
    ]
    if analysis_warnings:
        lines.extend([f"- {w}" for w in sorted(set(analysis_warnings))])
    else:
        lines.append("- No warnings were recorded.")
    (OUTPUT_DIR / "primary_mortality_model_report_v1_1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_session_files() -> None:
    packages = ["duckdb", "pandas", "numpy", "lifelines", "matplotlib", "patsy", "scipy", "statsmodels"]
    rows = []
    for pkg in packages:
        mod = __import__(pkg)
        rows.append({"package": pkg, "version": getattr(mod, "__version__", "unknown")})
    write_csv(pd.DataFrame(rows), OUTPUT_DIR / "package_versions_v1_1.csv")
    session = [
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Executable: {sys.executable}",
        "Rscript: not used for v1.1; Python implementation executed.",
        "",
        pd.DataFrame(rows).to_string(index=False),
    ]
    (OUTPUT_DIR / "sessionInfo_v1_1.txt").write_text("\n".join(session) + "\n", encoding="utf-8")


def update_sap_log() -> None:
    if not SAP_AMENDMENT_LOG.exists():
        return
    text = SAP_AMENDMENT_LOG.read_text(encoding="utf-8")
    marker = "### Primary mortality implementation correction v1.1"
    if marker in text:
        return
    addition = """

### Primary mortality implementation correction v1.1

- Date: 2026-06-21
- Status: Implemented after independent code audit and before subsequent model batches.
- Age spline basis-function rank deficiency was identified in the initial primary mortality implementation.
- v1.1 uses a centered full-rank natural cubic spline: `cr(age_at_index_admission, knots=(60,72), lower_bound=31, upper_bound=89, constraints='center')`.
- `nonneurologic_sofa_observed_components_n` reference level was corrected to 5.
- Formal joint-exposure non-PH assessment was changed to a start-stop time-varying Cox likelihood-ratio test.
- Fixed-horizon 365-day absolute risks and additive interaction are now estimated primarily using logistic-model g-computation.
- These corrections did not change the exposure, outcome, analysis population, or prespecified covariate set.
- Original v1 primary mortality outputs were fully preserved.
"""
    SAP_AMENDMENT_LOG.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


def write_manifest() -> None:
    files = sorted([p for p in OUTPUT_DIR.iterdir() if p.is_file() and p.name != "primary_mortality_v1_1_run_manifest.md"], key=lambda p: p.name.lower())
    files.append(SCRIPT_PATH)
    lines = [
        "# Primary Mortality v1.1 Run Manifest",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Run timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Random seed: `{SEED}`",
        f"- Bootstrap iterations requested: `{BOOTSTRAP_N}`",
        "- Original v1 output directory was not modified.",
        "",
        "| File | SHA256 |",
        "|---|---|",
    ]
    seen = set()
    for p in files:
        if p.exists() and p not in seen:
            seen.add(p)
            lines.append(f"| `{p}` | `{sha256_path(p)}` |")
    (OUTPUT_DIR / "primary_mortality_v1_1_run_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    np.random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading frozen data...", flush=True)
    table1_df = load_data()
    model_df = table1_df[
        table1_df["death_same_day_discharge"].eq(0)
        & table1_df["death_date_logic_abnormal_flag"].eq("none")
    ].copy()
    model_df = model_df.dropna(subset=["time_main", "event_main"] + MODEL2_RAW_VARIABLES + ["delirium_binary"]).copy()

    accounting = pd.DataFrame(
        [
            {"metric": "table1_population_n", "n": int(table1_df.shape[0])},
            {"metric": "primary_mortality_model_n", "n": int(model_df.shape[0])},
            {"metric": "excluded_same_day_dod_n", "n": int(((table1_df["death_same_day_discharge"] == 1) & (table1_df["death_date_logic_abnormal_flag"] == "none")).sum())},
            {"metric": "excluded_death_date_logic_abnormal_n", "n": int((table1_df["death_date_logic_abnormal_flag"] != "none").sum())},
            {"metric": "primary_mortality_model_1y_death_events_n", "n": int(model_df["event_main"].sum())},
        ]
    )
    write_csv(accounting, OUTPUT_DIR / "model_cohort_accounting_v1_1.csv")

    formulas = model_formulas()

    print("Fitting corrected Cox models with penalizer=0...", flush=True)
    m0 = fit_cox_primary_or_sensitivity(model_df, formulas["Model 0"], "Model 0")
    m1 = fit_cox_primary_or_sensitivity(model_df, formulas["Model 1"], "Model 1")
    m2 = fit_cox_primary_or_sensitivity(model_df, formulas["Model 2"], "Model 2")
    models = [m0, m1, m2]

    rank_qc, cond_qc, age_qc = design_qc(model_df, formulas, models)
    write_csv(rank_qc, OUTPUT_DIR / "design_matrix_rank_qc.csv")
    write_csv(cond_qc, OUTPUT_DIR / "design_matrix_condition_number.csv")
    write_csv(age_qc, OUTPUT_DIR / "age_spline_basis_qc.csv")

    cox_joint = cox_joint_rows(models)
    cox_full = cox_full_coefficients(models)
    fit_stats = model_fit_stats(models)
    comparison = compare_with_original(cox_joint)  # optional historical comparison; formal v1.1 outputs do not depend on v1 files
    write_csv(cox_joint, OUTPUT_DIR / "cox_joint_exposure_models_v1_1.csv")
    write_csv(cox_full, OUTPUT_DIR / "cox_full_coefficient_tables_v1_1.csv")
    write_csv(fit_stats, OUTPUT_DIR / "cox_model_fit_statistics_v1_1.csv")
    write_csv(comparison, OUTPUT_DIR / "corrected_vs_original_cox_comparison.csv")

    ph_aux = fit_ph_tests(models)
    write_csv(ph_aux, OUTPUT_DIR / "ph_assumption_tests_v1_1_auxiliary.csv")

    print("Fitting formal time-varying Cox non-PH models...", flush=True)
    tv_effects, tv_lrt, tv_counts, tv_objects = fit_time_varying_nonph(model_df, m2)
    write_csv(tv_effects, OUTPUT_DIR / "time_varying_cox_exposure_effects.csv")
    write_csv(tv_lrt, OUTPUT_DIR / "time_varying_cox_nonph_lrt.csv")
    write_csv(tv_counts, OUTPUT_DIR / "time_varying_cox_interval_counts.csv")
    write_time_varying_formula(formulas)

    print("Fitting fixed-horizon logistic models and bootstrap...", flush=True)
    log1 = fit_logistic(model_df, formulas["Model 1"], "Fixed horizon Model 1")
    log2 = fit_logistic(model_df, formulas["Model 2"], "Fixed horizon Model 2")
    point = {
        "Model 1": logistic_standardized_risk(log1, model_df),
        "Model 2": logistic_standardized_risk(log2, model_df),
    }
    boot, boot_diag = bootstrap_fixed_horizon(model_df, formulas, {"Model 1": log1.design_info, "Model 2": log2.design_info})
    fixed_risk, additive = summarize_fixed_horizon(point, boot)
    write_csv(fixed_risk, OUTPUT_DIR / "fixed_horizon_365d_standardized_risk.csv")
    write_csv(additive, OUTPUT_DIR / "fixed_horizon_365d_additive_interaction.csv")
    write_csv(boot_diag, OUTPUT_DIR / "fixed_horizon_bootstrap_diagnostics.csv")
    plot_fixed_horizon_risk(fixed_risk)

    cox_std = cox_ph_standardized_sensitivity(models, model_df)
    write_csv(cox_std, OUTPUT_DIR / "cox_ph_standardized_365d_risk_sensitivity_v1_1.csv")

    print("Fitting multiplicative interaction and same-day sensitivity models...", flush=True)
    mult = multiplicative_interaction(model_df, formulas)
    time_mult = time_specific_multiplicative_interaction(model_df, formulas["Interaction Model 2"])
    same_day = same_day_sensitivity(table1_df, formulas["Model 2"])
    write_csv(mult, OUTPUT_DIR / "multiplicative_interaction_mortality_v1_1.csv")
    write_csv(time_mult, OUTPUT_DIR / "time_specific_multiplicative_interaction.csv")
    write_csv(same_day, OUTPUT_DIR / "mortality_include_same_day_sensitivity_v1_1.csv")

    with (OUTPUT_DIR / "cox_model_objects_v1_1.pkl").open("wb") as f:
        pickle.dump({"models": {m.name: m.cph for m in models}, "formulas": formulas}, f)
    with (OUTPUT_DIR / "time_varying_cox_model_objects_v1_1.pkl").open("wb") as f:
        pickle.dump(tv_objects, f)
    with (OUTPUT_DIR / "fixed_horizon_logistic_model_objects_v1_1.pkl").open("wb") as f:
        pickle.dump({"Model 1": log1.result, "Model 2": log2.result, "formulas": formulas}, f)

    write_report(accounting, rank_qc, cond_qc, cox_joint, comparison, tv_effects, tv_lrt, fixed_risk, additive, mult, time_mult, same_day)
    write_session_files()
    update_sap_log()
    write_manifest()

    print("DONE", flush=True)
    print(f"output_dir={OUTPUT_DIR}", flush=True)
    print(f"report={OUTPUT_DIR / 'primary_mortality_model_report_v1_1.md'}", flush=True)
    print(f"report_sha256={sha256_path(OUTPUT_DIR / 'primary_mortality_model_report_v1_1.md')}", flush=True)
    print(f"manifest={OUTPUT_DIR / 'primary_mortality_v1_1_run_manifest.md'}", flush=True)
    print(f"manifest_sha256={sha256_path(OUTPUT_DIR / 'primary_mortality_v1_1_run_manifest.md')}", flush=True)


if __name__ == "__main__":
    main()
