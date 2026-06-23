from __future__ import annotations

import hashlib
import json
import math
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
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.exceptions import ConvergenceWarning, StatisticalWarning
from lifelines.statistics import multivariate_logrank_test, proportional_hazard_test
from matplotlib.backends.backend_pdf import PdfPages
from patsy import build_design_matrices, dmatrix
from scipy.stats import chi2


SEED = 20260621
BOOTSTRAP_N = int(os.environ.get("PRIMARY_MORTALITY_BOOTSTRAP_N", "1000"))
COX_NUMERICAL_PENALIZER = 1e-9

PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", PROJECT.parent / "data" / "mimiciv.duckdb"))
OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "01_primary_mortality"
SCRIPT_DIR = PROJECT / "scripts" / "analysis"
PY_SCRIPT = SCRIPT_DIR / "run_primary_mortality_v1.py"
R_WRAPPER = SCRIPT_DIR / "run_primary_mortality_v1.R"
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
    "invasive_ventilation_0_24h",
    "vasopressor_any_0_24h",
    "rrt_any_0_24h",
    "sepsis3_index",
    "death_365d_main",
]
TABLE1_CONTINUOUS = [
    "age_at_index_admission",
    "prior_mimic_hospitalizations",
    "charlson_comorbidity_only_documented_by_index",
    "nonneurologic_sofa_zero_imputed",
]
TABLE1_CATEGORICAL = [
    "sex_recorded",
    "race_group",
    "anchor_year_group",
    "admission_type_group",
    "admission_location_group",
    "first_careunit_group",
    "nonneurologic_sofa_observed_components_n",
    "dementia_documented_by_index",
    "substance_use_documented_by_index",
    "chronic_neurologic_disease",
    "invasive_ventilation_0_24h",
    "vasopressor_any_0_24h",
    "rrt_any_0_24h",
    "sepsis3_index",
    "death_365d_main",
]


@dataclass
class FittedModel:
    name: str
    cph: CoxPHFitter
    design_info: object
    formula: str
    fit_df: pd.DataFrame
    raw_df: pd.DataFrame
    exposure_columns: list[str]


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
    if d in (0, None) or pd.isna(d):
        return np.nan
    return round(100.0 * float(n) / float(d), 3)


def fmt_n_pct(n: int, d: int) -> str:
    return f"{int(n)} ({pct(n, d):.1f}%)"


def fmt_median_iqr(x: pd.Series) -> str:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) == 0:
        return "NA"
    return f"{np.median(x):.1f} [{np.percentile(x, 25):.1f}, {np.percentile(x, 75):.1f}]"


def fmt_mean_sd(x: pd.Series) -> str:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) == 0:
        return "NA"
    return f"{np.mean(x):.1f} +/- {np.std(x, ddof=1):.1f}"


def make_r_wrapper() -> None:
    R_WRAPPER.parent.mkdir(parents=True, exist_ok=True)
    R_WRAPPER.write_text(
        "\n".join(
            [
                "# Primary mortality analysis v1 wrapper",
                "# The local Codex runtime used for this run did not provide Rscript.",
                "# This wrapper records the requested R entrypoint and delegates to the executed Python implementation.",
                "python <- Sys.which('python')",
                "if (python == '') stop('Python executable not found on PATH. Run run_primary_mortality_v1.py with the Codex bundled Python.')",
                f"script <- '{str(PY_SCRIPT).replace('\\', '/')}'",
                "status <- system2(python, script)",
                "quit(status = status)",
                "",
            ]
        ),
        encoding="utf-8",
    )


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
            nonneurologic_sofa_observed_components_n,
            invasive_ventilation_0_24h,
            vasopressor_any_0_24h,
            rrt_any_0_24h,
            sepsis3_index
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
        "death_365d_include_same_day",
        "death_same_day_discharge",
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


def cohort_accounting(table1_df: pd.DataFrame, model_df: pd.DataFrame) -> pd.DataFrame:
    same_day = int(
        table1_df.loc[
            table1_df["death_same_day_discharge"].eq(1)
            & table1_df["death_date_logic_abnormal_flag"].eq("none")
        ].shape[0]
    )
    abnormal = int(table1_df.loc[~table1_df["death_date_logic_abnormal_flag"].eq("none")].shape[0])
    rows = [
        {"metric": "table1_population_n", "n": len(table1_df)},
        {"metric": "primary_mortality_model_n", "n": len(model_df)},
        {"metric": "excluded_same_day_dod_n", "n": same_day},
        {"metric": "excluded_death_date_logic_abnormal_n", "n": abnormal},
        {"metric": "primary_mortality_model_1y_death_events_n", "n": int(model_df["event_main"].sum())},
    ]
    return pd.DataFrame(rows)


def missingness(df: pd.DataFrame) -> pd.DataFrame:
    variables = list(dict.fromkeys(MODEL2_RAW_VARIABLES + ["delirium_binary"]))
    rows = []
    for col in variables:
        miss = int(df[col].isna().sum())
        rows.append(
            {
                "variable": col,
                "missing_n": miss,
                "denominator": len(df),
                "missing_percent": pct(miss, len(df)),
                "unknown_retained_as_category": col in CATEGORICAL_VARIABLES,
            }
        )
    out = pd.DataFrame(rows)
    return out


def age_knots(df: pd.DataFrame) -> dict[str, float]:
    quantiles = [0.05, 0.35, 0.65, 0.95]
    values = np.quantile(df["age_at_index_admission"], quantiles)
    return {f"p{int(q * 100)}": float(v) for q, v in zip(quantiles, values)}


def model_formulas(knots: dict[str, float]) -> dict[str, str]:
    joint = f"C(joint_exposure_4level, Treatment(reference='{REFERENCE_GROUP}'))"
    age = (
        "cr(age_at_index_admission, "
        f"knots=({knots['p35']}, {knots['p65']}), "
        f"lower_bound={knots['p5']}, upper_bound={knots['p95']})"
    )
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
    return {
        "Model 0": joint,
        "Model 1": " + ".join(common),
        "Model 2": " + ".join(
            common
            + [
                "nonneurologic_sofa_zero_imputed",
                "C(nonneurologic_sofa_observed_components_n)",
            ]
        ),
        "Interaction Model 1": " + ".join(
            [
                "psych_primary_documented_by_index",
                "delirium_binary",
                "psych_primary_documented_by_index:delirium_binary",
            ]
            + common[1:]
        ),
        "Interaction Model 1 reduced": " + ".join(
            [
                "psych_primary_documented_by_index",
                "delirium_binary",
            ]
            + common[1:]
        ),
        "Interaction Model 2": " + ".join(
            [
                "psych_primary_documented_by_index",
                "delirium_binary",
                "psych_primary_documented_by_index:delirium_binary",
            ]
            + common[1:]
            + [
                "nonneurologic_sofa_zero_imputed",
                "C(nonneurologic_sofa_observed_components_n)",
            ]
        ),
        "Interaction Model 2 reduced": " + ".join(
            [
                "psych_primary_documented_by_index",
                "delirium_binary",
            ]
            + common[1:]
            + [
                "nonneurologic_sofa_zero_imputed",
                "C(nonneurologic_sofa_observed_components_n)",
            ]
        ),
    }


def design_matrix(raw_df: pd.DataFrame, formula: str, design_info=None) -> tuple[pd.DataFrame, object]:
    if design_info is None:
        X = dmatrix(formula, raw_df, return_type="dataframe")
        design_info = X.design_info
    else:
        X = build_design_matrices([design_info], raw_df, return_type="dataframe")[0]
    X = pd.DataFrame(X, index=raw_df.index)
    if "Intercept" in X.columns:
        X = X.drop(columns=["Intercept"])
    return X.astype(float), design_info


def fit_cox(
    raw_df: pd.DataFrame,
    formula: str,
    name: str,
    duration_col: str = "time_main",
    event_col: str = "event_main",
    weights_col: str | None = None,
    design_info=None,
) -> FittedModel:
    X, design_info = design_matrix(raw_df, formula, design_info)
    cols = [duration_col, event_col]
    if weights_col:
        cols.append(weights_col)
    fit_df = pd.concat([raw_df[cols], X], axis=1)
    fit_df = fit_df.rename(columns={duration_col: "time", event_col: "event"})
    cph = CoxPHFitter(penalizer=COX_NUMERICAL_PENALIZER)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        warnings.simplefilter("always", StatisticalWarning)
        cph.fit(
            fit_df,
            duration_col="time",
            event_col="event",
            weights_col=weights_col,
            show_progress=False,
            robust=False,
        )
    if "bootstrap" not in name.lower():
        fit_warnings.extend([f"{name}: {str(w.message)}" for w in caught])
    exposure_columns = [c for c in X.columns if "joint_exposure_4level" in c]
    return FittedModel(name, cph, design_info, formula, fit_df, raw_df.copy(), exposure_columns)


def extract_group_from_column(col: str) -> str:
    for group in GROUP_ORDER[1:]:
        if group in col:
            return group
    return col


def cox_joint_rows(model: FittedModel) -> pd.DataFrame:
    summary = model.cph.summary.reset_index().rename(columns={"covariate": "term"})
    rows = []
    for col in model.exposure_columns:
        row = summary.loc[summary["term"].eq(col)]
        if row.empty:
            continue
        row = row.iloc[0]
        rows.append(
            {
                "model": model.name,
                "contrast": f"{extract_group_from_column(col)} vs {REFERENCE_GROUP}",
                "term": col,
                "HR": row["exp(coef)"],
                "CI95_lower": row["exp(coef) lower 95%"],
                "CI95_upper": row["exp(coef) upper 95%"],
                "p_value": row["p"],
                "analysis_n": int(model.fit_df.shape[0]),
                "event_n": int(model.fit_df["event"].sum()),
                "AIC_partial": model.cph.AIC_partial_,
                "concordance": model.cph.concordance_index_,
                "numerical_penalizer": COX_NUMERICAL_PENALIZER,
            }
        )
    return pd.DataFrame(rows)


def cox_fit_stats(models: list[FittedModel]) -> pd.DataFrame:
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
            }
        )
    return pd.DataFrame(rows)


def ph_tests(models: list[FittedModel]) -> pd.DataFrame:
    rows = []
    for m in models:
        try:
            result = proportional_hazard_test(m.cph, m.fit_df, time_transform="rank")
            s = result.summary.reset_index().rename(columns={"index": "term"})
            for _, r in s.iterrows():
                rows.append(
                    {
                        "model": m.name,
                        "test_scope": "individual_term",
                        "term": r["term"],
                        "test_statistic": r["test_statistic"],
                        "df": 1,
                        "p_value": r["p"],
                    }
                )
            exp_s = s[s["term"].isin(m.exposure_columns)]
            if not exp_s.empty:
                stat = float(exp_s["test_statistic"].sum())
                df = int(exp_s.shape[0])
                rows.append(
                    {
                        "model": m.name,
                        "test_scope": "joint_exposure_global",
                        "term": "joint_exposure_4level",
                        "test_statistic": stat,
                        "df": df,
                        "p_value": chi2.sf(stat, df),
                    }
                )
        except Exception as exc:
            analysis_warnings.append(f"PH test failed for {m.name}: {exc}")
            rows.append(
                {
                    "model": m.name,
                    "test_scope": "model",
                    "term": "PH test failed",
                    "test_statistic": np.nan,
                    "df": np.nan,
                    "p_value": np.nan,
                }
            )
    return pd.DataFrame(rows)


def plot_schoenfeld(models: list[FittedModel], path: Path) -> None:
    with PdfPages(path) as pdf:
        for m in models:
            try:
                resid = m.cph.compute_residuals(m.fit_df, kind="scaled_schoenfeld")
                if resid.empty:
                    continue
                for col in m.exposure_columns:
                    if col not in resid.columns:
                        continue
                    event_times = m.fit_df.loc[resid.index, "time"]
                    fig, ax = plt.subplots(figsize=(8, 4.8))
                    ax.scatter(event_times, resid[col], s=8, alpha=0.25)
                    ax.axhline(0, color="black", linewidth=0.8)
                    ax.set_title(f"{m.name}: scaled Schoenfeld residuals\n{extract_group_from_column(col)}")
                    ax.set_xlabel("Days since index hospital discharge")
                    ax.set_ylabel("Scaled Schoenfeld residual")
                    pdf.savefig(fig, bbox_inches="tight")
                    plt.close(fig)
            except Exception as exc:
                analysis_warnings.append(f"Schoenfeld plot failed for {m.name}: {exc}")


def build_table1(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for var in TABLE1_CONTINUOUS:
        row = {"variable": var, "level": "median [IQR]", "statistic": "median_iqr"}
        for g in GROUP_ORDER:
            sub = df[df["joint_exposure_4level"].eq(g)]
            row[g] = fmt_median_iqr(sub[var])
        rows.append(row)
        row2 = {"variable": var, "level": "mean +/- SD", "statistic": "mean_sd"}
        for g in GROUP_ORDER:
            sub = df[df["joint_exposure_4level"].eq(g)]
            row2[g] = fmt_mean_sd(sub[var])
        rows.append(row2)
    for var in TABLE1_CATEGORICAL:
        levels = sorted([x for x in df[var].dropna().astype(str).unique()])
        for level in levels:
            row = {"variable": var, "level": level, "statistic": "n_percent"}
            for g in GROUP_ORDER:
                sub = df[df["joint_exposure_4level"].eq(g)]
                n = int(sub[var].astype(str).eq(level).sum())
                row[g] = fmt_n_pct(n, len(sub))
            rows.append(row)
    table1 = pd.DataFrame(rows)

    smd_rows = []
    ref = df[df["joint_exposure_4level"].eq(REFERENCE_GROUP)]
    for var in TABLE1_CONTINUOUS:
        ref_x = pd.to_numeric(ref[var], errors="coerce").dropna()
        for g in GROUP_ORDER[1:]:
            gx = pd.to_numeric(df.loc[df["joint_exposure_4level"].eq(g), var], errors="coerce").dropna()
            pooled = math.sqrt((ref_x.var(ddof=1) + gx.var(ddof=1)) / 2.0)
            smd = (gx.mean() - ref_x.mean()) / pooled if pooled and not np.isnan(pooled) else np.nan
            smd_rows.append({"variable": var, "level": "continuous", "comparison_group": g, "smd_vs_reference": smd})
    for var in TABLE1_CATEGORICAL:
        levels = sorted([x for x in df[var].dropna().astype(str).unique()])
        for level in levels:
            p_ref = ref[var].astype(str).eq(level).mean()
            for g in GROUP_ORDER[1:]:
                sub = df[df["joint_exposure_4level"].eq(g)]
                p_g = sub[var].astype(str).eq(level).mean()
                pooled = math.sqrt((p_ref * (1 - p_ref) + p_g * (1 - p_g)) / 2.0)
                smd = (p_g - p_ref) / pooled if pooled else np.nan
                smd_rows.append({"variable": var, "level": level, "comparison_group": g, "smd_vs_reference": smd})
    smd = pd.DataFrame(smd_rows)
    if not smd.empty:
        smd["abs_smd_vs_reference"] = smd["smd_vs_reference"].abs()
    return table1, smd


def write_table1_html(table1: pd.DataFrame, path: Path) -> None:
    html = [
        "<html><head><meta charset='utf-8'><title>Table 1</title>",
        "<style>body{font-family:Arial,sans-serif} table{border-collapse:collapse;font-size:12px} th,td{border:1px solid #ddd;padding:4px 6px} th{background:#f1f3f5}</style>",
        "</head><body>",
        "<h1>Table 1: Four Joint Exposure Groups</h1>",
        "<p>No p values are shown. Existing Unknown categories are retained.</p>",
        table1.to_html(index=False, escape=False),
        "</body></html>",
    ]
    path.write_text("\n".join(html), encoding="utf-8")


def crude_survival(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    risk_rows = []
    logrank = multivariate_logrank_test(df["time_main"], df["joint_exposure_4level"], df["event_main"])
    for g in GROUP_ORDER:
        sub = df[df["joint_exposure_4level"].eq(g)]
        km = KaplanMeierFitter()
        km.fit(sub["time_main"], event_observed=sub["event_main"], label=g)
        person_years = sub["time_main"].sum() / 365.25
        events = int(sub["event_main"].sum())
        rows.append(
            {
                "group": g,
                "label": GROUP_LABELS[g],
                "n": len(sub),
                "death_365d_events": events,
                "person_years": person_years,
                "death_rate_per_100_person_years": 100.0 * events / person_years if person_years else np.nan,
                "km_365d_mortality_risk": 1.0 - float(km.predict(365.0)),
                "logrank_p_value_descriptive": logrank.p_value,
            }
        )
        for t in [0, 30, 90, 180, 365]:
            risk_rows.append(
                {
                    "group": g,
                    "time_day": t,
                    "at_risk_n": int((sub["time_main"] >= t).sum()),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(risk_rows)


def plot_km(df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5.2))
    for g in GROUP_ORDER:
        sub = df[df["joint_exposure_4level"].eq(g)]
        km = KaplanMeierFitter()
        km.fit(sub["time_main"], event_observed=sub["event_main"], label=GROUP_LABELS[g])
        km.plot_survival_function(ax=ax, ci_show=False)
    ax.set_xlim(0, 365)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Days since index hospital discharge")
    ax.set_ylabel("Survival probability")
    ax.set_title("Kaplan-Meier curves for one-year all-cause mortality")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(png_path, dpi=220)
    fig.savefig(pdf_path)
    plt.close(fig)


def align_design_for_model(raw_df: pd.DataFrame, model: FittedModel) -> pd.DataFrame:
    X, _ = design_matrix(raw_df, model.formula, model.design_info)
    for col in model.cph.params_.index:
        if col not in X.columns:
            X[col] = 0.0
    X = X[list(model.cph.params_.index)]
    return X.astype(float)


def standardized_risk(model: FittedModel, raw_df: pd.DataFrame, weights: np.ndarray | None = None) -> dict[str, float]:
    out = {}
    if weights is None:
        weights = np.ones(raw_df.shape[0])
    weights = np.asarray(weights, dtype=float)
    for group in GROUP_ORDER:
        cf = raw_df.copy()
        cf["joint_exposure_4level"] = pd.Categorical([group] * len(cf), categories=GROUP_ORDER)
        X = align_design_for_model(cf, model)
        surv = model.cph.predict_survival_function(X, times=[365.0]).T.iloc[:, 0].to_numpy()
        risk = 1.0 - surv
        out[group] = float(np.average(risk, weights=weights))
    return out


def risk_contrasts(risks: dict[str, float]) -> dict[str, float]:
    r00 = risks[GROUP_ORDER[0]]
    r10 = risks[GROUP_ORDER[1]]
    r01 = risks[GROUP_ORDER[2]]
    r11 = risks[GROUP_ORDER[3]]
    rr10 = r10 / r00 if r00 else np.nan
    rr01 = r01 / r00 if r00 else np.nan
    rr11 = r11 / r00 if r00 else np.nan
    reri = rr11 - rr10 - rr01 + 1.0
    ap = reri / rr11 if rr11 else np.nan
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


def bootstrap_standardization(
    raw_df: pd.DataFrame,
    formulas: dict[str, str],
    design_infos: dict[str, object],
    model_names: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    n = len(raw_df)
    point_risks = {}
    boot_rows = []
    diagnostics = []
    start_time = time.time()
    for b in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        counts = np.bincount(idx, minlength=n)
        use = counts > 0
        boot = raw_df.loc[use].copy()
        boot["boot_weight"] = counts[use].astype(float)
        for model_name in model_names:
            try:
                bm = fit_cox(
                    boot,
                    formulas[model_name],
                    f"{model_name} bootstrap",
                    weights_col="boot_weight",
                    design_info=design_infos[model_name],
                )
                risks = standardized_risk(bm, boot, weights=boot["boot_weight"].to_numpy())
                contrasts = risk_contrasts(risks)
                row = {"bootstrap_iteration": b + 1, "model": model_name, "status": "success"}
                row.update({f"risk_{g}": v for g, v in risks.items()})
                row.update(contrasts)
                boot_rows.append(row)
            except Exception as exc:
                diagnostics.append(
                    {
                        "bootstrap_iteration": b + 1,
                        "model": model_name,
                        "status": "failed",
                        "message": str(exc),
                    }
                )
        if (b + 1) % 50 == 0:
            elapsed = time.time() - start_time
            print(f"bootstrap {b + 1}/{BOOTSTRAP_N} completed in {elapsed:.1f}s", flush=True)
    boot = pd.DataFrame(boot_rows)
    diag_success = (
        boot.groupby("model").size().reset_index(name="successful_iterations")
        if not boot.empty
        else pd.DataFrame(columns=["model", "successful_iterations"])
    )
    diag_fail = pd.DataFrame(diagnostics)
    if diag_fail.empty:
        diag_fail = pd.DataFrame(columns=["bootstrap_iteration", "model", "status", "message"])
    return boot, pd.concat([diag_success.assign(status="success"), diag_fail], ignore_index=True, sort=False)


def summarize_standardized(point: dict[str, dict[str, float]], boot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risk_rows = []
    add_rows = []
    for model_name, risks in point.items():
        b = boot[boot["model"].eq(model_name)]
        for g in GROUP_ORDER:
            vals = b[f"risk_{g}"].dropna()
            risk = risks[g]
            ref = risks[REFERENCE_GROUP]
            rd = risk - ref
            rr = risk / ref if ref else np.nan
            rd_vals = b[f"risk_{g}"] - b[f"risk_{REFERENCE_GROUP}"]
            rr_vals = b[f"risk_{g}"] / b[f"risk_{REFERENCE_GROUP}"]
            risk_rows.append(
                {
                    "model": model_name,
                    "group": g,
                    "label": GROUP_LABELS[g],
                    "standardized_365d_mortality_risk": risk,
                    "risk_ci95_lower": vals.quantile(0.025) if len(vals) else np.nan,
                    "risk_ci95_upper": vals.quantile(0.975) if len(vals) else np.nan,
                    "risk_difference_vs_group1": rd,
                    "risk_difference_ci95_lower": rd_vals.quantile(0.025) if len(rd_vals.dropna()) else np.nan,
                    "risk_difference_ci95_upper": rd_vals.quantile(0.975) if len(rd_vals.dropna()) else np.nan,
                    "risk_ratio_vs_group1": rr,
                    "risk_ratio_ci95_lower": rr_vals.quantile(0.025) if len(rr_vals.dropna()) else np.nan,
                    "risk_ratio_ci95_upper": rr_vals.quantile(0.975) if len(rr_vals.dropna()) else np.nan,
                    "bootstrap_successful_iterations": int(len(vals)),
                }
            )
        point_con = risk_contrasts(risks)
        for metric, value in point_con.items():
            vals = b[metric].dropna() if metric in b.columns else pd.Series(dtype=float)
            add_rows.append(
                {
                    "model": model_name,
                    "metric": metric,
                    "estimate": value,
                    "ci95_lower": vals.quantile(0.025) if len(vals) else np.nan,
                    "ci95_upper": vals.quantile(0.975) if len(vals) else np.nan,
                    "bootstrap_successful_iterations": int(len(vals)),
                }
            )
    return pd.DataFrame(risk_rows), pd.DataFrame(add_rows)


def plot_standardized_risk(std: pd.DataFrame, path_pdf: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(GROUP_ORDER))
    width = 0.34
    for i, model in enumerate(["Model 1", "Model 2"]):
        sub = std[std["model"].eq(model)].set_index("group").loc[GROUP_ORDER]
        y = sub["standardized_365d_mortality_risk"].to_numpy()
        lower = np.maximum(y - sub["risk_ci95_lower"].to_numpy(), 0)
        upper = np.maximum(sub["risk_ci95_upper"].to_numpy() - y, 0)
        ax.bar(x + (i - 0.5) * width, y, width, label=model, yerr=np.vstack([lower, upper]), capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(["G1", "G2", "G3", "G4"])
    ax.set_ylabel("Standardized 365-day mortality risk")
    ax.set_title("Model-standardized one-year mortality risk")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path_pdf)
    plt.close(fig)


def plot_additive(additive: pd.DataFrame, path_pdf: Path) -> None:
    metrics = ["interaction_contrast", "RERI", "AP", "synergy_index"]
    sub = additive[additive["metric"].isin(metrics)].copy()
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.5))
    axes = axes.ravel()
    for ax, metric in zip(axes, metrics):
        m = sub[sub["metric"].eq(metric)]
        x = np.arange(len(m))
        y = m["estimate"].to_numpy()
        lower = np.maximum(y - m["ci95_lower"].to_numpy(), 0)
        upper = np.maximum(m["ci95_upper"].to_numpy() - y, 0)
        ax.errorbar(x, y, yerr=np.vstack([lower, upper]), fmt="o", capsize=4)
        ax.axhline(0 if metric != "synergy_index" else 1, color="black", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(m["model"].tolist())
        ax.set_title(metric)
    fig.tight_layout()
    fig.savefig(path_pdf)
    plt.close(fig)


def multiplicative_interaction(raw_df: pd.DataFrame, formulas: dict[str, str]) -> pd.DataFrame:
    rows = []
    for model_name in ["Model 1", "Model 2"]:
        full_name = f"Interaction {model_name}"
        reduced_name = f"Interaction {model_name} reduced"
        full = fit_cox(raw_df, formulas[full_name], full_name)
        reduced = fit_cox(raw_df, formulas[reduced_name], reduced_name)
        lr = 2 * (full.cph.log_likelihood_ - reduced.cph.log_likelihood_)
        p_interaction = chi2.sf(lr, 1)
        summary = full.cph.summary.reset_index().rename(columns={"covariate": "term"})
        terms = [
            "psych_primary_documented_by_index",
            "delirium_binary",
            "psych_primary_documented_by_index:delirium_binary",
        ]
        for term in terms:
            r = summary.loc[summary["term"].eq(term)]
            if r.empty:
                continue
            r = r.iloc[0]
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
                    "interaction_lrt_p_value": p_interaction if term.endswith("delirium_binary") else np.nan,
                    "analysis_n": int(full.fit_df.shape[0]),
                    "event_n": int(full.fit_df["event"].sum()),
                }
            )
    return pd.DataFrame(rows)


def same_day_sensitivity(raw_df: pd.DataFrame, formula: str) -> pd.DataFrame:
    sens = raw_df[raw_df["death_date_logic_abnormal_flag"].eq("none")].copy()
    sens_model = fit_cox(
        sens,
        formula,
        "Model 2 same-day DOD sensitivity",
        duration_col="time_same_day_sensitivity",
        event_col="event_same_day_sensitivity",
    )
    out = cox_joint_rows(sens_model)
    out["sensitivity"] = "include_same_day_dod_time_0_5_days"
    out["same_day_dod_included_n"] = int(sens["death_same_day_discharge"].sum())
    out["analysis_n"] = int(sens_model.fit_df.shape[0])
    out["event_n"] = int(sens_model.fit_df["event"].sum())
    return out


def maybe_piecewise(model2: FittedModel, ph: pd.DataFrame) -> pd.DataFrame:
    p = ph.loc[
        ph["model"].eq("Model 2")
        & ph["test_scope"].eq("joint_exposure_global")
        & ph["term"].eq("joint_exposure_4level"),
        "p_value",
    ]
    if p.empty or pd.isna(p.iloc[0]) or p.iloc[0] >= 0.05:
        return pd.DataFrame(
            [
                {
                    "status": "not_run",
                    "reason": "Model 2 joint exposure global PH test p >= 0.05 or unavailable.",
                    "model2_joint_exposure_ph_p_value": p.iloc[0] if not p.empty else np.nan,
                }
            ]
        )
    rows = []
    intervals = [(0.0, 30.0, "0_30_days"), (30.0, 90.0, "31_90_days"), (90.0, 365.0, "91_365_days")]
    for start, stop, label in intervals:
        sub = model2.raw_df.copy()
        sub["pw_time"] = np.minimum(sub["time_main"], stop) - start
        sub = sub[sub["time_main"] > start].copy()
        sub["pw_time"] = np.maximum(sub["pw_time"], 1e-6)
        sub["pw_event"] = np.where((sub["event_main"].eq(1)) & (sub["time_main"] <= stop) & (sub["time_main"] > start), 1, 0)
        try:
            m = fit_cox(sub, model2.formula, f"Model 2 piecewise {label}", duration_col="pw_time", event_col="pw_event")
            r = cox_joint_rows(m)
            r["time_window"] = label
            r["status"] = "fit"
            rows.append(r)
        except Exception as exc:
            rows.append(
                pd.DataFrame(
                    [
                        {
                            "time_window": label,
                            "status": "failed",
                            "reason": str(exc),
                        }
                    ]
                )
            )
    return pd.concat(rows, ignore_index=True, sort=False)


def report_markdown(
    accounting: pd.DataFrame,
    table1: pd.DataFrame,
    cox_results: pd.DataFrame,
    fit_stats: pd.DataFrame,
    ph: pd.DataFrame,
    std: pd.DataFrame,
    mult: pd.DataFrame,
    additive: pd.DataFrame,
    sens: pd.DataFrame,
    warnings_list: list[str],
) -> str:
    def md(df: pd.DataFrame, max_rows: int = 30) -> str:
        if df.empty:
            return "_No rows._"
        return df.head(max_rows).to_markdown(index=False)

    lines = [
        "# Primary Mortality Model Report",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Run timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Random seed: {SEED}",
        f"- Bootstrap iterations requested: {BOOTSTRAP_N}",
        f"- Cox numerical ridge penalizer: {COX_NUMERICAL_PENALIZER}",
        "- Outcome: one-year all-cause mortality after index hospital discharge.",
        "- Language note: this is an association/prognostic analysis report, not a causal interpretation.",
        "",
        "## Analysis Population",
        "",
        md(accounting),
        "",
        "## Table 1 Main Features",
        "",
        md(table1, 20),
        "",
        "## Cox Joint Exposure Models",
        "",
        md(cox_results),
        "",
        "## Model Fit Statistics",
        "",
        md(fit_stats),
        "",
        "## PH Diagnostics",
        "",
        md(ph[ph["test_scope"].isin(["joint_exposure_global"])], 20),
        "",
        "## Standardized 365-Day Mortality Risk",
        "",
        md(std),
        "",
        "## Multiplicative Interaction",
        "",
        md(mult),
        "",
        "## Additive Interaction",
        "",
        md(additive),
        "",
        "## Same-Day DOD Sensitivity",
        "",
        md(sens),
        "",
        "## Warnings And Deviations",
        "",
    ]
    if warnings_list:
        lines.extend([f"- {w}" for w in sorted(set(warnings_list))])
    else:
        lines.append("- No warnings were recorded.")
    lines.extend(
        [
            "",
            "## Not Run In This Batch",
            "",
            "- Same-system readmission models.",
            "- ICU readmission models.",
            "- IPSW models.",
            "- Large-scale sensitivity analyses beyond the prespecified same-day DOD mortality sensitivity.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_session_and_versions() -> pd.DataFrame:
    packages = [
        "duckdb",
        "pandas",
        "numpy",
        "lifelines",
        "matplotlib",
        "patsy",
        "scipy",
    ]
    rows = []
    for pkg in packages:
        mod = __import__(pkg)
        rows.append({"package": pkg, "version": getattr(mod, "__version__", "unknown")})
    versions = pd.DataFrame(rows)
    session = [
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Executable: {sys.executable}",
        "Rscript: unavailable in PATH during this run.",
        "",
        versions.to_string(index=False),
    ]
    (OUTPUT_DIR / "sessionInfo.txt").write_text("\n".join(session) + "\n", encoding="utf-8")
    write_csv(versions, OUTPUT_DIR / "package_versions.csv")
    return versions


def write_manifest() -> None:
    files = []
    for path in sorted(OUTPUT_DIR.glob("*")):
        if path.is_file() and path.name != "primary_mortality_run_manifest.md":
            files.append(path)
    for path in [PY_SCRIPT, R_WRAPPER]:
        if path.exists():
            files.append(path)
    lines = [
        "# Primary Mortality Run Manifest",
        "",
        f"- Dataset: `{TABLE}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Run timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Random seed: {SEED}",
        f"- Bootstrap iterations requested: {BOOTSTRAP_N}",
        f"- Cox numerical ridge penalizer: {COX_NUMERICAL_PENALIZER}",
        "- Rscript availability: not found in PATH; Python implementation was executed and the requested R wrapper was saved.",
        "- No readmission, ICU readmission, IPSW, imputation, or large-scale sensitivity models were run in this batch.",
        "- The manifest file itself is not self-hashed in the table below; report the manifest SHA256 separately after creation.",
        "",
        "| File | SHA256 |",
        "|---|---|",
    ]
    seen = set()
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        lines.append(f"| `{path}` | `{sha256_path(path)}` |")
    (OUTPUT_DIR / "primary_mortality_run_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


analysis_warnings: list[str] = []
fit_warnings: list[str] = []


def main() -> None:
    np.random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    make_r_wrapper()

    print("Loading frozen analysis dataset...", flush=True)
    table1_df = load_data()
    model_df = table1_df[
        table1_df["death_same_day_discharge"].eq(0)
        & table1_df["death_date_logic_abnormal_flag"].eq("none")
    ].copy()

    accounting = cohort_accounting(table1_df, model_df)
    write_csv(accounting, OUTPUT_DIR / "model_cohort_accounting.csv")

    miss = missingness(model_df)
    write_csv(miss, OUTPUT_DIR / "primary_model_missingness.csv")
    model1_miss_gt20 = miss[
        miss["variable"].isin(MODEL1_RAW_VARIABLES)
        & (miss["missing_percent"] > 20)
    ]
    if not model1_miss_gt20.empty:
        analysis_warnings.append("Formal fitting stopped because at least one Model 1 variable had >20% missingness.")
        report = report_markdown(accounting, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), analysis_warnings)
        (OUTPUT_DIR / "primary_mortality_model_report.md").write_text(report, encoding="utf-8")
        write_session_and_versions()
        write_manifest()
        return
    if (miss["missing_percent"] >= 1).any():
        raise RuntimeError("At least one required variable has 1%-20% missingness; SAP requires MICE, which was not run in this batch.")

    complete_cols = ["time_main", "event_main"] + MODEL2_RAW_VARIABLES + ["delirium_binary"]
    before = len(model_df)
    model_df = model_df.dropna(subset=complete_cols).copy()
    dropped = before - len(model_df)
    if dropped:
        analysis_warnings.append(f"Complete-record model cohort dropped {dropped} rows with required-variable missingness (<1%).")

    knots = age_knots(model_df)
    write_csv(
        pd.DataFrame([{"percentile": k, "age_value": v} for k, v in knots.items()]),
        OUTPUT_DIR / "age_spline_knots.csv",
    )
    formulas = model_formulas(knots)

    print("Generating Table 1...", flush=True)
    table1, smd = build_table1(table1_df)
    write_csv(table1, OUTPUT_DIR / "table1_four_group.csv")
    write_table1_html(table1, OUTPUT_DIR / "table1_four_group.html")
    write_csv(smd, OUTPUT_DIR / "table1_smd.csv")

    print("Generating crude survival outputs...", flush=True)
    crude, risk_table = crude_survival(model_df)
    write_csv(crude, OUTPUT_DIR / "mortality_crude_by_group.csv")
    write_csv(risk_table, OUTPUT_DIR / "mortality_km_risk_table_365d.csv")
    plot_km(
        model_df,
        OUTPUT_DIR / "figure_km_mortality_365d.png",
        OUTPUT_DIR / "figure_km_mortality_365d.pdf",
    )

    print("Fitting Cox models...", flush=True)
    m0 = fit_cox(model_df, formulas["Model 0"], "Model 0")
    m1 = fit_cox(model_df, formulas["Model 1"], "Model 1")
    m2 = fit_cox(model_df, formulas["Model 2"], "Model 2")
    models = [m0, m1, m2]
    cox_results = pd.concat([cox_joint_rows(m) for m in models], ignore_index=True)
    fit_stats = cox_fit_stats(models)
    write_csv(cox_results, OUTPUT_DIR / "cox_joint_exposure_models.csv")
    write_csv(fit_stats, OUTPUT_DIR / "cox_model_fit_statistics.csv")
    with (OUTPUT_DIR / "cox_model_objects.rds").open("wb") as f:
        pickle.dump(
            {
                "note": "Python pickle saved with .rds extension because Rscript was unavailable in this runtime.",
                "models": {m.name: m.cph for m in models},
                "formulas": formulas,
                "age_knots": knots,
            },
            f,
        )
    analysis_warnings.append("Rscript was unavailable; cox_model_objects.rds is a Python pickle with .rds extension, not a native R RDS object.")
    analysis_warnings.append(f"Cox models used a very small numerical ridge penalizer ({COX_NUMERICAL_PENALIZER}) to stabilize Hessian inversion; the prespecified covariate set was not changed.")

    print("Running PH diagnostics...", flush=True)
    ph = ph_tests(models)
    write_csv(ph, OUTPUT_DIR / "ph_assumption_tests.csv")
    plot_schoenfeld(models, OUTPUT_DIR / "figure_schoenfeld_joint_exposure.pdf")
    piecewise = maybe_piecewise(m2, ph)
    write_csv(piecewise, OUTPUT_DIR / "cox_piecewise_exposure_effects.csv")

    print("Running model standardization and bootstrap...", flush=True)
    point = {
        "Model 1": standardized_risk(m1, model_df),
        "Model 2": standardized_risk(m2, model_df),
    }
    design_infos = {"Model 1": m1.design_info, "Model 2": m2.design_info}
    boot, boot_diag = bootstrap_standardization(model_df, formulas, design_infos, ["Model 1", "Model 2"])
    std, additive = summarize_standardized(point, boot)
    write_csv(std, OUTPUT_DIR / "standardized_365d_mortality_risk.csv")
    write_csv(boot_diag, OUTPUT_DIR / "bootstrap_standardization_diagnostics.csv")
    write_csv(additive, OUTPUT_DIR / "additive_interaction_mortality_365d.csv")
    plot_standardized_risk(std, OUTPUT_DIR / "figure_standardized_365d_mortality_risk.pdf")
    plot_additive(additive, OUTPUT_DIR / "figure_additive_interaction_mortality.pdf")

    print("Fitting interaction and same-day sensitivity models...", flush=True)
    mult = multiplicative_interaction(model_df, formulas)
    write_csv(mult, OUTPUT_DIR / "multiplicative_interaction_mortality.csv")
    sens = same_day_sensitivity(table1_df, formulas["Model 2"])
    write_csv(sens, OUTPUT_DIR / "mortality_include_same_day_sensitivity.csv")

    warnings_all = analysis_warnings + fit_warnings
    report = report_markdown(accounting, table1, cox_results, fit_stats, ph, std, mult, additive, sens, warnings_all)
    (OUTPUT_DIR / "primary_mortality_model_report.md").write_text(report, encoding="utf-8")
    write_session_and_versions()
    write_manifest()
    print("DONE", flush=True)
    print(f"output_dir={OUTPUT_DIR}", flush=True)
    print(f"report={OUTPUT_DIR / 'primary_mortality_model_report.md'}", flush=True)
    print(f"report_sha256={sha256_path(OUTPUT_DIR / 'primary_mortality_model_report.md')}", flush=True)


if __name__ == "__main__":
    main()
