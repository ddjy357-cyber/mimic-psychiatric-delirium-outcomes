from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", PROJECT.parent))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", WORKSPACE / "data" / "mimiciv.duckdb"))
OUTDIR = PROJECT / "outputs" / "psychiatric_code_validation"
VALIDATION_SCRIPT = PROJECT / "scripts" / "run_psychiatric_code_validation.py"
V1_MAPPING = OUTDIR / "psychiatric_code_mapping_validated_v1.csv"
V11_MAPPING = OUTDIR / "psychiatric_code_mapping_validated_v1.1.csv"

FREEZE_DATE = "2026-06-19"
CCSR_VERSION = "AHRQ CCSR for ICD-10-CM Diagnoses, v2026.1"
CCS9_VERSION = "AHRQ HCUP Single-Level CCS for ICD-9-CM Diagnoses, 2015"

PRIMARY_CATEGORIES = [
    "depressive_disorders",
    "anxiety_disorders",
    "trauma_and_stressor_related_disorders",
    "bipolar_disorders",
    "schizophrenia_spectrum_and_other_psychotic_disorders",
]

F06_SECONDARY_CODES = {"F060", "F061", "F062", "F0631", "F0632", "F0633", "F0634", "F064"}
TRAUMA_ALLOWED_ICD10_PREFIXES = ("F43",)
TRAUMA_ALLOWED_ICD9_PREFIXES = ("308", "309")
EXCLUDED_ICD9_TRAUMA_CODES = {"30921"}
OTHER_MBD007_PREFIXES = ("F44", "F481", "F94")


def load_validation_module():
    spec = importlib.util.spec_from_file_location("psy_validation_v11", VALIDATION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {VALIDATION_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def q(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).fetchdf()


def pct(num, den) -> float | None:
    if den is None or den == 0 or pd.isna(den):
        return None
    if num is None or pd.isna(num):
        num = 0
    return round(float(num) / float(den) * 100.0, 2)


def save_csv(df: pd.DataFrame, name: str) -> Path:
    path = OUTDIR / name
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            clean = df[col].dropna()
            if not clean.empty and np.isclose(clean, np.round(clean)).all():
                df[col] = df[col].round().astype("Int64")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_v11_mapping_changes(v1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping = v1.copy()
    mapping["v1_clinical_priority_category"] = mapping["clinical_priority_category"]
    mapping["v1_mapping_status"] = mapping["mapping_status"]
    mapping["v1_mapping_reason"] = mapping["mapping_reason"]
    mapping["v1_primary_psychiatric_comorbidity_flag"] = mapping[
        "primary_psychiatric_comorbidity_flag"
    ]

    def set_row(mask, category, status, reason):
        mapping.loc[mask, "clinical_priority_category"] = category
        mapping.loc[mask, "mapping_status"] = status
        mapping.loc[mask, "mapping_reason"] = reason
        mapping.loc[mask, "primary_psychiatric_comorbidity_flag"] = "0"
        mapping.loc[mask, "dementia_flag"] = "0"
        mapping.loc[mask, "substance_flag"] = "0"

    f06_mask = (mapping["icd_version"].astype(str) == "10") & mapping[
        "icd_code_norm"
    ].isin(F06_SECONDARY_CODES)
    set_row(
        f06_mask,
        "secondary_psychiatric_due_to_physiological_condition",
        "excluded_secondary_physiological_condition",
        "v1.1 rule: ICD-10 F06 family due to known physiological condition is excluded before MBD001/MBD002/MBD003/MBD005 primary-category assignment.",
    )

    code30921_mask = (mapping["icd_version"].astype(str) == "9") & (
        mapping["icd_code_norm"] == "30921"
    )
    set_row(
        code30921_mask,
        "excluded_other_psychiatric_category",
        "excluded_other_psychiatric_category",
        "v1.1 rule: ICD-9 30921 separation anxiety disorder is not trauma/stressor for the main exposure.",
    )

    other_mbd007_mask = (
        (mapping["icd_version"].astype(str) == "10")
        & mapping["icd_code_norm"].str.startswith(OTHER_MBD007_PREFIXES, na=False)
        & (mapping["clinical_priority_category"] == "trauma_and_stressor_related_disorders")
    )
    set_row(
        other_mbd007_mask,
        "other_psychiatric_disorders",
        "kept_nonprimary_other_psychiatric_disorders",
        "v1.1 rule: MBD007 is restricted to ICD-10 F43 family for main trauma/stressor exposure; dissociative, conversion, depersonalization, and childhood attachment disorder codes are non-primary.",
    )

    # Guardrail: trauma/stressor primary category should be F43 for ICD-10 and
    # 308/309 for ICD-9, with 30921 excluded above.
    trauma_mask = mapping["clinical_priority_category"] == "trauma_and_stressor_related_disorders"
    invalid_trauma = trauma_mask & (
        (
            (mapping["icd_version"].astype(str) == "10")
            & ~mapping["icd_code_norm"].str.startswith(TRAUMA_ALLOWED_ICD10_PREFIXES, na=False)
        )
        | (
            (mapping["icd_version"].astype(str) == "9")
            & ~mapping["icd_code_norm"].str.startswith(TRAUMA_ALLOWED_ICD9_PREFIXES, na=False)
        )
        | mapping["icd_code_norm"].isin(EXCLUDED_ICD9_TRAUMA_CODES)
    )
    set_row(
        invalid_trauma,
        "other_psychiatric_disorders",
        "kept_nonprimary_other_psychiatric_disorders",
        "v1.1 guardrail: code does not meet restricted trauma/stressor main-exposure family rule.",
    )

    mapping["primary_psychiatric_comorbidity_flag"] = mapping[
        "clinical_priority_category"
    ].isin(PRIMARY_CATEGORIES).astype(int).astype(str)
    mapping["dementia_flag"] = (
        mapping["clinical_priority_category"] == "dementia_cognitive_disorders"
    ).astype(int).astype(str)
    mapping["substance_flag"] = mapping["clinical_priority_category"].isin(
        ["alcohol_related_disorders", "other_substance_related_disorders"]
    ).astype(int).astype(str)

    change_cols = [
        "icd_code",
        "icd_code_norm",
        "icd_version",
        "mimic_long_title",
        "v1_clinical_priority_category",
        "clinical_priority_category",
        "v1_mapping_status",
        "mapping_status",
        "v1_primary_psychiatric_comorbidity_flag",
        "primary_psychiatric_comorbidity_flag",
        "mapping_reason",
    ]
    changes = mapping[
        (mapping["v1_clinical_priority_category"] != mapping["clinical_priority_category"])
        | (
            mapping["v1_primary_psychiatric_comorbidity_flag"].astype(str)
            != mapping["primary_psychiatric_comorbidity_flag"].astype(str)
        )
    ][change_cols].copy()
    return mapping.drop(
        columns=[
            "v1_clinical_priority_category",
            "v1_mapping_status",
            "v1_mapping_reason",
            "v1_primary_psychiatric_comorbidity_flag",
        ]
    ), changes


def freeze_v11_mapping(mapping: pd.DataFrame) -> None:
    if V11_MAPPING.exists():
        os.chmod(V11_MAPPING, stat.S_IWRITE | stat.S_IREAD)
    mapping.to_csv(V11_MAPPING, index=False, encoding="utf-8-sig")
    os.chmod(V11_MAPPING, stat.S_IREAD)


def setup_v11_tables(con: duckdb.DuckDBPyConnection, mapping: pd.DataFrame) -> None:
    validation = load_validation_module()
    validation.setup_base_tables(con)
    validation.register_mapping(con, mapping)
    validation.setup_validated_exposure_tables(con)


def run_category_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    base_n = int(q(con, "select count(*) as n from index_base")["n"].iloc[0])
    out = q(
        con,
        """
        select
            'category_count' as section,
            clinical_priority_category as category,
            'strict_prior' as definition,
            count(distinct subject_id) filter (where diagnosis_relation = 'prior_admission') as patient_count
        from psych_dx_events_validated
        group by clinical_priority_category
        union all
        select
            'category_count' as section,
            clinical_priority_category as category,
            'documented_by_index' as definition,
            count(distinct subject_id) filter (where diagnosis_relation in ('prior_admission', 'index_admission')) as patient_count
        from psych_dx_events_validated
        group by clinical_priority_category
        union all
        select
            'category_count' as section,
            clinical_priority_category as category,
            'index_admission_recorded' as definition,
            count(distinct subject_id) filter (where diagnosis_relation = 'index_admission') as patient_count
        from psych_dx_events_validated
        group by clinical_priority_category
        """
    )
    out["percent_of_base"] = out["patient_count"].map(lambda x: pct(x, base_n))

    overall = q(
        con,
        """
        select
            'overall' as section,
            'primary_psychiatric_comorbidity' as category,
            'strict_prior' as definition,
            sum(primary_strict_prior) as patient_count
        from psych_flags_validated
        union all
        select
            'overall' as section,
            'primary_psychiatric_comorbidity' as category,
            'documented_by_index' as definition,
            sum(primary_documented_by_index) as patient_count
        from psych_flags_validated
        union all
        select
            'overall' as section,
            'primary_psychiatric_comorbidity' as category,
            'index_admission_only' as definition,
            sum(case when primary_documented_by_index = 1 and primary_strict_prior = 0 then 1 else 0 end) as patient_count
        from psych_flags_validated
        """
    )
    overall["percent_of_base"] = overall["patient_count"].map(lambda x: pct(x, base_n))
    final = pd.concat([out, overall], ignore_index=True, sort=False).sort_values(
        ["section", "category", "definition"]
    )
    save_csv(final, "psychiatric_category_counts_v1.1.csv")
    return final


def run_timing(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = q(con, "select * from pre_model_patient_validated")
    rows: list[dict] = []
    for group in [
        "no_documented_psychiatric_comorbidity",
        "strict_prior_psychiatric_comorbidity",
        "index_admission_only_psychiatric_comorbidity",
    ]:
        sub = df[df["psychiatric_timing_group"] == group]
        n = len(sub)
        rows.append(
            {
                "section": "group_summary",
                "psychiatric_timing_group": group,
                "level": "",
                "patient_count": n,
                "death_1y_n": int(sub["death_1y_after_discharge"].sum()),
                "death_1y_percent": pct(int(sub["death_1y_after_discharge"].sum()), n),
                "readmit_90d_n": int(sub["readmit_90d_same_system"].sum()),
                "readmit_90d_percent": pct(int(sub["readmit_90d_same_system"].sum()), n),
                "hospice_discharge_n": int(sub["hospice_discharge"].sum()),
                "hospice_discharge_percent": pct(int(sub["hospice_discharge"].sum()), n),
            }
        )
        for status in ["negative", "positive", "unclassifiable"]:
            if status == "unclassifiable":
                count = int((~sub["final_72h_delirium_status"].isin(["negative", "positive"])).sum())
            else:
                count = int((sub["final_72h_delirium_status"] == status).sum())
            rows.append(
                {
                    "section": "delirium_cross_final_72h",
                    "psychiatric_timing_group": group,
                    "level": status,
                    "patient_count": count,
                    "percent_within_timing_group": pct(count, n),
                }
            )
    out = pd.DataFrame(rows)
    save_csv(out, "psychiatric_timing_groups_v1.1.csv")
    return out


def run_four_groups(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = q(
        con,
        """
        select
            case
                when primary_psych_documented_by_index = 0 and final_72h_delirium_status = 'negative'
                    then '1_no_primary_psych_no_delirium'
                when primary_psych_documented_by_index = 1 and final_72h_delirium_status = 'negative'
                    then '2_primary_psych_no_delirium'
                when primary_psych_documented_by_index = 0 and final_72h_delirium_status = 'positive'
                    then '3_no_primary_psych_delirium'
                when primary_psych_documented_by_index = 1 and final_72h_delirium_status = 'positive'
                    then '4_primary_psych_delirium'
                else 'excluded_unclassifiable_delirium'
            end as four_group,
            count(*) as patient_count,
            sum(death_1y_after_discharge) as death_1y_n,
            round(100.0 * sum(death_1y_after_discharge) / nullif(count(*), 0), 2) as death_1y_percent,
            sum(readmit_90d_same_system) as readmit_90d_n,
            round(100.0 * sum(readmit_90d_same_system) / nullif(count(*), 0), 2) as readmit_90d_percent,
            sum(icu_readmit_1y_same_system) as icu_readmit_1y_n,
            round(100.0 * sum(icu_readmit_1y_same_system) / nullif(count(*), 0), 2) as icu_readmit_1y_percent
        from pre_model_patient_validated
        group by four_group
        order by four_group
        """
    )
    save_csv(out, "four_group_counts_v1.1.csv")
    return out


def run_crude_interaction(four: pd.DataFrame) -> pd.DataFrame:
    summary = four[four["four_group"] != "excluded_unclassifiable_delirium"].copy()
    group_map = {
        "1_no_primary_psych_no_delirium": "00_no_psych_no_delirium",
        "2_primary_psych_no_delirium": "10_psych_no_delirium",
        "3_no_primary_psych_delirium": "01_no_psych_delirium",
        "4_primary_psych_delirium": "11_psych_delirium",
    }
    summary["risk_group"] = summary["four_group"].map(group_map)
    outcomes = [
        ("death_1y", "death_1y_n"),
        ("readmit_90d_same_system", "readmit_90d_n"),
        ("icu_readmit_1y_same_system", "icu_readmit_1y_n"),
    ]
    rows = []
    for outcome, event_col in outcomes:
        risks = {}
        ref = None
        for _, row in summary.iterrows():
            risk = float(row[event_col]) / float(row["patient_count"])
            risks[row["risk_group"]] = risk
            if row["risk_group"] == "00_no_psych_no_delirium":
                ref = risk
        for _, row in summary.iterrows():
            risk = risks[row["risk_group"]]
            rows.append(
                {
                    "section": "group_crude_risk",
                    "outcome": outcome,
                    "risk_group": row["risk_group"],
                    "patient_count": int(row["patient_count"]),
                    "event_count": int(row[event_col]),
                    "risk_percent": round(risk * 100, 2),
                    "crude_rr_vs_00": round(risk / ref, 6) if ref else None,
                    "note": "Unadjusted descriptive measure only; not causal.",
                }
            )
        rr10 = risks["10_psych_no_delirium"] / risks["00_no_psych_no_delirium"]
        rr01 = risks["01_no_psych_delirium"] / risks["00_no_psych_no_delirium"]
        rr11 = risks["11_psych_delirium"] / risks["00_no_psych_no_delirium"]
        reri = rr11 - rr10 - rr01 + 1
        ap = reri / rr11 if rr11 else None
        denom = (rr10 - 1) + (rr01 - 1)
        synergy = (rr11 - 1) / denom if denom else None
        rows.append(
            {
                "section": "crude_additive_interaction",
                "outcome": outcome,
                "risk_group": "summary",
                "rr10_psych_only": round(rr10, 6),
                "rr01_delirium_only": round(rr01, 6),
                "rr11_both": round(rr11, 6),
                "crude_reri": round(reri, 6),
                "crude_attributable_proportion": round(ap, 6) if ap is not None else None,
                "crude_synergy_index": round(synergy, 6) if synergy is not None else None,
                "interaction_direction": "positive_additive"
                if reri > 0
                else "negative_additive"
                if reri < 0
                else "null_additive",
                "note": "Unadjusted exploratory description only; no regression or P-value.",
            }
        )
    out = pd.DataFrame(rows)
    save_csv(out, "crude_interaction_descriptive_v1.1.csv")
    return out


def run_qc(mapping: pd.DataFrame, four: pd.DataFrame) -> pd.DataFrame:
    primary = mapping[mapping["primary_psychiatric_comorbidity_flag"].astype(str) == "1"]
    multi_primary = (
        primary.groupby(["icd_code_norm", "icd_version"])["clinical_priority_category"]
        .nunique()
        .reset_index(name="ncat")
    )
    classifiable_n = int(
        four.loc[
            four["four_group"] != "excluded_unclassifiable_delirium", "patient_count"
        ].sum()
    )
    rows = [
        {
            "check": "f06_family_in_primary",
            "value": int(primary["icd_code_norm"].str.startswith("F06", na=False).sum()),
            "passed": int(primary["icd_code_norm"].str.startswith("F06", na=False).sum()) == 0,
        },
        {
            "check": "secondary_category_in_primary",
            "value": int((primary["clinical_priority_category"] == "secondary_psychiatric_due_to_physiological_condition").sum()),
            "passed": int((primary["clinical_priority_category"] == "secondary_psychiatric_due_to_physiological_condition").sum()) == 0,
        },
        {
            "check": "substance_related_in_primary",
            "value": int(primary["clinical_priority_category"].isin(["alcohol_related_disorders", "other_substance_related_disorders"]).sum()),
            "passed": int(primary["clinical_priority_category"].isin(["alcohol_related_disorders", "other_substance_related_disorders"]).sum()) == 0,
        },
        {
            "check": "dementia_in_primary",
            "value": int((primary["clinical_priority_category"] == "dementia_cognitive_disorders").sum()),
            "passed": int((primary["clinical_priority_category"] == "dementia_cognitive_disorders").sum()) == 0,
        },
        {
            "check": "delirium_in_primary",
            "value": int(primary["icd_code_norm"].str.startswith(("F05", "2930", "2931"), na=False).sum()),
            "passed": int(primary["icd_code_norm"].str.startswith(("F05", "2930", "2931"), na=False).sum()) == 0,
        },
        {
            "check": "code_version_multiple_primary_categories",
            "value": int((multi_primary["ncat"] > 1).sum()),
            "passed": int((multi_primary["ncat"] > 1).sum()) == 0,
        },
        {
            "check": "four_group_classifiable_total",
            "value": classifiable_n,
            "passed": classifiable_n == 29458,
        },
    ]
    out = pd.DataFrame(rows)
    save_csv(out, "psychiatric_mapping_freeze_qc_v1.1.csv")
    return out


def write_provenance(mapping: pd.DataFrame, changes: pd.DataFrame, qc: pd.DataFrame) -> None:
    sha = sha256_file(V11_MAPPING)
    path = OUTDIR / "psychiatric_mapping_provenance_v1.1.md"
    lines = [
        "# Psychiatric Mapping Provenance v1.1",
        "",
        f"- Frozen mapping file: `{V11_MAPPING}`",
        f"- Frozen date: `{FREEZE_DATE}`",
        f"- SHA256: `{sha}`",
        f"- ICD-10 source: {CCSR_VERSION}",
        f"- ICD-9 source: {CCS9_VERSION}",
        "",
        "## v1.1 Rule Updates",
        "",
        "- ICD-10 F06 family is assigned before MBD001/MBD002/MBD003/MBD005 and excluded from primary exposure as `secondary_psychiatric_due_to_physiological_condition`.",
        "- ICD-9 30921 separation anxiety disorder is removed from trauma/stressor and marked `excluded_other_psychiatric_category`.",
        "- Main trauma/stressor exposure is restricted to ICD-10 F43 and ICD-9 308/309 acute stress reaction/PTSD/adjustment-family codes; F44, F48.1, and F94 MBD007 codes are retained only as `other_psychiatric_disorders`.",
        "",
        "## Changed Codes",
        "",
        md_table(
            changes[
                [
                    "icd_code_norm",
                    "icd_version",
                    "mimic_long_title",
                    "v1_clinical_priority_category",
                    "clinical_priority_category",
                    "v1_primary_psychiatric_comorbidity_flag",
                    "primary_psychiatric_comorbidity_flag",
                ]
            ]
        ),
        "",
        "## Quality Checks",
        "",
        md_table(qc),
        "",
        "No adjusted model, formal interaction model, or P-value test was run.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_exclusions(mapping: pd.DataFrame) -> None:
    exclusions = mapping[mapping["primary_psychiatric_comorbidity_flag"].astype(str) != "1"].copy()
    save_csv(exclusions, "psychiatric_code_exclusions_v1.1.csv")


def main() -> None:
    v1 = pd.read_csv(V1_MAPPING, dtype=str)
    v11, changes = apply_v11_mapping_changes(v1)
    freeze_v11_mapping(v11)
    save_csv(changes, "psychiatric_mapping_v1_to_v1.1_changes.csv")
    write_exclusions(v11)

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        setup_v11_tables(con, v11)
        category_counts = run_category_counts(con)
        timing = run_timing(con)
        four = run_four_groups(con)
        crude = run_crude_interaction(four)
        qc = run_qc(v11, four)
        write_provenance(v11, changes, qc)
    finally:
        con.close()
    print(f"v1.1 mapping: {V11_MAPPING}")
    print(f"v1.1 changed codes: {len(changes)}")


if __name__ == "__main__":
    main()
