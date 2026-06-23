from __future__ import annotations

import hashlib
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parents[1]
DB_PATH = WORKSPACE / "data" / "mimiciv.duckdb"
ANALYSIS_DIR = PROJECT / "analysis"
QC_DIR = ANALYSIS_DIR / "qc_v1_1"
SCRIPT_DIR = PROJECT / "scripts" / "derived_concepts"
OFFICIAL_COMMIT = "57069783095e7770e66ea97da264c0200078ddbf"
OFFICIAL_ARCHIVE_DIR = (
    SCRIPT_DIR
    / f"official_mimic_code_{OFFICIAL_COMMIT}"
    / f"mimic-code-{OFFICIAL_COMMIT}"
)
ADAPTED_SQL_DIR = SCRIPT_DIR / "duckdb_adapted"
PROJECT_SQL_DIR = SCRIPT_DIR / "project_specific"
PSYCH_MAPPING_PATH = (
    PROJECT
    / "outputs"
    / "psychiatric_code_validation"
    / "psychiatric_code_mapping_validated_v1.1.csv"
)
FREEZE_LOG_PATH = ANALYSIS_DIR / "analysis_data_freeze_log_v1_1.md"
MANIFEST_PATH = ANALYSIS_DIR / "analysis_dataset_manifest_v1_1.md"
HOTFIX_LOG_PATH = ANALYSIS_DIR / "analysis_data_hotfix_v1_to_v1_1.md"
STUDY_FREEZE_LOG = PROJECT / "docs" / "study_definition_freeze_log.md"

DERIVED_SCHEMA = "mental_delirium_derived"
ANALYSIS_SCHEMA = "mental_delirium_analysis"
ANALYSIS_TABLE_NAME = "analysis_dataset_v1_1"
ANALYSIS_TABLE = f"{ANALYSIS_SCHEMA}.{ANALYSIS_TABLE_NAME}"

EXPECTED = {
    "base_population_n": 46316,
    "classifiable_n": 29458,
    "unclassifiable_n": 16858,
    "four_groups": {
        "1_no_primary_psych_no_delirium": 13909,
        "2_primary_psych_no_delirium": 5987,
        "3_no_primary_psych_delirium": 6067,
        "4_primary_psych_delirium": 3495,
    },
    "death_365d_main_classifiable_approx": 5105,
}

OFFICIAL_SEQUENCE = [
    ("age", "mimic-iv/concepts_duckdb/demographics/age.sql"),
    ("icustay_times", "mimic-iv/concepts_duckdb/demographics/icustay_times.sql"),
    ("icustay_hourly", "mimic-iv/concepts_duckdb/demographics/icustay_hourly.sql"),
    ("weight_durations", "mimic-iv/concepts_duckdb/demographics/weight_durations.sql"),
    ("charlson", "mimic-iv/concepts_duckdb/comorbidity/charlson.sql"),
    ("vitalsign", "mimic-iv/concepts_duckdb/measurement/vitalsign.sql"),
    ("urine_output", "mimic-iv/concepts_duckdb/measurement/urine_output.sql"),
    ("urine_output_rate", "mimic-iv/concepts_duckdb/measurement/urine_output_rate.sql"),
    ("gcs", "mimic-iv/concepts_duckdb/measurement/gcs.sql"),
    ("bg", "mimic-iv/concepts_duckdb/measurement/bg.sql"),
    ("chemistry", "mimic-iv/concepts_duckdb/measurement/chemistry.sql"),
    ("complete_blood_count", "mimic-iv/concepts_duckdb/measurement/complete_blood_count.sql"),
    ("blood_differential", "mimic-iv/concepts_duckdb/measurement/blood_differential.sql"),
    ("coagulation", "mimic-iv/concepts_duckdb/measurement/coagulation.sql"),
    ("enzyme", "mimic-iv/concepts_duckdb/measurement/enzyme.sql"),
    ("height", "mimic-iv/concepts_duckdb/measurement/height.sql"),
    ("first_day_vitalsign", "mimic-iv/concepts_duckdb/firstday/first_day_vitalsign.sql"),
    ("first_day_urine_output", "mimic-iv/concepts_duckdb/firstday/first_day_urine_output.sql"),
    ("first_day_gcs", "mimic-iv/concepts_duckdb/firstday/first_day_gcs.sql"),
    ("first_day_lab", "mimic-iv/concepts_duckdb/firstday/first_day_lab.sql"),
    ("first_day_bg", "mimic-iv/concepts_duckdb/firstday/first_day_bg.sql"),
    ("first_day_bg_art", "mimic-iv/concepts_duckdb/firstday/first_day_bg_art.sql"),
    ("first_day_height", "mimic-iv/concepts_duckdb/firstday/first_day_height.sql"),
    ("first_day_weight", "mimic-iv/concepts_duckdb/firstday/first_day_weight.sql"),
    ("dobutamine", "mimic-iv/concepts_duckdb/medication/dobutamine.sql"),
    ("dopamine", "mimic-iv/concepts_duckdb/medication/dopamine.sql"),
    ("epinephrine", "mimic-iv/concepts_duckdb/medication/epinephrine.sql"),
    ("norepinephrine", "mimic-iv/concepts_duckdb/medication/norepinephrine.sql"),
    ("phenylephrine", "mimic-iv/concepts_duckdb/medication/phenylephrine.sql"),
    ("vasopressin", "mimic-iv/concepts_duckdb/medication/vasopressin.sql"),
    ("milrinone", "mimic-iv/concepts_duckdb/medication/milrinone.sql"),
    ("vasoactive_agent", "mimic-iv/concepts_duckdb/medication/vasoactive_agent.sql"),
    (
        "norepinephrine_equivalent_dose",
        "mimic-iv/concepts_duckdb/medication/norepinephrine_equivalent_dose.sql",
    ),
    ("rrt", "mimic-iv/concepts_duckdb/treatment/rrt.sql"),
    ("crrt", "mimic-iv/concepts_duckdb/treatment/crrt.sql"),
    ("first_day_rrt", "mimic-iv/concepts_duckdb/firstday/first_day_rrt.sql"),
    ("ventilator_setting", "mimic-iv/concepts_duckdb/measurement/ventilator_setting.sql"),
    ("oxygen_delivery", "mimic-iv/concepts_duckdb/measurement/oxygen_delivery.sql"),
    ("ventilation", "mimic-iv/concepts_duckdb/treatment/ventilation.sql"),
    ("first_day_sofa", "mimic-iv/concepts_duckdb/firstday/first_day_sofa.sql"),
    ("oasis", "mimic-iv/concepts_duckdb/score/oasis.sql"),
    ("sofa", "mimic-iv/concepts_duckdb/score/sofa.sql"),
    ("antibiotic", "mimic-iv/concepts_duckdb/medication/antibiotic.sql"),
    ("suspicion_of_infection", "mimic-iv/concepts_duckdb/sepsis/suspicion_of_infection.sql"),
    ("sepsis3", "mimic-iv/concepts_duckdb/sepsis/sepsis3.sql"),
]

PRIMARY_KEYS = {
    "age": ["hadm_id"],
    "icustay_times": ["stay_id"],
    "icustay_hourly": ["stay_id", "hr"],
    "weight_durations": ["stay_id", "starttime", "endtime"],
    "charlson": ["hadm_id"],
    "vitalsign": ["stay_id", "charttime"],
    "urine_output": ["stay_id", "charttime"],
    "urine_output_rate": ["stay_id", "hr"],
    "gcs": ["stay_id", "charttime"],
    "bg": ["subject_id", "charttime"],
    "chemistry": ["subject_id", "charttime"],
    "complete_blood_count": ["subject_id", "charttime"],
    "blood_differential": ["subject_id", "charttime"],
    "coagulation": ["subject_id", "charttime"],
    "enzyme": ["subject_id", "charttime"],
    "height": ["stay_id", "charttime"],
    "first_day_vitalsign": ["stay_id"],
    "first_day_urine_output": ["stay_id"],
    "first_day_gcs": ["stay_id"],
    "first_day_lab": ["stay_id"],
    "first_day_bg": ["stay_id"],
    "first_day_bg_art": ["stay_id"],
    "first_day_height": ["stay_id"],
    "first_day_weight": ["stay_id"],
    "dobutamine": ["stay_id", "linkorderid", "starttime", "endtime"],
    "dopamine": ["stay_id", "linkorderid", "starttime", "endtime"],
    "epinephrine": ["stay_id", "linkorderid", "starttime", "endtime"],
    "norepinephrine": ["stay_id", "linkorderid", "starttime", "endtime"],
    "phenylephrine": ["stay_id", "linkorderid", "starttime", "endtime"],
    "vasopressin": ["stay_id", "linkorderid", "starttime", "endtime"],
    "milrinone": ["stay_id", "linkorderid", "starttime", "endtime"],
    "vasoactive_agent": ["stay_id", "starttime", "endtime"],
    "norepinephrine_equivalent_dose": ["stay_id", "starttime", "endtime"],
    "rrt": ["stay_id", "charttime"],
    "crrt": ["stay_id", "charttime"],
    "first_day_rrt": ["stay_id"],
    "ventilator_setting": ["stay_id", "charttime"],
    "oxygen_delivery": ["stay_id", "charttime"],
    "ventilation": ["stay_id", "starttime", "endtime", "ventilation_status"],
    "first_day_sofa": ["stay_id"],
    "oasis": ["stay_id"],
    "sofa": ["stay_id", "hr"],
    "antibiotic": ["subject_id", "hadm_id", "starttime", "stoptime", "antibiotic"],
    "suspicion_of_infection": ["subject_id", "stay_id", "ab_id"],
    "sepsis3": ["stay_id"],
    "non_neurologic_sofa_0_24h": ["stay_id"],
    "non_neurologic_sofa_0_6h": ["stay_id"],
    "charlson_timing": ["subject_id"],
    "early_organ_support_0_24h": ["stay_id"],
    "maintenance_dialysis": ["subject_id"],
}

MODEL_VARIABLES = [
    "psych_primary_documented_by_index",
    "psych_primary_strict_prior",
    "psych_primary_index_only",
    "psych_depressive",
    "psych_anxiety",
    "psych_trauma_stressor",
    "psych_bipolar",
    "psych_psychotic",
    "psych_common_mental_disorder",
    "psych_serious_mental_illness",
    "delirium_status_72h",
    "delirium_status_48h",
    "joint_exposure_4level",
    "death_365d_main",
    "death_365d_include_same_day",
    "death_same_day_discharge",
    "time_to_death_or_censor_365d",
    "readmission_90d_event",
    "time_to_readmission_90d",
    "death_before_readmission_90d",
    "icu_readmission_365d_event",
    "time_to_icu_readmission_365d",
    "death_before_icu_readmission_365d",
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
    "nonneurologic_sofa_zero_imputed",
    "nonneurologic_sofa_observed_components_n",
    "invasive_ventilation_0_24h",
    "vasopressor_any_0_24h",
    "rrt_any_0_24h",
    "full_sofa_official_first_day",
    "oasis_official_first_day",
    "sepsis3_index",
    "insurance_group",
    "language_group",
    "marital_status_group",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def pct(num, den) -> float | None:
    if den is None or den == 0 or pd.isna(den):
        return None
    if num is None or pd.isna(num):
        num = 0
    return round(float(num) / float(den) * 100.0, 3)


def q(con: duckdb.DuckDBPyConnection, sql: str, params=None) -> pd.DataFrame:
    return con.execute(sql, params or []).fetchdf()


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            clean = df[col].dropna()
            if not clean.empty and np.isclose(clean, np.round(clean)).all():
                df[col] = df[col].round().astype("Int64")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_No rows._"
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for col in cols:
            val = "" if pd.isna(row[col]) else str(row[col])
            values.append(val.replace("|", "\\|").replace("\n", "<br>"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def adapted_filename(relative_sql_path: str) -> Path:
    return ADAPTED_SQL_DIR / relative_sql_path.replace("/", "__")


def duplicate_key_count(con: duckdb.DuckDBPyConnection, table: str, keys: list[str]) -> int | None:
    cols = set(
        q(
            con,
            """
            select column_name
            from information_schema.columns
            where table_schema = ?
              and table_name = ?
            """,
            [DERIVED_SCHEMA, table],
        )["column_name"].astype(str)
    )
    if not keys or any(k not in cols for k in keys):
        return None
    key_expr = ", ".join(keys)
    return int(
        q(
            con,
            f"""
            select coalesce(sum(cnt - 1), 0) as duplicate_rows
            from (
                select {key_expr}, count(*) as cnt
                from {DERIVED_SCHEMA}.{table}
                group by {key_expr}
                having count(*) > 1
            )
            """,
        )["duplicate_rows"].iloc[0]
        or 0
    )


def time_logic_issue_count(con: duckdb.DuckDBPyConnection, table: str) -> int | None:
    cols = set(
        q(
            con,
            """
            select column_name
            from information_schema.columns
            where table_schema = ?
              and table_name = ?
            """,
            [DERIVED_SCHEMA, table],
        )["column_name"].astype(str)
    )
    if {"starttime", "endtime"}.issubset(cols):
        return int(
            q(
                con,
                f"select count(*) as n from {DERIVED_SCHEMA}.{table} where endtime < starttime",
            )["n"].iloc[0]
        )
    if {"intime", "outtime"}.issubset(cols):
        return int(
            q(
                con,
                f"select count(*) as n from {DERIVED_SCHEMA}.{table} where outtime <= intime",
            )["n"].iloc[0]
        )
    return None


def setup_schemas(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"create schema if not exists {DERIVED_SCHEMA}")
    con.execute(f"create schema if not exists {ANALYSIS_SCHEMA}")
    con.execute(
        f"""
        create table if not exists {DERIVED_SCHEMA}.concept_build_metadata (
            table_name varchar,
            official_commit varchar,
            official_sql_path varchar,
            official_sql_file varchar,
            official_sql_sha256 varchar,
            adapted_sql_file varchar,
            adapted_sql_sha256 varchar,
            build_time varchar,
            row_count bigint,
            primary_key varchar,
            duplicate_key_count bigint,
            time_logic_issue_count bigint,
            range_time_qc varchar,
            build_status varchar,
            build_note varchar
        )
        """
    )


def execute_formal_sql(con: duckdb.DuckDBPyConnection, sql_text: str) -> None:
    sql_text = sql_text.replace("mimiciv_derived.", f"{DERIVED_SCHEMA}.")
    sql_text = sql_text.replace("mimiciv_hosp.", "hosp.")
    sql_text = sql_text.replace("mimiciv_icu.", "icu.")
    con.execute(sql_text)


def build_official_concepts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    con.execute(f"delete from {DERIVED_SCHEMA}.concept_build_metadata")
    rows: list[dict] = []
    for table_name, rel_path in OFFICIAL_SEQUENCE:
        official_path = OFFICIAL_ARCHIVE_DIR / rel_path
        adapted_path = adapted_filename(rel_path)
        started = datetime.now().isoformat(timespec="seconds")
        status = "built"
        note = ""
        try:
            execute_formal_sql(con, adapted_path.read_text(encoding="utf-8"))
            row_count = int(q(con, f"select count(*) as n from {DERIVED_SCHEMA}.{table_name}")["n"].iloc[0])
            key = PRIMARY_KEYS.get(table_name, [])
            dup = duplicate_key_count(con, table_name, key)
            time_issues = time_logic_issue_count(con, table_name)
            qc = "range/time QC complete: duplicate key and time-order checks recorded"
        except Exception as exc:
            row_count = None
            key = PRIMARY_KEYS.get(table_name, [])
            dup = None
            time_issues = None
            status = "failed"
            qc = "not complete"
            note = f"{type(exc).__name__}: {str(exc)[:500]}"
            raise
        row = {
            "table_name": table_name,
            "official_commit": OFFICIAL_COMMIT,
            "official_sql_path": rel_path,
            "official_sql_file": str(official_path),
            "official_sql_sha256": sha256_path(official_path),
            "adapted_sql_file": str(adapted_path),
            "adapted_sql_sha256": sha256_path(adapted_path),
            "build_time": started,
            "row_count": row_count,
            "primary_key": ",".join(key),
            "duplicate_key_count": dup,
            "time_logic_issue_count": time_issues,
            "range_time_qc": qc,
            "build_status": status,
            "build_note": note,
        }
        rows.append(row)
        con.register("concept_meta_row", pd.DataFrame([row]))
        con.execute(f"insert into {DERIVED_SCHEMA}.concept_build_metadata select * from concept_meta_row")
        con.unregister("concept_meta_row")
        print(f"built {table_name}: {row_count:,} rows")
    return pd.DataFrame(rows)


def official_concepts_ready(con: duckdb.DuckDBPyConnection) -> bool:
    existing = set(
        q(
            con,
            """
            select table_name
            from information_schema.tables
            where table_schema = ?
            """,
            [DERIVED_SCHEMA],
        )["table_name"].astype(str)
    )
    expected_tables = {name for name, _ in OFFICIAL_SEQUENCE}
    if not expected_tables.issubset(existing):
        return False
    meta_n = int(
        q(
            con,
            f"""
            select count(*) as n
            from {DERIVED_SCHEMA}.concept_build_metadata
            where table_name in ({",".join(["?"] * len(expected_tables))})
            """,
            sorted(expected_tables),
        )["n"].iloc[0]
    )
    return meta_n >= len(expected_tables)


def build_index_base(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.index_base_v1;
        create table {DERIVED_SCHEMA}.index_base_v1 as
        with index_icu as (
            select
                ie.subject_id,
                ie.hadm_id,
                ie.stay_id,
                ie.first_careunit,
                ie.last_careunit,
                ie.intime,
                ie.outtime,
                ie.los as icu_los_days,
                p.gender,
                p.anchor_age,
                p.anchor_year,
                p.anchor_year_group,
                p.dod,
                a.admittime,
                a.dischtime,
                a.deathtime,
                a.admission_type,
                a.admission_location,
                a.discharge_location,
                a.insurance,
                a.language,
                a.marital_status,
                a.race,
                a.hospital_expire_flag,
                p.anchor_age + date_part('year', a.admittime)::integer - p.anchor_year as age_at_index_admission,
                date_diff('hour', ie.intime, ie.outtime) as icu_los_hours,
                date_diff('hour', a.admittime, a.dischtime) / 24.0 as hospital_los_days,
                row_number() over (
                    partition by ie.subject_id
                    order by ie.intime, ie.stay_id
                ) as rn_subject
            from icu.icustays ie
            join hosp.patients p using (subject_id)
            join hosp.admissions a using (subject_id, hadm_id)
        )
        select *
        from index_icu
        where rn_subject = 1
          and anchor_age >= 18
          and icu_los_days >= 1
          and hospital_expire_flag = 0
        """
    )


def build_delirium(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.delirium_events_v1;
        create table {DERIVED_SCHEMA}.delirium_events_v1 as
        select
            row_number() over (
                order by ce.subject_id, ce.hadm_id, ce.stay_id, ce.charttime, ce.storetime, ce.value
            ) as assessment_id,
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            ib.intime,
            ib.outtime,
            ce.charttime,
            cast(ce.charttime as date) as assessment_date,
            ce.value,
            ce.valuenum,
            case
                when lower(coalesce(ce.value, '')) = 'positive' then 'positive'
                when lower(coalesce(ce.value, '')) = 'negative' then 'negative'
                when lower(coalesce(ce.value, '')) = 'uta' then 'uta'
                else 'other_or_missing'
            end as value_class
        from {DERIVED_SCHEMA}.index_base_v1 ib
        join icu.chartevents ce
          on ib.subject_id = ce.subject_id
         and ib.hadm_id = ce.hadm_id
         and ib.stay_id = ce.stay_id
        where ce.itemid = 228332
          and ce.charttime >= ib.intime
          and ce.charttime <= ib.outtime
        """
    )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.rass_events_v1;
        create table {DERIVED_SCHEMA}.rass_events_v1 as
        select
            row_number() over (
                order by ce.subject_id, ce.hadm_id, ce.stay_id, ce.charttime, ce.storetime, ce.value
            ) as rass_id,
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            ce.charttime,
            ce.value,
            ce.valuenum
        from {DERIVED_SCHEMA}.index_base_v1 ib
        join icu.chartevents ce
          on ib.subject_id = ce.subject_id
         and ib.hadm_id = ce.hadm_id
         and ib.stay_id = ce.stay_id
        where ce.itemid = 228096
          and ce.charttime >= ib.intime
          and ce.charttime <= ib.outtime
        """
    )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.nearest_rass_within_1h_v1;
        create table {DERIVED_SCHEMA}.nearest_rass_within_1h_v1 as
        with matches as (
            select
                d.assessment_id,
                r.rass_id,
                r.charttime as rass_charttime,
                r.value as rass_value,
                r.valuenum as rass_valuenum,
                abs(date_diff('second', d.charttime, r.charttime)) as abs_seconds,
                row_number() over (
                    partition by d.assessment_id
                    order by abs(date_diff('second', d.charttime, r.charttime)), r.charttime, r.rass_id
                ) as rn
            from {DERIVED_SCHEMA}.delirium_events_v1 d
            join {DERIVED_SCHEMA}.rass_events_v1 r
              on d.subject_id = r.subject_id
             and d.hadm_id = r.hadm_id
             and d.stay_id = r.stay_id
            where abs(date_diff('second', d.charttime, r.charttime)) <= 3600
        )
        select *
        from matches
        where rn = 1
        """
    )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.delirium_events_rass_valid_within_1h_v1;
        create table {DERIVED_SCHEMA}.delirium_events_rass_valid_within_1h_v1 as
        select
            d.*,
            nr.rass_valuenum,
            nr.rass_value,
            nr.abs_seconds,
            case when d.value_class = 'negative'
                   and nr.rass_valuenum <= -4
                 then 1 else 0 end as invalid_negative_rass_le_minus4
        from {DERIVED_SCHEMA}.delirium_events_v1 d
        left join {DERIVED_SCHEMA}.nearest_rass_within_1h_v1 nr
          on d.assessment_id = nr.assessment_id
        """
    )
    parts = []
    for window, hours in [("48h_two_negative_days", 48), ("72h_two_negative_days", 72)]:
        parts.append(
            f"""
            select
                subject_id,
                hadm_id,
                stay_id,
                '{window}' as delirium_window,
                assessment_count,
                positive_count,
                negative_count,
                negative_days,
                uta_count,
                rass_conflicting_negative_n,
                case
                    when positive_count > 0 then 'positive'
                    when positive_count = 0 and negative_days >= 2 then 'negative'
                    else 'unclassifiable'
                end as delirium_status
            from (
                select
                    ib.subject_id,
                    ib.hadm_id,
                    ib.stay_id,
                    count(de.assessment_id) as assessment_count,
                    sum(case when de.value_class = 'positive' then 1 else 0 end) as positive_count,
                    sum(case when de.value_class = 'negative' and de.invalid_negative_rass_le_minus4 = 0 then 1 else 0 end) as negative_count,
                    count(distinct case when de.value_class = 'negative' and de.invalid_negative_rass_le_minus4 = 0 then de.assessment_date end) as negative_days,
                    sum(case when de.value_class = 'uta' then 1 else 0 end) as uta_count,
                    sum(case when de.invalid_negative_rass_le_minus4 = 1 then 1 else 0 end) as rass_conflicting_negative_n
                from {DERIVED_SCHEMA}.index_base_v1 ib
                left join {DERIVED_SCHEMA}.delirium_events_rass_valid_within_1h_v1 de
                  on ib.subject_id = de.subject_id
                 and ib.hadm_id = de.hadm_id
                 and ib.stay_id = de.stay_id
                 and de.charttime >= ib.intime
                 and de.charttime <= least(ib.outtime, ib.intime + interval '{hours} hours')
                group by ib.subject_id, ib.hadm_id, ib.stay_id
            )
            """
        )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.delirium_window_classification_v1;
        create table {DERIVED_SCHEMA}.delirium_window_classification_v1 as
        {" union all ".join(parts)}
        """
    )


def build_psychiatric_exposure(con: duckdb.DuckDBPyConnection) -> None:
    mapping = pd.read_csv(PSYCH_MAPPING_PATH, dtype={"icd_code_norm": str, "icd_version": int})
    keep_cols = [
        "icd_code_norm",
        "icd_version",
        "clinical_priority_category",
        "primary_psychiatric_comorbidity_flag",
        "dementia_flag",
        "substance_flag",
    ]
    con.register("psych_mapping_df", mapping[keep_cols].drop_duplicates())
    con.execute(f"drop table if exists {DERIVED_SCHEMA}.psychiatric_code_mapping_v1_1")
    con.execute(
        f"""
        create table {DERIVED_SCHEMA}.psychiatric_code_mapping_v1_1 as
        select * from psych_mapping_df
        """
    )
    con.unregister("psych_mapping_df")
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.psych_dx_events_v1;
        create table {DERIVED_SCHEMA}.psych_dx_events_v1 as
        select
            ib.subject_id,
            ib.hadm_id as index_hadm_id,
            ib.admittime as index_admittime,
            m.clinical_priority_category,
            cast(m.primary_psychiatric_comorbidity_flag as integer) as primary_psychiatric_comorbidity_flag,
            cast(m.dementia_flag as integer) as dementia_flag,
            cast(m.substance_flag as integer) as substance_flag,
            dx.hadm_id as dx_hadm_id,
            adm.admittime as dx_admittime,
            dx.icd_code,
            dx.icd_version,
            case
                when adm.admittime < ib.admittime and dx.hadm_id <> ib.hadm_id then 'prior_admission'
                when dx.hadm_id = ib.hadm_id then 'index_admission'
                else 'after_index_or_uncertain'
            end as diagnosis_relation
        from {DERIVED_SCHEMA}.index_base_v1 ib
        join hosp.diagnoses_icd dx
          on ib.subject_id = dx.subject_id
        join hosp.admissions adm
          on dx.subject_id = adm.subject_id
         and dx.hadm_id = adm.hadm_id
        join {DERIVED_SCHEMA}.psychiatric_code_mapping_v1_1 m
          on upper(replace(dx.icd_code, '.', '')) = m.icd_code_norm
         and dx.icd_version = m.icd_version
        """
    )
    cat_exprs = []
    category_aliases = {
        "depressive_disorders": "psych_depressive",
        "anxiety_disorders": "psych_anxiety",
        "trauma_and_stressor_related_disorders": "psych_trauma_stressor",
        "bipolar_disorders": "psych_bipolar",
        "schizophrenia_spectrum_and_other_psychotic_disorders": "psych_psychotic",
    }
    for category, alias in category_aliases.items():
        cat_exprs.append(
            f"""
            max(case when e.clinical_priority_category = '{category}'
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
             then 1 else 0 end) as {alias}
            """
        )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.psych_flags_base_v1;
        create table {DERIVED_SCHEMA}.psych_flags_base_v1 as
        select
            ib.subject_id,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as psych_primary_strict_prior,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as psych_primary_documented_by_index,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation = 'index_admission'
                     then 1 else 0 end) as psych_primary_index_admission_recorded,
            max(case when e.dementia_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as dementia_strict_prior,
            max(case when e.dementia_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as dementia_documented_by_index,
            max(case when e.substance_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as substance_use_strict_prior,
            max(case when e.substance_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as substance_use_documented_by_index,
            {",".join(cat_exprs)}
        from {DERIVED_SCHEMA}.index_base_v1 ib
        left join {DERIVED_SCHEMA}.psych_dx_events_v1 e
          on ib.subject_id = e.subject_id
        group by ib.subject_id
        """
    )
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.psych_flags_v1;
        create or replace table {DERIVED_SCHEMA}.psych_flags_v1 as
        select
            *,
            case
                when psych_primary_documented_by_index = 1 and psych_primary_strict_prior = 0 then 1
                else 0
            end as psych_primary_index_only,
            greatest(psych_depressive, psych_anxiety, psych_trauma_stressor) as psych_common_mental_disorder,
            greatest(psych_bipolar, psych_psychotic) as psych_serious_mental_illness,
            psych_depressive + psych_anxiety + psych_trauma_stressor + psych_bipolar + psych_psychotic as psych_category_count,
            case
                when psych_primary_documented_by_index = 0 then 'no_documented_psychiatric_comorbidity'
                when psych_primary_strict_prior = 1 then 'strict_prior_psychiatric_comorbidity'
                else 'index_admission_only_psychiatric_comorbidity'
            end as psych_timing_group
        from {DERIVED_SCHEMA}.psych_flags_base_v1
        """
    )


def build_project_specific_tables(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows: list[dict] = []
    for filename, table_name in [
        ("non_neurologic_sofa_0_24h.sql", "non_neurologic_sofa_0_24h"),
        ("non_neurologic_sofa_0_6h.sql", "non_neurologic_sofa_0_6h"),
    ]:
        path = PROJECT_SQL_DIR / filename
        execute_formal_sql(con, path.read_text(encoding="utf-8"))
        row_count = int(q(con, f"select count(*) as n from {DERIVED_SCHEMA}.{table_name}")["n"].iloc[0])
        dup = duplicate_key_count(con, table_name, PRIMARY_KEYS[table_name])
        rows.append(
            {
                "table_name": table_name,
                "source": "project_specific",
                "script_path": str(path),
                "script_sha256": sha256_path(path),
                "row_count": row_count,
                "primary_key": ",".join(PRIMARY_KEYS[table_name]),
                "duplicate_key_count": dup,
                "qc_note": "CNS/GCS excluded; candidate missing strategies retained.",
            }
        )

    components = [
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
    component_max = ", ".join([f"max(coalesce(c.{col}, 0)) as {col}" for col in components])
    comorbidity_score_expr = """
        myocardial_infarct
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
    score_expr = f"index_age_score + {comorbidity_score_expr}"
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.charlson_timing_v1;
        create table {DERIVED_SCHEMA}.charlson_timing_v1 as
        with base as (
            select
                subject_id,
                hadm_id,
                admittime as index_admittime,
                age_at_index_admission as index_age,
                case
                    when age_at_index_admission <= 50 then 0
                    when age_at_index_admission <= 60 then 1
                    when age_at_index_admission <= 70 then 2
                    when age_at_index_admission <= 80 then 3
                    else 4
                end as index_age_score
            from {DERIVED_SCHEMA}.index_base_v1
        ),
        index_hadm as (
            select b.subject_id, c.charlson_comorbidity_index as charlson_index_hadm
            from base b
            left join {DERIVED_SCHEMA}.charlson c
              on b.hadm_id = c.hadm_id
        ),
        documented_components as (
            select b.subject_id, b.index_age_score, {component_max}
            from base b
            left join hosp.admissions adm
              on b.subject_id = adm.subject_id
             and adm.admittime <= b.index_admittime
            left join {DERIVED_SCHEMA}.charlson c
              on adm.hadm_id = c.hadm_id
            group by b.subject_id, b.index_age_score
        ),
        strict_components as (
            select b.subject_id, b.index_age_score, {component_max}
            from base b
            left join hosp.admissions adm
              on b.subject_id = adm.subject_id
             and adm.hadm_id <> b.hadm_id
             and adm.admittime < b.index_admittime
            left join {DERIVED_SCHEMA}.charlson c
              on adm.hadm_id = c.hadm_id
            group by b.subject_id, b.index_age_score
        ),
        documented_score as (
            select
                *,
                {comorbidity_score_expr} as charlson_comorbidity_only_documented_by_index,
                {score_expr} as charlson_documented_by_index
            from documented_components
        ),
        strict_score as (
            select
                *,
                {comorbidity_score_expr} as charlson_comorbidity_only_strict_prior,
                {score_expr} as charlson_strict_prior
            from strict_components
        )
        select
            b.subject_id,
            ih.charlson_index_hadm,
            ds.charlson_documented_by_index,
            ss.charlson_strict_prior,
            ds.charlson_comorbidity_only_documented_by_index,
            ss.charlson_comorbidity_only_strict_prior,
            ds.cerebrovascular_disease as charlson_cerebrovascular_disease_documented_by_index,
            ds.paraplegia as charlson_paraplegia_documented_by_index
        from base b
        left join index_hadm ih using (subject_id)
        left join documented_score ds using (subject_id)
        left join strict_score ss using (subject_id)
        """
    )

    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.early_organ_support_0_24h_v1;
        create table {DERIVED_SCHEMA}.early_organ_support_0_24h_v1 as
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            case when exists (
                select 1
                from {DERIVED_SCHEMA}.ventilation v
                where v.stay_id = ib.stay_id
                  and v.ventilation_status = 'InvasiveVent'
                  and v.starttime < least(ib.outtime, ib.intime + interval '24 hours')
                  and v.endtime > ib.intime
            ) then 1 else 0 end as invasive_ventilation_0_24h,
            case when exists (
                select 1
                from {DERIVED_SCHEMA}.vasoactive_agent v
                where v.stay_id = ib.stay_id
                  and v.starttime < least(ib.outtime, ib.intime + interval '24 hours')
                  and v.endtime > ib.intime
            ) then 1 else 0 end as vasopressor_any_0_24h,
            coalesce(fdrrt.dialysis_present, 0) as rrt_any_0_24h,
            case when exists (
                select 1
                from {DERIVED_SCHEMA}.crrt c
                where c.stay_id = ib.stay_id
                  and c.charttime >= ib.intime
                  and c.charttime < least(ib.outtime, ib.intime + interval '24 hours')
            ) then 1 else 0 end as crrt_any_0_24h
        from {DERIVED_SCHEMA}.index_base_v1 ib
        left join {DERIVED_SCHEMA}.first_day_rrt fdrrt
          on ib.stay_id = fdrrt.stay_id
        """
    )

    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.maintenance_dialysis_v1;
        create table {DERIVED_SCHEMA}.maintenance_dialysis_v1 as
        with dialysis_dx as (
            select distinct
                ib.subject_id,
                dx.hadm_id,
                adm.admittime,
                case
                    when adm.admittime < ib.admittime and dx.hadm_id <> ib.hadm_id then 'strict_prior'
                    when adm.admittime <= ib.admittime then 'documented_by_index'
                    else 'after_index'
                end as relation
            from {DERIVED_SCHEMA}.index_base_v1 ib
            join hosp.diagnoses_icd dx
              on ib.subject_id = dx.subject_id
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
            ib.subject_id,
            case when exists (
                select 1 from dialysis_dx d
                where d.subject_id = ib.subject_id
                  and d.relation in ('strict_prior', 'documented_by_index')
            ) then 1 else 0 end as maintenance_dialysis_documented_by_index,
            case when exists (
                select 1 from dialysis_dx d
                where d.subject_id = ib.subject_id
                  and d.relation = 'strict_prior'
            ) then 1 else 0 end as maintenance_dialysis_strict_prior
        from {DERIVED_SCHEMA}.index_base_v1 ib
        """
    )

    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.chronic_neurologic_disease_v1;
        create table {DERIVED_SCHEMA}.chronic_neurologic_disease_v1 as
        with dx_by_index as (
            select ib.subject_id, dx.icd_version, upper(replace(dx.icd_code, '.', '')) as code
            from {DERIVED_SCHEMA}.index_base_v1 ib
            join hosp.diagnoses_icd dx on ib.subject_id = dx.subject_id
            join hosp.admissions adm on dx.subject_id = adm.subject_id and dx.hadm_id = adm.hadm_id
            where dx.hadm_id = ib.hadm_id
               or (adm.admittime < ib.admittime and dx.hadm_id <> ib.hadm_id)
        )
        select
            ib.subject_id,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(331|332|333|334|335|340|341|342|343|344|345|438)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(G20|G21|G22|G23|G24|G25|G26|G30|G31|G32|G35|G36|G37|G40|G41|G80|G81|G82|G83|I69)'))
            ) then 1 else 0 end) as chronic_neurologic_disease
        from {DERIVED_SCHEMA}.index_base_v1 ib
        left join dx_by_index d using (subject_id)
        group by ib.subject_id
        """
    )

    for table_name in [
        "charlson_timing_v1",
        "early_organ_support_0_24h_v1",
        "maintenance_dialysis_v1",
        "chronic_neurologic_disease_v1",
    ]:
        short_name = table_name.replace("_v1", "")
        key = PRIMARY_KEYS.get(short_name, ["subject_id"])
        rows.append(
            {
                "table_name": table_name,
                "source": "project_specific",
                "script_path": str(Path(__file__)),
                "script_sha256": sha256_path(Path(__file__)),
                "row_count": int(q(con, f"select count(*) as n from {DERIVED_SCHEMA}.{table_name}")["n"].iloc[0]),
                "primary_key": ",".join(key),
                "duplicate_key_count": duplicate_key_count(con, table_name, key),
                "qc_note": "Project-specific formal variable table.",
            }
        )
    return pd.DataFrame(rows)


def build_analysis_dataset(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        drop table if exists {ANALYSIS_TABLE};
        create table {ANALYSIS_TABLE} as
        with service_first as (
            select *
            from (
                select
                    ib.subject_id,
                    ib.hadm_id,
                    s.curr_service,
                    row_number() over (
                        partition by ib.subject_id, ib.hadm_id
                        order by s.transfertime nulls last, s.curr_service nulls last
                    ) as rn
                from {DERIVED_SCHEMA}.index_base_v1 ib
                left join hosp.services s
                  on ib.subject_id = s.subject_id
                 and ib.hadm_id = s.hadm_id
            )
            where rn = 1
        ),
        later_hadm as (
            select
                ib.subject_id,
                ib.hadm_id,
                min(ra.admittime) as first_readmission_admittime
            from {DERIVED_SCHEMA}.index_base_v1 ib
            left join hosp.admissions ra
              on ib.subject_id = ra.subject_id
             and ra.hadm_id <> ib.hadm_id
             and ra.admittime > ib.dischtime
            group by ib.subject_id, ib.hadm_id
        ),
        later_icu as (
            select
                ib.subject_id,
                ib.hadm_id,
                min(ri.intime) as first_icu_readmission_intime
            from {DERIVED_SCHEMA}.index_base_v1 ib
            left join icu.icustays ri
              on ib.subject_id = ri.subject_id
             and ri.hadm_id <> ib.hadm_id
             and ri.intime > ib.dischtime
            left join hosp.admissions ra
              on ri.subject_id = ra.subject_id
             and ri.hadm_id = ra.hadm_id
            where ri.stay_id is null or ra.admittime > ib.dischtime
            group by ib.subject_id, ib.hadm_id
        ),
        calendar as (
            select
                ib.subject_id,
                cast(regexp_extract(ib.anchor_year_group, '([0-9]{{4}})', 1) as integer)
                  + (date_part('year', ib.dischtime)::integer - ib.anchor_year) as approximate_discharge_year_lower,
                cast(regexp_extract(ib.anchor_year_group, '.*([0-9]{{4}})', 1) as integer)
                  + (date_part('year', ib.dischtime)::integer - ib.anchor_year) as approximate_discharge_year_upper
            from {DERIVED_SCHEMA}.index_base_v1 ib
        ),
        event_times as (
            select
                ib.subject_id,
                ib.hadm_id,
                lh.first_readmission_admittime,
                li.first_icu_readmission_intime,
                case when lh.first_readmission_admittime > ib.dischtime
                       and lh.first_readmission_admittime <= ib.dischtime + interval 90 day
                     then 1 else 0 end as readmission_90d_event_flag,
                case when li.first_icu_readmission_intime > ib.dischtime
                       and li.first_icu_readmission_intime <= ib.dischtime + interval 365 day
                     then 1 else 0 end as icu_readmission_365d_event_flag,
                case when ib.dod is not null
                       and not (
                           ib.dod < cast(ib.admittime as date)
                           or (ib.dod >= cast(ib.admittime as date) and ib.dod < cast(ib.dischtime as date))
                       )
                       and ib.dod >= cast(ib.dischtime as date)
                       and ib.dod <= cast(ib.dischtime as date) + interval 90 day
                     then 1 else 0 end as valid_competing_death_90d,
                case when ib.dod is not null
                       and not (
                           ib.dod < cast(ib.admittime as date)
                           or (ib.dod >= cast(ib.admittime as date) and ib.dod < cast(ib.dischtime as date))
                       )
                       and ib.dod >= cast(ib.dischtime as date)
                       and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                     then 1 else 0 end as valid_competing_death_365d,
                case
                    when ib.dod = cast(ib.dischtime as date) then 0.5
                    else cast(date_diff('day', cast(ib.dischtime as date), ib.dod) as double)
                end as valid_death_time_days
            from {DERIVED_SCHEMA}.index_base_v1 ib
            left join later_hadm lh using (subject_id, hadm_id)
            left join later_icu li using (subject_id, hadm_id)
        )
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            ib.intime as index_icu_intime,
            ib.outtime as index_icu_outtime,
            ib.admittime as index_admittime,
            ib.dischtime as index_dischtime,
            1 as base_population,
            case when d72.delirium_status in ('positive', 'negative') then 1 else 0 end as delirium_classifiable_72h,
            case when d72.delirium_status in ('positive', 'negative') then 1 else 0 end as primary_analysis_cohort,
            case when d72.delirium_status in ('positive', 'negative')
                   and cal.approximate_discharge_year_upper <= 2021
                 then 1 else 0 end as conservative_readmission_cohort,
            coalesce(pf.psych_primary_documented_by_index, 0) as psych_primary_documented_by_index,
            coalesce(pf.psych_primary_strict_prior, 0) as psych_primary_strict_prior,
            coalesce(pf.psych_primary_index_only, 0) as psych_primary_index_only,
            coalesce(pf.psych_timing_group, 'no_documented_psychiatric_comorbidity') as psych_timing_group,
            coalesce(pf.psych_depressive, 0) as psych_depressive,
            coalesce(pf.psych_anxiety, 0) as psych_anxiety,
            coalesce(pf.psych_trauma_stressor, 0) as psych_trauma_stressor,
            coalesce(pf.psych_bipolar, 0) as psych_bipolar,
            coalesce(pf.psych_psychotic, 0) as psych_psychotic,
            coalesce(pf.psych_common_mental_disorder, 0) as psych_common_mental_disorder,
            coalesce(pf.psych_serious_mental_illness, 0) as psych_serious_mental_illness,
            coalesce(pf.psych_category_count, 0) as psych_category_count,
            coalesce(d72.delirium_status, 'unclassifiable') as delirium_status_72h,
            coalesce(d48.delirium_status, 'unclassifiable') as delirium_status_48h,
            case
                when coalesce(pf.psych_primary_documented_by_index, 0) = 0 and d72.delirium_status = 'negative'
                    then '1_no_primary_psych_no_delirium'
                when coalesce(pf.psych_primary_documented_by_index, 0) = 1 and d72.delirium_status = 'negative'
                    then '2_primary_psych_no_delirium'
                when coalesce(pf.psych_primary_documented_by_index, 0) = 0 and d72.delirium_status = 'positive'
                    then '3_no_primary_psych_delirium'
                when coalesce(pf.psych_primary_documented_by_index, 0) = 1 and d72.delirium_status = 'positive'
                    then '4_primary_psych_delirium'
                else 'excluded_unclassifiable_delirium'
            end as joint_exposure_4level,
            case when ib.dod > cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                 then 1 else 0 end as death_365d_main,
            case when ib.dod >= cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                 then 1 else 0 end as death_365d_include_same_day,
            case when ib.dod = cast(ib.dischtime as date) then 1 else 0 end as death_same_day_discharge,
            case
                when ib.dod < cast(ib.admittime as date) then 'dod_before_index_admission'
                when ib.dod >= cast(ib.admittime as date) and ib.dod < cast(ib.dischtime as date) then 'dod_between_index_admission_and_discharge'
                else 'none'
            end as death_date_logic_abnormal_flag,
            case
                when ib.dod < cast(ib.admittime as date)
                  or (ib.dod >= cast(ib.admittime as date) and ib.dod < cast(ib.dischtime as date))
                    then null
                when ib.dod > cast(ib.dischtime as date)
                  and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                    then date_diff('day', cast(ib.dischtime as date), ib.dod)
                else 365
            end as time_to_death_or_censor_365d,
            case
                when et.readmission_90d_event_flag = 1
                 and not (
                     et.valid_competing_death_90d = 1
                     and ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then 1
                else 0
            end as readmission_90d_event,
            case when et.readmission_90d_event_flag = 1
                 then date_diff('hour', ib.dischtime, et.first_readmission_admittime) / 24.0
                 else 90.0 end as time_to_readmission_90d,
            case
                when et.readmission_90d_event_flag = 1
                 and not (
                     et.valid_competing_death_90d = 1
                     and ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then 1
                when et.valid_competing_death_90d = 1
                 and (
                     et.readmission_90d_event_flag = 0
                     or ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then 2
                else 0
            end as readmission_90d_status,
            case
                when et.readmission_90d_event_flag = 1
                 and not (
                     et.valid_competing_death_90d = 1
                     and ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then date_diff('hour', ib.dischtime, et.first_readmission_admittime) / 24.0
                when et.valid_competing_death_90d = 1
                 and (
                     et.readmission_90d_event_flag = 0
                     or ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then et.valid_death_time_days
                else 90.0
            end as time_to_first_readmission_or_death_90d,
            case
                when et.valid_competing_death_90d = 1
                 and (
                     et.readmission_90d_event_flag = 0
                     or ib.dod < cast(et.first_readmission_admittime as date)
                 )
                    then 1
                else 0
            end as death_before_readmission_90d,
            case
                when et.icu_readmission_365d_event_flag = 1
                 and not (
                     et.valid_competing_death_365d = 1
                     and ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then 1
                else 0
            end as icu_readmission_365d_event,
            case when et.icu_readmission_365d_event_flag = 1
                 then date_diff('hour', ib.dischtime, et.first_icu_readmission_intime) / 24.0
                 else 365.0 end as time_to_icu_readmission_365d,
            case
                when et.icu_readmission_365d_event_flag = 1
                 and not (
                     et.valid_competing_death_365d = 1
                     and ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then 1
                when et.valid_competing_death_365d = 1
                 and (
                     et.icu_readmission_365d_event_flag = 0
                     or ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then 2
                else 0
            end as icu_readmission_365d_status,
            case
                when et.icu_readmission_365d_event_flag = 1
                 and not (
                     et.valid_competing_death_365d = 1
                     and ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then date_diff('hour', ib.dischtime, et.first_icu_readmission_intime) / 24.0
                when et.valid_competing_death_365d = 1
                 and (
                     et.icu_readmission_365d_event_flag = 0
                     or ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then et.valid_death_time_days
                else 365.0
            end as time_to_first_icu_readmission_or_death_365d,
            case
                when et.valid_competing_death_365d = 1
                 and (
                     et.icu_readmission_365d_event_flag = 0
                     or ib.dod < cast(et.first_icu_readmission_intime as date)
                 )
                    then 1
                else 0
            end as death_before_icu_readmission_365d,
            ib.age_at_index_admission,
            coalesce(ib.gender, 'Unknown') as sex_recorded,
            case
                when ib.race is null or regexp_matches(upper(ib.race), 'UNKNOWN|UNABLE|DECLINED|NOT SPECIFIED') then 'Unknown-Unable'
                when regexp_matches(upper(ib.race), 'HISPANIC|LATINO|SOUTH AMERICAN') then 'Hispanic-Latino'
                when regexp_matches(upper(ib.race), 'BLACK|AFRICAN') then 'Black'
                when regexp_matches(upper(ib.race), 'ASIAN') then 'Asian'
                when regexp_matches(upper(ib.race), 'WHITE|PORTUGUESE') then 'White'
                else 'Other-Multiple'
            end as race_group,
            ib.anchor_year_group,
            case
                when ib.admission_type is null then 'unknown'
                when regexp_matches(upper(ib.admission_type), 'ELECTIVE|SURGICAL SAME DAY') then 'elective'
                when regexp_matches(upper(ib.admission_type), 'OBSERVATION') then 'observation'
                when regexp_matches(upper(ib.admission_type), 'EMER|URGENT') then 'urgent-emergency'
                else 'other'
            end as admission_type_group,
            case
                when ib.admission_location is null or regexp_matches(upper(ib.admission_location), 'INFORMATION NOT AVAILABLE') then 'other-unknown'
                when regexp_matches(upper(ib.admission_location), 'EMERGENCY ROOM|WALK-IN') then 'ed'
                when regexp_matches(upper(ib.admission_location), 'TRANSFER FROM HOSPITAL') then 'transfer-hospital'
                when regexp_matches(upper(ib.admission_location), 'SKILLED NURSING') then 'transfer-facility'
                when regexp_matches(upper(ib.admission_location), 'CLINIC|PHYSICIAN') then 'clinic-physician'
                when regexp_matches(upper(ib.admission_location), 'PROCEDURE|PACU|SURGERY') then 'procedure'
                else 'other-unknown'
            end as admission_location_group,
            case
                when ib.first_careunit is null then 'Unknown'
                when regexp_matches(ib.first_careunit, 'Trauma|TSICU') then 'Trauma'
                when regexp_matches(ib.first_careunit, 'Neuro') then 'Neuro'
                when regexp_matches(ib.first_careunit, 'CVICU|CCU|Cardiac|Coronary') then 'CCU-CVICU'
                when regexp_matches(ib.first_careunit, 'MICU|Medical Intensive') then 'MICU'
                when regexp_matches(ib.first_careunit, 'SICU|Surgical Intensive') then 'SICU'
                else 'Mixed-other'
            end as first_careunit_group,
            coalesce(pu.prior_mimic_hospitalizations, 0) as prior_mimic_hospitalizations,
            coalesce(pu.prior_mimic_icu_stays, 0) as prior_mimic_icu_stays,
            true as prior_mimic_icu_stays_constant_nonestimable,
            ct.charlson_index_hadm,
            ct.charlson_documented_by_index,
            ct.charlson_strict_prior,
            ct.charlson_comorbidity_only_documented_by_index,
            ct.charlson_comorbidity_only_strict_prior,
            coalesce(pf.dementia_documented_by_index, 0) as dementia_documented_by_index,
            coalesce(pf.dementia_strict_prior, 0) as dementia_strict_prior,
            coalesce(pf.substance_use_documented_by_index, 0) as substance_use_documented_by_index,
            coalesce(pf.substance_use_strict_prior, 0) as substance_use_strict_prior,
            coalesce(cn.chronic_neurologic_disease, 0) as chronic_neurologic_disease,
            case
                when ib.admission_location is null or regexp_matches(upper(ib.admission_location), 'INFORMATION NOT AVAILABLE') then 'unknown'
                when regexp_matches(upper(ib.admission_location), 'SKILLED NURSING|LONG TERM|CHRONIC|NURSING') then 'institutional_care_proxy'
                else 'no_institutional_care_proxy'
            end as pre_admission_care_proxy,
            nn.respiratory_score,
            nn.coagulation_score,
            nn.liver_score,
            nn.cardiovascular_score,
            nn.renal_score,
            nn.respiratory_observed,
            nn.coagulation_observed,
            nn.liver_observed,
            nn.cardiovascular_observed,
            nn.renal_observed,
            nn.observed_components_n as nonneurologic_sofa_observed_components_n,
            nn.nonneurologic_sofa_zero_imputed,
            nn.nonneurologic_sofa_complete_case,
            nn.complete_case_flag as nonneurologic_sofa_complete_case_flag,
            eos.invasive_ventilation_0_24h,
            eos.vasopressor_any_0_24h,
            eos.rrt_any_0_24h,
            eos.crrt_any_0_24h,
            fds.sofa as full_sofa_0_24h,
            oas.oasis as oasis_0_24h,
            true as full_sofa_0_24h_deprecated,
            true as oasis_0_24h_deprecated,
            fds.sofa as full_sofa_official_first_day,
            oas.oasis as oasis_official_first_day,
            case when coalesce(sep.sepsis3, false) then 1 else 0 end as sepsis3_index,
            case
                when ib.insurance is null then 'other-unknown'
                when upper(ib.insurance) like '%MEDICARE%' then 'Medicare'
                when upper(ib.insurance) like '%MEDICAID%' then 'Medicaid'
                when upper(ib.insurance) like '%PRIVATE%' then 'Private'
                when upper(ib.insurance) like '%SELF%' then 'Self-pay'
                else 'other-unknown'
            end as insurance_group,
            case
                when ib.language is null or trim(ib.language) = '' or upper(ib.language) in ('?', 'UNKNOWN') then 'unknown'
                when upper(ib.language) like 'ENGLISH%' or upper(ib.language) = 'ENGL' then 'English'
                else 'non-English'
            end as language_group,
            case
                when ib.marital_status is null then 'unknown'
                when upper(ib.marital_status) like '%MARRIED%' then 'married-partnered'
                when upper(ib.marital_status) like '%SINGLE%' then 'single'
                when regexp_matches(upper(ib.marital_status), 'DIVORCED|SEPARATED') then 'divorced-separated'
                when upper(ib.marital_status) like '%WIDOW%' then 'widowed'
                else 'unknown'
            end as marital_status_group,
            case when lower(coalesce(ib.discharge_location, '')) like '%hospice%' then 1 else 0 end as hospice_discharge,
            case
                when ib.discharge_location is null then 'unknown'
                when ib.discharge_location = 'HOME' then 'home'
                when ib.discharge_location = 'HOME HEALTH CARE' then 'home_health'
                when ib.discharge_location = 'REHAB' then 'rehab'
                when regexp_matches(ib.discharge_location, 'SKILLED NURSING|CHRONIC|LONG TERM|ASSISTED LIVING') then 'snf_ltc'
                when ib.discharge_location = 'HOSPICE' then 'hospice'
                else 'other'
            end as discharge_destination_group,
            ib.icu_los_days,
            ib.hospital_los_days,
            md.maintenance_dialysis_documented_by_index,
            md.maintenance_dialysis_strict_prior,
            d72.assessment_count as delirium_assessment_count_72h,
            d72.uta_count as delirium_uta_count_72h,
            d72.rass_conflicting_negative_n as rass_conflicting_negative_n_72h,
            cal.approximate_discharge_year_lower,
            cal.approximate_discharge_year_upper,
            sf.curr_service as index_first_service,
            '{OFFICIAL_COMMIT}' as mimic_code_commit,
            'analysis_dataset_v1_1' as analysis_dataset_version,
            current_timestamp as dataset_build_timestamp
        from {DERIVED_SCHEMA}.index_base_v1 ib
        left join {DERIVED_SCHEMA}.delirium_window_classification_v1 d72
          on ib.subject_id = d72.subject_id and ib.hadm_id = d72.hadm_id and ib.stay_id = d72.stay_id
         and d72.delirium_window = '72h_two_negative_days'
        left join {DERIVED_SCHEMA}.delirium_window_classification_v1 d48
          on ib.subject_id = d48.subject_id and ib.hadm_id = d48.hadm_id and ib.stay_id = d48.stay_id
         and d48.delirium_window = '48h_two_negative_days'
        left join {DERIVED_SCHEMA}.psych_flags_v1 pf
          on ib.subject_id = pf.subject_id
        left join {DERIVED_SCHEMA}.prior_utilization_v1 pu
          on ib.subject_id = pu.subject_id
        left join {DERIVED_SCHEMA}.charlson_timing_v1 ct
          on ib.subject_id = ct.subject_id
        left join {DERIVED_SCHEMA}.chronic_neurologic_disease_v1 cn
          on ib.subject_id = cn.subject_id
        left join {DERIVED_SCHEMA}.non_neurologic_sofa_0_24h nn
          on ib.stay_id = nn.stay_id
        left join {DERIVED_SCHEMA}.early_organ_support_0_24h_v1 eos
          on ib.subject_id = eos.subject_id
         and ib.hadm_id = eos.hadm_id
         and ib.stay_id = eos.stay_id
        left join {DERIVED_SCHEMA}.first_day_sofa fds
          on ib.stay_id = fds.stay_id
        left join {DERIVED_SCHEMA}.oasis oas
          on ib.stay_id = oas.stay_id
        left join {DERIVED_SCHEMA}.sepsis3 sep
          on ib.stay_id = sep.stay_id
        left join {DERIVED_SCHEMA}.maintenance_dialysis_v1 md
          on ib.subject_id = md.subject_id
        left join event_times et
          on ib.subject_id = et.subject_id
         and ib.hadm_id = et.hadm_id
        left join calendar cal
          on ib.subject_id = cal.subject_id
        left join service_first sf
          on ib.subject_id = sf.subject_id
         and ib.hadm_id = sf.hadm_id
        """
    )


def build_prior_utilization(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        drop table if exists {DERIVED_SCHEMA}.prior_utilization_v1;
        create table {DERIVED_SCHEMA}.prior_utilization_v1 as
        select
            ib.subject_id,
            count(distinct adm.hadm_id) filter (
                where adm.hadm_id <> ib.hadm_id and adm.admittime < ib.admittime
            ) as prior_mimic_hospitalizations,
            count(distinct icu.stay_id) filter (
                where icu.stay_id <> ib.stay_id and icu.intime < ib.intime
            ) as prior_mimic_icu_stays
        from {DERIVED_SCHEMA}.index_base_v1 ib
        left join hosp.admissions adm
          on ib.subject_id = adm.subject_id
        left join icu.icustays icu
          on ib.subject_id = icu.subject_id
        group by ib.subject_id
        """
    )


def get_columns(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    return q(
        con,
        """
        select column_name
        from information_schema.columns
        where table_schema = ?
          and table_name = ?
        order by ordinal_position
        """,
        [schema, table],
    )["column_name"].astype(str).tolist()


def table_fingerprint(con: duckdb.DuckDBPyConnection) -> str:
    cols = get_columns(con, ANALYSIS_SCHEMA, ANALYSIS_TABLE_NAME)
    expr = " || '|' || ".join([f"coalesce(cast({c} as varchar), '')" for c in cols])
    return q(
        con,
        f"""
        select md5(string_agg(row_hash, '' order by subject_id)) as table_md5
        from (
            select md5({expr}) as row_hash, subject_id
            from {ANALYSIS_TABLE}
        )
        """,
    )["table_md5"].iloc[0]


def generate_qc(con: duckdb.DuckDBPyConnection, concept_meta: pd.DataFrame, project_meta: pd.DataFrame) -> dict:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    n = int(q(con, f"select count(*) as n from {ANALYSIS_TABLE}")["n"].iloc[0])
    classifiable = int(q(con, f"select sum(delirium_classifiable_72h) as n from {ANALYSIS_TABLE}")["n"].iloc[0])
    unclassifiable = n - classifiable
    primary = int(q(con, f"select sum(primary_analysis_cohort) as n from {ANALYSIS_TABLE}")["n"].iloc[0])
    conservative = int(q(con, f"select sum(conservative_readmission_cohort) as n from {ANALYSIS_TABLE}")["n"].iloc[0])

    row_count_qc = pd.DataFrame(
        [
            {"metric": "base_population_rows", "actual": n, "expected": EXPECTED["base_population_n"], "pass": n == EXPECTED["base_population_n"]},
            {"metric": "primary_analysis_cohort_rows", "actual": primary, "expected": EXPECTED["classifiable_n"], "pass": primary == EXPECTED["classifiable_n"]},
            {"metric": "delirium_classifiable_72h_rows", "actual": classifiable, "expected": EXPECTED["classifiable_n"], "pass": classifiable == EXPECTED["classifiable_n"]},
            {"metric": "delirium_unclassifiable_72h_rows", "actual": unclassifiable, "expected": EXPECTED["unclassifiable_n"], "pass": unclassifiable == EXPECTED["unclassifiable_n"]},
            {"metric": "conservative_readmission_cohort_rows", "actual": conservative, "expected": 24033, "pass": conservative == 24033},
        ]
    )
    write_csv(row_count_qc, QC_DIR / "analysis_dataset_row_count_qc.csv")

    key_rows = []
    for key in ["subject_id", "hadm_id", "stay_id"]:
        dup = int(
            q(
                con,
                f"""
                select coalesce(sum(cnt - 1), 0) as duplicate_rows
                from (
                    select {key}, count(*) as cnt
                    from {ANALYSIS_TABLE}
                    group by {key}
                    having count(*) > 1
                )
                """,
            )["duplicate_rows"].iloc[0]
            or 0
        )
        key_rows.append({"key": key, "duplicate_rows": dup, "pass": dup == 0})
    write_csv(pd.DataFrame(key_rows), QC_DIR / "analysis_dataset_key_qc.csv")

    cols = get_columns(con, ANALYSIS_SCHEMA, ANALYSIS_TABLE_NAME)
    miss_rows = []
    for col in cols:
        missing = int(q(con, f"select count(*) as n from {ANALYSIS_TABLE} where {col} is null")["n"].iloc[0])
        miss_rows.append(
            {
                "variable": col,
                "missing_n": missing,
                "nonmissing_n": n - missing,
                "denominator": n,
                "missing_percent": pct(missing, n),
                "model_variable": col in MODEL_VARIABLES,
            }
        )
    write_csv(pd.DataFrame(miss_rows), QC_DIR / "analysis_dataset_missingness.csv")

    numeric_cols = q(
        con,
        """
        select column_name
        from information_schema.columns
        where table_schema = ?
          and table_name = ?
          and data_type in ('BIGINT','INTEGER','DOUBLE','FLOAT','REAL','DECIMAL','HUGEINT','UBIGINT')
        order by ordinal_position
        """,
        [ANALYSIS_SCHEMA, ANALYSIS_TABLE_NAME],
    )["column_name"].astype(str).tolist()
    range_rows = []
    for col in numeric_cols:
        row = q(
            con,
            f"""
            select
                count({col}) as nonmissing_n,
                min({col}) as min_value,
                quantile_cont({col}, 0.25) as p25,
                median({col}) as median_value,
                quantile_cont({col}, 0.75) as p75,
                max({col}) as max_value
            from {ANALYSIS_TABLE}
            """
        ).iloc[0].to_dict()
        row["variable"] = col
        range_rows.append(row)
    write_csv(pd.DataFrame(range_rows), QC_DIR / "analysis_dataset_range_qc.csv")

    time_logic = q(
        con,
        f"""
        select 'icu_time_order_error' as metric, count(*) as count
        from {ANALYSIS_TABLE}
        where index_icu_outtime <= index_icu_intime
        union all
        select 'hospital_time_order_error', count(*)
        from {ANALYSIS_TABLE}
        where index_dischtime < index_admittime
        union all
        select 'icu_before_hospital_admission', count(*)
        from {ANALYSIS_TABLE}
        where index_icu_intime < index_admittime
        union all
        select 'icu_discharge_date_after_hospital_discharge_date', count(*)
        from {ANALYSIS_TABLE}
        where cast(index_icu_outtime as date) > cast(index_dischtime as date)
        union all
        select 'death_and_readmission_90d_both_coded', count(*)
        from {ANALYSIS_TABLE}
        where readmission_90d_event = 1 and death_before_readmission_90d = 1
        union all
        select 'death_and_icu_readmission_365d_both_coded', count(*)
        from {ANALYSIS_TABLE}
        where icu_readmission_365d_event = 1 and death_before_icu_readmission_365d = 1
        union all
        select 'death_date_logic_abnormal_any', count(*)
        from {ANALYSIS_TABLE}
        where death_date_logic_abnormal_flag <> 'none'
        """
    )
    nonblocking_time_metrics = [
        "death_date_logic_abnormal_any",
        "icu_before_hospital_admission",
        "icu_discharge_date_after_hospital_discharge_date",
    ]
    time_logic["pass"] = time_logic.apply(
        lambda r: True if r["metric"] in nonblocking_time_metrics else r["count"] == 0,
        axis=1,
    )
    write_csv(time_logic, QC_DIR / "analysis_dataset_time_logic_qc.csv")
    time_warning = q(
        con,
        f"""
        select
            'icu_intime_before_hospital_admittime' as warning,
            count(*) as n,
            min(date_diff('minute', index_icu_intime, index_admittime)) as min_minutes,
            quantile_cont(date_diff('minute', index_icu_intime, index_admittime), 0.25) as p25_minutes,
            median(date_diff('minute', index_icu_intime, index_admittime)) as median_minutes,
            quantile_cont(date_diff('minute', index_icu_intime, index_admittime), 0.75) as p75_minutes,
            max(date_diff('minute', index_icu_intime, index_admittime)) as max_minutes,
            sum(case when cast(index_icu_intime as date) = cast(index_admittime as date) then 1 else 0 end) as same_calendar_date_n,
            sum(case when date_diff('hour', index_icu_intime, index_admittime) <= 6 then 1 else 0 end) as within_6h_n,
            sum(case when date_diff('hour', index_icu_intime, index_admittime) <= 24 then 1 else 0 end) as within_24h_n,
            sum(delirium_classifiable_72h) as classifiable_n,
            'Known MIMIC timestamp boundary issue; not used to change the frozen cohort.' as interpretation
        from {ANALYSIS_TABLE}
        where index_icu_intime < index_admittime
        """
    )
    write_csv(time_warning, QC_DIR / "analysis_dataset_time_logic_warning_summary.csv")

    cat_cols = [
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
        "pre_admission_care_proxy",
        "psych_timing_group",
        "delirium_status_72h",
        "delirium_status_48h",
        "joint_exposure_4level",
        "index_first_service",
    ]
    cat_rows = []
    for col in cat_cols:
        df = q(
            con,
            f"""
            select
                '{col}' as variable,
                coalesce(cast({col} as varchar), 'Missing') as level,
                count(*) as n
            from {ANALYSIS_TABLE}
            group by level
            order by n desc, level
            """
        )
        df["denominator"] = n
        df["percent"] = [pct(x, n) for x in df["n"]]
        cat_rows.append(df)
    write_csv(pd.concat(cat_rows, ignore_index=True), QC_DIR / "analysis_dataset_category_levels.csv")

    cohort_counts = q(
        con,
        f"""
        select 'base_population' as cohort, count(*) as n from {ANALYSIS_TABLE}
        union all select 'delirium_classifiable_72h', sum(delirium_classifiable_72h) from {ANALYSIS_TABLE}
        union all select 'delirium_unclassifiable_72h', sum(case when delirium_classifiable_72h = 0 then 1 else 0 end) from {ANALYSIS_TABLE}
        union all select 'primary_analysis_cohort', sum(primary_analysis_cohort) from {ANALYSIS_TABLE}
        union all select 'conservative_readmission_cohort', sum(conservative_readmission_cohort) from {ANALYSIS_TABLE}
        """
    )
    write_csv(cohort_counts, QC_DIR / "analysis_dataset_cohort_counts.csv")

    four = q(
        con,
        f"""
        select
            joint_exposure_4level,
            count(*) as n,
            sum(death_365d_main) as death_365d_main_n,
            round(100.0 * sum(death_365d_main) / nullif(count(*), 0), 3) as death_365d_main_percent,
            sum(readmission_90d_event) as readmission_90d_n,
            round(100.0 * sum(readmission_90d_event) / nullif(count(*), 0), 3) as readmission_90d_percent,
            sum(icu_readmission_365d_event) as icu_readmission_365d_n,
            round(100.0 * sum(icu_readmission_365d_event) / nullif(count(*), 0), 3) as icu_readmission_365d_percent
        from {ANALYSIS_TABLE}
        group by joint_exposure_4level
        order by joint_exposure_4level
        """
    )
    write_csv(four, QC_DIR / "analysis_dataset_four_group_counts.csv")

    outcome = q(
        con,
        f"""
        select 'primary_analysis_cohort' as population,
            count(*) as n,
            sum(death_365d_main) as death_365d_main_n,
            sum(readmission_90d_event) as readmission_90d_n,
            sum(icu_readmission_365d_event) as icu_readmission_365d_n
        from {ANALYSIS_TABLE}
        where primary_analysis_cohort = 1
        union all
        select 'conservative_readmission_cohort' as population,
            count(*) as n,
            sum(death_365d_main) as death_365d_main_n,
            sum(readmission_90d_event) as readmission_90d_n,
            sum(icu_readmission_365d_event) as icu_readmission_365d_n
        from {ANALYSIS_TABLE}
        where conservative_readmission_cohort = 1
        union all
        select 'base_population' as population,
            count(*) as n,
            sum(death_365d_main) as death_365d_main_n,
            sum(readmission_90d_event) as readmission_90d_n,
            sum(icu_readmission_365d_event) as icu_readmission_365d_n
        from {ANALYSIS_TABLE}
        """
    )
    write_csv(outcome, QC_DIR / "analysis_dataset_outcome_counts.csv")

    competing_status = q(
        con,
        f"""
        with populations as (
            select 'full_classifiable_cohort' as population, *
            from {ANALYSIS_TABLE}
            where primary_analysis_cohort = 1
            union all
            select 'conservative_readmission_cohort' as population, *
            from {ANALYSIS_TABLE}
            where conservative_readmission_cohort = 1
        ),
        status_counts as (
            select
                population,
                'readmission_90d' as outcome,
                readmission_90d_status as status,
                count(*) as n
            from populations
            group by population, readmission_90d_status
            union all
            select
                population,
                'icu_readmission_365d' as outcome,
                icu_readmission_365d_status as status,
                count(*) as n
            from populations
            group by population, icu_readmission_365d_status
        )
        select
            outcome,
            population,
            status,
            case
                when status = 0 then 'no_target_event_no_competing_death'
                when status = 1 then 'target_event'
                when status = 2 then 'competing_death_before_target_event'
                else 'unexpected'
            end as status_label,
            n,
            sum(n) over (partition by outcome, population) as denominator,
            round(100.0 * n / nullif(sum(n) over (partition by outcome, population), 0), 3) as percent
        from status_counts
        order by outcome, population, status
        """
    )
    write_csv(competing_status, QC_DIR / "analysis_dataset_competing_risk_status_counts.csv")

    competing_time_qc = q(
        con,
        f"""
        with death_times as (
            select
                a.*,
                ib.dod,
                case
                    when ib.dod = cast(a.index_dischtime as date) then 0.5
                    when ib.dod is not null then date_diff('day', cast(a.index_dischtime as date), ib.dod)
                    else null
                end as valid_death_time_days
            from {ANALYSIS_TABLE} a
            left join {DERIVED_SCHEMA}.index_base_v1 ib
                on a.subject_id = ib.subject_id
               and a.hadm_id = ib.hadm_id
               and a.stay_id = ib.stay_id
        )
        select
            'readmission_status1_time_equals_target_event_time' as qc_check,
            count(*) as checked_n,
            sum(case when abs(time_to_first_readmission_or_death_90d - time_to_readmission_90d) <= 0.000001 then 0 else 1 end) as fail_n
        from death_times
        where readmission_90d_status = 1
        union all
        select
            'readmission_status2_time_equals_death_time',
            count(*),
            sum(case when abs(time_to_first_readmission_or_death_90d - valid_death_time_days) <= 0.000001 then 0 else 1 end)
        from death_times
        where readmission_90d_status = 2
        union all
        select
            'readmission_status0_time_equals_90',
            count(*),
            sum(case when abs(time_to_first_readmission_or_death_90d - 90.0) <= 0.000001 then 0 else 1 end)
        from death_times
        where readmission_90d_status = 0
        union all
        select
            'readmission_no_target_and_competing_death_double_code',
            count(*),
            sum(case when (readmission_90d_status = 1 and death_before_readmission_90d = 1)
                      or (readmission_90d_status = 2 and readmission_90d_event = 1)
                     then 1 else 0 end)
        from death_times
        union all
        select
            'icu_readmission_status1_time_equals_target_event_time',
            count(*),
            sum(case when abs(time_to_first_icu_readmission_or_death_365d - time_to_icu_readmission_365d) <= 0.000001 then 0 else 1 end)
        from death_times
        where icu_readmission_365d_status = 1
        union all
        select
            'icu_readmission_status2_time_equals_death_time',
            count(*),
            sum(case when abs(time_to_first_icu_readmission_or_death_365d - valid_death_time_days) <= 0.000001 then 0 else 1 end)
        from death_times
        where icu_readmission_365d_status = 2
        union all
        select
            'icu_readmission_status0_time_equals_365',
            count(*),
            sum(case when abs(time_to_first_icu_readmission_or_death_365d - 365.0) <= 0.000001 then 0 else 1 end)
        from death_times
        where icu_readmission_365d_status = 0
        union all
        select
            'icu_readmission_no_target_and_competing_death_double_code',
            count(*),
            sum(case when (icu_readmission_365d_status = 1 and death_before_icu_readmission_365d = 1)
                      or (icu_readmission_365d_status = 2 and icu_readmission_365d_event = 1)
                     then 1 else 0 end)
        from death_times
        """
    )
    competing_time_qc["pass"] = competing_time_qc["fail_n"] == 0
    write_csv(competing_time_qc, QC_DIR / "analysis_dataset_competing_risk_time_qc.csv")

    icu_mapping = q(
        con,
        f"""
        select
            coalesce(v1.first_careunit_group, 'Missing') as first_careunit_group_v1,
            coalesce(v11.first_careunit_group, 'Missing') as first_careunit_group_v1_1,
            count(*) as n,
            sum(v11.primary_analysis_cohort) as primary_analysis_cohort_n
        from {ANALYSIS_SCHEMA}.analysis_dataset_v1 v1
        inner join {ANALYSIS_TABLE} v11
            on v1.subject_id = v11.subject_id
           and v1.hadm_id = v11.hadm_id
           and v1.stay_id = v11.stay_id
        group by first_careunit_group_v1, first_careunit_group_v1_1
        order by n desc, first_careunit_group_v1, first_careunit_group_v1_1
        """
    )
    write_csv(icu_mapping, QC_DIR / "analysis_dataset_icu_type_mapping_v1_to_v1_1.csv")

    charlson_hotfix = q(
        con,
        f"""
        select
            'charlson_comorbidity_only_documented_by_index' as variable,
            count(*) as denominator,
            count(charlson_comorbidity_only_documented_by_index) as nonmissing_n,
            min(charlson_comorbidity_only_documented_by_index) as min_value,
            quantile_cont(charlson_comorbidity_only_documented_by_index, 0.25) as p25,
            median(charlson_comorbidity_only_documented_by_index) as median_value,
            quantile_cont(charlson_comorbidity_only_documented_by_index, 0.75) as p75,
            max(charlson_comorbidity_only_documented_by_index) as max_value
        from {ANALYSIS_TABLE}
        union all
        select
            'charlson_comorbidity_only_strict_prior' as variable,
            count(*) as denominator,
            count(charlson_comorbidity_only_strict_prior) as nonmissing_n,
            min(charlson_comorbidity_only_strict_prior) as min_value,
            quantile_cont(charlson_comorbidity_only_strict_prior, 0.25) as p25,
            median(charlson_comorbidity_only_strict_prior) as median_value,
            quantile_cont(charlson_comorbidity_only_strict_prior, 0.75) as p75,
            max(charlson_comorbidity_only_strict_prior) as max_value
        from {ANALYSIS_TABLE}
        """
    )
    write_csv(charlson_hotfix, QC_DIR / "analysis_dataset_charlson_hotfix_qc.csv")

    prior_icu = q(
        con,
        f"""
        select
            count(distinct prior_mimic_icu_stays) as prior_icu_distinct_values,
            min(prior_mimic_icu_stays) as prior_icu_min,
            max(prior_mimic_icu_stays) as prior_icu_max,
            sum(case when prior_mimic_icu_stays_constant_nonestimable then 1 else 0 end) as constant_nonestimable_true_n,
            count(*) as denominator
        from {ANALYSIS_TABLE}
        """
    ).iloc[0]
    model_hotfix = pd.DataFrame(
        [
            {
                "variable": "prior_mimic_icu_stays",
                "retained_in_dataset": True,
                "allowed_in_formal_models": False,
                "reason": "Index stay is each patient's first ICU stay; variable is constant and nonestimable.",
                "qc_detail": f"distinct={int(prior_icu['prior_icu_distinct_values'])}; min={int(prior_icu['prior_icu_min'])}; max={int(prior_icu['prior_icu_max'])}; constant_flag_true_n={int(prior_icu['constant_nonestimable_true_n'])}/{int(prior_icu['denominator'])}",
            },
            {
                "variable": "pre_admission_care_proxy",
                "retained_in_dataset": True,
                "allowed_in_formal_models": False,
                "reason": "Derived from admission_location and redundant with admission_location_group.",
                "qc_detail": "Descriptive-only proxy; not allowed in Model 1 or IPSW.",
            },
            {
                "variable": "charlson_comorbidity_only_documented_by_index",
                "retained_in_dataset": True,
                "allowed_in_formal_models": True,
                "reason": "Charlson disease-component weighted sum excluding index_age_score; Model 1 candidate.",
                "qc_detail": "Range recorded in analysis_dataset_charlson_hotfix_qc.csv.",
            },
            {
                "variable": "full_sofa_official_first_day",
                "retained_in_dataset": True,
                "allowed_in_formal_models": True,
                "reason": "MIT-LCP official first-day SOFA name; old full_sofa_0_24h column retained only as deprecated.",
                "qc_detail": "Official first-day window, not relabeled as strict 0-24h.",
            },
            {
                "variable": "oasis_official_first_day",
                "retained_in_dataset": True,
                "allowed_in_formal_models": True,
                "reason": "MIT-LCP official first-day OASIS name; old oasis_0_24h column retained only as deprecated.",
                "qc_detail": "Official first-day window, not relabeled as strict 0-24h.",
            },
        ]
    )
    write_csv(model_hotfix, QC_DIR / "analysis_dataset_model_variable_hotfix_qc.csv")

    concept_qc = pd.concat(
        [
            concept_meta.assign(source="official_mit_lcp"),
            project_meta.assign(
                official_commit=OFFICIAL_COMMIT,
                official_sql_path="project_specific",
                official_sql_file="",
                official_sql_sha256="",
                adapted_sql_file=project_meta["script_path"],
                adapted_sql_sha256=project_meta["script_sha256"],
                build_time=datetime.now().isoformat(timespec="seconds"),
                time_logic_issue_count=pd.NA,
                range_time_qc=project_meta["qc_note"],
                build_status="built",
                build_note="",
            )[
                [
                    "table_name",
                    "official_commit",
                    "official_sql_path",
                    "official_sql_file",
                    "official_sql_sha256",
                    "adapted_sql_file",
                    "adapted_sql_sha256",
                    "build_time",
                    "row_count",
                    "primary_key",
                    "duplicate_key_count",
                    "time_logic_issue_count",
                    "range_time_qc",
                    "build_status",
                    "build_note",
                    "source",
                ]
            ],
        ],
        ignore_index=True,
        sort=False,
    )
    write_csv(concept_qc, QC_DIR / "analysis_dataset_derived_concept_qc.csv")

    discrepancies = []
    for _, row in row_count_qc.iterrows():
        if not bool(row["pass"]):
            discrepancies.append(f"- {row['metric']}: actual {row['actual']} vs expected {row['expected']}.")
    four_class = four[four["joint_exposure_4level"] != "excluded_unclassifiable_delirium"].copy()
    for group, expected in EXPECTED["four_groups"].items():
        actual_series = four_class.loc[four_class["joint_exposure_4level"] == group, "n"]
        actual = int(actual_series.iloc[0]) if not actual_series.empty else 0
        if actual != expected:
            discrepancies.append(f"- {group}: actual {actual} vs frozen {expected}.")
    class_death = int(outcome.loc[outcome["population"] == "primary_analysis_cohort", "death_365d_main_n"].iloc[0])
    if class_death != EXPECTED["death_365d_main_classifiable_approx"]:
        discrepancies.append(
            f"- Primary 1-year death count: actual {class_death} vs frozen feasibility value about {EXPECTED['death_365d_main_classifiable_approx']}."
        )
    if not discrepancies:
        discrepancies.append("- No discrepancy from frozen cohort/four-group counts; death event count matches the frozen feasibility value.")
    report_lines = [
        "# Analysis Dataset Discrepancy Report",
        "",
        "No formal model was run. This report compares the frozen cohort values with the formal DuckDB analysis table.",
        "",
        "## Discrepancies",
        "",
        *discrepancies,
        "",
        "## Row Count QC",
        "",
        md_table(row_count_qc),
        "",
        "## Key QC",
        "",
        md_table(pd.DataFrame(key_rows)),
        "",
        "## Time Logic QC",
        "",
        md_table(time_logic),
        "",
        "## Competing Risk Status Counts",
        "",
        md_table(competing_status),
        "",
        "## Competing Risk Time QC",
        "",
        md_table(competing_time_qc),
        "",
        "## Known Nonblocking Time-Stamp Warning",
        "",
        md_table(time_warning),
    ]
    (QC_DIR / "analysis_dataset_discrepancy_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "n": n,
        "classifiable": classifiable,
        "unclassifiable": unclassifiable,
        "primary": primary,
        "conservative": conservative,
        "four": four,
        "outcome": outcome,
        "row_count_qc": row_count_qc,
        "key_qc": pd.DataFrame(key_rows),
        "time_logic_qc": time_logic,
        "time_warning": time_warning,
        "competing_status": competing_status,
        "competing_time_qc": competing_time_qc,
        "icu_mapping": icu_mapping,
        "charlson_hotfix": charlson_hotfix,
        "model_hotfix": model_hotfix,
        "discrepancies": discrepancies,
        "table_fingerprint_md5": table_fingerprint(con),
    }


def write_freeze_docs(con: duckdb.DuckDBPyConnection, qc: dict) -> None:
    cols = len(get_columns(con, ANALYSIS_SCHEMA, ANALYSIS_TABLE_NAME))
    duckdb_version = q(con, "select version() as v")["v"].iloc[0]
    py_version = platform.python_version()
    script_hash = sha256_path(Path(__file__))
    generated_files = [
        QC_DIR / "analysis_dataset_row_count_qc.csv",
        QC_DIR / "analysis_dataset_key_qc.csv",
        QC_DIR / "analysis_dataset_missingness.csv",
        QC_DIR / "analysis_dataset_range_qc.csv",
        QC_DIR / "analysis_dataset_time_logic_qc.csv",
        QC_DIR / "analysis_dataset_time_logic_warning_summary.csv",
        QC_DIR / "analysis_dataset_category_levels.csv",
        QC_DIR / "analysis_dataset_cohort_counts.csv",
        QC_DIR / "analysis_dataset_four_group_counts.csv",
        QC_DIR / "analysis_dataset_outcome_counts.csv",
        QC_DIR / "analysis_dataset_competing_risk_status_counts.csv",
        QC_DIR / "analysis_dataset_competing_risk_time_qc.csv",
        QC_DIR / "analysis_dataset_icu_type_mapping_v1_to_v1_1.csv",
        QC_DIR / "analysis_dataset_charlson_hotfix_qc.csv",
        QC_DIR / "analysis_dataset_model_variable_hotfix_qc.csv",
        QC_DIR / "analysis_dataset_derived_concept_qc.csv",
        QC_DIR / "analysis_dataset_discrepancy_report.md",
    ]
    script_files = [Path(__file__)] + [adapted_filename(rel) for _, rel in OFFICIAL_SEQUENCE] + [
        PROJECT_SQL_DIR / "non_neurologic_sofa_0_24h.sql",
        PROJECT_SQL_DIR / "non_neurologic_sofa_0_6h.sql",
    ]
    four_class = qc["four"][qc["four"]["joint_exposure_4level"] != "excluded_unclassifiable_delirium"]
    outcome = qc["outcome"]
    primary_outcome = outcome[outcome["population"] == "primary_analysis_cohort"].iloc[0]
    conservative_outcome = outcome[outcome["population"] == "conservative_readmission_cohort"].iloc[0]

    lines = [
        "# Analysis Data Freeze Log",
        "",
        f"- Analysis table: `{ANALYSIS_TABLE}`",
        "- Freeze status: frozen for prespecified statistical modeling; no formal outcome model has been run.",
        f"- Build date: {datetime.now().isoformat(timespec='seconds')}",
        f"- Row count: {qc['n']:,}",
        f"- Column count: {cols:,}",
        f"- Primary analysis cohort: {qc['primary']:,}",
        f"- Conservative readmission cohort: {qc['conservative']:,}",
        f"- Table fingerprint method: MD5 of per-row hashes ordered by subject_id.",
        f"- Table fingerprint MD5: `{qc['table_fingerprint_md5']}`",
        f"- DuckDB version: `{duckdb_version}`",
        f"- Python version: `{py_version}`",
        f"- Build script: `{Path(__file__)}`",
        f"- Build script SHA256: `{script_hash}`",
        "",
        "## Pre-Model Hotfix v1.1",
        "",
        "- Competing-risk readmission and ICU-readmission status/time variables now stop follow-up at valid competing death before the target event.",
        "- Model 1 Charlson implementation now uses the comorbidity-only documented-by-index score; age remains an independent model variable.",
        "- prior_mimic_icu_stays is retained for description but flagged as constant_nonestimable and excluded from all formal model variable lists.",
        "- pre_admission_care_proxy is retained for description but excluded from Model 1 and IPSW because it is derived from admission_location.",
        "- Trauma/TSICU is mapped before SICU so Trauma SICU is no longer absorbed into ordinary SICU.",
        "- MIT-LCP first-day SOFA and OASIS are named full_sofa_official_first_day and oasis_official_first_day; old names are retained as deprecated columns.",
        "",
        "## Four Groups",
        "",
        md_table(four_class),
        "",
        "## Outcome Event Counts",
        "",
        f"- Primary-analysis one-year death events: {int(primary_outcome['death_365d_main_n']):,}",
        f"- Conservative-cohort 90-day same-system readmission events: {int(conservative_outcome['readmission_90d_n']):,}",
        f"- Conservative-cohort one-year same-system ICU readmission events: {int(conservative_outcome['icu_readmission_365d_n']):,}",
        "",
        "## Known Limitations",
        "",
        "- Same-system readmission outcomes do not capture care outside the MIMIC hospital system.",
        "- Exact patient-level administrative follow-up completeness at 90 or 365 days is not identifiable from shifted dates; conservative approximate-year cohort is used for primary readmission/ICU-readmission analyses.",
        "- Same-day DOD is excluded from the main death definition and retained for sensitivity analysis.",
        "- Hospice discharge is retained in the main analysis and reserved for sensitivity analyses.",
        "- Non-neurologic SOFA uses zero-imputed components plus observed component count, per SAP v1.0.",
        "- Chronic neurologic disease uses prespecified ICD families and should be described as a documented-code flag.",
        "- A nonblocking time-stamp warning remains: some ICU intime values precede hospital admittime within 24 hours; these were retained because the base cohort definition is frozen.",
        "- analysis_dataset_v1 and its original freeze log were not overwritten or deleted.",
        "",
        "## Build Scripts And SHA256",
        "",
        "| Script | SHA256 |",
        "|---|---|",
    ]
    for path in script_files:
        if path.exists():
            lines.append(f"| `{path}` | `{sha256_path(path)}` |")
    lines.extend(
        [
            "",
            "## QC Output Files",
            "",
            "| File | SHA256 |",
            "|---|---|",
        ]
    )
    for path in generated_files:
        lines.append(f"| `{path}` | `{sha256_path(path)}` |")
    FREEZE_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_lines = [
        "# Analysis Dataset Manifest",
        "",
        f"- Analysis table: `{ANALYSIS_TABLE}`",
        f"- Database: `{DB_PATH}`",
        f"- Derived schema: `{DERIVED_SCHEMA}`",
        f"- Analysis schema: `{ANALYSIS_SCHEMA}`",
        f"- Rows: {qc['n']:,}",
        f"- Columns: {cols:,}",
        f"- Primary analysis cohort: {qc['primary']:,}",
        f"- Conservative readmission cohort: {qc['conservative']:,}",
        f"- Internal fingerprint MD5: `{qc['table_fingerprint_md5']}`",
        f"- Build script SHA256: `{script_hash}`",
        "",
        "## Included Variable Blocks",
        "",
        "- Internal IDs: subject_id, hadm_id, stay_id.",
        "- Cohort flags: base_population, delirium_classifiable_72h, primary_analysis_cohort, conservative_readmission_cohort.",
        "- Frozen exposures: psychiatric v1.1 documented-by-index, strict-prior, index-only, five primary categories, 48h/72h delirium status, four-level joint exposure.",
        "- Frozen outcomes: one-year death, 90-day same-system readmission, one-year same-system ICU readmission, competing death indicators.",
        "- Model variables: Model 1, Model 2, Model 3, sensitivity/descriptive variables specified in SAP v1.0.",
        "",
        "## Non-patient-level QC Files",
        "",
        *[f"- `{path}`" for path in generated_files],
    ]
    MANIFEST_PATH.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    hotfix_lines = [
        "# Analysis Data Hotfix v1 to v1.1",
        "",
        "- Status: implemented before any formal outcome model.",
        f"- Source table preserved: `{ANALYSIS_SCHEMA}.analysis_dataset_v1`.",
        f"- New table: `{ANALYSIS_TABLE}`.",
        f"- Build date: {datetime.now().isoformat(timespec='seconds')}",
        f"- Build script: `{Path(__file__)}`",
        f"- Build script SHA256: `{script_hash}`",
        "",
        "## Hotfix Items",
        "",
        "1. Added three-state competing-risk status and combined time variables for 90-day readmission and 365-day ICU readmission.",
        "2. Added Charlson comorbidity-only documented-by-index and strict-prior scores, excluding the age score.",
        "3. Retained prior_mimic_icu_stays but marked it constant_nonestimable and excluded it from formal model variable lists.",
        "4. Retained pre_admission_care_proxy for description only and excluded it from Model 1 and IPSW.",
        "5. Reordered ICU type mapping so Trauma/TSICU is evaluated before SICU.",
        "6. Clarified official first-day SOFA and OASIS variable names; deprecated old strict-looking names.",
        "",
        "## Unchanged Frozen Counts",
        "",
        md_table(qc["row_count_qc"]),
        "",
        "## Four Groups",
        "",
        md_table(four_class),
        "",
        "## Outcome Counts",
        "",
        md_table(qc["outcome"]),
        "",
        "## Competing Risk Three-State Counts",
        "",
        md_table(qc["competing_status"]),
        "",
        "## Competing Risk Time QC",
        "",
        md_table(qc["competing_time_qc"]),
        "",
        "## ICU Type Mapping v1 to v1.1",
        "",
        md_table(qc["icu_mapping"]),
        "",
        "## Charlson Comorbidity-Only QC",
        "",
        md_table(qc["charlson_hotfix"]),
        "",
        "## Model Variable Hotfix QC",
        "",
        md_table(qc["model_hotfix"]),
        "",
        "No Cox, Fine-Gray, multiple imputation, IPSW, interaction model, bootstrap, P value, or confidence interval was run.",
    ]
    HOTFIX_LOG_PATH.write_text("\n".join(hotfix_lines) + "\n", encoding="utf-8")


def update_study_freeze_log() -> None:
    text = STUDY_FREEZE_LOG.read_text(encoding="utf-8")
    text = re.sub(
        r"## Project Status\s+\n.*?\n\n",
        "## Project Status\n\nFormal analysis dataset v1.1 hotfix built and frozen; ready for prespecified statistical modeling.\n\n",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace("## Pending SAP Decisions", "## Resolved SAP Decisions")
    old_bullets = (
        "- Same-day DOD after hospital discharge: 144 base-population patients had DOD equal to discharge date. SAP must specify inclusion, exclusion, or sensitivity handling.\n"
        "- Hospice discharge: 1,205 base-population patients were discharged to hospice, with 85.56% one-year mortality. SAP must specify exclusion, stratification, adjustment, or sensitivity handling.\n"
    )
    new_bullets = (
        "- Same-day DOD is not included in the main one-year death definition and is retained for sensitivity analysis.\n"
        "- Hospice discharge is retained in the main analysis; excluding hospice is retained for sensitivity analysis.\n"
        "- Same-system readmission and ICU readmission use the conservative approximate-year cohort for primary analyses.\n"
        "- Non-neurologic SOFA uses the zero-imputed score plus observed component count.\n"
    )
    text = text.replace(old_bullets, new_bullets)
    STUDY_FREEZE_LOG.write_text(text, encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("pragma threads=4")
    setup_schemas(con)
    if official_concepts_ready(con):
        print("Reusing complete persisted MIT-LCP derived concepts...")
        concept_meta = q(con, f"select * from {DERIVED_SCHEMA}.concept_build_metadata")
    else:
        print("Building MIT-LCP derived concepts...")
        concept_meta = build_official_concepts(con)
    print("Building index base...")
    build_index_base(con)
    print("Building frozen delirium classification...")
    build_delirium(con)
    print("Building psychiatric exposure from v1.1 mapping...")
    build_psychiatric_exposure(con)
    print("Building prior utilization...")
    build_prior_utilization(con)
    print("Building project-specific variables...")
    project_meta = build_project_specific_tables(con)
    print("Building analysis dataset...")
    build_analysis_dataset(con)
    print("Generating QC outputs...")
    qc = generate_qc(con, concept_meta, project_meta)
    print("Writing freeze logs...")
    write_freeze_docs(con, qc)
    update_study_freeze_log()
    con.close()
    print("DONE")
    print(f"analysis_table={ANALYSIS_TABLE}")
    print(f"base_n={qc['n']}")
    print(f"primary_n={qc['primary']}")
    print(f"conservative_n={qc['conservative']}")
    print(f"freeze_log={FREEZE_LOG_PATH}")
    print(f"freeze_log_sha256={sha256_path(FREEZE_LOG_PATH)}")
    print(f"manifest={MANIFEST_PATH}")
    print(f"manifest_sha256={sha256_path(MANIFEST_PATH)}")
    print(f"hotfix_log={HOTFIX_LOG_PATH}")
    print(f"hotfix_log_sha256={sha256_path(HOTFIX_LOG_PATH)}")


if __name__ == "__main__":
    main()
