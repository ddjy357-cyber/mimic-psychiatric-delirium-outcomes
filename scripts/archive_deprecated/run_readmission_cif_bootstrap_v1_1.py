from __future__ import annotations

import concurrent.futures as cf
import hashlib
import importlib.util
import os
import pickle
import platform
import sys
import time
import traceback
import warnings
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from patsy import build_design_matrices
from scipy.optimize import minimize


SEED = 20260621
BOOTSTRAP_N = int(os.environ.get("READMISSION_BOOTSTRAP_N", "1000"))
MIN_SUCCESS = 950
WORKERS = int(os.environ.get("READMISSION_BOOTSTRAP_WORKERS", str(max(1, min(4, (os.cpu_count() or 2) - 1)))))

PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_readmission_cif_bootstrap_v1_1.py"
V1_SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_readmission_outcomes_v1.py"
V1_OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes"
OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes_v1_1"


def load_v1_module():
    spec = importlib.util.spec_from_file_location("readmission_v1", V1_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v1 module from {V1_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["readmission_v1"] = module
    spec.loader.exec_module(module)
    return module


v1 = load_v1_module()

GROUP_ORDER = v1.GROUP_ORDER
GROUP_LABELS = v1.GROUP_LABELS
REFERENCE_GROUP = v1.REFERENCE_GROUP
OUTCOMES = v1.OUTCOMES

MODEL_NAMES = ["Model 1", "Model 2"]

# Fixed from original v1 formal non-PH assessment. Model structure is not
# re-selected inside bootstrap iterations.
USE_TIME_VARYING = {
    ("readmission_90d", "target"): False,
    ("readmission_90d", "competing_death"): True,
    ("icu_readmission_365d", "target"): True,
    ("icu_readmission_365d", "competing_death"): True,
}

_RAW: pd.DataFrame | None = None
_FORMS: dict[str, str] | None = None
_DESIGN_INFOS: dict[str, object] | None = None
_INITIAL_FITTERS: dict[tuple[str, str, str], object] | None = None


@dataclass
class BootstrapTask:
    iteration: int
    seed: int


class WeightedEfronFitterAdapter:
    def __init__(self, params: np.ndarray, columns: list[str], baseline_times: np.ndarray, baseline_cumhaz: np.ndarray):
        self.params_ = pd.Series(np.asarray(params, dtype=float), index=columns)
        self.baseline_cumulative_hazard_ = pd.DataFrame(
            {"baseline cumulative hazard": np.asarray(baseline_cumhaz, dtype=float)},
            index=np.asarray(baseline_times, dtype=float),
        )


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def design_matrix_from_info(raw_df: pd.DataFrame, design_info) -> pd.DataFrame:
    x = build_design_matrices([design_info], raw_df, return_type="dataframe")[0]
    x = pd.DataFrame(x, index=raw_df.index).astype(float)
    if "Intercept" in x.columns:
        x = x.drop(columns=["Intercept"])
    return x


def initial_params(outcome: str, model_name: str, cause: str, columns: list[str]) -> np.ndarray:
    if _INITIAL_FITTERS is None:
        return np.zeros(len(columns), dtype=float)
    fitter = _INITIAL_FITTERS[(outcome, model_name, cause)]
    return fitter.params_.reindex(columns).fillna(0.0).to_numpy(dtype=float)


def fit_weighted_efron_cox(
    x: pd.DataFrame,
    start: np.ndarray,
    stop: np.ndarray,
    event: np.ndarray,
    weights: np.ndarray,
    init: np.ndarray,
) -> tuple[WeightedEfronFitterAdapter, list[str]]:
    columns = list(x.columns)
    xmat = np.ascontiguousarray(x.to_numpy(dtype=float))
    start = np.asarray(start, dtype=float)
    stop = np.asarray(stop, dtype=float)
    event = np.asarray(event, dtype=int)
    weights = np.asarray(weights, dtype=float)
    p = xmat.shape[1]
    event_rows = np.where(event == 1)[0]
    if event_rows.size == 0:
        raise RuntimeError("No events available for cause-specific Cox fit.")
    event_times = np.sort(np.unique(stop[event_rows]))
    event_index = {float(t): i for i, t in enumerate(event_times)}
    event_weight = np.zeros(event_times.size, dtype=float)
    event_x_weight = np.zeros((event_times.size, p), dtype=float)
    event_ids: list[list[int]] = [[] for _ in range(event_times.size)]
    for i in event_rows:
        j = event_index[float(stop[i])]
        event_weight[j] += weights[i]
        event_x_weight[j, :] += weights[i] * xmat[i, :]
        event_ids[j].append(int(i))
    start_order = np.argsort(start)
    stop_order = np.argsort(stop)

    def fgh(beta: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        eta = np.clip(xmat @ beta, -50.0, 50.0)
        weighted_hazard = weights * np.exp(eta)
        loglik = 0.0
        grad = np.zeros(p, dtype=float)
        hess = np.zeros((p, p), dtype=float)
        risk0 = 0.0
        risk1 = np.zeros(p, dtype=float)
        risk2 = np.zeros((p, p), dtype=float)
        add_pos = 0
        remove_pos = 0
        n = weights.size
        for j, t in enumerate(event_times):
            add_start = add_pos
            while add_pos < n and start[start_order[add_pos]] < t:
                add_pos += 1
            if add_pos > add_start:
                ids = start_order[add_start:add_pos]
                aa = weighted_hazard[ids]
                xx = xmat[ids, :]
                risk0 += float(aa.sum())
                risk1 += aa @ xx
                risk2 += xx.T @ (xx * aa[:, None])
            remove_start = remove_pos
            while remove_pos < n and stop[stop_order[remove_pos]] < t:
                remove_pos += 1
            if remove_pos > remove_start:
                ids = stop_order[remove_start:remove_pos]
                aa = weighted_hazard[ids]
                xx = xmat[ids, :]
                risk0 -= float(aa.sum())
                risk1 -= aa @ xx
                risk2 -= xx.T @ (xx * aa[:, None])
            if event_weight[j] <= 0:
                continue
            ids = np.asarray(event_ids[j], dtype=int)
            aa = weighted_hazard[ids]
            xx = xmat[ids, :]
            tied0 = float(aa.sum())
            tied1 = aa @ xx
            tied2 = xx.T @ (xx * aa[:, None])
            tied_events_n = int(round(event_weight[j]))
            if tied_events_n <= 0:
                continue
            loglik += float(event_x_weight[j, :] @ beta)
            event_mean_x = event_x_weight[j, :] / tied_events_n
            for l in range(tied_events_n):
                frac = l / tied_events_n
                denom = risk0 - frac * tied0
                if denom <= 0 or not np.isfinite(denom):
                    return 1e100, np.zeros(p, dtype=float), np.eye(p, dtype=float)
                num1 = risk1 - frac * tied1
                num2 = risk2 - frac * tied2
                mean = num1 / denom
                loglik -= np.log(denom)
                grad += event_mean_x - mean
                hess -= num2 / denom - np.outer(mean, mean)
        return -loglik, -grad, -hess

    result = minimize(
        lambda b: fgh(b)[0],
        init,
        method="trust-exact",
        jac=lambda b: fgh(b)[1],
        hess=lambda b: fgh(b)[2],
        options={"maxiter": 50, "gtol": 1e-4},
    )
    grad_norm = float(np.linalg.norm(result.jac)) if hasattr(result, "jac") else np.nan
    warning_text: list[str] = []
    if not result.success:
        if np.isfinite(grad_norm) and grad_norm <= 1e-3:
            warning_text.append(f"OptimizerWarning: {result.message}; accepted with gradient norm {grad_norm:.3g}")
        else:
            raise RuntimeError(f"Weighted Efron Cox did not converge: {result.message}; gradient norm={grad_norm:.6g}")
    beta = np.asarray(result.x, dtype=float)
    if not np.all(np.isfinite(beta)):
        raise RuntimeError("Weighted Efron Cox returned non-finite coefficients.")
    # Breslow baseline cumulative hazard evaluated at the Efron coefficient estimates,
    # matching the standard baseline hazard convention for Cox predictions.
    eta = np.clip(xmat @ beta, -50.0, 50.0)
    weighted_hazard = weights * np.exp(eta)
    increments = []
    risk0 = 0.0
    add_pos = 0
    remove_pos = 0
    n = weights.size
    for j, t in enumerate(event_times):
        add_start = add_pos
        while add_pos < n and start[start_order[add_pos]] < t:
            add_pos += 1
        if add_pos > add_start:
            ids = start_order[add_start:add_pos]
            risk0 += float(weighted_hazard[ids].sum())
        remove_start = remove_pos
        while remove_pos < n and stop[stop_order[remove_pos]] < t:
            remove_pos += 1
        if remove_pos > remove_start:
            ids = stop_order[remove_start:remove_pos]
            risk0 -= float(weighted_hazard[ids].sum())
        if risk0 <= 0:
            raise RuntimeError("Non-positive risk set while estimating baseline hazard.")
        increments.append(event_weight[j] / risk0)
    centering_factor = float(np.exp(np.clip(np.asarray(x.mean(axis=0), dtype=float) @ beta, -50.0, 50.0)))
    baseline_cumhaz = np.cumsum(np.asarray(increments, dtype=float)) * centering_factor
    return WeightedEfronFitterAdapter(beta, columns, event_times, baseline_cumhaz), warning_text


def fit_cox_weighted(raw: pd.DataFrame, outcome: str, cause: str, cause_status: int, model_name: str, weights: np.ndarray):
    forms = _FORMS
    design_infos = _DESIGN_INFOS
    if forms is None or design_infos is None:
        raise RuntimeError("Worker is not initialized.")
    cfg = OUTCOMES[outcome]
    df = raw.copy()
    df["time"] = df[cfg["time_col"]].astype(float)
    df["event"] = (df[cfg["status_col"]] == cause_status).astype(int)
    x = design_matrix_from_info(df, design_infos[model_name])
    fit_df = pd.concat([df[["time", "event"]], x], axis=1)
    fitter, warning_text = fit_weighted_efron_cox(
        x,
        start=np.full(df.shape[0], -1e-9, dtype=float),
        stop=df["time"].to_numpy(dtype=float),
        event=df["event"].to_numpy(dtype=int),
        weights=weights,
        init=initial_params(outcome, model_name, cause, list(x.columns)),
    )
    return v1.CoxModel(
        model_name=model_name,
        outcome=outcome,
        cause=cause,
        formula=forms[model_name],
        design_info=design_infos[model_name],
        fitter=fitter,
        fit_df=fit_df,
        raw_df=raw.copy(),
        exposure_columns=v1.exposure_cols(list(x.columns)),
        penalizer=0.0,
        converged_without_ridge=True,
    ), warning_text


def fit_time_varying_full_weighted(raw: pd.DataFrame, outcome: str, cause: str, cause_status: int, model_name: str, weights: np.ndarray):
    forms = _FORMS
    design_infos = _DESIGN_INFOS
    if forms is None or design_infos is None:
        raise RuntimeError("Worker is not initialized.")
    cfg = OUTCOMES[outcome]
    tv = v1.build_tv_raw(raw, outcome, cause_status)
    tv["boot_weight"] = weights[tv["_pid"].to_numpy()].astype(float)
    x = design_matrix_from_info(tv, design_infos[model_name])
    exp_cols = v1.exposure_cols(list(x.columns))
    later_labels = [label for _, _, label in cfg["windows"][1:]]
    full_x = x.copy()
    for col in exp_cols:
        for label in later_labels:
            full_x[f"{col}:interval_{label}"] = full_x[col] * tv[f"interval_{label}"].to_numpy()
    fit_df = pd.concat([tv[["_pid", "start", "stop", "event_tv"]], full_x], axis=1)
    fitter, warning_text = fit_weighted_efron_cox(
        full_x,
        start=fit_df["start"].to_numpy(dtype=float),
        stop=fit_df["stop"].to_numpy(dtype=float),
        event=fit_df["event_tv"].to_numpy(dtype=int),
        weights=tv["boot_weight"].to_numpy(dtype=float),
        init=initial_params(outcome, model_name, cause, list(full_x.columns)),
    )
    return v1.TVModel(
        model_name=model_name,
        outcome=outcome,
        cause=cause,
        formula=forms[model_name],
        design_info=design_infos[model_name],
        fitter=fitter,
        exposure_columns=exp_cols,
        windows=cfg["windows"],
        later_labels=later_labels,
        converged_without_ridge=True,
    ), warning_text


def fit_refit_model(raw: pd.DataFrame, outcome: str, cause: str, cause_status: int, model_name: str, weights: np.ndarray):
    if USE_TIME_VARYING[(outcome, cause)]:
        return fit_time_varying_full_weighted(raw, outcome, cause, cause_status, model_name, weights)
    return fit_cox_weighted(raw, outcome, cause, cause_status, model_name, weights)


def individual_cif_by_group_fast(target_model, death_model, raw: pd.DataFrame, outcome: str) -> dict[str, np.ndarray]:
    cfg = OUTCOMES[outcome]
    horizon = cfg["horizon"]
    dht = v1.baseline_increment(target_model.fitter, horizon)
    dhd = v1.baseline_increment(death_model.fitter, horizon)
    times = np.array(sorted(set(dht.index.astype(float)).union(set(dhd.index.astype(float)))), dtype=float)
    if times.size == 0:
        return {group: np.zeros(raw.shape[0], dtype=float) for group in GROUP_ORDER}
    dht_vec = np.array([float(dht.loc[t]) if t in dht.index else 0.0 for t in times], dtype=float)
    dhd_vec = np.array([float(dhd.loc[t]) if t in dhd.index else 0.0 for t in times], dtype=float)
    labels = [label for _, _, label in cfg["windows"]]
    label_index = np.array([labels.index(v1.interval_label(float(t), cfg["windows"])) for t in times], dtype=int)
    out = {}
    for group in GROUP_ORDER:
        et_by_label = np.column_stack([np.exp(v1.lp_for_group(target_model, raw, group, label)) for label in labels])
        ed_by_label = np.column_stack([np.exp(v1.lp_for_group(death_model, raw, group, label)) for label in labels])
        cumulative_hazard = np.zeros(raw.shape[0], dtype=float)
        cif = np.zeros(raw.shape[0], dtype=float)
        for j, li in enumerate(label_index):
            if dht_vec[j] != 0.0:
                cif += np.exp(-cumulative_hazard) * et_by_label[:, li] * dht_vec[j]
            if dht_vec[j] != 0.0 or dhd_vec[j] != 0.0:
                cumulative_hazard += et_by_label[:, li] * dht_vec[j] + ed_by_label[:, li] * dhd_vec[j]
        out[group] = cif
    return out


def standardized_cif_fast(target_model, death_model, raw: pd.DataFrame, outcome: str, weights: np.ndarray) -> dict[str, float]:
    individual = individual_cif_by_group_fast(target_model, death_model, raw, outcome)
    return {group: float(np.average(values, weights=weights)) for group, values in individual.items()}


def successful_result_row(iteration: int, outcome: str, model_name: str, risks: dict[str, float]) -> dict[str, float | int | str | bool]:
    row: dict[str, float | int | str | bool] = {
        "bootstrap_iteration": iteration,
        "outcome": outcome,
        "model": model_name,
        "status": "success_refit_models",
        "target_model_converged": True,
        "competing_death_model_converged": True,
        "cif_success": True,
        "invalid_cif": False,
        "interaction_metrics_computable": True,
        "used_ridge": False,
    }
    row.update({f"risk_{g}": float(v) for g, v in risks.items()})
    row.update(v1.risk_contrasts(risks))
    return row


def failure_result_row(iteration: int, outcome: str, model_name: str, stage: str, exc: BaseException) -> dict[str, object]:
    return {
        "bootstrap_iteration": iteration,
        "outcome": outcome,
        "model": model_name,
        "stage": stage,
        "failure_type": type(exc).__name__,
        "failure_reason": str(exc),
        "traceback_tail": traceback.format_exc(limit=4),
    }


def run_one_task(task: BootstrapTask) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw = _RAW
    if raw is None:
        raise RuntimeError("Worker is not initialized.")
    rng = np.random.default_rng(task.seed)
    n = raw.shape[0]
    sampled = rng.integers(0, n, size=n)
    counts = np.bincount(sampled, minlength=n).astype(float)
    keep = counts > 0
    boot_raw = raw.loc[keep].reset_index(drop=True).copy()
    boot_weights = counts[keep]
    if int(boot_weights.sum()) != n:
        raise RuntimeError("Bootstrap frequency weights do not sum to the analysis cohort size.")
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for outcome in OUTCOMES:
        for model_name in MODEL_NAMES:
            target = None
            death = None
            target_warnings: list[str] = []
            death_warnings: list[str] = []
            try:
                target, target_warnings = fit_refit_model(boot_raw, outcome, "target", 1, model_name, boot_weights)
            except BaseException as exc:
                failures.append(failure_result_row(task.iteration, outcome, model_name, "target_model_fit", exc))
                continue
            try:
                death, death_warnings = fit_refit_model(boot_raw, outcome, "competing_death", 2, model_name, boot_weights)
            except BaseException as exc:
                failures.append(failure_result_row(task.iteration, outcome, model_name, "competing_death_model_fit", exc))
                continue
            try:
                risks = standardized_cif_fast(target, death, boot_raw, outcome, weights=boot_weights)
                invalid = any((not np.isfinite(x)) or x < -1e-10 or x > 1 + 1e-10 for x in risks.values())
                if invalid:
                    raise ValueError(f"Invalid CIF values: {risks}")
                contrasts = v1.risk_contrasts(risks)
                if not all(np.isfinite(v) for v in contrasts.values() if v is not None):
                    raise ValueError(f"Non-finite additive interaction metrics: {contrasts}")
                row = successful_result_row(task.iteration, outcome, model_name, risks)
                row["target_warning_count"] = len(target_warnings)
                row["competing_death_warning_count"] = len(death_warnings)
                row["target_warnings"] = " | ".join(target_warnings)
                row["competing_death_warnings"] = " | ".join(death_warnings)
                rows.append(row)
            except BaseException as exc:
                failures.append(failure_result_row(task.iteration, outcome, model_name, "standardized_cif_or_interaction", exc))
    return rows, failures


def init_worker(raw: pd.DataFrame, forms: dict[str, str], design_infos: dict[str, object] | None = None) -> None:
    global _RAW, _FORMS, _DESIGN_INFOS, _INITIAL_FITTERS
    _RAW = raw
    _FORMS = forms
    if design_infos is None:
        _DESIGN_INFOS = {}
        for model_name in MODEL_NAMES:
            _, _DESIGN_INFOS[model_name] = v1.design_matrix(raw, forms[model_name], drop_intercept=True)
    else:
        _DESIGN_INFOS = design_infos
    with (V1_OUTPUT_DIR / "readmission_standardization_models.pkl").open("rb") as f:
        _INITIAL_FITTERS = pickle.load(f)


def point_estimates_from_v1() -> dict[tuple[str, str], dict[str, float]]:
    std = pd.concat(
        [
            pd.read_csv(V1_OUTPUT_DIR / "standardized_90d_readmission_cif.csv"),
            pd.read_csv(V1_OUTPUT_DIR / "standardized_365d_icu_readmission_cif.csv"),
        ],
        ignore_index=True,
    )
    point: dict[tuple[str, str], dict[str, float]] = {}
    for outcome in OUTCOMES:
        for model_name in MODEL_NAMES:
            sub = std[(std["outcome"].eq(outcome)) & (std["model"].eq(model_name))]
            point[(outcome, model_name)] = {
                row["group"]: float(row["standardized_cif"]) for _, row in sub.iterrows()
            }
    return point


def summarize(point: dict[tuple[str, str], dict[str, float]], boot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return v1.summarize_standardization(point, boot)


def diagnostics(boot: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in OUTCOMES:
        for model_name in MODEL_NAMES:
            b = boot[(boot["outcome"].eq(outcome)) & (boot["model"].eq(model_name))]
            f = failures[(failures["outcome"].eq(outcome)) & (failures["model"].eq(model_name))] if not failures.empty else pd.DataFrame()
            rows.append(
                {
                    "outcome": outcome,
                    "model": model_name,
                    "planned_iterations": BOOTSTRAP_N,
                    "successful_iterations": int(b.shape[0]),
                    "failed_iterations": int(BOOTSTRAP_N - b.shape[0]),
                    "minimum_success_threshold": MIN_SUCCESS,
                    "threshold_met": bool(b.shape[0] >= MIN_SUCCESS),
                    "target_model_success_n": int((b["target_model_converged"] == True).sum()) if not b.empty else 0,
                    "competing_death_model_success_n": int((b["competing_death_model_converged"] == True).sum()) if not b.empty else 0,
                    "cif_success_n": int((b["cif_success"] == True).sum()) if not b.empty else 0,
                    "invalid_cif_n": int((b["invalid_cif"] == True).sum()) if not b.empty else 0,
                    "interaction_metrics_not_computable_n": int((b["interaction_metrics_computable"] == False).sum()) if not b.empty else 0,
                    "target_model_warning_iterations": int((b["target_warning_count"].fillna(0) > 0).sum()) if not b.empty else 0,
                    "competing_death_model_warning_iterations": int((b["competing_death_warning_count"].fillna(0) > 0).sum()) if not b.empty else 0,
                    "model_refit_each_iteration": True,
                    "bootstrap_method": "patient_level_integer_frequency_weights",
                    "weights_sum_per_iteration": int(24033),
                    "used_ridge": False,
                    "failure_rows_recorded": int(f.shape[0]),
                    "status": "success" if b.shape[0] >= MIN_SUCCESS else "insufficient_successes",
                }
            )
    return pd.DataFrame(rows)


def comparison_table(std: pd.DataFrame, additive: pd.DataFrame) -> pd.DataFrame:
    old_std = pd.concat(
        [
            pd.read_csv(V1_OUTPUT_DIR / "standardized_90d_readmission_cif.csv"),
            pd.read_csv(V1_OUTPUT_DIR / "standardized_365d_icu_readmission_cif.csv"),
        ],
        ignore_index=True,
    )
    old_add = pd.concat(
        [
            pd.read_csv(V1_OUTPUT_DIR / "additive_interaction_readmission_90d.csv"),
            pd.read_csv(V1_OUTPUT_DIR / "additive_interaction_icu_readmission_365d.csv"),
        ],
        ignore_index=True,
    )
    rows = []
    for _, r in std.iterrows():
        old = old_std[
            old_std["outcome"].eq(r["outcome"])
            & old_std["model"].eq(r["model"])
            & old_std["group"].eq(r["group"])
        ].iloc[0]
        for metric, estimate_col, lower_col, upper_col in [
            ("standardized_cif", "standardized_cif", "ci95_lower", "ci95_upper"),
            ("risk_difference_vs_group1", "risk_difference_vs_group1", "risk_difference_ci95_lower", "risk_difference_ci95_upper"),
            ("risk_ratio_vs_group1", "risk_ratio_vs_group1", "risk_ratio_ci95_lower", "risk_ratio_ci95_upper"),
        ]:
            old_width = float(old[upper_col] - old[lower_col])
            new_width = float(r[upper_col] - r[lower_col])
            rows.append(
                {
                    "result_family": "standardized_cif",
                    "outcome": r["outcome"],
                    "model": r["model"],
                    "group_or_metric": r["group"],
                    "metric": metric,
                    "v1_point_estimate": old[estimate_col],
                    "v1_ci_lower": old[lower_col],
                    "v1_ci_upper": old[upper_col],
                    "v1_ci_width": old_width,
                    "v1_1_point_estimate": r[estimate_col],
                    "v1_1_ci_lower": r[lower_col],
                    "v1_1_ci_upper": r[upper_col],
                    "v1_1_ci_width": new_width,
                    "ci_width_change_percent": 100.0 * (new_width - old_width) / old_width if old_width != 0 else np.nan,
                }
            )
    for _, r in additive.iterrows():
        old = old_add[
            old_add["outcome"].eq(r["outcome"])
            & old_add["model"].eq(r["model"])
            & old_add["metric"].eq(r["metric"])
        ].iloc[0]
        old_width = float(old["ci95_upper"] - old["ci95_lower"])
        new_width = float(r["ci95_upper"] - r["ci95_lower"])
        rows.append(
            {
                "result_family": "additive_interaction",
                "outcome": r["outcome"],
                "model": r["model"],
                "group_or_metric": r["metric"],
                "metric": r["metric"],
                "v1_point_estimate": old["estimate"],
                "v1_ci_lower": old["ci95_lower"],
                "v1_ci_upper": old["ci95_upper"],
                "v1_ci_width": old_width,
                "v1_1_point_estimate": r["estimate"],
                "v1_1_ci_lower": r["ci95_lower"],
                "v1_1_ci_upper": r["ci95_upper"],
                "v1_1_ci_width": new_width,
                "ci_width_change_percent": 100.0 * (new_width - old_width) / old_width if old_width != 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def report(std: pd.DataFrame, additive: pd.DataFrame, diag: pd.DataFrame, failures: pd.DataFrame, comp: pd.DataFrame) -> None:
    lines: list[str] = []
    lines += [
        "# Readmission Outcomes Standardized CIF Bootstrap Correction v1.1",
        "",
        f"- Created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "- Scope: standardized CIF, percentile confidence intervals, and CIF-based additive interaction only.",
        "- Original v1 directory was not modified.",
        "- v1 used patient-level resampling of fixed fitted models and therefore did not include model parameter-estimation uncertainty.",
        "- v1.1 refits the target-event and competing-death cause-specific models inside every patient-level bootstrap iteration.",
        "- Integer frequency weights were used to represent each patient-level bootstrap sample with replacement; each iteration weights sum to 24,033.",
        "- This is the validated frequency-weight implementation of the requested patient-level bootstrap and avoids changing the covariate design when rare levels are not sampled.",
        "- Original-sample point estimates were read from the v1 formal output; v1.1 replaces only bootstrap percentile intervals and CIF-based additive interaction intervals.",
        "- No ridge penalty, no covariate changes, no exposure/outcome changes, no cohort changes, and no model-structure selection inside bootstrap iterations.",
        "- Fine-Gray remains not run because no available R environment was documented in v1.",
        "",
        "## Fixed Model Structure",
        "",
        "| Outcome | Cause | Bootstrap model structure |",
        "|---|---|---|",
    ]
    for outcome in OUTCOMES:
        for cause in ["target", "competing_death"]:
            structure = "time-varying joint exposure across prespecified windows" if USE_TIME_VARYING[(outcome, cause)] else "single average joint exposure coefficient"
            lines.append(f"| {outcome} | {cause} | {structure} |")
    lines += [
        "",
        "## Bootstrap Diagnostics",
        "",
        diag.to_markdown(index=False),
        "",
        "## Model 2 Standardized CIF",
        "",
        std[std["model"].eq("Model 2")][
            ["outcome", "group", "standardized_cif", "ci95_lower", "ci95_upper", "risk_difference_vs_group1", "risk_ratio_vs_group1"]
        ].to_markdown(index=False),
        "",
        "## Model 2 Additive Interaction",
        "",
        additive[additive["model"].eq("Model 2")][["outcome", "metric", "estimate", "ci95_lower", "ci95_upper"]].to_markdown(index=False),
        "",
        "## v1 vs v1.1 CI Width",
        "",
        comp[comp["model"].eq("Model 2")][
            ["result_family", "outcome", "group_or_metric", "metric", "v1_ci_width", "v1_1_ci_width", "ci_width_change_percent"]
        ].to_markdown(index=False),
        "",
        "## Failures And Warnings",
        "",
    ]
    if failures.empty:
        lines.append("- No bootstrap failures were recorded.")
    else:
        lines.append(f"- Failure rows recorded: {failures.shape[0]}. See `readmission_cif_bootstrap_failures_v1_1.csv`.")
    if (diag["threshold_met"] == False).any():
        lines.append("- At least one outcome/model did not meet the minimum 950 successful bootstrap iterations; its confidence intervals should not be treated as finalized.")
    else:
        lines.append("- All outcome/model combinations met the prespecified minimum of 950 successful iterations.")
    lines += [
        "",
        "## Interpretation",
        "",
        "- Cause-specific Cox estimates, crude CIF, and time-varying HRs are unchanged from v1 and are referenced rather than regenerated here.",
        "- The v1.1 percentile intervals are wider because they include parameter-estimation uncertainty from refitting both cause-specific models.",
        "- Clinical interpretation should rely on v1.1 intervals for standardized absolute risks and CIF-based additive interaction.",
        "",
    ]
    (OUTPUT_DIR / "readmission_outcomes_model_report_v1_1.md").write_text("\n".join(lines), encoding="utf-8")


def manifest() -> None:
    files = sorted([p for p in OUTPUT_DIR.iterdir() if p.is_file()])
    lines = [
        "# Readmission Outcomes v1.1 Run Manifest",
        "",
        f"- Script: `{SCRIPT_PATH}`",
        f"- Source v1 script reused for frozen formulas and helper functions: `{V1_SCRIPT_PATH}`",
        f"- Output directory: `{OUTPUT_DIR}`",
        f"- Random seed: `{SEED}`",
        f"- Planned bootstrap iterations: `{BOOTSTRAP_N}`",
        f"- Workers: `{WORKERS}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Platform: `{platform.platform()}`",
        "",
        "| File | SHA256 |",
        "|---|---|",
    ]
    for path in files:
        lines.append(f"| `{path}` | `{sha256_path(path)}` |")
    lines.append(f"| `{SCRIPT_PATH}` | `{sha256_path(SCRIPT_PATH)}` |")
    (OUTPUT_DIR / "readmission_outcomes_v1_1_run_manifest.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    raw = v1.load_data()
    if raw.shape[0] != 24033:
        raise RuntimeError(f"Expected conservative analysis cohort n=24033, observed {raw.shape[0]}")
    forms = v1.formulas()
    design_infos = {}
    for model_name in MODEL_NAMES:
        _, design_infos[model_name] = v1.design_matrix(raw, forms[model_name], drop_intercept=True)

    print("Loading original-sample standardized CIF point estimates from v1...", flush=True)
    point = point_estimates_from_v1()

    rng = np.random.default_rng(SEED)
    tasks = [BootstrapTask(i + 1, int(s)) for i, s in enumerate(rng.integers(1, np.iinfo(np.int32).max, size=BOOTSTRAP_N))]
    all_rows: list[dict[str, object]] = []
    all_failures: list[dict[str, object]] = []
    print(f"Running refit bootstrap: iterations={BOOTSTRAP_N}, workers={WORKERS}", flush=True)
    if WORKERS == 1:
        init_worker(raw, forms, design_infos)
        for task in tasks:
            rows, failures = run_one_task(task)
            all_rows.extend(rows)
            all_failures.extend(failures)
            if task.iteration % 10 == 0 or task.iteration == BOOTSTRAP_N:
                print(f"Bootstrap {task.iteration}/{BOOTSTRAP_N} completed in {time.time() - start:.1f}s", flush=True)
    else:
        with cf.ProcessPoolExecutor(max_workers=WORKERS, initializer=init_worker, initargs=(raw, forms, None)) as ex:
            futures = {ex.submit(run_one_task, task): task.iteration for task in tasks}
            completed = 0
            for fut in cf.as_completed(futures):
                completed += 1
                try:
                    rows, failures = fut.result()
                    all_rows.extend(rows)
                    all_failures.extend(failures)
                except BaseException as exc:
                    iteration = futures[fut]
                    all_failures.append(failure_result_row(iteration, "all", "all", "worker_process", exc))
                if completed % 10 == 0 or completed == BOOTSTRAP_N:
                    print(f"Bootstrap {completed}/{BOOTSTRAP_N} completed in {time.time() - start:.1f}s", flush=True)

    boot = pd.DataFrame(all_rows)
    failure_cols = [
        "bootstrap_iteration",
        "outcome",
        "model",
        "stage",
        "failure_type",
        "failure_reason",
        "traceback_tail",
    ]
    failures = pd.DataFrame(all_failures, columns=failure_cols)
    diag = diagnostics(boot, failures)
    if (diag["successful_iterations"] < MIN_SUCCESS).any():
        print("WARNING: at least one outcome/model has fewer than 950 successful iterations.", flush=True)

    std, additive = summarize(point, boot)
    comp = comparison_table(std, additive)

    write_csv(std[std["outcome"].eq("readmission_90d")], OUTPUT_DIR / "standardized_90d_readmission_cif_v1_1.csv")
    write_csv(std[std["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / "standardized_365d_icu_readmission_cif_v1_1.csv")
    write_csv(additive[additive["outcome"].eq("readmission_90d")], OUTPUT_DIR / "additive_interaction_readmission_90d_v1_1.csv")
    write_csv(additive[additive["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / "additive_interaction_icu_readmission_365d_v1_1.csv")
    write_csv(diag, OUTPUT_DIR / "readmission_cif_bootstrap_diagnostics_v1_1.csv")
    write_csv(failures, OUTPUT_DIR / "readmission_cif_bootstrap_failures_v1_1.csv")
    write_csv(comp, OUTPUT_DIR / "fixed_vs_refitted_bootstrap_ci_comparison.csv")
    with (OUTPUT_DIR / "readmission_cif_refit_bootstrap_raw_results_v1_1.pkl").open("wb") as f:
        pickle.dump({"bootstrap_rows": boot, "point_estimates": point, "diagnostics": diag}, f)
    report(std, additive, diag, failures, comp)
    manifest()

    print("DONE", flush=True)
    print(f"output_dir={OUTPUT_DIR}", flush=True)
    print(f"report={OUTPUT_DIR / 'readmission_outcomes_model_report_v1_1.md'}", flush=True)
    print(f"report_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_model_report_v1_1.md')}", flush=True)
    print(f"manifest={OUTPUT_DIR / 'readmission_outcomes_v1_1_run_manifest.md'}", flush=True)
    print(f"manifest_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_v1_1_run_manifest.md')}", flush=True)


if __name__ == "__main__":
    main()
