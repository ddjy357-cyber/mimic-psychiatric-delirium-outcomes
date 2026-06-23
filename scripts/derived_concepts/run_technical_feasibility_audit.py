from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


WORKSPACE = Path(__file__).resolve().parents[4]
PROJECT = WORKSPACE / "projects" / "mental_delirium_longterm"
DB_PATH = WORKSPACE / "data" / "mimiciv.duckdb"
OUTDIR = PROJECT / "outputs" / "technical_feasibility_audit"
SCRIPT_DIR = PROJECT / "scripts" / "derived_concepts"
DEFREF_SCRIPT = PROJECT / "scripts" / "run_definition_refinement.py"

MIMIC_CODE_COMMIT = "57069783095e7770e66ea97da264c0200078ddbf"
OFFICIAL_ARCHIVE_DIR = (
    SCRIPT_DIR
    / f"official_mimic_code_{MIMIC_CODE_COMMIT}"
    / f"mimic-code-{MIMIC_CODE_COMMIT}"
)
OFFICIAL_SQL_DIR = SCRIPT_DIR / "official_sql"
ADAPTED_SQL_DIR = SCRIPT_DIR / "duckdb_adapted"

FORBIDDEN_OUTPUT_TOKENS = ["subject_id", "hadm_id", "stay_id"]


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


CONCEPT_GROUPS = {
    "Charlson": {
        "official_sql_path": "mimic-iv/concepts_duckdb/comorbidity/charlson.sql",
        "tables": ["age", "charlson"],
        "upstream": "diagnosis codes; age concept",
        "local_sources": "hosp diagnoses and patients/admissions tables",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Low",
        "order": 1,
    },
    "vasoactive agents": {
        "official_sql_path": "mimic-iv/concepts_duckdb/medication/vasoactive_agent.sql",
        "tables": [
            "dobutamine",
            "dopamine",
            "epinephrine",
            "norepinephrine",
            "phenylephrine",
            "vasopressin",
            "milrinone",
            "vasoactive_agent",
        ],
        "upstream": "ICU medication infusion records and agent-specific concepts",
        "local_sources": "ICU input events",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Low",
        "order": 2,
    },
    "norepinephrine equivalent dose": {
        "official_sql_path": "mimic-iv/concepts_duckdb/medication/norepinephrine_equivalent_dose.sql",
        "tables": ["norepinephrine_equivalent_dose"],
        "upstream": "vasoactive_agent concept",
        "local_sources": "derived vasoactive-agent intervals",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Low",
        "order": 3,
    },
    "RRT": {
        "official_sql_path": "mimic-iv/concepts_duckdb/treatment/rrt.sql",
        "tables": ["rrt", "first_day_rrt"],
        "upstream": "ICU chart, input, and procedure events",
        "local_sources": "ICU chart/input/procedure events",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Low",
        "order": 4,
    },
    "CRRT": {
        "official_sql_path": "mimic-iv/concepts_duckdb/treatment/crrt.sql",
        "tables": ["crrt"],
        "upstream": "ICU CRRT chart events",
        "local_sources": "ICU chart events",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Low",
        "order": 5,
    },
    "ventilation": {
        "official_sql_path": "mimic-iv/concepts_duckdb/treatment/ventilation.sql",
        "tables": ["ventilator_setting", "oxygen_delivery", "ventilation"],
        "upstream": "ventilator-setting and oxygen-delivery measurement concepts",
        "local_sources": "ICU chart events",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Medium",
        "order": 6,
    },
    "first-day SOFA": {
        "official_sql_path": "mimic-iv/concepts_duckdb/firstday/first_day_sofa.sql",
        "tables": [
            "first_day_vitalsign",
            "first_day_urine_output",
            "first_day_gcs",
            "first_day_lab",
            "first_day_bg",
            "first_day_sofa",
            "sofa",
        ],
        "upstream": "vitals, labs, blood gases, urine output, vasoactive agents, ventilation, GCS",
        "local_sources": "ICU chart/output/input events and hospital lab events",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "High",
        "order": 7,
    },
    "OASIS": {
        "official_sql_path": "mimic-iv/concepts_duckdb/score/oasis.sql",
        "tables": ["oasis"],
        "upstream": "age, first-day vitals, GCS, urine output, ventilation, services",
        "local_sources": "ICU, hospital admission, services and derived first-day concepts",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "Medium",
        "order": 8,
    },
    "Sepsis-3": {
        "official_sql_path": "mimic-iv/concepts_duckdb/sepsis/sepsis3.sql",
        "tables": ["antibiotic", "suspicion_of_infection", "sepsis3"],
        "upstream": "SOFA and suspected infection concepts",
        "local_sources": "hospital prescriptions/microbiology and derived hourly SOFA",
        "expected_modification": "No SQL body change; executed with read-only schema aliases.",
        "difficulty": "High",
        "order": 9,
    },
}


def load_definition_module():
    spec = importlib.util.spec_from_file_location("definition_refinement_for_tech_audit", DEFREF_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {DEFREF_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_dirs() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    OFFICIAL_SQL_DIR.mkdir(parents=True, exist_ok=True)
    ADAPTED_SQL_DIR.mkdir(parents=True, exist_ok=True)


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
    return round(float(num) / float(den) * 100.0, 2)


def q(con: duckdb.DuckDBPyConnection, sql: str, params=None) -> pd.DataFrame:
    return con.execute(sql, params or []).fetchdf()


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


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_No rows._"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)


def write_md(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def setup_source_aliases(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"ATTACH '{DB_PATH.as_posix()}' AS src (READ_ONLY)")
    for schema in ["hosp", "icu", "mimiciv_hosp", "mimiciv_icu", "mimiciv_derived"]:
        con.execute(f"CREATE SCHEMA {schema}")
    for schema in ["hosp", "icu"]:
        tables = con.execute(
            """
            select table_name
            from information_schema.tables
            where table_catalog = 'src'
              and table_schema = ?
            order by table_name
            """,
            [schema],
        ).fetchall()
        for (table_name,) in tables:
            con.execute(f"CREATE VIEW {schema}.{table_name} AS SELECT * FROM src.{schema}.{table_name}")
            con.execute(
                f"CREATE VIEW mimiciv_{schema}.{table_name} AS SELECT * FROM src.{schema}.{table_name}"
            )


def setup_cohort_and_delirium(con: duckdb.DuckDBPyConnection) -> None:
    defref = load_definition_module()
    defref.setup_index_base(con)
    defref.setup_outcome_and_utilization_tables(con)
    defref.setup_delirium_tables(con)
    defref.setup_rass_matching_tables(con)
    defref.create_window_classification(
        con,
        "delirium_window_classification_final_technical",
        source_table="delirium_events_rass_valid_within_1h_refined",
        negative_valid_condition="de.value_class = 'negative' and de.invalid_negative_rass_le_minus4 = 0",
    )
    con.execute(
        """
        create or replace temp table audit_cohort as
        select
            ib.*,
            a.language,
            a.marital_status,
            date_diff('hour', ib.admittime, ib.dischtime) / 24.0 as hospital_los_days,
            case when dw.delirium_status in ('positive', 'negative') then 1 else 0 end as delirium_classifiable_72h,
            dw.delirium_status as delirium_status_72h
        from index_base ib
        left join hosp.admissions a
          on ib.subject_id = a.subject_id
         and ib.hadm_id = a.hadm_id
        left join delirium_window_classification_final_technical dw
          on ib.subject_id = dw.subject_id
         and ib.hadm_id = dw.hadm_id
         and ib.stay_id = dw.stay_id
         and dw.delirium_window = '72h_two_negative_days'
        """
    )
    con.execute(
        """
        create or replace temp table service_first as
        select *
        from (
            select
                ac.subject_id,
                ac.hadm_id,
                s.curr_service,
                s.prev_service,
                s.transfertime,
                row_number() over (
                    partition by ac.subject_id, ac.hadm_id
                    order by s.transfertime nulls last, s.curr_service nulls last
                ) as rn
            from audit_cohort ac
            left join hosp.services s
              on ac.subject_id = s.subject_id
             and ac.hadm_id = s.hadm_id
        )
        where rn = 1
        """
    )


def population_filter(population: str) -> str:
    if population == "base_population":
        return "1 = 1"
    if population == "classifiable_72h_population":
        return "delirium_classifiable_72h = 1"
    raise ValueError(population)


def summarize_single_category(
    con: duckdb.DuckDBPyConnection,
    variable_name: str,
    column_expr: str,
    source_note: str,
    population: str,
) -> pd.DataFrame:
    where = population_filter(population)
    denom = int(q(con, f"select count(*) as n from audit_cohort where {where}")["n"].iloc[0])
    missing = int(
        q(
            con,
            f"""
            select count(*) as n
            from audit_cohort
            where {where}
              and ({column_expr}) is null
            """,
        )["n"].iloc[0]
    )
    df = q(
        con,
        f"""
        select
            cast(coalesce(cast({column_expr} as varchar), '[MISSING]') as varchar) as raw_level,
            count(*) as patient_count
        from audit_cohort
        where {where}
        group by raw_level
        order by patient_count desc, raw_level
        """,
    )
    df.insert(0, "population", population)
    df.insert(1, "variable", variable_name)
    df["denominator"] = denom
    df["percent"] = df["patient_count"].map(lambda x: pct(x, denom))
    df["missing_count_for_variable"] = missing
    df["missing_percent_for_variable"] = pct(missing, denom)
    df["multi_valued_patient_variable"] = 0
    df["source_note"] = source_note
    return df


def summarize_service_any(con: duckdb.DuckDBPyConnection, population: str) -> pd.DataFrame:
    where = "ac.delirium_classifiable_72h = 1" if population == "classifiable_72h_population" else "1 = 1"
    denom = int(q(con, f"select count(*) as n from audit_cohort ac where {where}")["n"].iloc[0])
    with_service = int(
        q(
            con,
            f"""
            select count(distinct ac.subject_id) as n
            from audit_cohort ac
            join hosp.services s
              on ac.subject_id = s.subject_id
             and ac.hadm_id = s.hadm_id
            where {where}
              and s.curr_service is not null
            """,
        )["n"].iloc[0]
    )
    df = q(
        con,
        f"""
        select
            cast(coalesce(s.curr_service, '[MISSING]') as varchar) as raw_level,
            count(distinct ac.subject_id) as patient_count
        from audit_cohort ac
        left join hosp.services s
          on ac.subject_id = s.subject_id
         and ac.hadm_id = s.hadm_id
        where {where}
        group by raw_level
        order by patient_count desc, raw_level
        """,
    )
    df.insert(0, "population", population)
    df.insert(1, "variable", "hosp.services.curr_service_any_index_hospitalization")
    df["denominator"] = denom
    df["percent"] = df["patient_count"].map(lambda x: pct(x, denom))
    df["missing_count_for_variable"] = denom - with_service
    df["missing_percent_for_variable"] = pct(denom - with_service, denom)
    df["multi_valued_patient_variable"] = 1
    df["source_note"] = (
        "Any current service recorded during the index hospitalization; counts can sum above denominator."
    )
    return df


def run_raw_category_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    variables = [
        ("patients.anchor_year_group", "anchor_year_group", "Use as cross-patient calendar-period variable."),
        ("patients.gender", "gender", "Raw sex/gender field from patients table."),
        ("admissions.race", "race", "Raw race field from index hospitalization."),
        ("admissions.admission_type", "admission_type", "Raw admission type from index hospitalization."),
        ("admissions.admission_location", "admission_location", "Raw admission location from index hospitalization."),
        ("icustays.first_careunit", "first_careunit", "Raw first ICU care unit for the index ICU stay."),
        ("admissions.insurance", "insurance", "Raw insurance field from index hospitalization."),
        ("admissions.language", "language", "Raw language field from index hospitalization."),
        ("admissions.marital_status", "marital_status", "Raw marital-status field from index hospitalization."),
        ("admissions.discharge_location", "discharge_location", "Raw discharge location from index hospitalization."),
        (
            "hosp.services.first_curr_service_index_hospitalization",
            "sf.curr_service",
            "First current service in services table during index hospitalization.",
        ),
    ]
    frames = []
    for population in ["base_population", "classifiable_72h_population"]:
        for variable_name, column_expr, note in variables:
            if column_expr.startswith("sf."):
                con.execute(
                    """
                    create or replace temp table audit_cohort_service_first as
                    select ac.*, sf.curr_service as first_curr_service
                    from audit_cohort ac
                    left join service_first sf
                      on ac.subject_id = sf.subject_id
                     and ac.hadm_id = sf.hadm_id
                    """
                )
                old_name = "audit_cohort"
                con.execute("create or replace temp table audit_cohort_original as select * from audit_cohort")
                con.execute("create or replace temp table audit_cohort as select * from audit_cohort_service_first")
                frames.append(
                    summarize_single_category(
                        con,
                        variable_name,
                        "first_curr_service",
                        note,
                        population,
                    )
                )
                con.execute("create or replace temp table audit_cohort as select * from audit_cohort_original")
                con.execute("drop table audit_cohort_original")
                _ = old_name
            else:
                frames.append(
                    summarize_single_category(con, variable_name, column_expr, note, population)
                )
        frames.append(summarize_service_any(con, population))
    out = pd.concat(frames, ignore_index=True)
    save_csv(out, "raw_category_levels.csv")

    mapping_rows = [
        ("patients.anchor_year_group", "all", "Keep ordered groups; do not replace with shifted admission/discharge year."),
        ("patients.gender", "M/F", "Use binary indicator or retain raw two-level category after QC."),
        ("admissions.race", "race strings", "Consider prespecified broad groups; keep Unknown/Unable separately."),
        ("admissions.admission_type", "admission types", "Consider emergency/urgent/elective/observation/surgical-direct groupings."),
        ("admissions.admission_location", "locations", "Consider ED, transfer, clinic/referral, procedural, other/unknown."),
        ("icustays.first_careunit", "care units", "Retain or group into medical, surgical, cardiac, neuro, trauma, other ICU."),
        ("admissions.insurance", "insurance", "Consider Medicare/Medicaid/private/self-pay/other."),
        ("admissions.language", "language", "Consider English vs non-English vs missing/unknown."),
        ("admissions.marital_status", "status", "Consider married/partnered, single, divorced/separated, widowed, unknown."),
        ("admissions.discharge_location", "locations", "Do not use in primary model; retain for hospice/discharge audit only."),
        ("hosp.services", "curr_service", "Consider broad clinical services only after SAP approval."),
    ]
    mapping = pd.DataFrame(
        [
            {
                "variable": v,
                "raw_level_or_family": fam,
                "technical_mapping_suggestion": sugg,
                "status": "proposal_only_not_applied",
            }
            for v, fam, sugg in mapping_rows
        ]
    )
    save_csv(mapping, "proposed_category_mapping.csv")

    base_n = int(q(con, "select count(*) as n from audit_cohort")["n"].iloc[0])
    class_n = int(
        q(con, "select count(*) as n from audit_cohort where delirium_classifiable_72h = 1")["n"].iloc[0]
    )
    write_md(
        OUTDIR / "raw_category_audit.md",
        [
            "# Raw Category Audit",
            "",
            f"Base population: {base_n:,}.",
            f"72-hour delirium-classifiable population: {class_n:,}.",
            "",
            "All categorical summaries are unstratified. No exposure groups, outcome groups, P values, or modeling were used.",
            "",
            "The services table was summarized two ways: first current service during index hospitalization and any current service during index hospitalization. The latter is multi-valued and can sum above the denominator.",
            "",
            "Mapping suggestions are technical proposals only and do not modify the formal data dictionary.",
        ],
    )
    return out


def parse_anchor_group(value: str) -> tuple[int | None, int | None]:
    years = re.findall(r"\d{4}", str(value))
    if not years:
        return None, None
    if len(years) == 1:
        year = int(years[0])
        return year, year
    return int(years[0]), int(years[-1])


def run_calendar_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    base = q(
        con,
        """
        select
            anchor_year_group,
            anchor_year,
            dischtime,
            delirium_classifiable_72h
        from audit_cohort
        """,
    )
    base["population_base"] = "base_population"
    base["discharge_year_shifted"] = pd.to_datetime(base["dischtime"]).dt.year
    base["shifted_year_delta"] = base["discharge_year_shifted"] - base["anchor_year"]
    parsed = base["anchor_year_group"].map(parse_anchor_group)
    base["anchor_year_group_lower"] = [x[0] for x in parsed]
    base["anchor_year_group_upper"] = [x[1] for x in parsed]
    base["approximate_discharge_year_lower"] = (
        base["anchor_year_group_lower"] + base["shifted_year_delta"]
    )
    base["approximate_discharge_year_upper"] = (
        base["anchor_year_group_upper"] + base["shifted_year_delta"]
    )

    def agg_anchor(df: pd.DataFrame, population: str) -> pd.DataFrame:
        out = (
            df.groupby("anchor_year_group", dropna=False)
            .size()
            .reset_index(name="patient_count")
            .sort_values("anchor_year_group")
        )
        out.insert(0, "population", population)
        out["denominator"] = len(df)
        out["percent"] = [pct(x, len(df)) for x in out["patient_count"]]
        return out

    anchor = pd.concat(
        [
            agg_anchor(base, "base_population"),
            agg_anchor(base[base["delirium_classifiable_72h"] == 1], "classifiable_72h_population"),
        ],
        ignore_index=True,
    )
    save_csv(anchor, "anchor_year_group_audit.csv")

    def agg_range(df: pd.DataFrame, population: str) -> pd.DataFrame:
        dist = (
            df.groupby(
                ["approximate_discharge_year_lower", "approximate_discharge_year_upper"],
                dropna=False,
            )
            .size()
            .reset_index(name="patient_count")
            .sort_values(["approximate_discharge_year_lower", "approximate_discharge_year_upper"])
        )
        dist.insert(0, "section", "approximate_year_interval_distribution")
        dist.insert(1, "population", population)
        dist["denominator"] = len(df)
        dist["percent"] = [pct(x, len(df)) for x in dist["patient_count"]]
        categories = [
            (
                "definitely_before_2022",
                int((df["approximate_discharge_year_upper"] < 2022).sum()),
            ),
            (
                "interval_overlaps_2022",
                int(
                    (
                        (df["approximate_discharge_year_lower"] <= 2022)
                        & (df["approximate_discharge_year_upper"] >= 2022)
                    ).sum()
                ),
            ),
            (
                "interval_entirely_2022",
                int(
                    (
                        (df["approximate_discharge_year_lower"] == 2022)
                        & (df["approximate_discharge_year_upper"] == 2022)
                    ).sum()
                ),
            ),
            (
                "theoretical_range_exceeds_2022",
                int((df["approximate_discharge_year_upper"] > 2022).sum()),
            ),
        ]
        cat = pd.DataFrame(
            [
                {
                    "section": "coverage_category",
                    "population": population,
                    "coverage_category": name,
                    "patient_count": n,
                    "denominator": len(df),
                    "percent": pct(n, len(df)),
                }
                for name, n in categories
            ]
        )
        return pd.concat([dist, cat], ignore_index=True, sort=False)

    ranges = pd.concat(
        [
            agg_range(base, "base_population"),
            agg_range(base[base["delirium_classifiable_72h"] == 1], "classifiable_72h_population"),
        ],
        ignore_index=True,
        sort=False,
    )
    save_csv(ranges, "approximate_calendar_range_audit.csv")

    impossible = int(
        (
            (base["approximate_discharge_year_lower"] < 2008)
            | (base["approximate_discharge_year_upper"] > 2022)
            | (base["approximate_discharge_year_lower"] > base["approximate_discharge_year_upper"])
        ).sum()
    )
    delta_summary = (
        base.groupby("shifted_year_delta", dropna=False)
        .size()
        .reset_index(name="patient_count")
        .sort_values("shifted_year_delta")
    )
    write_md(
        OUTDIR / "calendar_time_audit.md",
        [
            "# Calendar Time Audit",
            "",
            "Shifted admission or discharge year must not be used as a cross-patient real calendar year.",
            "",
            "Approximate actual discharge-year intervals were computed from the patient anchor-year group plus the within-patient shifted-year delta between index discharge and anchor year.",
            "",
            f"Rows with an approximate interval outside 2008-2022 or internally impossible: {impossible:,}.",
            "",
            "Shifted-year delta distribution:",
            "",
            md_table(delta_summary),
            "",
            "Because patient dates are independently shifted, exact patient-level administrative end-of-data follow-up cannot be recovered from these intervals.",
        ],
    )
    return base


def run_mortality_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    full = q(con, "select count(*) as denominator, count(dod) as numerator from hosp.patients").iloc[0]
    rows.append(
        {
            "population": "all_patients_table",
            "metric": "nonmissing_death_date",
            "numerator": int(full["numerator"]),
            "denominator": int(full["denominator"]),
            "percent": pct(full["numerator"], full["denominator"]),
            "note": "All patients table, not restricted to the study cohort.",
        }
    )
    for population, where in [
        ("base_population", "1 = 1"),
        ("classifiable_72h_population", "ac.delirium_classifiable_72h = 1"),
    ]:
        metrics = q(
            con,
            f"""
            with x as (
                select
                    ac.*,
                    cast(ac.dischtime as date) as discharge_date,
                    cast(ac.admittime as date) as admission_date,
                    case when exists (
                        select 1
                        from hosp.admissions later
                        where later.subject_id = ac.subject_id
                          and later.hadm_id <> ac.hadm_id
                          and later.admittime > ac.dischtime
                    ) then 0 else 1 end as index_is_last_hospitalization
                from audit_cohort ac
                where {where}
            )
            select
                count(*) as denominator,
                count(dod) as dod_nonmissing,
                sum(case when dod > discharge_date and dod <= discharge_date + interval 365 day then 1 else 0 end) as death_after_discharge_1y,
                sum(case when dod >= discharge_date and dod <= discharge_date + interval 365 day then 1 else 0 end) as death_0_to_365_including_same_day,
                sum(case when dod = discharge_date then 1 else 0 end) as dod_equals_discharge_date,
                sum(case when dod < discharge_date then 1 else 0 end) as dod_before_discharge_date,
                sum(case when dod < admission_date then 1 else 0 end) as dod_before_admission_date,
                sum(case when dod > discharge_date + interval 365 day then 1 else 0 end) as dod_after_365_days,
                sum(index_is_last_hospitalization) as index_is_last_hospitalization_n,
                sum(case when index_is_last_hospitalization = 0 then 1 else 0 end) as index_not_last_hospitalization_n,
                sum(case when index_is_last_hospitalization = 0 and dod > discharge_date and dod <= discharge_date + interval 365 day then 1 else 0 end) as death_1y_among_index_not_last_n
            from x
            """
        ).iloc[0]
        denominator = int(metrics["denominator"])
        for metric in metrics.index:
            if metric == "denominator":
                continue
            value = int(metrics[metric] or 0)
            rows.append(
                {
                    "population": population,
                    "metric": metric,
                    "numerator": value,
                    "denominator": denominator,
                    "percent": pct(value, denominator),
                    "note": "Death-time zero is index hospital discharge date.",
                }
            )
    out = pd.DataFrame(rows)
    save_csv(out, "mortality_followup_qc.csv")
    write_md(
        OUTDIR / "mortality_followup_audit.md",
        [
            "# Mortality Follow-up Audit",
            "",
            "Death outcomes use the patient death date and index hospital discharge as time zero.",
            "",
            "Same-day death date equals discharge date is audited separately from the primary after-discharge death definition.",
            "",
            "When index hospitalization is not the patient's last local hospitalization, the one-year death definition remains logically time-based because it uses the death date relative to index discharge, not the last local encounter.",
            "",
            md_table(out),
        ],
    )
    return out


def run_followup_coverage(calendar_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for population, df in [
        ("base_population", calendar_df),
        ("classifiable_72h_population", calendar_df[calendar_df["delirium_classifiable_72h"] == 1]),
    ]:
        denom = len(df)
        strategies = [
            (
                "A_all_patients_time_to_event_same_system",
                np.ones(denom, dtype=bool),
                "Use all patients; acknowledge same-system events and database boundary limitations.",
            ),
            (
                "B_conservative_365d_upper_not_later_than_2021",
                (df["approximate_discharge_year_upper"] <= 2021).to_numpy(),
                "Reduces one-year database-end truncation risk using approximate upper year.",
            ),
            (
                "C_exploratory_90d_upper_not_later_than_2022",
                (df["approximate_discharge_year_upper"] <= 2022).to_numpy(),
                "Permissive 90-day option; still not exact day-level administrative censoring.",
            ),
            (
                "D_very_conservative_90d_upper_not_later_than_2021",
                (df["approximate_discharge_year_upper"] <= 2021).to_numpy(),
                "Same conservative restriction as one-year analyses; may sacrifice sample size.",
            ),
        ]
        for name, mask, note in strategies:
            n = int(mask.sum())
            rows.append(
                {
                    "population": population,
                    "strategy": name,
                    "retained_patient_count": n,
                    "denominator": denom,
                    "retained_percent": pct(n, denom),
                    "exact_followup_complete_flag_not_identifiable": True,
                    "note": note,
                }
            )
        for category, n in [
            ("definitely_before_2022", int((df["approximate_discharge_year_upper"] < 2022).sum())),
            (
                "interval_overlaps_2022",
                int(
                    (
                        (df["approximate_discharge_year_lower"] <= 2022)
                        & (df["approximate_discharge_year_upper"] >= 2022)
                    ).sum()
                ),
            ),
            (
                "interval_entirely_2022",
                int(
                    (
                        (df["approximate_discharge_year_lower"] == 2022)
                        & (df["approximate_discharge_year_upper"] == 2022)
                    ).sum()
                ),
            ),
            ("theoretical_range_exceeds_2022", int((df["approximate_discharge_year_upper"] > 2022).sum())),
        ]:
            rows.append(
                {
                    "population": population,
                    "strategy": f"coverage_{category}",
                    "retained_patient_count": n,
                    "denominator": denom,
                    "retained_percent": pct(n, denom),
                    "exact_followup_complete_flag_not_identifiable": True,
                    "note": "Coverage category based on approximate actual discharge-year interval.",
                }
            )
    readmit = pd.DataFrame(rows)
    save_csv(readmit, "readmission_followup_coverage.csv")
    icu = readmit.copy()
    icu["coverage_target"] = "same-system ICU readmission"
    save_csv(icu, "icu_readmission_followup_coverage.csv")
    write_md(
        OUTDIR / "followup_strategy_options.md",
        [
            "# Follow-up Strategy Options",
            "",
            "Local MIMIC-IV v3.1 coverage is treated as extending through 2022, but exact patient-level administrative follow-up completeness cannot be recovered because patient timelines are independently shifted.",
            "",
            "`exact_followup_complete_flag_not_identifiable = true` for readmission and ICU readmission follow-up.",
            "",
            "Strategy A: include all patients in same-system time-to-event analyses and state that outside-hospital events and database-end boundaries are not fully observable.",
            "",
            "Strategy B: restrict conservatively to patients whose approximate actual discharge-year upper bound is not later than 2021 for one-year same-system readmission or ICU readmission analyses.",
            "",
            "A 90-day restricted option can be prespecified, but anchor-year groups do not provide exact day-level administrative censoring.",
            "",
            md_table(readmit),
        ],
    )
    return readmit, icu


def copy_and_prepare_sql_files() -> pd.DataFrame:
    rows = []
    for table_name, rel in OFFICIAL_SEQUENCE:
        src = OFFICIAL_ARCHIVE_DIR / rel
        if not src.exists():
            rows.append(
                {
                    "derived_table": table_name,
                    "official_relative_path": rel,
                    "official_sql_available": False,
                    "official_sql_copy": "",
                    "official_sql_sha256": "",
                    "adapted_sql_path": "",
                    "adapted_sql_sha256": "",
                }
            )
            continue
        safe_name = rel.replace("/", "__").replace("\\", "__")
        official_copy = OFFICIAL_SQL_DIR / safe_name
        adapted = ADAPTED_SQL_DIR / safe_name
        shutil.copyfile(src, official_copy)
        original = src.read_text(encoding="utf-8")
        adapted.write_text(
            "\n".join(
                [
                    f"-- Adapted for project technical feasibility audit, commit {MIMIC_CODE_COMMIT}.",
                    "-- SQL body below is the official DuckDB SQL; execution uses read-only local schema aliases.",
                    original,
                ]
            ),
            encoding="utf-8",
        )
        rows.append(
            {
                "derived_table": table_name,
                "official_relative_path": rel,
                "official_sql_available": True,
                "official_sql_copy": str(official_copy),
                "official_sql_sha256": sha256_path(official_copy),
                "adapted_sql_path": str(adapted),
                "adapted_sql_sha256": sha256_path(adapted),
            }
        )
    return pd.DataFrame(rows)


def duplicate_count(con: duckdb.DuckDBPyConnection, table: str, key_cols: list[str]) -> int | None:
    cols = ", ".join(key_cols)
    try:
        return int(
            q(
                con,
                f"""
                select count(*) as n
                from (
                    select {cols}, count(*) as row_n
                    from mimiciv_derived.{table}
                    group by {cols}
                    having count(*) > 1
                )
                """,
            )["n"].iloc[0]
        )
    except Exception:
        return None


def row_count(con: duckdb.DuckDBPyConnection, table: str) -> int | None:
    try:
        return int(q(con, f"select count(*) as n from mimiciv_derived.{table}")["n"].iloc[0])
    except Exception:
        return None


def run_official_builds(con: duckdb.DuckDBPyConnection, sql_inventory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    inventory = sql_inventory.set_index("derived_table")
    for table_name, rel in OFFICIAL_SEQUENCE:
        official_path = OFFICIAL_ARCHIVE_DIR / rel
        start = time.time()
        status = "not_run"
        error = ""
        count = None
        if official_path.exists():
            try:
                con.execute(official_path.read_text(encoding="utf-8"))
                count = row_count(con, table_name)
                status = "built"
            except Exception as exc:
                status = "failed"
                error = f"{type(exc).__name__}: {str(exc)[:500]}"
        else:
            status = "official_sql_missing"
        rows.append(
            {
                "derived_table": table_name,
                "official_relative_path": rel,
                "official_commit": MIMIC_CODE_COMMIT,
                "build_status": status,
                "row_count": count,
                "elapsed_seconds": round(time.time() - start, 2),
                "official_sql_sha256": inventory.loc[table_name, "official_sql_sha256"]
                if table_name in inventory.index
                else "",
                "adapted_sql_sha256": inventory.loc[table_name, "adapted_sql_sha256"]
                if table_name in inventory.index
                else "",
                "error_or_note": error,
            }
        )
    return pd.DataFrame(rows)


def run_dependency_matrix(builds: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    built = set(builds.loc[builds["build_status"] == "built", "derived_table"])
    for concept, info in CONCEPT_GROUPS.items():
        all_built = all(t in built for t in info["tables"])
        hashes = inventory[inventory["derived_table"].isin(info["tables"])]
        rows.append(
            {
                "concept": concept,
                "official_sql_path": info["official_sql_path"],
                "official_commit": MIMIC_CODE_COMMIT,
                "upstream_dependencies": info["upstream"],
                "local_existing_sources": info["local_sources"],
                "missing_tables_or_concepts": "none_detected" if all_built else "see_build_status",
                "duckdb_compatibility_issue": "none_detected" if all_built else "build_failed_or_not_run",
                "expected_duckdb_modification": info["expected_modification"],
                "build_difficulty": info["difficulty"],
                "can_directly_build": all_built,
                "depends_on_previous_concept": "yes" if info["order"] > 1 else "no",
                "recommended_build_order": info["order"],
                "official_sql_sha256_list": "; ".join(hashes["official_sql_sha256"].dropna().astype(str)),
                "adapted_sql_sha256_list": "; ".join(hashes["adapted_sql_sha256"].dropna().astype(str)),
            }
        )
    out = pd.DataFrame(rows)
    save_csv(out, "derived_concept_dependency_matrix.csv")
    write_md(
        OUTDIR / "derived_concept_dependency_report.md",
        [
            "# Derived Concept Dependency Report",
            "",
            f"Official MIT-LCP mimic-code commit: `{MIMIC_CODE_COMMIT}`.",
            "",
            "Official DuckDB SQL files were copied without changing their body. They were executed in an in-memory DuckDB session using read-only schema aliases to the local MIMIC-IV database.",
            "",
            md_table(out[["concept", "can_directly_build", "build_difficulty", "recommended_build_order", "missing_tables_or_concepts"]]),
            "",
            "Build status for all executed source files:",
            "",
            md_table(builds[["derived_table", "build_status", "row_count", "elapsed_seconds", "error_or_note"]]),
        ],
    )
    return out


def distribution(values: pd.Series) -> dict:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return {"n_nonmissing": 0}
    return {
        "n_nonmissing": int(v.size),
        "min": round(float(v.min()), 4),
        "p25": round(float(v.quantile(0.25)), 4),
        "median": round(float(v.median()), 4),
        "p75": round(float(v.quantile(0.75)), 4),
        "max": round(float(v.max()), 4),
    }


def concept_base_counts(con: duckdb.DuckDBPyConnection, table: str, join_col: str, predicate: str = "1 = 1") -> dict:
    return q(
        con,
        f"""
        select
            count(*) as base_denominator,
            count(*) filter (where x.{join_col} is not null and {predicate}) as base_with_concept,
            count(*) filter (where ac.delirium_classifiable_72h = 1) as classifiable_denominator,
            count(*) filter (
                where ac.delirium_classifiable_72h = 1
                  and x.{join_col} is not null
                  and {predicate}
            ) as classifiable_with_concept
        from audit_cohort ac
        left join mimiciv_derived.{table} x
          on ac.{join_col} = x.{join_col}
        """
    ).iloc[0].to_dict()


def run_charlson_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    dup = duplicate_count(con, "charlson", ["hadm_id"])
    stats = q(
        con,
        """
        select
            'base_population' as population,
            count(*) as denominator,
            count(c.charlson_comorbidity_index) as nonmissing_n,
            min(c.charlson_comorbidity_index) as min_value,
            quantile_cont(c.charlson_comorbidity_index, 0.25) as p25,
            median(c.charlson_comorbidity_index) as median_value,
            quantile_cont(c.charlson_comorbidity_index, 0.75) as p75,
            max(c.charlson_comorbidity_index) as max_value
        from audit_cohort ac
        left join mimiciv_derived.charlson c
          on ac.hadm_id = c.hadm_id
        union all
        select
            'classifiable_72h_population' as population,
            count(*) as denominator,
            count(c.charlson_comorbidity_index) as nonmissing_n,
            min(c.charlson_comorbidity_index) as min_value,
            quantile_cont(c.charlson_comorbidity_index, 0.25) as p25,
            median(c.charlson_comorbidity_index) as median_value,
            quantile_cont(c.charlson_comorbidity_index, 0.75) as p75,
            max(c.charlson_comorbidity_index) as max_value
        from audit_cohort ac
        left join mimiciv_derived.charlson c
          on ac.hadm_id = c.hadm_id
        where ac.delirium_classifiable_72h = 1
        """
    )
    stats["table_row_count"] = row_count(con, "charlson")
    stats["duplicate_key_count"] = dup
    stats["key_scope"] = "one row per hospitalization expected"
    stats["status"] = "built_from_official_duckdb_sql"
    save_csv(stats, "charlson_feasibility.csv")
    return stats


def run_vasoactive_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    for table in [
        "dobutamine",
        "dopamine",
        "epinephrine",
        "norepinephrine",
        "phenylephrine",
        "vasopressin",
        "milrinone",
        "vasoactive_agent",
        "norepinephrine_equivalent_dose",
    ]:
        rc = row_count(con, table)
        dup = duplicate_count(con, table, ["stay_id", "starttime", "endtime"]) if table != "vasoactive_agent" else duplicate_count(con, table, ["stay_id", "starttime", "endtime"])
        rows.append(
            {
                "concept_table": table,
                "table_row_count": rc,
                "duplicate_interval_key_count": dup,
                "status": "built_from_official_duckdb_sql",
            }
        )
    exposure = q(
        con,
        """
        select
            'first_24h_vasoactive_any' as metric,
            count(*) as denominator,
            sum(case when exists (
                select 1
                from mimiciv_derived.vasoactive_agent v
                where v.stay_id = ac.stay_id
                  and v.starttime < ac.intime + interval 24 hour
                  and coalesce(v.endtime, v.starttime) >= ac.intime
            ) then 1 else 0 end) as patient_count
        from audit_cohort ac
        union all
        select
            'first_24h_vasoactive_any_classifiable' as metric,
            count(*) as denominator,
            sum(case when exists (
                select 1
                from mimiciv_derived.vasoactive_agent v
                where v.stay_id = ac.stay_id
                  and v.starttime < ac.intime + interval 24 hour
                  and coalesce(v.endtime, v.starttime) >= ac.intime
            ) then 1 else 0 end) as patient_count
        from audit_cohort ac
        where ac.delirium_classifiable_72h = 1
        """
    )
    exposure["percent"] = [pct(x, d) for x, d in zip(exposure["patient_count"], exposure["denominator"])]
    out = pd.concat([pd.DataFrame(rows), exposure], ignore_index=True, sort=False)
    save_csv(out, "vasoactive_feasibility.csv")
    return out


def run_rrt_crrt_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    for table, key in [("rrt", ["stay_id", "charttime"]), ("crrt", ["stay_id", "charttime"]), ("first_day_rrt", ["stay_id"])]:
        rows.append(
            {
                "concept_table": table,
                "table_row_count": row_count(con, table),
                "duplicate_key_count": duplicate_count(con, table, key),
                "key_scope": "ICU time point" if len(key) == 2 else "one row per ICU stay expected",
                "status": "built_from_official_duckdb_sql",
            }
        )
    exposure = q(
        con,
        """
        select
            'first_24h_active_rrt' as metric,
            count(*) as denominator,
            sum(coalesce(fdrrt.dialysis_present, 0)) as patient_count
        from audit_cohort ac
        left join mimiciv_derived.first_day_rrt fdrrt
          on ac.stay_id = fdrrt.stay_id
        union all
        select
            'first_24h_active_rrt_classifiable' as metric,
            count(*) as denominator,
            sum(coalesce(fdrrt.dialysis_present, 0)) as patient_count
        from audit_cohort ac
        left join mimiciv_derived.first_day_rrt fdrrt
          on ac.stay_id = fdrrt.stay_id
        where ac.delirium_classifiable_72h = 1
        """
    )
    exposure["percent"] = [pct(x, d) for x, d in zip(exposure["patient_count"], exposure["denominator"])]
    out = pd.concat([pd.DataFrame(rows), exposure], ignore_index=True, sort=False)
    save_csv(out, "rrt_crrt_feasibility.csv")
    return out


def run_ventilation_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    for table, key in [
        ("ventilator_setting", ["stay_id", "charttime"]),
        ("oxygen_delivery", ["stay_id", "charttime"]),
        ("ventilation", ["stay_id", "starttime", "endtime", "ventilation_status"]),
    ]:
        rows.append(
            {
                "concept_table": table,
                "table_row_count": row_count(con, table),
                "duplicate_key_count": duplicate_count(con, table, key),
                "negative_or_zero_interval_count": int(
                    q(
                        con,
                        """
                        select count(*) as n
                        from mimiciv_derived.ventilation
                        where endtime <= starttime
                        """,
                    )["n"].iloc[0]
                )
                if table == "ventilation"
                else None,
                "status": "built_from_official_duckdb_sql",
            }
        )
    status_counts = q(
        con,
        """
        select
            ventilation_status as ventilation_category,
            count(*) as interval_count
        from mimiciv_derived.ventilation
        group by ventilation_status
        order by interval_count desc
        """
    )
    status_counts["concept_table"] = "ventilation_status_distribution"
    invasive = q(
        con,
        """
        select
            'first_24h_invasive_ventilation' as metric,
            count(*) as denominator,
            sum(case when exists (
                select 1
                from mimiciv_derived.ventilation v
                where v.stay_id = ac.stay_id
                  and v.ventilation_status = 'InvasiveVent'
                  and v.starttime < ac.intime + interval 24 hour
                  and v.endtime >= ac.intime
            ) then 1 else 0 end) as patient_count
        from audit_cohort ac
        union all
        select
            'first_24h_invasive_ventilation_classifiable' as metric,
            count(*) as denominator,
            sum(case when exists (
                select 1
                from mimiciv_derived.ventilation v
                where v.stay_id = ac.stay_id
                  and v.ventilation_status = 'InvasiveVent'
                  and v.starttime < ac.intime + interval 24 hour
                  and v.endtime >= ac.intime
            ) then 1 else 0 end) as patient_count
        from audit_cohort ac
        where ac.delirium_classifiable_72h = 1
        """
    )
    invasive["percent"] = [pct(x, d) for x, d in zip(invasive["patient_count"], invasive["denominator"])]
    out = pd.concat([pd.DataFrame(rows), status_counts, invasive], ignore_index=True, sort=False)
    save_csv(out, "ventilation_feasibility.csv")
    return out


def run_sofa_feasibility(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame]:
    comp = q(
        con,
        """
        select
            'base_population' as population,
            count(*) as denominator,
            count(fds.sofa) as sofa_nonmissing_n,
            count(fds.respiration) as respiratory_nonmissing_n,
            count(fds.coagulation) as coagulation_nonmissing_n,
            count(fds.liver) as liver_nonmissing_n,
            count(fds.cardiovascular) as cardiovascular_nonmissing_n,
            count(fds.renal) as renal_nonmissing_n,
            count(fds.cns) as cns_nonmissing_n,
            min(fds.sofa) as sofa_min,
            median(fds.sofa) as sofa_median,
            max(fds.sofa) as sofa_max
        from audit_cohort ac
        left join mimiciv_derived.first_day_sofa fds
          on ac.stay_id = fds.stay_id
        union all
        select
            'classifiable_72h_population' as population,
            count(*) as denominator,
            count(fds.sofa) as sofa_nonmissing_n,
            count(fds.respiration) as respiratory_nonmissing_n,
            count(fds.coagulation) as coagulation_nonmissing_n,
            count(fds.liver) as liver_nonmissing_n,
            count(fds.cardiovascular) as cardiovascular_nonmissing_n,
            count(fds.renal) as renal_nonmissing_n,
            count(fds.cns) as cns_nonmissing_n,
            min(fds.sofa) as sofa_min,
            median(fds.sofa) as sofa_median,
            max(fds.sofa) as sofa_max
        from audit_cohort ac
        left join mimiciv_derived.first_day_sofa fds
          on ac.stay_id = fds.stay_id
        where ac.delirium_classifiable_72h = 1
        """
    )
    comp["first_day_sofa_table_rows"] = row_count(con, "first_day_sofa")
    comp["hourly_sofa_table_rows"] = row_count(con, "sofa")
    comp["first_day_sofa_duplicate_key_count"] = duplicate_count(con, "first_day_sofa", ["stay_id"])
    save_csv(comp, "sofa_component_feasibility.csv")

    nn = q(
        con,
        """
        with first24 as (
            select
                ac.delirium_classifiable_72h,
                fds.sofa,
                fds.respiration,
                fds.coagulation,
                fds.liver,
                fds.cardiovascular,
                fds.renal,
                coalesce(fds.respiration, 0)
                + coalesce(fds.coagulation, 0)
                + coalesce(fds.liver, 0)
                + coalesce(fds.cardiovascular, 0)
                + coalesce(fds.renal, 0) as non_neurologic_sofa_zero_imputed,
                case when fds.respiration is not null
                       and fds.coagulation is not null
                       and fds.liver is not null
                       and fds.cardiovascular is not null
                       and fds.renal is not null
                     then fds.respiration + fds.coagulation + fds.liver + fds.cardiovascular + fds.renal
                     else null end as non_neurologic_sofa_complete_case
            from audit_cohort ac
            left join mimiciv_derived.first_day_sofa fds
              on ac.stay_id = fds.stay_id
        ),
        first6 as (
            select
                ac.stay_id,
                max(s.respiration) as respiration_0_6h,
                max(s.coagulation) as coagulation_0_6h,
                max(s.liver) as liver_0_6h,
                max(s.cardiovascular) as cardiovascular_0_6h,
                max(s.renal) as renal_0_6h
            from audit_cohort ac
            left join mimiciv_derived.sofa s
              on ac.stay_id = s.stay_id
             and s.hr between 0 and 6
            group by ac.stay_id
        ),
        first6_summary as (
            select
                count(*) as denominator,
                sum(case when respiration_0_6h is not null
                           and coagulation_0_6h is not null
                           and liver_0_6h is not null
                           and cardiovascular_0_6h is not null
                           and renal_0_6h is not null
                         then 1 else 0 end) as complete_0_6h_n
            from first6
        )
        select
            '0_24h_base_population' as window_population,
            count(*) as denominator,
            count(non_neurologic_sofa_complete_case) as complete_case_n,
            count(*) - count(non_neurologic_sofa_complete_case) as partial_missing_n,
            min(non_neurologic_sofa_zero_imputed) as zero_imputed_min,
            median(non_neurologic_sofa_zero_imputed) as zero_imputed_median,
            max(non_neurologic_sofa_zero_imputed) as zero_imputed_max,
            corr(non_neurologic_sofa_zero_imputed, sofa) as pearson_corr_with_complete_sofa,
            (select complete_0_6h_n from first6_summary) as complete_0_6h_n
        from first24
        union all
        select
            '0_24h_classifiable_72h_population' as window_population,
            count(*) as denominator,
            count(non_neurologic_sofa_complete_case) as complete_case_n,
            count(*) - count(non_neurologic_sofa_complete_case) as partial_missing_n,
            min(non_neurologic_sofa_zero_imputed) as zero_imputed_min,
            median(non_neurologic_sofa_zero_imputed) as zero_imputed_median,
            max(non_neurologic_sofa_zero_imputed) as zero_imputed_max,
            corr(non_neurologic_sofa_zero_imputed, sofa) as pearson_corr_with_complete_sofa,
            null as complete_0_6h_n
        from first24
        where delirium_classifiable_72h = 1
        """
    )
    missing_options = pd.DataFrame(
        [
            {
                "window_population": "candidate_missing_strategy",
                "candidate_strategy": "complete_case",
                "description": "Use only patients with all five non-neurologic organ components observed.",
                "sap_decision_required": True,
            },
            {
                "window_population": "candidate_missing_strategy",
                "candidate_strategy": "missing_component_as_zero",
                "description": "Official first-day SOFA total uses zero for missing components; may understate severity.",
                "sap_decision_required": True,
            },
            {
                "window_population": "candidate_missing_strategy",
                "candidate_strategy": "multiple_imputation_or_missing_indicators",
                "description": "Prespecify if non-neurologic SOFA enters adjusted models.",
                "sap_decision_required": True,
            },
        ]
    )
    out = pd.concat([nn, missing_options], ignore_index=True, sort=False)
    save_csv(out, "non_neurologic_sofa_feasibility.csv")
    return comp, out


def run_oasis_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = q(
        con,
        """
        select
            'base_population' as population,
            count(*) as denominator,
            count(o.oasis) as nonmissing_n,
            min(o.oasis) as min_value,
            quantile_cont(o.oasis, 0.25) as p25,
            median(o.oasis) as median_value,
            quantile_cont(o.oasis, 0.75) as p75,
            max(o.oasis) as max_value
        from audit_cohort ac
        left join mimiciv_derived.oasis o
          on ac.stay_id = o.stay_id
        union all
        select
            'classifiable_72h_population' as population,
            count(*) as denominator,
            count(o.oasis) as nonmissing_n,
            min(o.oasis) as min_value,
            quantile_cont(o.oasis, 0.25) as p25,
            median(o.oasis) as median_value,
            quantile_cont(o.oasis, 0.75) as p75,
            max(o.oasis) as max_value
        from audit_cohort ac
        left join mimiciv_derived.oasis o
          on ac.stay_id = o.stay_id
        where ac.delirium_classifiable_72h = 1
        """
    )
    out["table_row_count"] = row_count(con, "oasis")
    out["duplicate_key_count"] = duplicate_count(con, "oasis", ["stay_id"])
    out["status"] = "built_from_official_duckdb_sql"
    save_csv(out, "oasis_feasibility.csv")
    return out


def run_sepsis3_feasibility(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = q(
        con,
        """
        select
            'base_population' as population,
            count(*) as denominator,
            sum(case when s.sepsis3 = true then 1 else 0 end) as sepsis3_n
        from audit_cohort ac
        left join mimiciv_derived.sepsis3 s
          on ac.stay_id = s.stay_id
        union all
        select
            'classifiable_72h_population' as population,
            count(*) as denominator,
            sum(case when s.sepsis3 = true then 1 else 0 end) as sepsis3_n
        from audit_cohort ac
        left join mimiciv_derived.sepsis3 s
          on ac.stay_id = s.stay_id
        where ac.delirium_classifiable_72h = 1
        """
    )
    out["percent"] = [pct(x, d) for x, d in zip(out["sepsis3_n"], out["denominator"])]
    out["table_row_count"] = row_count(con, "sepsis3")
    out["duplicate_key_count"] = duplicate_count(con, "sepsis3", ["stay_id"])
    out["status"] = "built_from_official_duckdb_sql"
    save_csv(out, "sepsis3_feasibility.csv")
    return out


def write_technical_report(
    build_matrix: pd.DataFrame,
    raw_levels: pd.DataFrame,
    mortality: pd.DataFrame,
    followup: pd.DataFrame,
    charlson: pd.DataFrame,
    ventilation: pd.DataFrame,
    sofa_nn: pd.DataFrame,
    oasis: pd.DataFrame,
    sepsis3: pd.DataFrame,
) -> Path:
    successful_concepts = build_matrix.loc[build_matrix["can_directly_build"], "concept"].tolist()
    failed_concepts = build_matrix.loc[~build_matrix["can_directly_build"], "concept"].tolist()
    exact_flag = bool(followup["exact_followup_complete_flag_not_identifiable"].all())
    non_neuro_built = not sofa_nn.empty and "0_24h_base_population" in set(sofa_nn["window_population"].astype(str))
    lines = [
        "# Technical Feasibility Audit Report",
        "",
        "This audit used the formal data dictionary v1.0 as the target specification. It did not run formal outcome regression, adjusted interaction models, P-value screening, exposure/outcome-driven variable selection, or patient-level CSV export.",
        "",
        "## Variable Constructability",
        "",
        "- Cohort anchors, raw demographics, admission descriptors, ICU type, services, discharge fields, and frozen delirium classifiability can be constructed from local MIMIC-IV v3.1 tables.",
        "- Frozen psychiatric exposure definitions were not modified in this audit.",
        "- One-year mortality after index discharge is technically constructible from the patient death date.",
        "- Same-system readmission and ICU readmission event indicators are constructible, but exact administrative follow-up completeness at 90 or 365 days is not identifiable from shifted dates.",
        "- Official Charlson, vasoactive-agent, norepinephrine-equivalent-dose, RRT/CRRT, ventilation, first-day SOFA, OASIS, and Sepsis-3 concepts were technically buildable in an in-memory DuckDB audit session.",
        "",
        "## Required Technical Revisions",
        "",
        "- Historical shifted admission-year variables should remain deprecated; cross-patient period variables should use the patient anchor-year group.",
        "- Follow-up-complete flags for readmission outcomes should not be generated as exact patient-level administrative censoring flags.",
        "- Discharge location, hospice, ICU/hospital length of stay, and post-delirium care variables remain inappropriate for the primary adjustment model unless SAP explicitly assigns sensitivity/descriptive roles.",
        "- Non-neurologic SOFA missing-component handling must be prespecified in SAP.",
        "",
        "## Official Concepts",
        "",
        f"Successful concept groups: {', '.join(successful_concepts) if successful_concepts else 'none'}.",
        f"Concept groups not built: {', '.join(failed_concepts) if failed_concepts else 'none'}.",
        "",
        md_table(build_matrix[["concept", "can_directly_build", "build_difficulty", "recommended_build_order"]]),
        "",
        "## Non-neurologic SOFA",
        "",
        f"Reliable construction of 0-24h non-neurologic SOFA is technically feasible: {non_neuro_built}. CNS/GCS is excluded from the non-neurologic score. The 0-6h version is feasible using official hourly SOFA components, but its final definition and missing-data strategy should be decided in SAP.",
        "",
        md_table(sofa_nn),
        "",
        "## Follow-up",
        "",
        "- One-year mortality follow-up is supported for the specified after-discharge definition.",
        f"- Exact 90-day and 365-day administrative follow-up completeness for same-system readmission is identifiable: {not exact_flag}.",
        "- Recommended readmission handling: prespecify Strategy A as the broad same-system analysis and Strategy B as a conservative database-boundary sensitivity analysis, unless the SAP chooses a stricter primary approach.",
        "",
        md_table(followup.head(12)),
        "",
        "## SAP Decisions Still Needed",
        "",
        "- Whether to use all-patient same-system readmission analyses or conservative approximate-year restrictions.",
        "- How to handle hospice discharge and same-day death in primary and sensitivity analyses.",
        "- Which acute severity measure enters each model tier and how to handle missing SOFA/OASIS components.",
        "- Whether Sepsis-3 is required by the final DAG/SAP or retained as sensitivity/descriptive information.",
        "",
        "## SAP Readiness",
        "",
        "The project has sufficient technical information to draft SAP v1.0, provided the SAP explicitly resolves follow-up boundary handling and severity-score missingness.",
        "",
        "## Output QC",
        "",
        "All CSV outputs are aggregate QC summaries and do not contain patient-level identifier columns.",
    ]
    return write_md(OUTDIR / "technical_feasibility_audit_report.md", lines)


def scan_outputs_for_forbidden_tokens() -> pd.DataFrame:
    rows = []
    for path in OUTDIR.glob("*"):
        if path.suffix.lower() not in {".csv", ".md"}:
            continue
        text = path.read_text(encoding="utf-8-sig" if path.suffix.lower() == ".csv" else "utf-8", errors="ignore").lower()
        hits = [tok for tok in FORBIDDEN_OUTPUT_TOKENS if tok in text]
        rows.append(
            {
                "file": path.name,
                "forbidden_token_found": bool(hits),
                "tokens": ";".join(hits),
            }
        )
    out = pd.DataFrame(rows)
    save_csv(out, "output_identifier_qc.csv")
    return out


def main() -> None:
    ensure_dirs()
    if not OFFICIAL_ARCHIVE_DIR.exists():
        raise FileNotFoundError(
            f"Official mimic-code archive not found: {OFFICIAL_ARCHIVE_DIR}. "
            "Download/extract the specified commit before running this script."
        )
    con = duckdb.connect(":memory:")
    setup_source_aliases(con)
    setup_cohort_and_delirium(con)

    print("Writing raw-category audit...")
    raw_levels = run_raw_category_audit(con)
    print("Writing calendar audit...")
    calendar = run_calendar_audit(con)
    print("Writing mortality audit...")
    mortality = run_mortality_audit(con)
    print("Writing follow-up coverage audit...")
    followup, _ = run_followup_coverage(calendar)

    print("Preparing official/adapted SQL files...")
    inventory = copy_and_prepare_sql_files()
    print("Building official derived concepts in memory...")
    builds = run_official_builds(con, inventory)
    print("Writing dependency matrix...")
    build_matrix = run_dependency_matrix(builds, inventory)

    print("Writing concept feasibility summaries...")
    charlson = run_charlson_feasibility(con)
    vaso = run_vasoactive_feasibility(con)
    rrt = run_rrt_crrt_feasibility(con)
    vent = run_ventilation_feasibility(con)
    sofa_comp, sofa_nn = run_sofa_feasibility(con)
    oasis = run_oasis_feasibility(con)
    sepsis3 = run_sepsis3_feasibility(con)

    _ = vaso, rrt, sofa_comp
    print("Writing technical report...")
    report = write_technical_report(
        build_matrix,
        raw_levels,
        mortality,
        followup,
        charlson,
        vent,
        sofa_nn,
        oasis,
        sepsis3,
    )
    print("Scanning outputs for identifier tokens...")
    qc = scan_outputs_for_forbidden_tokens()
    bad = qc[qc["forbidden_token_found"]]
    if not bad.empty:
        raise RuntimeError(
            "Forbidden identifier tokens found in output files: "
            + ", ".join(bad["file"].astype(str).tolist())
        )
    print(f"Technical feasibility audit complete: {report}")
    con.close()


if __name__ == "__main__":
    main()
