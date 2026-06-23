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
SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_readmission_cif_bootstrap_v1_2.py"
V1_SCRIPT_PATH = PROJECT / "scripts" / "analysis" / "run_readmission_outcomes_v1.py"
V1_OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes"
V11_OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes_v1_1"
OUTPUT_DIR = PROJECT / "analysis" / "formal_models_v1" / "02_readmission_outcomes_v1_2"


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
    # Uncentered Breslow baseline cumulative hazard evaluated at the Efron
    # coefficient estimates. Counterfactual CIF predictions use exp(X beta)
    # on this same uncentered scale.
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
    baseline_cumhaz = np.cumsum(np.asarray(increments, dtype=float))
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


def point_estimates_refit(raw: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    point: dict[tuple[str, str], dict[str, float]] = {}
    weights = np.ones(raw.shape[0], dtype=float)
    for outcome in OUTCOMES:
        for model_name in MODEL_NAMES:
            target, _ = fit_refit_model(raw, outcome, "target", 1, model_name, weights)
            death, _ = fit_refit_model(raw, outcome, "competing_death", 2, model_name, weights)
            point[(outcome, model_name)] = standardized_cif_fast(target, death, raw, outcome, weights)
    return point


def step_at(series: pd.Series, times: np.ndarray) -> np.ndarray:
    idx = series.index.to_numpy(dtype=float)
    vals = series.to_numpy(dtype=float)
    pos = np.searchsorted(idx, times.astype(float), side="right") - 1
    out = np.zeros(times.size, dtype=float)
    ok = pos >= 0
    out[ok] = vals[pos[ok]]
    return out


def error_metrics(manual: np.ndarray, reference: np.ndarray) -> tuple[float, float, bool]:
    manual = np.asarray(manual, dtype=float)
    reference = np.asarray(reference, dtype=float)
    abs_diff = np.abs(manual - reference)
    rel_diff = abs_diff / np.maximum(np.abs(reference), 1e-12)
    max_abs = float(np.nanmax(abs_diff))
    max_rel = float(np.nanmax(rel_diff))
    passed = bool((max_abs < 1e-8) or (max_rel < 1e-6))
    return max_abs, max_rel, passed


def validation_row(
    validation_type: str,
    outcome: str,
    cause: str,
    model_name: str,
    interval_label: str,
    n_checked: int,
    max_abs: float,
    max_rel: float,
    passed: bool,
    details: str,
) -> dict[str, object]:
    return {
        "validation_type": validation_type,
        "outcome": outcome,
        "cause": cause,
        "model": model_name,
        "interval_label": interval_label,
        "n_checked": n_checked,
        "max_abs_error": max_abs,
        "max_relative_error": max_rel,
        "passed": passed,
        "details": details,
    }


def centering_validation(raw: pd.DataFrame, forms: dict[str, str], design_infos: dict[str, object]) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    weights = np.ones(raw.shape[0], dtype=float)
    rows: list[dict[str, object]] = []

    for model_name in MODEL_NAMES:
        lifelines_model = v1.fit_cox(
            raw,
            forms[model_name],
            model_name,
            "readmission_90d",
            "target",
            1,
            design_info=design_infos[model_name],
        )
        x = design_matrix_from_info(raw, design_infos[model_name])
        sample_n = min(100, x.shape[0])
        sample_idx = rng.choice(np.arange(x.shape[0]), size=sample_n, replace=False)
        x_sample = x.iloc[sample_idx, :].copy()
        lifelines_beta = lifelines_model.fitter.params_.reindex(x.columns).to_numpy(dtype=float)

        lifelines_times = lifelines_model.fitter.baseline_cumulative_hazard_.index.to_numpy(dtype=float)
        lifelines_times = lifelines_times[lifelines_times <= OUTCOMES["readmission_90d"]["horizon"]]
        pos = np.unique(np.linspace(0, len(lifelines_times) - 1, min(25, len(lifelines_times))).astype(int))
        check_times = lifelines_times[pos]
        mean_x = lifelines_model.fitter._norm_mean.reindex(x.columns).to_numpy(dtype=float)
        lifelines_baseline = lifelines_model.fitter.baseline_cumulative_hazard_.iloc[:, 0]
        validation_uncentered_baseline = lifelines_baseline / float(np.exp(mean_x @ lifelines_beta))
        manual_ch = np.outer(step_at(validation_uncentered_baseline, check_times), np.exp(x_sample.to_numpy(dtype=float) @ lifelines_beta)).T
        lifelines_ch = lifelines_model.fitter.predict_cumulative_hazard(x_sample, times=check_times)
        reference_ch = lifelines_ch.to_numpy(dtype=float).T
        max_abs, max_rel, passed = error_metrics(manual_ch, reference_ch)
        rows.append(
            validation_row(
                "non_time_varying_cumulative_hazard",
                "readmission_90d",
                "target",
                model_name,
                "not_applicable",
                int(sample_n * check_times.size),
                max_abs,
                max_rel,
                passed,
                "uncentered baseline times exp(X beta) vs lifelines predict_cumulative_hazard",
            )
        )

        manual_ph = np.exp((x_sample.to_numpy(dtype=float) - mean_x) @ lifelines_beta)
        reference_ph = lifelines_model.fitter.predict_partial_hazard(x_sample).to_numpy(dtype=float).reshape(-1)
        max_abs, max_rel, passed = error_metrics(manual_ph, reference_ph)
        rows.append(
            validation_row(
                "non_time_varying_partial_hazard",
                "readmission_90d",
                "target",
                model_name,
                "not_applicable",
                int(sample_n),
                max_abs,
                max_rel,
                passed,
                "exp((X - mean_X) beta) vs lifelines predict_partial_hazard",
            )
        )

        centered_from_uncentered = validation_uncentered_baseline * float(np.exp(mean_x @ lifelines_beta))
        union_times = np.array(sorted(set(centered_from_uncentered.index.astype(float)).union(set(lifelines_baseline.index.astype(float)))), dtype=float)
        manual_base = step_at(centered_from_uncentered, union_times)
        reference_base = step_at(lifelines_baseline, union_times)
        max_abs, max_rel, passed = error_metrics(manual_base, reference_base)
        rows.append(
            validation_row(
                "baseline_conversion",
                "readmission_90d",
                "target",
                model_name,
                "not_applicable",
                int(union_times.size),
                max_abs,
                max_rel,
                passed,
                "uncentered baseline times exp(mean_X beta) vs lifelines centered baseline",
            )
        )

    tv_specs = [
        ("readmission_90d", "competing_death", 2),
        ("icu_readmission_365d", "target", 1),
        ("icu_readmission_365d", "competing_death", 2),
    ]
    for outcome, cause, status in tv_specs:
        cfg = OUTCOMES[outcome]
        for model_name in MODEL_NAMES:
            _, full_model, _, _ = v1.fit_tv(raw, outcome, cause, status, forms[model_name], model_name, design_info=design_infos[model_name])
            tv = v1.build_tv_raw(raw, outcome, status)
            x = design_matrix_from_info(tv, design_infos[model_name])
            exp_cols = v1.exposure_cols(list(x.columns))
            later_labels = [label for _, _, label in cfg["windows"][1:]]
            full_x = x.copy()
            for col in exp_cols:
                for label in later_labels:
                    full_x[f"{col}:interval_{label}"] = full_x[col] * tv[f"interval_{label}"].to_numpy()
            full_x = full_x.reindex(columns=full_model.fitter.params_.index)
            beta = full_model.fitter.params_.to_numpy(dtype=float)
            mean_x = full_model.fitter._norm_mean.reindex(full_x.columns).to_numpy(dtype=float)
            for _, _, label in cfg["windows"]:
                eligible = np.where(tv["interval_label"].eq(label).to_numpy())[0]
                sample_n = min(100, eligible.size)
                sample_idx = rng.choice(eligible, size=sample_n, replace=False)
                x_sample = full_x.iloc[sample_idx, :].copy()
                manual_ph = np.exp((x_sample.to_numpy(dtype=float) - mean_x) @ beta)
                reference_ph = full_model.fitter.predict_partial_hazard(x_sample).to_numpy(dtype=float).reshape(-1)
                max_abs, max_rel, passed = error_metrics(manual_ph, reference_ph)
                rows.append(
                    validation_row(
                        "time_varying_partial_hazard",
                        outcome,
                        cause,
                        model_name,
                        label,
                        int(sample_n),
                        max_abs,
                        max_rel,
                        passed,
                        "exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard",
                    )
                )
    return pd.DataFrame(rows)


def summarize(point: dict[tuple[str, str], dict[str, float]], boot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return v1.summarize_standardization(point, boot)


def add_synergy_interpretability(additive: pd.DataFrame, boot: pd.DataFrame) -> pd.DataFrame:
    additive = additive.copy()
    additive["formal_interpretability"] = "reported"
    for (outcome, model_name), sub in additive.groupby(["outcome", "model"]):
        idx = sub[sub["metric"].eq("synergy_index")].index
        if idx.empty:
            continue
        rr10 = float(sub[sub["metric"].eq("RR10")]["estimate"].iloc[0])
        rr01 = float(sub[sub["metric"].eq("RR01")]["estimate"].iloc[0])
        denom = (rr10 - 1.0) + (rr01 - 1.0)
        same_direction = np.sign(rr10 - 1.0) == np.sign(rr01 - 1.0) and np.sign(rr10 - 1.0) != 0
        denom_stable = abs(denom) >= 0.05
        b = boot[(boot["outcome"].eq(outcome)) & (boot["model"].eq(model_name))]
        b_denom = (b["RR10"] - 1.0) + (b["RR01"] - 1.0)
        sign_flip_fraction = float(np.mean(np.sign(b_denom) != np.sign(denom))) if denom != 0 and not b.empty else 1.0
        interpretable = bool(same_direction and denom_stable and sign_flip_fraction <= 0.10)
        additive.loc[idx, "formal_interpretability"] = "interpretable" if interpretable else "not_interpretable"
        additive.loc[idx, "synergy_index_same_rr_direction"] = same_direction
        additive.loc[idx, "synergy_index_denom"] = denom
        additive.loc[idx, "synergy_index_bootstrap_denom_sign_flip_fraction"] = sign_flip_fraction
    return additive


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
    v1_std = pd.concat(
        [
            pd.read_csv(V1_OUTPUT_DIR / "standardized_90d_readmission_cif.csv"),
            pd.read_csv(V1_OUTPUT_DIR / "standardized_365d_icu_readmission_cif.csv"),
        ],
        ignore_index=True,
    )
    v1_add = pd.concat(
        [
            pd.read_csv(V1_OUTPUT_DIR / "additive_interaction_readmission_90d.csv"),
            pd.read_csv(V1_OUTPUT_DIR / "additive_interaction_icu_readmission_365d.csv"),
        ],
        ignore_index=True,
    )
    v11_std = pd.concat(
        [
            pd.read_csv(V11_OUTPUT_DIR / "standardized_90d_readmission_cif_v1_1.csv"),
            pd.read_csv(V11_OUTPUT_DIR / "standardized_365d_icu_readmission_cif_v1_1.csv"),
        ],
        ignore_index=True,
    )
    v11_add = pd.concat(
        [
            pd.read_csv(V11_OUTPUT_DIR / "additive_interaction_readmission_90d_v1_1.csv"),
            pd.read_csv(V11_OUTPUT_DIR / "additive_interaction_icu_readmission_365d_v1_1.csv"),
        ],
        ignore_index=True,
    )
    rows = []
    for _, r in std.iterrows():
        old = v1_std[
            v1_std["outcome"].eq(r["outcome"])
            & v1_std["model"].eq(r["model"])
            & v1_std["group"].eq(r["group"])
        ].iloc[0]
        prev = v11_std[
            v11_std["outcome"].eq(r["outcome"])
            & v11_std["model"].eq(r["model"])
            & v11_std["group"].eq(r["group"])
        ].iloc[0]
        for metric, estimate_col, lower_col, upper_col in [
            ("standardized_cif", "standardized_cif", "ci95_lower", "ci95_upper"),
            ("risk_difference_vs_group1", "risk_difference_vs_group1", "risk_difference_ci95_lower", "risk_difference_ci95_upper"),
            ("risk_ratio_vs_group1", "risk_ratio_vs_group1", "risk_ratio_ci95_lower", "risk_ratio_ci95_upper"),
        ]:
            old_width = float(old[upper_col] - old[lower_col])
            prev_width = float(prev[upper_col] - prev[lower_col])
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
                    "v1_1_point_estimate": prev[estimate_col],
                    "v1_1_ci_lower": prev[lower_col],
                    "v1_1_ci_upper": prev[upper_col],
                    "v1_1_ci_width": prev_width,
                    "v1_2_point_estimate": r[estimate_col],
                    "v1_2_ci_lower": r[lower_col],
                    "v1_2_ci_upper": r[upper_col],
                    "v1_2_ci_width": new_width,
                    "v1_2_minus_v1_1_point": r[estimate_col] - prev[estimate_col],
                    "v1_2_vs_v1_1_ci_width_change_percent": 100.0 * (new_width - prev_width) / prev_width if prev_width != 0 else np.nan,
                }
            )
    for _, r in additive.iterrows():
        old = v1_add[
            v1_add["outcome"].eq(r["outcome"])
            & v1_add["model"].eq(r["model"])
            & v1_add["metric"].eq(r["metric"])
        ].iloc[0]
        prev = v11_add[
            v11_add["outcome"].eq(r["outcome"])
            & v11_add["model"].eq(r["model"])
            & v11_add["metric"].eq(r["metric"])
        ].iloc[0]
        old_width = float(old["ci95_upper"] - old["ci95_lower"])
        prev_width = float(prev["ci95_upper"] - prev["ci95_lower"])
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
                "v1_1_point_estimate": prev["estimate"],
                "v1_1_ci_lower": prev["ci95_lower"],
                "v1_1_ci_upper": prev["ci95_upper"],
                "v1_1_ci_width": prev_width,
                "v1_2_point_estimate": r["estimate"],
                "v1_2_ci_lower": r["ci95_lower"],
                "v1_2_ci_upper": r["ci95_upper"],
                "v1_2_ci_width": new_width,
                "v1_2_minus_v1_1_point": r["estimate"] - prev["estimate"],
                "v1_2_vs_v1_1_ci_width_change_percent": 100.0 * (new_width - prev_width) / prev_width if prev_width != 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def report(std: pd.DataFrame, additive: pd.DataFrame, diag: pd.DataFrame, failures: pd.DataFrame, comp: pd.DataFrame, validation: pd.DataFrame) -> None:
    lines: list[str] = []
    lines += [
        "# Readmission Outcomes Standardized CIF Centering Correction v1.2",
        "",
        f"- Created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "- Scope: standardized CIF, percentile confidence intervals, and CIF-based additive interaction only.",
        "- Original v1 and v1.1 directories were not modified.",
        "- v1 used fixed-model bootstrap and underestimated uncertainty.",
        "- v1.1 refit models in each bootstrap iteration but mixed centered baseline hazard with uncentered linear predictors.",
        "- v1.2 uses uncentered baseline hazard with exp(X beta) for both original-sample point estimates and refitted bootstrap predictions.",
        "- Cause-specific HRs, non-PH LRTs, and time-varying HRs are unchanged and are referenced from v1.",
        "- v1 and v1.1 standardized CIF, RD, RR, and additive interaction outputs are deprecated; clinical interpretation should use v1.2.",
        "- No ridge penalty, no covariate changes, no exposure/outcome changes, no cohort changes, and no model-structure selection inside bootstrap iterations.",
        "- Fine-Gray remains not run because no available R environment was documented in v1.",
        "",
        "## Centering Validation",
        "",
        validation.to_markdown(index=False),
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
        "## v1.1 vs v1.2 CIF and CI Changes",
        "",
        comp[comp["model"].eq("Model 2")][
            ["result_family", "outcome", "group_or_metric", "metric", "v1_1_point_estimate", "v1_2_point_estimate", "v1_2_minus_v1_1_point", "v1_1_ci_width", "v1_2_ci_width", "v1_2_vs_v1_1_ci_width_change_percent"]
        ].to_markdown(index=False),
        "",
        "## Failures And Warnings",
        "",
    ]
    if failures.empty:
        lines.append("- No bootstrap failures were recorded.")
    else:
        lines.append(f"- Failure rows recorded: {failures.shape[0]}. See `readmission_cif_bootstrap_failures_v1_2.csv`.")
    if (diag["threshold_met"] == False).any():
        lines.append("- At least one outcome/model did not meet the minimum 950 successful bootstrap iterations; its confidence intervals should not be treated as finalized.")
    else:
        lines.append("- All outcome/model combinations met the prespecified minimum of 950 successful iterations.")
    lines += [
        "",
        "## Interpretation",
        "",
        "- Cause-specific Cox estimates, crude CIF, and time-varying HRs are unchanged from v1 and are referenced rather than regenerated here.",
        "- The v1.2 percentile intervals include parameter-estimation uncertainty from refitting both cause-specific models.",
        "- Synergy index rows are retained for technical audit only when marked not interpretable.",
        "- Clinical interpretation should rely on v1.2 intervals for standardized absolute risks and CIF-based additive interaction.",
        "",
    ]
    (OUTPUT_DIR / "readmission_outcomes_model_report_v1_2.md").write_text("\n".join(lines), encoding="utf-8")


def manifest() -> None:
    files = sorted([p for p in OUTPUT_DIR.iterdir() if p.is_file()])
    lines = [
        "# Readmission Outcomes v1.2 Run Manifest",
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
    (OUTPUT_DIR / "readmission_outcomes_v1_2_run_manifest.md").write_text("\n".join(lines), encoding="utf-8")


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

    init_worker(raw, forms, design_infos)
    print("Running CIF centering validation...", flush=True)
    validation = centering_validation(raw, forms, design_infos)
    write_csv(validation, OUTPUT_DIR / "cif_centering_validation.csv")
    if not validation["passed"].all():
        raise RuntimeError("CIF centering validation failed; formal CIF outputs were not generated.")

    print("Computing original-sample standardized CIF point estimates with uncentered baseline...", flush=True)
    point = point_estimates_refit(raw)

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
    additive = add_synergy_interpretability(additive, boot)
    comp = comparison_table(std, additive)

    write_csv(std[std["outcome"].eq("readmission_90d")], OUTPUT_DIR / "standardized_90d_readmission_cif_v1_2.csv")
    write_csv(std[std["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / "standardized_365d_icu_readmission_cif_v1_2.csv")
    write_csv(additive[additive["outcome"].eq("readmission_90d")], OUTPUT_DIR / "additive_interaction_readmission_90d_v1_2.csv")
    write_csv(additive[additive["outcome"].eq("icu_readmission_365d")], OUTPUT_DIR / "additive_interaction_icu_readmission_365d_v1_2.csv")
    write_csv(diag, OUTPUT_DIR / "readmission_cif_bootstrap_diagnostics_v1_2.csv")
    write_csv(failures, OUTPUT_DIR / "readmission_cif_bootstrap_failures_v1_2.csv")
    write_csv(comp, OUTPUT_DIR / "cif_v1_v1_1_v1_2_comparison.csv")
    with (OUTPUT_DIR / "readmission_cif_refit_bootstrap_raw_results_v1_2.pkl").open("wb") as f:
        pickle.dump({"bootstrap_rows": boot, "point_estimates": point, "diagnostics": diag}, f)
    report(std, additive, diag, failures, comp, validation)
    manifest()

    print("DONE", flush=True)
    print(f"output_dir={OUTPUT_DIR}", flush=True)
    print(f"report={OUTPUT_DIR / 'readmission_outcomes_model_report_v1_2.md'}", flush=True)
    print(f"report_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_model_report_v1_2.md')}", flush=True)
    print(f"manifest={OUTPUT_DIR / 'readmission_outcomes_v1_2_run_manifest.md'}", flush=True)
    print(f"manifest_sha256={sha256_path(OUTPUT_DIR / 'readmission_outcomes_v1_2_run_manifest.md')}", flush=True)


if __name__ == "__main__":
    main()
