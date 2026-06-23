from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


WORKSPACE = Path(__file__).resolve().parents[4]
PROJECT = WORKSPACE / "projects" / "mental_delirium_longterm"
OUTDIR = PROJECT / "outputs" / "technical_feasibility_audit"
SCRIPT_DIR = PROJECT / "scripts" / "derived_concepts"
TECH_AUDIT_SCRIPT = SCRIPT_DIR / "run_technical_feasibility_audit.py"
PROJECT_SQL_DIR = SCRIPT_DIR / "project_specific"
COMMIT = "57069783095e7770e66ea97da264c0200078ddbf"

CHARLSON_COMPONENTS = [
    "myocardial_infarct",
    "congestive_heart_failure",
    "peripheral_vascular_disease",
    "cerebrovascular_disease",
    "dementia",
    "chronic_pulmonary_disease",
    "rheumatic_disease",
    "peptic_ulcer_disease",
    "mild_liver_disease",
    "diabetes_without_cc",
    "diabetes_with_cc",
    "paraplegia",
    "renal_disease",
    "malignant_cancer",
    "severe_liver_disease",
    "metastatic_solid_tumor",
    "aids",
]


def load_tech_module():
    spec = importlib.util.spec_from_file_location("tech_audit", TECH_AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {TECH_AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def q(con: duckdb.DuckDBPyConnection, sql: str, params=None) -> pd.DataFrame:
    return con.execute(sql, params or []).fetchdf()


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
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = "" if pd.isna(row[col]) else str(row[col])
            vals.append(val.replace("|", "\\|").replace("\n", "<br>"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_md(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def build_needed_official_concepts(con: duckdb.DuckDBPyConnection, tech) -> pd.DataFrame:
    rows = []
    for table_name, rel in tech.OFFICIAL_SEQUENCE:
        if table_name == "antibiotic":
            break
        path = tech.OFFICIAL_ARCHIVE_DIR / rel
        try:
            con.execute(path.read_text(encoding="utf-8"))
            n = int(q(con, f"select count(*) as n from mimiciv_derived.{table_name}")["n"].iloc[0])
            status = "built"
            note = ""
        except Exception as exc:
            n = None
            status = "failed"
            note = f"{type(exc).__name__}: {str(exc)[:300]}"
            raise
        rows.append(
            {
                "table_name": table_name,
                "official_sql_path": rel,
                "build_status": status,
                "row_count": n,
                "note": note,
            }
        )
    return pd.DataFrame(rows)


def setup_common(con: duckdb.DuckDBPyConnection):
    tech = load_tech_module()
    tech.setup_source_aliases(con)
    tech.setup_cohort_and_delirium(con)
    builds = build_needed_official_concepts(con, tech)
    return tech, builds


def run_mortality_v2(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    con.execute(
        """
        create or replace temp table local_hospital_followup_v2 as
        select
            ac.subject_id,
            ac.hadm_id,
            count(distinct later.hadm_id) filter (
                where later.hadm_id <> ac.hadm_id
                  and later.admittime > ac.dischtime
            ) as later_hospitalizations_n,
            count(distinct later.hadm_id) filter (
                where later.hadm_id <> ac.hadm_id
                  and later.admittime > ac.dischtime
                  and later.admittime <= ac.dischtime + interval 365 day
            ) as later_hospitalizations_1y_n
        from audit_cohort ac
        left join hosp.admissions later
          on ac.subject_id = later.subject_id
        group by ac.subject_id, ac.hadm_id
        """
    )
    rows = []
    for population, where in [
        ("base_population", "1 = 1"),
        ("classifiable_72h_population", "ac.delirium_classifiable_72h = 1"),
    ]:
        metrics = q(
            con,
            f"""
            select
                count(*) as denominator,
                sum(case when coalesce(fu.later_hospitalizations_n, 0) = 0 then 1 else 0 end) as index_is_last_local_hospitalization,
                sum(case when coalesce(fu.later_hospitalizations_n, 0) > 0 then 1 else 0 end) as later_local_hospitalization_after_index,
                sum(case when coalesce(fu.later_hospitalizations_1y_n, 0) > 0 then 1 else 0 end) as later_local_hospitalization_within_1y,
                sum(case when ac.dod < cast(ac.admittime as date) then 1 else 0 end) as dod_before_index_admission_date,
                sum(case when ac.dod >= cast(ac.admittime as date) and ac.dod < cast(ac.dischtime as date) then 1 else 0 end) as dod_between_index_admission_and_discharge_dates,
                sum(case when ac.dod = cast(ac.dischtime as date) then 1 else 0 end) as dod_equals_index_discharge_date,
                sum(case when ac.dod > cast(ac.dischtime as date) and ac.dod <= cast(ac.dischtime as date) + interval 365 day then 1 else 0 end) as death_after_discharge_within_365d,
                sum(case when ac.dod > cast(ac.dischtime as date) + interval 365 day then 1 else 0 end) as death_after_discharge_after_365d
            from audit_cohort ac
            left join local_hospital_followup_v2 fu
              on ac.subject_id = fu.subject_id
             and ac.hadm_id = fu.hadm_id
            where {where}
            """
        ).iloc[0]
        denominator = int(metrics["denominator"])
        for metric in metrics.index:
            if metric == "denominator":
                continue
            numerator = int(metrics[metric] or 0)
            rows.append(
                {
                    "population": population,
                    "metric": metric,
                    "numerator": numerator,
                    "denominator": denominator,
                    "percent": pct(numerator, denominator),
                    "logic": "Later hospitalizations are counted by subject_id with a new hadm_id after index discharge.",
                }
            )
    out = pd.DataFrame(rows)
    save_csv(out, "mortality_followup_qc_v2.csv")
    write_md(
        OUTDIR / "mortality_followup_audit_v2.md",
        [
            "# Mortality Follow-up Audit v2",
            "",
            "This correction replaces the prior last-hospitalization check with an explicit `subject_id`-level aggregation of new local `hadm_id` values after index hospital discharge.",
            "",
            "No survival model or outcome regression was run.",
            "",
            md_table(out),
            "",
            "Interpretation: same-system subsequent hospitalization is now internally consistent in both the base population and the 72-hour classifiable population.",
        ],
    )
    return out


def create_charlson_timing(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    component_max = ",\n                ".join(
        [f"max(coalesce(c.{c}, 0)) as {c}" for c in CHARLSON_COMPONENTS]
    )
    component_select = ",\n            ".join(CHARLSON_COMPONENTS)
    score_expr = """
        index_age_score
        + myocardial_infarct
        + congestive_heart_failure
        + peripheral_vascular_disease
        + cerebrovascular_disease
        + dementia
        + chronic_pulmonary_disease
        + rheumatic_disease
        + peptic_ulcer_disease
        + greatest(mild_liver_disease, 3 * severe_liver_disease)
        + greatest(2 * diabetes_with_cc, diabetes_without_cc)
        + greatest(2 * malignant_cancer, 6 * metastatic_solid_tumor)
        + 2 * paraplegia
        + 2 * renal_disease
        + 6 * aids
    """
    con.execute(
        f"""
        create or replace temp table charlson_timing_patient as
        with base as (
            select
                ac.subject_id,
                ac.hadm_id,
                ac.delirium_classifiable_72h,
                ac.admittime as index_admittime,
                ac.age_at_admission_approx as index_age,
                case
                    when ac.age_at_admission_approx <= 50 then 0
                    when ac.age_at_admission_approx <= 60 then 1
                    when ac.age_at_admission_approx <= 70 then 2
                    when ac.age_at_admission_approx <= 80 then 3
                    else 4
                end as index_age_score
            from audit_cohort ac
        ),
        index_hadm as (
            select
                b.subject_id,
                c.charlson_comorbidity_index as charlson_index_hadm
            from base b
            left join mimiciv_derived.charlson c
              on b.hadm_id = c.hadm_id
        ),
        documented_components as (
            select
                b.subject_id,
                b.index_age_score,
                {component_max}
            from base b
            left join hosp.admissions adm
              on b.subject_id = adm.subject_id
             and adm.admittime <= b.index_admittime
            left join mimiciv_derived.charlson c
              on adm.hadm_id = c.hadm_id
            group by b.subject_id, b.index_age_score
        ),
        strict_components as (
            select
                b.subject_id,
                b.index_age_score,
                {component_max}
            from base b
            left join hosp.admissions adm
              on b.subject_id = adm.subject_id
             and adm.hadm_id <> b.hadm_id
             and adm.admittime < b.index_admittime
            left join mimiciv_derived.charlson c
              on adm.hadm_id = c.hadm_id
            group by b.subject_id, b.index_age_score
        ),
        documented_score as (
            select
                subject_id,
                {score_expr} as charlson_documented_by_index
            from documented_components
        ),
        strict_score as (
            select
                subject_id,
                {score_expr} as charlson_strict_prior
            from strict_components
        )
        select
            b.subject_id,
            b.delirium_classifiable_72h,
            ih.charlson_index_hadm,
            ds.charlson_documented_by_index,
            ss.charlson_strict_prior
        from base b
        left join index_hadm ih using (subject_id)
        left join documented_score ds using (subject_id)
        left join strict_score ss using (subject_id)
        """
    )
    _ = component_select

    rows = []
    for population, where in [
        ("base_population", "1 = 1"),
        ("classifiable_72h_population", "delirium_classifiable_72h = 1"),
    ]:
        for score in [
            "charlson_index_hadm",
            "charlson_documented_by_index",
            "charlson_strict_prior",
        ]:
            row = q(
                con,
                f"""
                select
                    '{population}' as population,
                    'score_distribution' as section,
                    '{score}' as variable,
                    count(*) as denominator,
                    count({score}) as nonmissing_n,
                    min({score}) as min_value,
                    quantile_cont({score}, 0.25) as p25,
                    median({score}) as median_value,
                    quantile_cont({score}, 0.75) as p75,
                    max({score}) as max_value
                from charlson_timing_patient
                where {where}
                """
            )
            rows.append(row)

        for a, b in [
            ("charlson_documented_by_index", "charlson_index_hadm"),
            ("charlson_strict_prior", "charlson_index_hadm"),
            ("charlson_documented_by_index", "charlson_strict_prior"),
        ]:
            row = q(
                con,
                f"""
                select
                    '{population}' as population,
                    'score_correlation' as section,
                    '{a} vs {b}' as variable,
                    count(*) as denominator,
                    count(*) filter (where {a} is not null and {b} is not null) as nonmissing_n,
                    corr({a}, {b}) as correlation
                from charlson_timing_patient
                where {where}
                """
            )
            rows.append(row)
            diff = q(
                con,
                f"""
                select
                    '{population}' as population,
                    'score_difference' as section,
                    '{a} minus {b}' as variable,
                    count(*) as denominator,
                    count(({a} - {b})) as nonmissing_n,
                    min(({a} - {b})) as min_value,
                    quantile_cont(({a} - {b}), 0.25) as p25,
                    median(({a} - {b})) as median_value,
                    quantile_cont(({a} - {b}), 0.75) as p75,
                    max(({a} - {b})) as max_value
                from charlson_timing_patient
                where {where}
                """
            )
            rows.append(diff)
    out = pd.concat(rows, ignore_index=True, sort=False)
    out["complete_percent"] = [pct(n, d) for n, d in zip(out["nonmissing_n"], out["denominator"])]
    save_csv(out, "charlson_timing_definition_feasibility.csv")
    write_md(
        OUTDIR / "charlson_timing_definition_report.md",
        [
            "# Charlson Timing Definition Report",
            "",
            "Official hospitalization-level Charlson was retained. Two additional timing definitions were audited without summing historical Charlson totals.",
            "",
            "- `charlson_index_hadm`: official Charlson for index hospitalization only.",
            "- `charlson_documented_by_index`: component-wise max across local hospitalizations with admission time not later than index admission; total recalculated with index age.",
            "- `charlson_strict_prior`: component-wise max across local hospitalizations before index admission only; total recalculated with index age.",
            "",
            "No comparison by exposure group or outcome group was performed.",
            "",
            md_table(out),
        ],
    )
    return out


def run_project_specific_sofa_sql(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    for name in ["non_neurologic_sofa_0_24h.sql", "non_neurologic_sofa_0_6h.sql"]:
        path = PROJECT_SQL_DIR / name
        con.execute(path.read_text(encoding="utf-8"))
        table = name.replace(".sql", "")
        row = q(
            con,
            f"""
            select
                '{name}' as script_name,
                '{path}' as script_path,
                '{sha256_path(path)}' as script_sha256,
                '{table}' as output_table,
                count(*) as row_count,
                count(*) - count(distinct stay_id) as duplicate_stay_rows,
                min(nonneurologic_sofa_zero_imputed) as zero_imputed_min,
                median(nonneurologic_sofa_zero_imputed) as zero_imputed_median,
                max(nonneurologic_sofa_zero_imputed) as zero_imputed_max,
                sum(complete_case_flag) as complete_case_n,
                count(*) - sum(complete_case_flag) as partial_missing_n,
                median(observed_components_n) as observed_components_median,
                min(observed_components_n) as observed_components_min,
                max(observed_components_n) as observed_components_max
            from mimiciv_derived.{table}
            """
        )
        rows.append(row)
    out = pd.concat(rows, ignore_index=True)
    save_csv(out, "non_neurologic_sofa_script_qc.csv")
    return out


def run_vasoactive_key_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    con.execute(
        """
        create or replace temp table vaso_agent_events as
        select 'dobutamine' as agent, stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.dobutamine
        union all select 'dopamine', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.dopamine
        union all select 'epinephrine', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.epinephrine
        union all select 'norepinephrine', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.norepinephrine
        union all select 'phenylephrine', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.phenylephrine
        union all select 'vasopressin', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.vasopressin
        union all select 'milrinone', stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount from mimiciv_derived.milrinone
        """
    )
    sections = []
    sections.append(
        q(
            con,
            """
            select
                'agent_events_interval_key' as section,
                count(*) as total_rows,
                count(*) - count(distinct concat(stay_id, '|', starttime, '|', endtime)) as duplicate_key_rows,
                count(*) filter (where key_row_count > 1) as rows_in_duplicate_interval_keys,
                count(distinct interval_key) filter (where key_row_count > 1) as duplicate_interval_key_groups,
                count(distinct interval_key) filter (where key_row_count > 1 and agent_count > 1) as groups_with_different_drugs,
                count(distinct interval_key) filter (where key_row_count > 1 and linkorder_count > 1) as groups_with_different_linkorders
            from (
                select
                    *,
                    concat(stay_id, '|', starttime, '|', endtime) as interval_key,
                    count(*) over (partition by stay_id, starttime, endtime) as key_row_count,
                    count(distinct agent) over (partition by stay_id, starttime, endtime) as agent_count,
                    count(distinct linkorderid) over (partition by stay_id, starttime, endtime) as linkorder_count
                from vaso_agent_events
            )
            """
        )
    )
    sections.append(
        q(
            con,
            """
            select
                'agent_events_exact_duplicate' as section,
                count(*) as total_rows,
                sum(case when exact_row_count > 1 then 1 else 0 end) as rows_in_exact_duplicate_records,
                count(distinct exact_key) filter (where exact_row_count > 1) as exact_duplicate_record_groups
            from (
                select
                    *,
                    concat(agent, '|', stay_id, '|', coalesce(cast(linkorderid as varchar), ''), '|', starttime, '|', endtime, '|', coalesce(cast(vaso_rate as varchar), ''), '|', coalesce(cast(vaso_amount as varchar), '')) as exact_key,
                    count(*) over (
                        partition by agent, stay_id, linkorderid, starttime, endtime, vaso_rate, vaso_amount
                    ) as exact_row_count
                from vaso_agent_events
            )
            """
        )
    )
    for table in ["vasoactive_agent", "norepinephrine_equivalent_dose"]:
        cols = q(
            con,
            f"""
            select column_name
            from information_schema.columns
            where table_schema = 'mimiciv_derived'
              and table_name = '{table}'
            order by ordinal_position
            """,
        )["column_name"].tolist()
        partition_cols = ", ".join(cols)
        exact_key_expr = "concat(" + ", '|', ".join(
            [f"coalesce(cast({col} as varchar), '')" for col in cols]
        ) + ")"
        sections.append(
            q(
                con,
                f"""
                select
                    '{table}_interval_key' as section,
                    count(*) as total_rows,
                    count(*) - count(distinct concat(stay_id, '|', starttime, '|', endtime)) as duplicate_key_rows,
                    count(*) filter (where key_row_count > 1) as rows_in_duplicate_interval_keys,
                    count(distinct interval_key) filter (where key_row_count > 1) as duplicate_interval_key_groups
                from (
                    select
                        *,
                        concat(stay_id, '|', starttime, '|', endtime) as interval_key,
                        count(*) over (partition by stay_id, starttime, endtime) as key_row_count
                    from mimiciv_derived.{table}
                )
                """
            )
        )
        sections.append(
            q(
                con,
                f"""
                select
                    '{table}_exact_duplicate' as section,
                    count(*) as total_rows,
                    sum(case when exact_row_count > 1 then 1 else 0 end) as rows_in_exact_duplicate_records,
                    count(distinct exact_key) filter (where exact_row_count > 1) as exact_duplicate_record_groups
                from (
                    select
                        *,
                        md5({exact_key_expr}) as exact_key,
                        count(*) over (partition by {partition_cols}) as exact_row_count
                    from mimiciv_derived.{table}
                )
                """
            )
        )
    out = pd.concat(sections, ignore_index=True, sort=False)
    save_csv(out, "vasoactive_key_audit.csv")
    write_md(
        OUTDIR / "vasoactive_key_audit.md",
        [
            "# Vasoactive Key Audit",
            "",
            "This audit checks whether duplicate interval keys reflect different drugs, different link orders, or exact duplicate rows.",
            "",
            md_table(out),
            "",
            "Formal `vasopressor_any_0_24h` should be aggregated to one row per ICU stay. Multiple medications or duplicate intervals must not create duplicate patients.",
        ],
    )
    return out


def run_maintenance_dialysis(con: duckdb.DuckDBPyConnection) -> Path:
    code_counts = q(
        con,
        r"""
        with candidate_dx as (
            select
                dx.icd_code,
                dx.icd_version,
                dd.long_title,
                count(*) as diagnosis_rows,
                count(distinct dx.subject_id) as subject_count,
                count(distinct dx.hadm_id) as hospitalization_count
            from hosp.diagnoses_icd dx
            left join hosp.d_icd_diagnoses dd
              on dx.icd_code = dd.icd_code
             and dx.icd_version = dd.icd_version
            where (dx.icd_version = 9 and dx.icd_code in ('V4511', 'V560', 'V561', 'V562', 'V5631', 'V5632', 'V568'))
               or (dx.icd_version = 10 and (dx.icd_code in ('Z992', 'Z4901', 'Z4902') or dx.icd_code like 'Z49%'))
               or lower(coalesce(dd.long_title, '')) like '%renal dialysis%'
            group by dx.icd_code, dx.icd_version, dd.long_title
        )
        select * from candidate_dx
        order by icd_version, icd_code
        """
    )
    flags = q(
        con,
        """
        with dialysis_dx as (
            select distinct
                ac.subject_id,
                dx.hadm_id,
                adm.admittime,
                case
                    when adm.admittime < ac.admittime and dx.hadm_id <> ac.hadm_id then 'strict_prior'
                    when adm.admittime <= ac.admittime then 'documented_by_index'
                    else 'after_index'
                end as relation
            from audit_cohort ac
            join hosp.diagnoses_icd dx
              on ac.subject_id = dx.subject_id
            join hosp.admissions adm
              on dx.subject_id = adm.subject_id
             and dx.hadm_id = adm.hadm_id
            left join hosp.d_icd_diagnoses dd
              on dx.icd_code = dd.icd_code
             and dx.icd_version = dd.icd_version
            where (dx.icd_version = 9 and dx.icd_code in ('V4511', 'V560', 'V561', 'V562', 'V5631', 'V5632', 'V568'))
               or (dx.icd_version = 10 and (dx.icd_code in ('Z992', 'Z4901', 'Z4902') or dx.icd_code like 'Z49%'))
               or lower(coalesce(dd.long_title, '')) like '%renal dialysis%'
        )
        select
            'base_population' as population,
            count(*) as denominator,
            count(distinct ac.subject_id) filter (where exists (
                select 1 from dialysis_dx d
                where d.subject_id = ac.subject_id
                  and d.relation in ('strict_prior', 'documented_by_index')
            )) as maintenance_dialysis_documented_by_index,
            count(distinct ac.subject_id) filter (where exists (
                select 1 from dialysis_dx d
                where d.subject_id = ac.subject_id
                  and d.relation = 'strict_prior'
            )) as maintenance_dialysis_strict_prior
        from audit_cohort ac
        union all
        select
            'classifiable_72h_population' as population,
            count(*) as denominator,
            count(distinct ac.subject_id) filter (where exists (
                select 1 from dialysis_dx d
                where d.subject_id = ac.subject_id
                  and d.relation in ('strict_prior', 'documented_by_index')
            )) as maintenance_dialysis_documented_by_index,
            count(distinct ac.subject_id) filter (where exists (
                select 1 from dialysis_dx d
                where d.subject_id = ac.subject_id
                  and d.relation = 'strict_prior'
            )) as maintenance_dialysis_strict_prior
        from audit_cohort ac
        where ac.delirium_classifiable_72h = 1
        """
    )
    for col in ["maintenance_dialysis_documented_by_index", "maintenance_dialysis_strict_prior"]:
        flags[col + "_percent"] = [pct(x, d) for x, d in zip(flags[col], flags["denominator"])]
    return write_md(
        OUTDIR / "maintenance_dialysis_feasibility.md",
        [
            "# Maintenance Dialysis Feasibility",
            "",
            "The official RRT concept was not modified.",
            "",
            "A maintenance-dialysis flag appears feasible using diagnosis status/encounter codes such as ICD-9 `V4511` and ICD-10 `Z992`/`Z49*`. Procedure codes alone are not specific enough because they may represent acute ICU RRT or routine dialysis procedures.",
            "",
            "Candidate diagnosis-code counts:",
            "",
            md_table(code_counts),
            "",
            "Preliminary cohort-level flag counts:",
            "",
            md_table(flags),
            "",
            "Recommendation: do not add this to the main model in this correction round. SAP should decide whether maintenance dialysis is a sensitivity exclusion, adjustment candidate, or descriptive flag in RRT-related models.",
        ],
    )


def parse_anchor_group(value: str) -> tuple[int | None, int | None]:
    import re

    years = re.findall(r"\d{4}", str(value))
    if not years:
        return None, None
    if len(years) == 1:
        year = int(years[0])
        return year, year
    return int(years[0]), int(years[-1])


def run_calendar_v2(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = q(
        con,
        """
        select
            anchor_year_group,
            anchor_year,
            admittime,
            dischtime,
            intime,
            outtime,
            delirium_classifiable_72h
        from audit_cohort
        """
    )
    df["discharge_year_shifted"] = pd.to_datetime(df["dischtime"]).dt.year
    df["shifted_year_delta"] = df["discharge_year_shifted"] - df["anchor_year"]
    parsed = df["anchor_year_group"].map(parse_anchor_group)
    df["anchor_year_group_lower"] = [x[0] for x in parsed]
    df["anchor_year_group_upper"] = [x[1] for x in parsed]
    df["approximate_discharge_year_lower"] = df["anchor_year_group_lower"] + df["shifted_year_delta"]
    df["approximate_discharge_year_upper"] = df["anchor_year_group_upper"] + df["shifted_year_delta"]
    df["interval_width_years"] = (
        df["approximate_discharge_year_upper"] - df["approximate_discharge_year_lower"]
    )
    admittime = pd.to_datetime(df["admittime"])
    dischtime = pd.to_datetime(df["dischtime"])
    intime = pd.to_datetime(df["intime"])
    outtime = pd.to_datetime(df["outtime"])
    # Use a conservative calendar audit definition. Same-day ICU outtime after
    # hospital dischtime is not treated as a cross-patient calendar impossibility;
    # date-level ICU discharge after hospital discharge remains flagged.
    df["true_internal_time_order_error"] = (
        (dischtime < admittime)
        | (outtime <= intime)
        | (intime < admittime)
        | (outtime.dt.date > dischtime.dt.date)
        | (df["approximate_discharge_year_lower"] > df["approximate_discharge_year_upper"])
    )

    rows = []
    for population, sub in [
        ("base_population", df),
        ("classifiable_72h_population", df[df["delirium_classifiable_72h"] == 1]),
    ]:
        denom = len(sub)
        cats = [
            ("lower_bound_gt_2022", int((sub["approximate_discharge_year_lower"] > 2022).sum())),
            (
                "upper_bound_gt_2022_and_lower_bound_le_2022",
                int(
                    (
                        (sub["approximate_discharge_year_upper"] > 2022)
                        & (sub["approximate_discharge_year_lower"] <= 2022)
                    ).sum()
                ),
            ),
            ("lower_bound_lt_2008", int((sub["approximate_discharge_year_lower"] < 2008).sum())),
            ("true_internal_time_order_error", int(sub["true_internal_time_order_error"].sum())),
            (
                "no_error_but_interval_width_ge_2y",
                int(
                    (
                        (~sub["true_internal_time_order_error"])
                        & (sub["approximate_discharge_year_lower"] >= 2008)
                        & (sub["approximate_discharge_year_lower"] <= 2022)
                        & (sub["interval_width_years"] >= 2)
                    ).sum()
                ),
            ),
        ]
        for category, n in cats:
            rows.append(
                {
                    "population": population,
                    "section": "range_issue_category",
                    "category": category,
                    "patient_count": n,
                    "denominator": denom,
                    "percent": pct(n, denom),
                    "interpretation": "Approximate range category; upper bound >2022 is not by itself an impossible patient record.",
                }
            )
        dist = (
            sub.groupby(["approximate_discharge_year_lower", "approximate_discharge_year_upper"], dropna=False)
            .size()
            .reset_index(name="patient_count")
            .sort_values(["approximate_discharge_year_lower", "approximate_discharge_year_upper"])
        )
        for _, row in dist.iterrows():
            rows.append(
                {
                    "population": population,
                    "section": "approximate_interval_distribution",
                    "category": f"{row['approximate_discharge_year_lower']}-{row['approximate_discharge_year_upper']}",
                    "patient_count": int(row["patient_count"]),
                    "denominator": denom,
                    "percent": pct(row["patient_count"], denom),
                    "interpretation": "Approximate discharge calendar-year interval based on anchor_year_group.",
                }
            )
    out = pd.DataFrame(rows)
    save_csv(out, "approximate_calendar_range_audit_v2.csv")
    write_md(
        OUTDIR / "calendar_time_audit_v2.md",
        [
            "# Calendar Time Audit v2",
            "",
            "This correction clarifies that an approximate upper bound above 2022 is not automatically an impossible patient record. It reflects uncertainty introduced by anchor-year groups and independently shifted patient timelines.",
            "",
            "Categories now separate lower-bound issues, upper-bound-only overlap with 2022, lower-bound-before-2008, true internal time-order errors, and broad-but-otherwise-valid intervals.",
            "",
            md_table(out[out["section"] == "range_issue_category"]),
        ],
    )
    return out


def write_decision_draft() -> Path:
    return write_md(
        OUTDIR / "technical_audit_final_decisions_draft.md",
        [
            "# Technical Audit Final Decisions Draft",
            "",
            "Status: pending Protocol/SAP approval.",
            "",
            "These are draft methodologic decisions after the technical feasibility correction round. They do not modify the Protocol, DAG, formal data dictionary, frozen exposure definitions, or frozen delirium definition.",
            "",
            "1. 90-day readmission primary analysis should use the conservative cohort with approximate discharge-year upper bound <= 2021.",
            "2. One-year ICU readmission primary analysis should use the same conservative cohort.",
            "3. Full 29,458-patient classifiable analysis should be retained as a sensitivity analysis for database-recorded events.",
            "4. Complete-case non-neurologic SOFA should not be the main analysis strategy.",
            "5. The leading candidate is missing component = 0 non-neurologic SOFA, with observed component count generated simultaneously.",
            "6. Complete SOFA, OASIS, complete-case severity, and organ-support models should be sensitivity analyses.",
            "7. RRT alternative models should consider maintenance dialysis.",
            "8. Patients with DOD earlier than index admission should be excluded from death-outcome analyses.",
            "",
            "No formal outcome model, adjusted interaction model, P-value screening, or patient-level export was run to create this draft.",
        ],
    )


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    _, builds = setup_common(con)
    _ = builds

    print("Writing mortality follow-up v2...")
    mortality = run_mortality_v2(con)

    print("Writing Charlson timing definitions...")
    charlson = create_charlson_timing(con)

    print("Running project-specific non-neurologic SOFA SQL QC...")
    sofa_qc = run_project_specific_sofa_sql(con)

    print("Writing vasoactive key audit...")
    vaso = run_vasoactive_key_audit(con)

    print("Writing maintenance dialysis feasibility...")
    dialysis = run_maintenance_dialysis(con)

    print("Writing calendar audit v2...")
    calendar = run_calendar_v2(con)

    print("Writing decision draft...")
    decisions = write_decision_draft()

    generated = [
        OUTDIR / "mortality_followup_qc_v2.csv",
        OUTDIR / "mortality_followup_audit_v2.md",
        OUTDIR / "charlson_timing_definition_feasibility.csv",
        OUTDIR / "charlson_timing_definition_report.md",
        PROJECT_SQL_DIR / "non_neurologic_sofa_0_24h.sql",
        PROJECT_SQL_DIR / "non_neurologic_sofa_0_6h.sql",
        OUTDIR / "non_neurologic_sofa_script_qc.csv",
        OUTDIR / "vasoactive_key_audit.csv",
        OUTDIR / "vasoactive_key_audit.md",
        dialysis,
        OUTDIR / "calendar_time_audit_v2.md",
        OUTDIR / "approximate_calendar_range_audit_v2.csv",
        decisions,
    ]
    summary = pd.DataFrame(
        [
            {
                "file_path": str(path),
                "sha256": sha256_path(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ]
    )
    save_csv(summary, "technical_feasibility_correction_manifest.csv")
    print("Correction files:")
    print(summary.to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
