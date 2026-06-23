from __future__ import annotations

import glob
import hashlib
import os
import pickle
import platform
import shutil
import subprocess
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
from lifelines import AalenJohansenFitter, CoxPHFitter, CoxTimeVaryingFitter
from lifelines.exceptions import ConvergenceWarning, StatisticalWarning
from lifelines.statistics import proportional_hazard_test
from patsy import build_design_matrices, dmatrix
from scipy.stats import chi2


SEED = 20260621
BOOTSTRAP_N = int(os.environ.get("READMISSION_BOOTSTRAP_N", "1000"))

PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", PROJECT.parent / "data" / "mimiciv.duckdb"))
OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes"
SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_readmission_outcomes_v1.py"
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

OUTCOMES = {
    "readmission_90d": {
        "label": "90-day same-system readmission",
        "time_col": "time_to_first_readmission_or_death_90d",
        "status_col": "readmission_90d_status",
        "horizon": 90.0,
        "windows": [(0.0, 30.0, "0_30_days"), (30.0, 90.0, "30_90_days")],
        "expected": {0: 16132, 1: 6321, 2: 1580},
        "target_file": "readmission_90d_cause_specific_cox.csv",
        "crude_file": "readmission_90d_crude_status_by_group.csv",
        "aj_file": "readmission_90d_aj_cif.csv",
        "figure_file": "figure_readmission_90d_cif.pdf",
        "std_file": "standardized_90d_readmission_cif.csv",
        "add_file": "additive_interaction_readmission_90d.csv",
        "fg_file": "readmission_90d_fine_gray.csv",
    },
    "icu_readmission_365d": {
        "label": "365-day same-system ICU readmission",
        "time_col": "time_to_first_icu_readmission_or_death_365d",
        "status_col": "icu_readmission_365d_status",
        "horizon": 365.0,
        "windows": [(0.0, 30.0, "0_30_days"), (30.0, 90.0, "30_90_days"), (90.0, 365.0, "90_365_days")],
        "expected": {0: 17728, 1: 3228, 2: 3077},
        "target_file": "icu_readmission_365d_cause_specific_cox.csv",
        "crude_file": "icu_readmission_365d_crude_status_by_group.csv",
        "aj_file": "icu_readmission_365d_aj_cif.csv",
        "figure_file": "figure_icu_readmission_365d_cif.pdf",
        "std_file": "standardized_365d_icu_readmission_cif.csv",
        "add_file": "additive_interaction_icu_readmission_365d.csv",
        "fg_file": "icu_readmission_365d_fine_gray.csv",
    },
}


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
MODEL2_ADDED_VARIABLES = ["nonneurologic_sofa_zero_imputed", "nonneurologic_sofa_observed_components_n"]
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


@dataclass
class CoxModel:
    model_name: str
    outcome: str
    cause: str
    formula: str
    design_info: object
    fitter: CoxPHFitter
    fit_df: pd.DataFrame
    raw_df: pd.DataFrame
    exposure_columns: list[str]
    penalizer: float
    converged_without_ridge: bool
    error: str = ""


@dataclass
class TVModel:
    model_name: str
    outcome: str
    cause: str
    formula: str
    design_info: object
    fitter: CoxTimeVaryingFitter
    exposure_columns: list[str]
    windows: list[tuple[float, float, str]]
    later_labels: list[str]
    converged_without_ridge: bool
    error: str = ""


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


def centered_age_spline() -> str:
    return "cr(age_at_index_admission, knots=(60, 72), lower_bound=31, upper_bound=89, constraints='center')"


def formulas() -> dict[str, str]:
    joint = f"C(joint_exposure_4level, Treatment(reference='{REFERENCE_GROUP}'))"
    common = [
        joint,
        centered_age_spline(),
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
    inter_base = [
        "psych_primary_documented_by_index",
        "delirium_binary",
        "psych_primary_documented_by_index:delirium_binary",
    ] + common[1:]
    inter_reduced = ["psych_primary_documented_by_index", "delirium_binary"] + common[1:]
    return {
        "Model 0": joint,
        "Model 1": " + ".join(common),
        "Model 2": " + ".join(common + model2_extra),
        "Interaction Model 1": " + ".join(inter_base),
        "Interaction Model 1 reduced": " + ".join(inter_reduced),
        "Interaction Model 2": " + ".join(inter_base + model2_extra),
        "Interaction Model 2 reduced": " + ".join(inter_reduced + model2_extra),
    }


def design_matrix(raw_df: pd.DataFrame, formula: str, design_info=None, drop_intercept=True) -> tuple[pd.DataFrame, object]:
    if design_info is None:
        X = dmatrix(formula, raw_df, return_type="dataframe")
        design_info = X.design_info
    else:
        X = build_design_matrices([design_info], raw_df, return_type="dataframe")[0]
    X = pd.DataFrame(X, index=raw_df.index).astype(float)
    if drop_intercept and "Intercept" in X.columns:
        X = X.drop(columns=["Intercept"])
    return X, design_info


def exposure_cols(cols: list[str]) -> list[str]:
    return [c for c in cols if "joint_exposure_4level" in c]


def load_data() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(
        f"""
        select
            joint_exposure_4level,
            psych_primary_documented_by_index,
            delirium_status_72h,
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
            nonneurologic_sofa_observed_components_n,
            time_to_first_readmission_or_death_90d,
            readmission_90d_status,
            time_to_first_icu_readmission_or_death_365d,
            icu_readmission_365d_status
        from {TABLE}
        where primary_analysis_cohort = 1
          and conservative_readmission_cohort = 1
        """
    ).fetchdf()
    con.close()
    return prepare_data(df)


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in CATEGORICAL_VARIABLES:
        df[col] = df[col].fillna("Missing").astype(str)
    numeric = [
        "psych_primary_documented_by_index",
        "age_at_index_admission",
        "prior_mimic_hospitalizations",
        "charlson_comorbidity_only_documented_by_index",
        "dementia_documented_by_index",
        "substance_use_documented_by_index",
        "chronic_neurologic_disease",
        "nonneurologic_sofa_zero_imputed",
        "nonneurologic_sofa_observed_components_n",
        "time_to_first_readmission_or_death_90d",
        "readmission_90d_status",
        "time_to_first_icu_readmission_or_death_365d",
        "icu_readmission_365d_status",
    ]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["delirium_binary"] = np.where(df["delirium_status_72h"].eq("positive"), 1, 0)
    df["log1p_prior_mimic_hospitalizations"] = np.log1p(df["prior_mimic_hospitalizations"])
    df["joint_exposure_4level"] = pd.Categorical(df["joint_exposure_4level"], categories=GROUP_ORDER)
    return df


def model_data(raw: pd.DataFrame, outcome: str, cause_status: int) -> pd.DataFrame:
    cfg = OUTCOMES[outcome]
    df = raw.copy()
    df["time"] = df[cfg["time_col"]].astype(float)
    df["event"] = (df[cfg["status_col"]] == cause_status).astype(int)
    return df


def fit_cox(
    raw: pd.DataFrame,
    formula: str,
    model_name: str,
    outcome: str,
    cause: str,
    cause_status: int,
    design_info=None,
    weights: np.ndarray | None = None,
    penalizer: float = 0.0,
) -> CoxModel:
    df = model_data(raw, outcome, cause_status)
    X, design_info = design_matrix(df, formula, design_info=design_info, drop_intercept=True)
    fit_df = pd.concat([df[["time", "event"]], X], axis=1)
    if weights is not None:
        fit_df["boot_weight"] = weights
    cph = CoxPHFitter(penalizer=penalizer)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        warnings.simplefilter("always", StatisticalWarning)
        cph.fit(
            fit_df,
            duration_col="time",
            event_col="event",
            weights_col="boot_weight" if weights is not None else None,
            show_progress=False,
        )
    if weights is None:
        for w in caught:
            analysis_warnings.append(f"{outcome} {cause} {model_name}: {str(w.message)}")
    return CoxModel(
        model_name=model_name,
        outcome=outcome,
        cause=cause,
        formula=formula,
        design_info=design_info,
        fitter=cph,
        fit_df=fit_df,
        raw_df=raw.copy(),
        exposure_columns=exposure_cols(list(X.columns)),
        penalizer=penalizer,
        converged_without_ridge=penalizer == 0.0,
    )


def fit_cox_no_silent_ridge(*args, **kwargs) -> CoxModel:
    try:
        return fit_cox(*args, penalizer=0.0, **kwargs)
    except Exception as exc:
        outcome = kwargs.get("outcome", args[3] if len(args) > 3 else "unknown")
        cause = kwargs.get("cause", args[4] if len(args) > 4 else "unknown")
        model_name = kwargs.get("model_name", args[2] if len(args) > 2 else "unknown")
        msg = f"{outcome} {cause} {model_name} did not converge with penalizer=0: {type(exc).__name__}: {exc}"
        analysis_warnings.append(msg)
        m = fit_cox(*args, penalizer=1e-9, **kwargs)
        m.converged_without_ridge = False
        m.error = msg
        return m


def coefficient_rows(model: CoxModel) -> pd.DataFrame:
    s = model.fitter.summary.reset_index().rename(columns={"covariate": "term"})
    rows = []
    for _, r in s.iterrows():
        rows.append(
            {
                "outcome": model.outcome,
                "cause": model.cause,
                "model": model.model_name,
                "term": r["term"],
                "coefficient": r["coef"],
                "standard_error": r["se(coef)"],
                "HR": r["exp(coef)"],
                "CI_lower": r["exp(coef) lower 95%"],
                "CI_upper": r["exp(coef) upper 95%"],
                "P_value": r["p"],
                "penalizer": model.penalizer,
                "converged_without_ridge": model.converged_without_ridge,
            }
        )
    return pd.DataFrame(rows)


def group_from_term(term: str) -> str:
    for group in GROUP_ORDER[1:]:
        if group in term:
            return group
    return term


def joint_rows(model: CoxModel) -> pd.DataFrame:
    s = model.fitter.summary.reset_index().rename(columns={"covariate": "term"})
    rows = []
    for col in model.exposure_columns:
        r = s[s["term"].eq(col)].iloc[0]
        rows.append(
            {
                "outcome": model.outcome,
                "cause": model.cause,
                "model": model.model_name,
                "contrast": f"{group_from_term(col)} vs {REFERENCE_GROUP}",
                "term": col,
                "HR": r["exp(coef)"],
                "CI95_lower": r["exp(coef) lower 95%"],
                "CI95_upper": r["exp(coef) upper 95%"],
                "p_value": r["p"],
                "analysis_n": int(model.fit_df.shape[0]),
                "event_n": int(model.fit_df["event"].sum()),
                "AIC_partial": model.fitter.AIC_partial_,
                "concordance": model.fitter.concordance_index_,
                "penalizer": model.penalizer,
                "converged_without_ridge": model.converged_without_ridge,
                "fit_error_if_any": model.error,
            }
        )
    return pd.DataFrame(rows)


def design_qc(raw: pd.DataFrame, forms: dict[str, str], fitted: list[CoxModel]) -> tuple[pd.DataFrame, pd.DataFrame]:
    fit_lookup = {(m.outcome, m.cause, m.model_name): m for m in fitted}
    rank_rows = []
    cond_rows = []
    for outcome in OUTCOMES:
        for cause in ["target", "competing_death"]:
            for model_name in ["Model 0", "Model 1", "Model 2"]:
                X, _ = design_matrix(raw, forms[model_name], drop_intercept=True)
                mat = X.to_numpy()
                rank = int(np.linalg.matrix_rank(mat))
                cond = float(np.linalg.cond(mat))
                m = fit_lookup[(outcome, cause, model_name)]
                rank_rows.append(
                    {
                        "outcome": outcome,
                        "cause": cause,
                        "model": model_name,
                        "design_matrix_columns_n": int(X.shape[1]),
                        "matrix_rank": rank,
                        "full_rank": bool(rank == X.shape[1]),
                        "penalizer": m.penalizer,
                        "converged_without_ridge": m.converged_without_ridge,
                        "warning_or_error": m.error,
                    }
                )
                s = np.linalg.svd(mat, compute_uv=False)
                cond_rows.append(
                    {
                        "outcome": outcome,
                        "cause": cause,
                        "model": model_name,
                        "condition_number": cond,
                        "min_singular_value": float(np.min(s)),
                        "max_singular_value": float(np.max(s)),
                    }
                )
    return pd.DataFrame(rank_rows), pd.DataFrame(cond_rows)


def crude_status_by_group(raw: pd.DataFrame, outcome: str) -> pd.DataFrame:
    cfg = OUTCOMES[outcome]
    rows = []
    for group in GROUP_ORDER:
        sub = raw[raw["joint_exposure_4level"].eq(group)]
        for status, label in [(0, "no_target_event_no_competing_death"), (1, "target_event"), (2, "competing_death_before_target")]:
            n = int((sub[cfg["status_col"]] == status).sum())
            rows.append(
                {
                    "outcome": outcome,
                    "group": group,
                    "label": GROUP_LABELS[group],
                    "status": status,
                    "status_label": label,
                    "n": n,
                    "denominator": int(sub.shape[0]),
                    "percent": 100.0 * n / sub.shape[0],
                }
            )
    return pd.DataFrame(rows)


def aalen_johansen(raw: pd.DataFrame, outcome: str) -> pd.DataFrame:
    cfg = OUTCOMES[outcome]
    rows = []
    for group in GROUP_ORDER:
        sub = raw[raw["joint_exposure_4level"].eq(group)]
        for cause, label in [(1, "target_event"), (2, "competing_death")]:
            aj = AalenJohansenFitter(jitter_level=1e-8, seed=SEED)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                aj.fit(sub[cfg["time_col"]], sub[cfg["status_col"]].astype(int), event_of_interest=cause)
            tmp = aj.cumulative_density_.reset_index()
            tmp.columns = ["time", "cif"]
            tmp = tmp[tmp["time"] <= cfg["horizon"]].copy()
            tmp["outcome"] = outcome
            tmp["group"] = group
            tmp["label"] = GROUP_LABELS[group]
            tmp["cause"] = cause
            tmp["cause_label"] = label
            rows.append(tmp[["outcome", "group", "label", "cause", "cause_label", "time", "cif"]])
    return pd.concat(rows, ignore_index=True)


def plot_aj(cif: pd.DataFrame, outcome: str) -> None:
    cfg = OUTCOMES[outcome]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=False)
    for ax, cause, title in [(axes[0], 1, "Target event CIF"), (axes[1], 2, "Competing death CIF")]:
        for group in GROUP_ORDER:
            sub = cif[(cif["group"].eq(group)) & (cif["cause"].eq(cause))]
            ax.step(sub["time"], sub["cif"], where="post", label=GROUP_LABELS[group])
        ax.set_xlim(0, cfg["horizon"])
        ax.set_xlabel("Days since index hospital discharge")
        ax.set_ylabel("Cumulative incidence")
        ax.set_title(title)
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=7)
    fig.suptitle(cfg["label"])
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / cfg["figure_file"])
    plt.close(fig)


def ph_tests(model2_target: CoxModel) -> pd.DataFrame:
    rows = []
    try:
        result = proportional_hazard_test(model2_target.fitter, model2_target.fit_df, time_transform="rank")
        s = result.summary.reset_index().rename(columns={"index": "term"})
        for _, r in s.iterrows():
            rows.append(
                {
                    "outcome": model2_target.outcome,
                    "cause": model2_target.cause,
                    "model": "Model 2",
                    "test_scope": "individual_term_auxiliary_schoenfeld",
                    "term": r["term"],
                    "test_statistic": r["test_statistic"],
                    "df": 1,
                    "p_value": r["p"],
                    "formal_status": "auxiliary_only",
                }
            )
    except Exception as exc:
        analysis_warnings.append(f"PH test failed for {model2_target.outcome}: {exc}")
    return pd.DataFrame(rows)


def build_tv_raw(raw: pd.DataFrame, outcome: str, cause_status: int) -> pd.DataFrame:
    cfg = OUTCOMES[outcome]
    base = raw.reset_index(drop=True).copy()
    base["_pid"] = np.arange(base.shape[0])
    pieces = []
    for start, stop, label in cfg["windows"]:
        part = base[base[cfg["time_col"]] > start].copy()
        part["start"] = start
        part["stop"] = np.minimum(part[cfg["time_col"]], stop)
        part["event_tv"] = np.where(
            (part[cfg["status_col"]] == cause_status) & (part[cfg["time_col"]] <= stop) & (part[cfg["time_col"]] > start),
            1,
            0,
        )
        part["interval_label"] = label
        for _, _, lab in cfg["windows"][1:]:
            part[f"interval_{lab}"] = int(label == lab)
        part = part[part["stop"] > part["start"]].copy()
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)


def fit_tv(raw: pd.DataFrame, outcome: str, cause: str, cause_status: int, formula: str, model_name: str, design_info=None, weights: np.ndarray | None = None) -> tuple[TVModel, TVModel, pd.DataFrame, pd.DataFrame]:
    cfg = OUTCOMES[outcome]
    tv = build_tv_raw(raw, outcome, cause_status)
    if weights is not None:
        tv["boot_weight"] = weights[tv["_pid"].to_numpy()]
    X, design_info = design_matrix(tv, formula, design_info=design_info, drop_intercept=True)
    reduced_df = pd.concat([tv[["_pid", "start", "stop", "event_tv"]], X], axis=1)
    if weights is not None:
        reduced_df["boot_weight"] = tv["boot_weight"].to_numpy()
    reduced = CoxTimeVaryingFitter(penalizer=0.0)
    reduced.fit(
        reduced_df,
        id_col="_pid",
        start_col="start",
        stop_col="stop",
        event_col="event_tv",
        weights_col="boot_weight" if weights is not None else None,
        show_progress=False,
    )
    later_labels = [lab for _, _, lab in cfg["windows"][1:]]
    full_X = X.copy()
    exp_cols = exposure_cols(list(X.columns))
    for col in exp_cols:
        for lab in later_labels:
            full_X[f"{col}:interval_{lab}"] = full_X[col] * tv[f"interval_{lab}"].to_numpy()
    full_df = pd.concat([tv[["_pid", "start", "stop", "event_tv"]], full_X], axis=1)
    if weights is not None:
        full_df["boot_weight"] = tv["boot_weight"].to_numpy()
    full = CoxTimeVaryingFitter(penalizer=0.0)
    full.fit(
        full_df,
        id_col="_pid",
        start_col="start",
        stop_col="stop",
        event_col="event_tv",
        weights_col="boot_weight" if weights is not None else None,
        show_progress=False,
    )
    red_model = TVModel(model_name, outcome, cause, formula, design_info, reduced, exp_cols, cfg["windows"], later_labels, True)
    full_model = TVModel(model_name, outcome, cause, formula, design_info, full, exp_cols, cfg["windows"], later_labels, True)
    lr = 2.0 * (full.log_likelihood_ - reduced.log_likelihood_)
    df_lrt = len(exp_cols) * len(later_labels)
    lrt = pd.DataFrame(
        [
            {
                "outcome": outcome,
                "cause": cause,
                "model": model_name,
                "test": "joint_exposure_time_varying_lrt",
                "reduced_log_likelihood": reduced.log_likelihood_,
                "full_log_likelihood": full.log_likelihood_,
                "chisq": lr,
                "df": df_lrt,
                "p_value": chi2.sf(lr, df_lrt),
            }
        ]
    )
    effects = tv_effect_rows(full_model)
    return red_model, full_model, effects, lrt


def tv_effect_rows(model: TVModel) -> pd.DataFrame:
    params = model.fitter.params_
    cov = model.fitter.variance_matrix_
    rows = []
    for col in model.exposure_columns:
        group = group_from_term(col)
        for _, _, label in model.windows:
            vec = pd.Series(0.0, index=params.index)
            vec[col] = 1.0
            if label in model.later_labels:
                vec[f"{col}:interval_{label}"] = 1.0
            beta = float(np.dot(vec, params))
            se = float(np.sqrt(np.dot(vec, np.dot(cov, vec))))
            rows.append(
                {
                    "outcome": model.outcome,
                    "cause": model.cause,
                    "model": model.model_name,
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
    return pd.DataFrame(rows)


def baseline_increment(fitter, horizon: float) -> pd.Series:
    s = fitter.baseline_cumulative_hazard_.iloc[:, 0].copy()
    s = s[s.index <= horizon]
    if s.empty:
        return pd.Series(dtype=float)
    inc = s.diff()
    inc.iloc[0] = s.iloc[0]
    inc = inc[inc > 0]
    return inc


def interval_label(time_value: float, windows: list[tuple[float, float, str]]) -> str:
    for start, stop, label in windows:
        if time_value > start and time_value <= stop:
            return label
    return windows[-1][2]


def lp_for_group(model, raw: pd.DataFrame, group: str, label: str | None = None) -> np.ndarray:
    cf = raw.copy()
    cf["joint_exposure_4level"] = pd.Categorical([group] * cf.shape[0], categories=GROUP_ORDER)
    X, _ = design_matrix(cf, model.formula, design_info=model.design_info, drop_intercept=True)
    params = model.fitter.params_
    for col in params.index:
        if col not in X.columns:
            X[col] = 0.0
    if isinstance(model, TVModel):
        for col in model.exposure_columns:
            for lab in model.later_labels:
                int_col = f"{col}:interval_{lab}"
                X[int_col] = X[col] if label == lab else 0.0
    X = X[list(params.index)]
    return np.asarray(np.dot(X, params), dtype=float)


def individual_cif_by_group(target_model, death_model, raw: pd.DataFrame, outcome: str) -> dict[str, np.ndarray]:
    cfg = OUTCOMES[outcome]
    horizon = cfg["horizon"]
    dht = baseline_increment(target_model.fitter, horizon)
    dhd = baseline_increment(death_model.fitter, horizon)
    times = np.array(sorted(set(dht.index.astype(float)).union(set(dhd.index.astype(float)))), dtype=float)
    if times.size == 0:
        return {group: np.zeros(raw.shape[0], dtype=float) for group in GROUP_ORDER}

    dht_vec = np.array([float(dht.loc[t]) if t in dht.index else 0.0 for t in times], dtype=float)
    dhd_vec = np.array([float(dhd.loc[t]) if t in dhd.index else 0.0 for t in times], dtype=float)
    labels = [lab for _, _, lab in cfg["windows"]]
    label_for_time = np.array([interval_label(float(t), cfg["windows"]) for t in times], dtype=object)
    label_index = np.array([labels.index(x) for x in label_for_time], dtype=int)
    ht_prev = np.zeros((times.size, len(labels)), dtype=float)
    hd_prev = np.zeros((times.size, len(labels)), dtype=float)
    running_t = np.zeros(len(labels), dtype=float)
    running_d = np.zeros(len(labels), dtype=float)
    for j, li in enumerate(label_index):
        ht_prev[j, :] = running_t
        hd_prev[j, :] = running_d
        running_t[li] += dht_vec[j]
        running_d[li] += dhd_vec[j]

    out = {}
    for group in GROUP_ORDER:
        et_by_label = np.column_stack([np.exp(lp_for_group(target_model, raw, group, lab)) for lab in labels])
        ed_by_label = np.column_stack([np.exp(lp_for_group(death_model, raw, group, lab)) for lab in labels])
        cif = np.zeros(raw.shape[0], dtype=float)
        chunk = 384
        for start in range(0, raw.shape[0], chunk):
            stop = min(start + chunk, raw.shape[0])
            et_chunk = et_by_label[start:stop, :]
            ed_chunk = ed_by_label[start:stop, :]
            cumhaz = et_chunk @ ht_prev.T + ed_chunk @ hd_prev.T
            et_current = et_chunk[:, label_index]
            increment = np.exp(-cumhaz) * et_current * dht_vec
            cif[start:stop] = increment.sum(axis=1)
        out[group] = cif
    return out


def standardized_cif(target_model, death_model, raw: pd.DataFrame, outcome: str, weights: np.ndarray | None = None) -> dict[str, float]:
    individual = individual_cif_by_group(target_model, death_model, raw, outcome)
    if weights is None:
        weights = np.ones(raw.shape[0])
    weights = np.asarray(weights, dtype=float)
    return {group: float(np.average(values, weights=weights)) for group, values in individual.items()}


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


def fit_standardization_pair(raw: pd.DataFrame, outcome: str, model_name: str, form: str, target_tv: bool, death_tv: bool, design_info=None, weights=None):
    if target_tv:
        _, target, _, _ = fit_tv(raw, outcome, "target", 1, form, model_name, design_info=design_info, weights=weights)
    else:
        target = fit_cox(raw, form, model_name, outcome, "target", 1, design_info=design_info, weights=weights)
    if death_tv:
        _, death, _, _ = fit_tv(raw, outcome, "competing_death", 2, form, model_name, design_info=design_info, weights=weights)
    else:
        death = fit_cox(raw, form, model_name, outcome, "competing_death", 2, design_info=design_info, weights=weights)
    return target, death


def summarize_standardization(point: dict[tuple[str, str], dict[str, float]], boot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risk_rows = []
    add_rows = []
    for (outcome, model), risks in point.items():
        b = boot[(boot["outcome"].eq(outcome)) & (boot["model"].eq(model))]
        for group in GROUP_ORDER:
            vals = b[f"risk_{group}"].dropna()
            ref = risks[REFERENCE_GROUP]
            rd_vals = b[f"risk_{group}"] - b[f"risk_{REFERENCE_GROUP}"]
            rr_vals = b[f"risk_{group}"] / b[f"risk_{REFERENCE_GROUP}"]
            risk_rows.append(
                {
                    "outcome": outcome,
                    "model": model,
                    "group": group,
                    "label": GROUP_LABELS[group],
                    "standardized_cif": risks[group],
                    "ci95_lower": vals.quantile(0.025),
                    "ci95_upper": vals.quantile(0.975),
                    "risk_difference_vs_group1": risks[group] - ref,
                    "risk_difference_ci95_lower": rd_vals.quantile(0.025),
                    "risk_difference_ci95_upper": rd_vals.quantile(0.975),
                    "risk_ratio_vs_group1": risks[group] / ref,
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
                    "outcome": outcome,
                    "model": model,
                    "metric": metric,
                    "estimate": value,
                    "ci95_lower": vals.quantile(0.025),
                    "ci95_upper": vals.quantile(0.975),
                    "bootstrap_successful_iterations": int(vals.shape[0]),
                }
            )
    return pd.DataFrame(risk_rows), pd.DataFrame(add_rows)


def plot_standardized(std: pd.DataFrame, outcome: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(GROUP_ORDER))
    width = 0.34
    for i, model in enumerate(["Model 1", "Model 2"]):
        sub = std[(std["outcome"].eq(outcome)) & (std["model"].eq(model))].set_index("group").loc[GROUP_ORDER]
        y = sub["standardized_cif"].to_numpy()
        lower = np.maximum(y - sub["ci95_lower"].to_numpy(), 0)
        upper = np.maximum(sub["ci95_upper"].to_numpy() - y, 0)
        ax.bar(x + (i - 0.5) * width, y, width, yerr=np.vstack([lower, upper]), capsize=3, label=model)
    ax.set_xticks(x)
    ax.set_xticklabels(["G1", "G2", "G3", "G4"])
    ax.set_ylabel("Standardized cumulative incidence")
    ax.set_title(OUTCOMES[outcome]["label"])
    ax.grid(axis="y", alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def bootstrap_standardized(raw: pd.DataFrame, individual_cifs: dict[tuple[str, str], dict[str, np.ndarray]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    analysis_warnings.append(
        "Standardized CIF bootstrap used patient-level resampling of fixed fitted cause-specific models; "
        "target and competing-death models were not refit inside each bootstrap iteration because time-varying Cox refitting was computationally infeasible in this runtime."
    )
    rng = np.random.default_rng(SEED)
    n = raw.shape[0]
    rows = []
    start_time = time.time()
    for b in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        counts = np.bincount(idx, minlength=n)
        weights = counts.astype(float)
        for (outcome, model), group_values in individual_cifs.items():
            risks = {group: float(np.average(values, weights=weights)) for group, values in group_values.items()}
            row = {"bootstrap_iteration": b + 1, "outcome": outcome, "model": model, "status": "success_fixed_model_resampling"}
            row.update({f"risk_{g}": v for g, v in risks.items()})
            row.update(risk_contrasts(risks))
            rows.append(row)
        if (b + 1) % 25 == 0:
            print(f"CIF bootstrap {b + 1}/{BOOTSTRAP_N} completed in {time.time() - start_time:.1f}s", flush=True)
    boot_df = pd.DataFrame(rows)
    success = boot_df.groupby(["outcome", "model"]).size().reset_index(name="successful_iterations") if not boot_df.empty else pd.DataFrame()
    if not success.empty:
        success["planned_iterations"] = BOOTSTRAP_N
        success["failed_iterations"] = success["planned_iterations"] - success["successful_iterations"]
        success["status"] = "success_fixed_model_resampling"
        success["model_refit_each_iteration"] = False
    return boot_df, success


def fine_gray_status() -> None:
    candidates = []
    found = shutil.which("Rscript")
    if found:
        candidates.append(found)
    candidates.extend(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"))
    candidates.extend(glob.glob(r"C:\Program Files\R\R-*\bin\x64\Rscript.exe"))
    candidates = sorted(set(candidates))
    lines = ["# Fine-Gray Implementation Status", ""]
    if not candidates:
        lines += [
            "- Status: not run.",
            "- Reason: `Rscript` was not found in PATH or standard Program Files R locations.",
            "- No unverified Python Fine-Gray implementation was used.",
            "- Cause-specific Cox and standardized CIF remain the formal primary results for this batch.",
        ]
        for outcome, cfg in OUTCOMES.items():
            write_csv(pd.DataFrame([{"outcome": outcome, "status": "not_run", "reason": "Rscript not available"}]), OUTPUT_DIR / cfg["fg_file"])
    else:
        rscript = candidates[0]
        status_rows = []
        for pkg in ["cmprsk", "riskRegression"]:
            code = f"quit(status = ifelse(requireNamespace('{pkg}', quietly=TRUE), 0, 1))"
            res = subprocess.run([rscript, "-e", code], capture_output=True, text=True)
            status_rows.append({"package": pkg, "available": res.returncode == 0})
        if any(r["available"] for r in status_rows):
            lines += [
                "- Status: Rscript and a Fine-Gray package were found, but this Python execution path did not run the R Fine-Gray model.",
                "- Reason: no validated R wrapper was pre-specified in this batch script.",
                "- Cause-specific Cox and standardized CIF remain the formal primary results; Fine-Gray is pending an R implementation wrapper.",
            ]
            reason = "R package available but wrapper not implemented in this batch"
        else:
            lines += [
                f"- Status: not run.",
                f"- Rscript found: `{rscript}`.",
                "- Reason: neither `cmprsk` nor `riskRegression` was available.",
                "- No unverified Python Fine-Gray implementation was used.",
            ]
            reason = "cmprsk/riskRegression unavailable"
        for outcome, cfg in OUTCOMES.items():
            write_csv(pd.DataFrame([{"outcome": outcome, "status": "not_run", "reason": reason}]), OUTPUT_DIR / cfg["fg_file"])
        lines += ["", "## R Package Check", "", pd.DataFrame(status_rows).to_markdown(index=False)]
    (OUTPUT_DIR / "fine_gray_implementation_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def multiplicative(raw: pd.DataFrame, forms: dict[str, str], outcome: str) -> pd.DataFrame:
    rows = []
    for model in ["Model 1", "Model 2"]:
        full = fit_cox_no_silent_ridge(raw, forms[f"Interaction {model}"], f"Interaction {model}", outcome, "target", 1)
        reduced = fit_cox_no_silent_ridge(raw, forms[f"Interaction {model} reduced"], f"Interaction {model} reduced", outcome, "target", 1)
        lr = 2.0 * (full.fitter.log_likelihood_ - reduced.fitter.log_likelihood_)
        p_lrt = chi2.sf(lr, 1)
        s = full.fitter.summary.reset_index().rename(columns={"covariate": "term"})
        term = "psych_primary_documented_by_index:delirium_binary"
        r = s[s["term"].eq(term)].iloc[0]
        rows.append(
            {
                "outcome": outcome,
                "model": model,
                "term": term,
                "HR": r["exp(coef)"],
                "CI95_lower": r["exp(coef) lower 95%"],
                "CI95_upper": r["exp(coef) upper 95%"],
                "wald_p_value": r["p"],
                "interaction_lrt_chisq": lr,
                "interaction_lrt_df": 1,
                "interaction_lrt_p_value": p_lrt,
                "analysis_n": int(full.fit_df.shape[0]),
                "event_n": int(full.fit_df["event"].sum()),
                "penalizer": full.penalizer,
            }
        )
    return pd.DataFrame(rows)


def time_specific_interaction(raw: pd.DataFrame, forms: dict[str, str], outcome: str) -> pd.DataFrame:
    cfg = OUTCOMES[outcome]
    rows = []
    for start, stop, label in cfg["windows"]:
        sub = raw[raw[cfg["time_col"]] > start].copy()
        sub["_window_time"] = np.minimum(sub[cfg["time_col"]], stop) - start
        sub["_window_event"] = np.where((sub[cfg["status_col"]] == 1) & (sub[cfg["time_col"]] <= stop) & (sub[cfg["time_col"]] > start), 1, 0)
        sub = sub[sub["_window_time"] > 0].copy()
        saved_time = cfg["time_col"]
        saved_status = cfg["status_col"]
        sub[saved_time] = sub["_window_time"]
        sub[saved_status] = np.where(sub["_window_event"] == 1, 1, 0)
        fit = fit_cox_no_silent_ridge(sub, forms["Interaction Model 2"], f"Time-specific Interaction Model 2 {label}", outcome, "target", 1)
        s = fit.fitter.summary.reset_index().rename(columns={"covariate": "term"})
        term = "psych_primary_documented_by_index:delirium_binary"
        r = s[s["term"].eq(term)].iloc[0]
        rows.append(
            {
                "outcome": outcome,
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


def report(
    cohort: pd.DataFrame,
    status_rows: dict[str, pd.DataFrame],
    target_rows: pd.DataFrame,
    tv_effects: pd.DataFrame,
    lrt: pd.DataFrame,
    std: pd.DataFrame,
    additive: pd.DataFrame,
    mult: pd.DataFrame,
    time_mult: pd.DataFrame,
    boot_diag: pd.DataFrame,
) -> None:
    def md(df: pd.DataFrame, n=30) -> str:
        return "_No rows._" if df.empty else df.head(n).to_markdown(index=False)

    lines = [
        "# Readmission Outcomes Model Report",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Run timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Random seed: `{SEED}`",
        f"- Bootstrap iterations requested: `{BOOTSTRAP_N}`",
        "- Analysis population: primary analysis cohort restricted to conservative readmission follow-up cohort.",
        "- Terminology: outcomes are same-system readmission and same-system ICU readmission, not all readmissions across all health systems.",
        "",
        "## Cohort Accounting",
        "",
        md(cohort),
        "",
        "## Three-State Counts",
        "",
    ]
    for outcome in OUTCOMES:
        lines += [f"### {OUTCOMES[outcome]['label']}", "", md(status_rows[outcome]), ""]
    lines += [
        "## Cause-Specific Cox Target Event Models",
        "",
        md(target_rows),
        "",
        "## Non-PH Time-Varying Effects",
        "",
        md(tv_effects),
        "",
        "## Formal Non-PH LRT",
        "",
        md(lrt),
        "",
        "## Standardized CIF",
        "",
        md(std),
        "",
        "## Additive Interaction",
        "",
        md(additive),
        "",
        "## Multiplicative Interaction",
        "",
        md(mult),
        "",
        "## Time-Specific Multiplicative Interaction",
        "",
        md(time_mult),
        "",
        "## Bootstrap Diagnostics",
        "",
        md(boot_diag),
        "",
        "## Fine-Gray",
        "",
        "- Fine-Gray status is recorded in `fine_gray_implementation_status.md`.",
        "",
        "## Warnings And Deviations",
        "",
    ]
    if analysis_warnings:
        lines.extend([f"- {w}" for w in sorted(set(analysis_warnings))])
    else:
        lines.append("- No warnings were recorded.")
    (OUTPUT_DIR / "readmission_outcomes_model_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def session_files() -> None:
    pkgs = ["duckdb", "pandas", "numpy", "lifelines", "matplotlib", "patsy", "scipy", "statsmodels"]
    rows = []
    for p in pkgs:
        mod = __import__(p)
        rows.append({"package": p, "version": getattr(mod, "__version__", "unknown")})
    write_csv(pd.DataFrame(rows), OUTPUT_DIR / "package_versions.csv")
    lines = [
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Executable: {sys.executable}",
        "",
        pd.DataFrame(rows).to_string(index=False),
    ]
    (OUTPUT_DIR / "sessionInfo.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def manifest() -> None:
    files = sorted([p for p in OUTPUT_DIR.iterdir() if p.is_file() and p.name != "readmission_outcomes_run_manifest.md"], key=lambda p: p.name.lower())
    files.append(SCRIPT_PATH)
    lines = [
        "# Readmission Outcomes Run Manifest",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Random seed: `{SEED}`",
        f"- Bootstrap iterations requested: `{BOOTSTRAP_N}`",
        "",
        "| File | SHA256 |",
        "|---|---|",
    ]
    seen = set()
    for p in files:
        if p.exists() and str(p) not in seen:
            seen.add(str(p))
            lines.append(f"| `{p}` | `{sha256_path(p)}` |")
    (OUTPUT_DIR / "readmission_outcomes_run_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    np.random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading conservative readmission cohort...", flush=True)
    raw = load_data()
    forms = formulas()

    cohort = pd.DataFrame([{"metric": "analysis_population_n", "n": int(raw.shape[0]), "expected_n": 24033, "pass": raw.shape[0] == 24033}])
    write_csv(cohort, OUTPUT_DIR / "readmission_model_cohort_accounting.csv")

    status_by_outcome = {}
    aj_by_outcome = {}
    for outcome, cfg in OUTCOMES.items():
        status = crude_status_by_group(raw, outcome)
        total = raw[cfg["status_col"]].value_counts().to_dict()
        for s, expected in cfg["expected"].items():
            actual = int(total.get(s, 0))
            if actual != expected:
                analysis_warnings.append(f"{outcome} status {s} actual {actual} differs from expected {expected}.")
        status_by_outcome[outcome] = status
        write_csv(status, OUTPUT_DIR / cfg["crude_file"])
        cif = aalen_johansen(raw, outcome)
        aj_by_outcome[outcome] = cif
        write_csv(cif, OUTPUT_DIR / cfg["aj_file"])
        plot_aj(cif, outcome)

    print("Fitting cause-specific Cox models...", flush=True)
    target_models = []
    death_models = []
    all_models = []
    for outcome in OUTCOMES:
        for model in ["Model 0", "Model 1", "Model 2"]:
            tm = fit_cox_no_silent_ridge(raw, forms[model], model, outcome, "target", 1)
            dm = fit_cox_no_silent_ridge(raw, forms[model], model, outcome, "competing_death", 2)
            target_models.append(tm)
            death_models.append(dm)
            all_models.extend([tm, dm])
    target_df = pd.concat([joint_rows(m) for m in target_models], ignore_index=True)
    death_df = pd.concat([joint_rows(m) for m in death_models], ignore_index=True)
    write_csv(target_df[target_df["outcome"].eq("readmission_90d")], OUTPUT_DIR / OUTCOMES["readmission_90d"]["target_file"])
    write_csv(target_df[target_df["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / OUTCOMES["icu_readmission_365d"]["target_file"])
    write_csv(death_df, OUTPUT_DIR / "competing_death_cause_specific_cox.csv")
    fit_stats = pd.DataFrame(
        [
            {
                "outcome": m.outcome,
                "cause": m.cause,
                "model": m.model_name,
                "analysis_n": int(m.fit_df.shape[0]),
                "event_n": int(m.fit_df["event"].sum()),
                "covariate_columns_n": len(m.fitter.params_),
                "log_likelihood": m.fitter.log_likelihood_,
                "AIC_partial": m.fitter.AIC_partial_,
                "concordance": m.fitter.concordance_index_,
                "penalizer": m.penalizer,
                "converged_without_ridge": m.converged_without_ridge,
                "fit_error_if_any": m.error,
            }
            for m in all_models
        ]
    )
    write_csv(fit_stats, OUTPUT_DIR / "readmission_cox_model_fit_statistics.csv")
    write_csv(pd.concat([coefficient_rows(m) for m in all_models], ignore_index=True), OUTPUT_DIR / "readmission_cox_full_coefficients.csv")

    rank_qc, cond_qc = design_qc(raw, forms, all_models)
    write_csv(rank_qc, OUTPUT_DIR / "readmission_design_matrix_rank_qc.csv")
    write_csv(cond_qc, OUTPUT_DIR / "readmission_design_matrix_condition_number.csv")

    print("Checking PH and fitting time-varying models...", flush=True)
    ph = pd.concat([ph_tests(m) for m in target_models if m.model_name == "Model 2"], ignore_index=True)
    write_csv(ph, OUTPUT_DIR / "readmission_ph_assumption_tests.csv")
    lrt_rows = []
    tv_effect_rows_all = []
    tv_models: dict[tuple[str, str, str], TVModel] = {}
    use_tv: dict[tuple[str, str], bool] = {}
    for outcome in OUTCOMES:
        for cause, status in [("target", 1), ("competing_death", 2)]:
            _, full_tv, effects, lrt = fit_tv(raw, outcome, cause, status, forms["Model 2"], "Model 2")
            lrt_rows.append(lrt)
            tv_effect_rows_all.append(effects)
            tv_models[(outcome, cause, "Model 2")] = full_tv
            use_tv[(outcome, cause)] = bool(lrt["p_value"].iloc[0] < 0.05)
    tv_effects = pd.concat(tv_effect_rows_all, ignore_index=True)
    lrt = pd.concat(lrt_rows, ignore_index=True)
    write_csv(tv_effects[tv_effects["outcome"].eq("readmission_90d")], OUTPUT_DIR / "readmission_90d_time_varying_effects.csv")
    write_csv(tv_effects[tv_effects["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / "icu_readmission_365d_time_varying_effects.csv")
    write_csv(lrt, OUTPUT_DIR / "readmission_nonph_lrt.csv")

    print("Running standardized CIF and bootstrap...", flush=True)
    design_infos = {}
    point = {}
    individual_cifs = {}
    standardization_models = {}
    for model in ["Model 1", "Model 2"]:
        _, di = design_matrix(raw, forms[model], drop_intercept=True)
        design_infos[model] = di
    for outcome in OUTCOMES:
        for model in ["Model 1", "Model 2"]:
            target, death = fit_standardization_pair(
                raw,
                outcome,
                model,
                forms[model],
                use_tv[(outcome, "target")],
                use_tv[(outcome, "competing_death")],
                design_info=design_infos[model],
            )
            standardization_models[(outcome, model, "target")] = target
            standardization_models[(outcome, model, "competing_death")] = death
            individual = individual_cif_by_group(target, death, raw, outcome)
            individual_cifs[(outcome, model)] = individual
            point[(outcome, model)] = {group: float(np.mean(values)) for group, values in individual.items()}
    boot, boot_diag = bootstrap_standardized(raw, individual_cifs)
    std, additive = summarize_standardization(point, boot)
    write_csv(std[std["outcome"].eq("readmission_90d")], OUTPUT_DIR / OUTCOMES["readmission_90d"]["std_file"])
    write_csv(std[std["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / OUTCOMES["icu_readmission_365d"]["std_file"])
    write_csv(boot_diag, OUTPUT_DIR / "readmission_cif_bootstrap_diagnostics.csv")
    write_csv(additive[additive["outcome"].eq("readmission_90d")], OUTPUT_DIR / OUTCOMES["readmission_90d"]["add_file"])
    write_csv(additive[additive["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / OUTCOMES["icu_readmission_365d"]["add_file"])
    plot_standardized(std, "readmission_90d", OUTPUT_DIR / "figure_standardized_90d_readmission_cif.pdf")
    plot_standardized(std, "icu_readmission_365d", OUTPUT_DIR / "figure_standardized_365d_icu_readmission_cif.pdf")

    print("Checking Fine-Gray and interactions...", flush=True)
    fine_gray_status()
    mult_read = multiplicative(raw, forms, "readmission_90d")
    mult_icu = multiplicative(raw, forms, "icu_readmission_365d")
    time_mult = pd.concat([time_specific_interaction(raw, forms, outcome) for outcome in OUTCOMES], ignore_index=True)
    write_csv(mult_read, OUTPUT_DIR / "multiplicative_interaction_readmission.csv")
    write_csv(mult_icu, OUTPUT_DIR / "multiplicative_interaction_icu_readmission.csv")
    write_csv(time_mult, OUTPUT_DIR / "time_specific_interaction_readmission.csv")

    with (OUTPUT_DIR / "readmission_cause_specific_cox_models.pkl").open("wb") as f:
        pickle.dump(
            {
                "target": {(m.outcome, m.cause, m.model_name): m.fitter for m in target_models},
                "death": {(m.outcome, m.cause, m.model_name): m.fitter for m in death_models},
                "forms": forms,
            },
            f,
        )
    with (OUTPUT_DIR / "readmission_time_varying_cox_models.pkl").open("wb") as f:
        pickle.dump({key: value.fitter for key, value in tv_models.items()}, f)
    with (OUTPUT_DIR / "readmission_standardization_models.pkl").open("wb") as f:
        pickle.dump({key: value.fitter for key, value in standardization_models.items()}, f)

    session_files()
    report(cohort, status_by_outcome, target_df, tv_effects, lrt, std, additive, pd.concat([mult_read, mult_icu], ignore_index=True), time_mult, boot_diag)
    manifest()

    print("DONE", flush=True)
    print(f"output_dir={OUTPUT_DIR}", flush=True)
    print(f"report={OUTPUT_DIR / 'readmission_outcomes_model_report.md'}", flush=True)
    print(f"report_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_model_report.md')}", flush=True)
    print(f"manifest={OUTPUT_DIR / 'readmission_outcomes_run_manifest.md'}", flush=True)
    print(f"manifest_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_run_manifest.md')}", flush=True)


if __name__ == "__main__":
    main()
