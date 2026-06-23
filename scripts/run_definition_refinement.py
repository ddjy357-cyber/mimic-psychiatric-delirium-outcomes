from __future__ import annotations

import itertools
from pathlib import Path
import os

import duckdb
import numpy as np
import pandas as pd


PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", PROJECT.parent))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", WORKSPACE / "data" / "mimiciv.duckdb"))
OUTDIR = PROJECT / "outputs" / "definition_refinement"
OFFICIAL_MIMIC_CODE_COMMIT = "57069783095e7770e66ea97da264c0200078ddbf"
OFFICIAL_VENTILATION_SQL_URL = (
    "https://github.com/MIT-LCP/mimic-code/blob/main/"
    "mimic-iv/concepts/treatment/ventilation.sql"
)


LEAF_CATEGORIES = [
    "depressive_disorders",
    "anxiety_disorders",
    "ptsd",
    "bipolar_disorders",
    "schizophrenia_psychotic_disorders",
    "alcohol_use_disorders",
    "other_substance_use_disorders",
    "dementia_cognitive_disorders",
]

PSYCH_CATEGORIES = [
    "common_mental_disorders",
    "serious_mental_illness",
    "substance_use_disorders",
    "dementia_cognitive_disorders",
    "primary_psychiatric_comorbidity",
]

WINDOWS = {
    "24h_at_least_one_negative": {
        "end_expr": "least(ib.outtime, ib.intime + interval '24 hours')",
        "rule": "one_negative",
    },
    "24h_at_least_two_negative_records": {
        "end_expr": "least(ib.outtime, ib.intime + interval '24 hours')",
        "rule": "two_negative_records",
    },
    "48h_two_negative_days": {
        "end_expr": "least(ib.outtime, ib.intime + interval '48 hours')",
        "rule": "two_negative_days",
    },
    "72h_two_negative_days": {
        "end_expr": "least(ib.outtime, ib.intime + interval '72 hours')",
        "rule": "two_negative_days",
    },
    "whole_icu_two_negative_days": {
        "end_expr": "ib.outtime",
        "rule": "two_negative_days",
    },
}


def ensure_dirs() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)


def q(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).fetchdf()


def pct(num: float | int | None, den: float | int | None) -> float | None:
    if den is None or den == 0 or pd.isna(den):
        return None
    if num is None or pd.isna(num):
        num = 0
    return round(float(num) / float(den) * 100.0, 2)


def save_csv(df: pd.DataFrame, filename: str) -> Path:
    path = OUTDIR / filename
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
    return df.to_markdown(index=False)


def setup_index_base(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table index_icu as
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
            a.race,
            a.hospital_expire_flag,
            p.anchor_age + date_part('year', a.admittime)::integer - p.anchor_year as age_at_admission_approx,
            row_number() over (
                partition by ie.subject_id
                order by ie.intime, ie.stay_id
            ) as rn_subject
        from icu.icustays ie
        join hosp.patients p using (subject_id)
        join hosp.admissions a using (subject_id, hadm_id)
        """
    )
    con.execute(
        """
        create or replace temp table index_base as
        select *
        from index_icu
        where rn_subject = 1
          and anchor_age >= 18
          and icu_los_days >= 1
          and hospital_expire_flag = 0
        """
    )


def setup_psychiatric_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        r"""
        create or replace temp table psych_candidate_codes_refined as
        with observed_codes as (
            select distinct
                dx.icd_code,
                dx.icd_version,
                dd.long_title
            from hosp.diagnoses_icd dx
            join hosp.d_icd_diagnoses dd
              on dx.icd_code = dd.icd_code
             and dx.icd_version = dd.icd_version
        )
        select *
        from (
            select 'depressive_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(depressive|depression|dysthym)')
            union all
            select 'anxiety_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(anxiety|panic disorder|phobia|phobic|obsessive-compulsive|ocd)')
            union all
            select 'ptsd' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(post-traumatic stress|posttraumatic stress|post traumatic stress|ptsd)')
            union all
            select 'bipolar_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(bipolar|manic episode|mania|cyclothym)')
            union all
            select 'schizophrenia_psychotic_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(schizo|psychosis|psychotic|delusional|paranoid)')
            union all
            select 'alcohol_use_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(alcohol dependence|alcohol abuse|alcohol use disorder|alcohol-induced|alcohol withdrawal|alcohol intoxication|alcoholism|alcoholic psychosis|alcoholic hallucinosis)')
            union all
            select 'other_substance_use_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(opioid|cannabis|sedative|hypnotic|anxiolytic|cocaine|amphetamine|stimulant|hallucinogen|inhalant|psychoactive substance|drug abuse|drug dependence|substance abuse|substance dependence|substance use disorder)')
              and not regexp_matches(lower(long_title), '(alcohol|tobacco|nicotine)')
            union all
            select 'dementia_cognitive_disorders' as leaf_category, * from observed_codes
            where regexp_matches(lower(long_title), '(dementia|alzheimer|mild cognitive|cognitive disorder|amnestic|memory loss|senile degeneration|frontotemporal|lewy body)')
        )
        """
    )

    con.execute(
        """
        create or replace temp table psych_dx_events_refined as
        select
            ib.subject_id,
            ib.hadm_id as index_hadm_id,
            ib.admittime as index_admittime,
            pc.leaf_category,
            dx.hadm_id as dx_hadm_id,
            adm.admittime as dx_admittime,
            date_diff('day', ib.admittime, adm.admittime) as dx_days_relative_to_index,
            dx.icd_code,
            dx.icd_version,
            pc.long_title,
            case
                when adm.admittime < ib.admittime and dx.hadm_id <> ib.hadm_id then 'prior_admission'
                when dx.hadm_id = ib.hadm_id then 'index_admission'
                else 'after_index_or_uncertain'
            end as diagnosis_relation
        from index_base ib
        join hosp.diagnoses_icd dx
          on ib.subject_id = dx.subject_id
        join hosp.admissions adm
          on dx.subject_id = adm.subject_id
         and dx.hadm_id = adm.hadm_id
        join psych_candidate_codes_refined pc
          on dx.icd_code = pc.icd_code
         and dx.icd_version = pc.icd_version
        """
    )

    leaf_sql = ",\n".join(
        [
            f"""
            max(case when e.leaf_category = '{cat}' and e.diagnosis_relation = 'prior_admission' then 1 else 0 end) as {cat}_strict_prior,
            max(case when e.leaf_category = '{cat}' and e.diagnosis_relation in ('prior_admission', 'index_admission') then 1 else 0 end) as {cat}_documented_by_index
            """
            for cat in LEAF_CATEGORIES
        ]
    )
    con.execute(
        f"""
        create or replace temp table psych_leaf_flags_refined as
        select
            ib.subject_id,
            {leaf_sql}
        from index_base ib
        left join psych_dx_events_refined e
          on ib.subject_id = e.subject_id
        group by ib.subject_id
        """
    )

    con.execute(
        """
        create or replace temp table psych_subject_flags_refined as
        select
            subject_id,
            greatest(
                depressive_disorders_strict_prior,
                anxiety_disorders_strict_prior,
                ptsd_strict_prior
            ) as common_mental_disorders_strict_prior,
            greatest(
                depressive_disorders_documented_by_index,
                anxiety_disorders_documented_by_index,
                ptsd_documented_by_index
            ) as common_mental_disorders_documented_by_index,
            greatest(
                bipolar_disorders_strict_prior,
                schizophrenia_psychotic_disorders_strict_prior
            ) as serious_mental_illness_strict_prior,
            greatest(
                bipolar_disorders_documented_by_index,
                schizophrenia_psychotic_disorders_documented_by_index
            ) as serious_mental_illness_documented_by_index,
            greatest(
                alcohol_use_disorders_strict_prior,
                other_substance_use_disorders_strict_prior
            ) as substance_use_disorders_strict_prior,
            greatest(
                alcohol_use_disorders_documented_by_index,
                other_substance_use_disorders_documented_by_index
            ) as substance_use_disorders_documented_by_index,
            dementia_cognitive_disorders_strict_prior,
            dementia_cognitive_disorders_documented_by_index,
            greatest(
                depressive_disorders_strict_prior,
                anxiety_disorders_strict_prior,
                ptsd_strict_prior,
                bipolar_disorders_strict_prior,
                schizophrenia_psychotic_disorders_strict_prior
            ) as primary_psychiatric_comorbidity_strict_prior,
            greatest(
                depressive_disorders_documented_by_index,
                anxiety_disorders_documented_by_index,
                ptsd_documented_by_index,
                bipolar_disorders_documented_by_index,
                schizophrenia_psychotic_disorders_documented_by_index
            ) as primary_psychiatric_comorbidity_documented_by_index,
            greatest(
                depressive_disorders_strict_prior,
                anxiety_disorders_strict_prior,
                ptsd_strict_prior,
                bipolar_disorders_strict_prior,
                schizophrenia_psychotic_disorders_strict_prior,
                alcohol_use_disorders_strict_prior,
                other_substance_use_disorders_strict_prior
            ) as primary_plus_substance_strict_prior,
            greatest(
                depressive_disorders_documented_by_index,
                anxiety_disorders_documented_by_index,
                ptsd_documented_by_index,
                bipolar_disorders_documented_by_index,
                schizophrenia_psychotic_disorders_documented_by_index,
                alcohol_use_disorders_documented_by_index,
                other_substance_use_disorders_documented_by_index
            ) as primary_plus_substance_documented_by_index,
            greatest(
                depressive_disorders_strict_prior,
                anxiety_disorders_strict_prior,
                ptsd_strict_prior,
                bipolar_disorders_strict_prior,
                schizophrenia_psychotic_disorders_strict_prior,
                dementia_cognitive_disorders_strict_prior
            ) as primary_plus_dementia_strict_prior,
            greatest(
                depressive_disorders_documented_by_index,
                anxiety_disorders_documented_by_index,
                ptsd_documented_by_index,
                bipolar_disorders_documented_by_index,
                schizophrenia_psychotic_disorders_documented_by_index,
                dementia_cognitive_disorders_documented_by_index
            ) as primary_plus_dementia_documented_by_index
        from psych_leaf_flags_refined
        """
    )

    tall_parts = []
    for category in PSYCH_CATEGORIES:
        for definition in ["strict_prior", "documented_by_index"]:
            tall_parts.append(
                f"""
                select
                    subject_id,
                    '{category}' as psychiatric_category,
                    '{definition}' as definition,
                    {category}_{definition} as flag
                from psych_subject_flags_refined
                """
            )
    con.execute(
        "create or replace temp table psych_category_tall_refined as "
        + "\nunion all\n".join(tall_parts)
    )


def setup_comorbidity_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table dx_by_index_refined as
        select
            ib.subject_id,
            dx.icd_code,
            dx.icd_version,
            upper(dx.icd_code) as code
        from index_base ib
        join hosp.diagnoses_icd dx
          on ib.subject_id = dx.subject_id
        join hosp.admissions adm
          on dx.subject_id = adm.subject_id
         and dx.hadm_id = adm.hadm_id
        where dx.hadm_id = ib.hadm_id
           or (adm.admittime < ib.admittime and dx.hadm_id <> ib.hadm_id)
        """
    )
    con.execute(
        r"""
        create or replace temp table comorbidity_flags_refined as
        select
            ib.subject_id,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(410|412)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(I21|I22|I252)'))
            ) then 1 else 0 end) as myocardial_infarction,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(39891|40201|40211|40291|40401|40403|40411|40413|40491|40493|428)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(I50|I110|I130|I132)'))
            ) then 1 else 0 end) as congestive_heart_failure,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(49[0-6]|50[0-5]|5064)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(J4[0-7]|J6[0-7])'))
            ) then 1 else 0 end) as chronic_pulmonary_disease,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(250)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(E10|E11|E12|E13|E14)'))
            ) then 1 else 0 end) as diabetes,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(585|586|V420|V451)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(N18|N19|Z940|Z992)'))
            ) then 1 else 0 end) as chronic_kidney_disease,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(070|570|571|572)')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(B18|K7[0-7])'))
            ) then 1 else 0 end) as liver_disease,
            max(case when (
                (d.icd_version = 9 and regexp_matches(d.code, '^(14[0-9]|15[0-9]|16[0-9]|17[0-6]|17[9]|18[0-9]|19[0-9]|20[0-9])')) or
                (d.icd_version = 10 and regexp_matches(d.code, '^(C|D0[0-9]|D3[7-9]|D4[0-8])'))
            ) then 1 else 0 end) as malignancy
        from index_base ib
        left join dx_by_index_refined d
          on ib.subject_id = d.subject_id
        group by ib.subject_id
        """
    )


def setup_outcome_and_utilization_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table outcomes_refined as
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            case when ib.dod = cast(ib.dischtime as date) then 1 else 0 end as dod_on_discharge_day,
            case when lower(coalesce(ib.discharge_location, '')) like '%hospice%' then 1 else 0 end as hospice_discharge,
            case when ib.dod > cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 30 day
                 then 1 else 0 end as death_30d_after_discharge,
            case when ib.dod > cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 90 day
                 then 1 else 0 end as death_90d_after_discharge,
            case when ib.dod > cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                 then 1 else 0 end as death_1y_after_discharge,
            case when ib.dod >= cast(ib.dischtime as date)
                    and ib.dod <= cast(ib.dischtime as date) + interval 365 day
                 then 1 else 0 end as death_1y_after_discharge_including_same_day_dod,
            case when exists (
                select 1
                from hosp.admissions ra
                where ra.subject_id = ib.subject_id
                  and ra.hadm_id <> ib.hadm_id
                  and ra.admittime > ib.dischtime
                  and ra.admittime <= ib.dischtime + interval 30 day
            ) then 1 else 0 end as readmit_30d_same_system,
            case when exists (
                select 1
                from hosp.admissions ra
                where ra.subject_id = ib.subject_id
                  and ra.hadm_id <> ib.hadm_id
                  and ra.admittime > ib.dischtime
                  and ra.admittime <= ib.dischtime + interval 90 day
            ) then 1 else 0 end as readmit_90d_same_system,
            case when exists (
                select 1
                from hosp.admissions ra
                where ra.subject_id = ib.subject_id
                  and ra.hadm_id <> ib.hadm_id
                  and ra.admittime > ib.dischtime
                  and ra.admittime <= ib.dischtime + interval 365 day
            ) then 1 else 0 end as readmit_1y_same_system,
            case when exists (
                select 1
                from icu.icustays ri
                join hosp.admissions ra
                  on ri.subject_id = ra.subject_id
                 and ri.hadm_id = ra.hadm_id
                where ri.subject_id = ib.subject_id
                  and ri.hadm_id <> ib.hadm_id
                  and ra.admittime > ib.dischtime
                  and ri.intime > ib.dischtime
                  and ri.intime <= ib.dischtime + interval 365 day
            ) then 1 else 0 end as icu_readmit_1y_same_system
        from index_base ib
        """
    )

    con.execute(
        """
        create or replace temp table prior_utilization_refined as
        select
            ib.subject_id,
            count(distinct adm.hadm_id) filter (
                where adm.hadm_id <> ib.hadm_id and adm.admittime < ib.admittime
            ) as prior_mimic_hospitalizations,
            count(distinct icu.stay_id) filter (
                where icu.stay_id <> ib.stay_id and icu.intime < ib.intime
            ) as prior_mimic_icu_stays
        from index_base ib
        left join hosp.admissions adm
          on ib.subject_id = adm.subject_id
        left join icu.icustays icu
          on ib.subject_id = icu.subject_id
        group by ib.subject_id
        """
    )


def setup_airway_and_ventilation_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table airway_and_ventilation_refined as
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            case when exists (
                select 1
                from icu.procedureevents pe
                where pe.subject_id = ib.subject_id
                  and pe.hadm_id = ib.hadm_id
                  and pe.stay_id = ib.stay_id
                  and pe.itemid in (224385, 225448, 226237)
                  and coalesce(pe.endtime, pe.starttime) >= ib.intime
                  and pe.starttime <= ib.outtime
            ) then 1 else 0 end as airway_procedure_proxy,
            case when exists (
                select 1
                from icu.procedureevents pe
                where pe.subject_id = ib.subject_id
                  and pe.hadm_id = ib.hadm_id
                  and pe.stay_id = ib.stay_id
                  and pe.itemid in (225792)
                  and coalesce(pe.endtime, pe.starttime) >= ib.intime
                  and pe.starttime <= ib.outtime
            ) then 1 else 0 end as procedure_invasive_ventilation_proxy,
            case when exists (
                select 1
                from icu.procedureevents pe
                where pe.subject_id = ib.subject_id
                  and pe.hadm_id = ib.hadm_id
                  and pe.stay_id = ib.stay_id
                  and pe.itemid in (225794)
                  and coalesce(pe.endtime, pe.starttime) >= ib.intime
                  and pe.starttime <= ib.outtime
            ) then 1 else 0 end as procedure_noninvasive_ventilation_proxy,
            cast(null as integer) as official_invasive_ventilation,
            'pending_derived_tables' as official_invasive_ventilation_status
        from index_base ib
        """
    )


def setup_delirium_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table delirium_events_refined as
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
        from index_base ib
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
        """
        create or replace temp table rass_events_refined as
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
        from index_base ib
        join icu.chartevents ce
          on ib.subject_id = ce.subject_id
         and ib.hadm_id = ce.hadm_id
         and ib.stay_id = ce.stay_id
        where ce.itemid = 228096
          and ce.charttime >= ib.intime
          and ce.charttime <= ib.outtime
        """
    )


def build_window_union_sql(
    source_table: str,
    output_table: str,
    negative_valid_condition: str = "de.value_class = 'negative'",
    positive_condition: str = "de.value_class = 'positive'",
    direct_positive_condition: str | None = None,
) -> None:
    # This helper returns SQL text through a closure below; keeping it as a real
    # function makes the repeated window definitions less error-prone.
    return None


def window_union_sql(
    source_table: str,
    positive_condition: str = "de.value_class = 'positive'",
    negative_valid_condition: str = "de.value_class = 'negative'",
    direct_positive_condition: str | None = None,
) -> str:
    parts = []
    for window_name, cfg in WINDOWS.items():
        end_expr = cfg["end_expr"]
        rule = cfg["rule"]
        if rule == "one_negative":
            negative_rule_sql = "negative_count >= 1"
        elif rule == "two_negative_records":
            negative_rule_sql = "negative_count >= 2"
        else:
            negative_rule_sql = "negative_days >= 2"
        direct_positive_inner_condition = (
            direct_positive_condition
            if direct_positive_condition
            else "de.value_class = 'positive'"
        )
        parts.append(
            f"""
            select
                subject_id,
                hadm_id,
                stay_id,
                '{window_name}' as delirium_window,
                assessment_count,
                positive_count,
                direct_positive_count,
                negative_count,
                negative_days,
                uta_count,
                uta_days,
                case
                    when positive_count > 0 then 'positive'
                    when direct_positive_count > 0 and positive_count = 0 then 'unclassifiable_direct_positive_without_cam_consistency'
                    when positive_count = 0 and {negative_rule_sql} then 'negative'
                    else 'unclassifiable'
                end as delirium_status
            from (
                select
                    ib.subject_id,
                    ib.hadm_id,
                    ib.stay_id,
                    count(de.assessment_id) as assessment_count,
                    sum(case when {positive_condition} then 1 else 0 end) as positive_count,
                    sum(case when {direct_positive_inner_condition} then 1 else 0 end) as direct_positive_count,
                    sum(case when {negative_valid_condition} then 1 else 0 end) as negative_count,
                    count(distinct case when {negative_valid_condition} then de.assessment_date end) as negative_days,
                    sum(case when de.value_class = 'uta' then 1 else 0 end) as uta_count,
                    count(distinct case when de.value_class = 'uta' then de.assessment_date end) as uta_days
                from index_base ib
                left join {source_table} de
                  on ib.subject_id = de.subject_id
                 and ib.hadm_id = de.hadm_id
                 and ib.stay_id = de.stay_id
                 and de.charttime >= ib.intime
                 and de.charttime <= {end_expr}
                group by ib.subject_id, ib.hadm_id, ib.stay_id
            )
            """
        )
    return "\nunion all\n".join(parts)


def create_window_classification(
    con: duckdb.DuckDBPyConnection,
    output_table: str,
    source_table: str = "delirium_events_refined",
    positive_condition: str = "de.value_class = 'positive'",
    negative_valid_condition: str = "de.value_class = 'negative'",
    direct_positive_condition: str | None = None,
) -> None:
    con.execute(
        f"""
        create or replace temp table {output_table} as
        {window_union_sql(source_table, positive_condition, negative_valid_condition, direct_positive_condition)}
        """
    )


def setup_cam_consistency_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        r"""
        create or replace temp table cam_component_day_flags_refined as
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            cast(ce.charttime as date) as component_date,
            max(case when ce.itemid in (228300, 228337, 229326)
                      and regexp_matches(lower(coalesce(ce.value, '')), '(^yes|positive)')
                     then 1 else 0 end) as ms_change_yes,
            max(case when ce.itemid in (228301, 228336, 229325)
                      and regexp_matches(lower(coalesce(ce.value, '')), '(^yes|positive)')
                     then 1 else 0 end) as inattention_yes,
            max(case when ce.itemid in (228303, 228335, 229324)
                      and regexp_matches(lower(coalesce(ce.value, '')), '(^yes|positive)')
                     then 1 else 0 end) as disorganized_yes,
            max(case when ce.itemid in (228302, 228334)
                      and regexp_matches(lower(coalesce(ce.value, '')), '(^yes|positive)')
                     then 1 else 0 end) as altered_loc_yes
        from index_base ib
        join icu.chartevents ce
          on ib.subject_id = ce.subject_id
         and ib.hadm_id = ce.hadm_id
         and ib.stay_id = ce.stay_id
        where ce.itemid in (228300, 228337, 229326, 228301, 228336, 229325, 228303, 228335, 229324, 228302, 228334)
          and ce.charttime >= ib.intime
          and ce.charttime <= ib.outtime
        group by ib.subject_id, ib.hadm_id, ib.stay_id, cast(ce.charttime as date)
        """
    )
    con.execute(
        """
        create or replace temp table cam_positive_days_refined as
        select
            subject_id,
            hadm_id,
            stay_id,
            component_date
        from cam_component_day_flags_refined
        where ms_change_yes = 1
          and inattention_yes = 1
          and (disorganized_yes = 1 or altered_loc_yes = 1)
        """
    )
    con.execute(
        """
        create or replace temp table delirium_events_cam_refined as
        select
            de.*,
            case when de.value_class = 'positive'
                   and exists (
                       select 1
                       from cam_positive_days_refined cp
                       where cp.subject_id = de.subject_id
                         and cp.hadm_id = de.hadm_id
                         and cp.stay_id = de.stay_id
                         and cp.component_date = de.assessment_date
                   )
                 then 1 else 0 end as direct_positive_cam_consistent
        from delirium_events_refined de
        """
    )


def setup_rass_matching_tables(con: duckdb.DuckDBPyConnection) -> None:
    thresholds = {
        "same_timestamp": 0,
        "within_1h": 3600,
        "within_4h": 14400,
    }
    for label, seconds in thresholds.items():
        con.execute(
            f"""
            create or replace temp table nearest_rass_{label}_refined as
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
                from delirium_events_refined d
                join rass_events_refined r
                  on d.subject_id = r.subject_id
                 and d.hadm_id = r.hadm_id
                 and d.stay_id = r.stay_id
                where abs(date_diff('second', d.charttime, r.charttime)) <= {seconds}
            )
            select *
            from matches
            where rn = 1
            """
        )

        con.execute(
            f"""
            create or replace temp table delirium_events_rass_valid_{label}_refined as
            select
                d.*,
                nr.rass_valuenum,
                nr.rass_value,
                nr.abs_seconds,
                case when d.value_class = 'negative'
                       and nr.rass_valuenum <= -4
                     then 1 else 0 end as invalid_negative_rass_le_minus4
            from delirium_events_refined d
            left join nearest_rass_{label}_refined nr
              on d.assessment_id = nr.assessment_id
            """
        )


def setup_master_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table cohort_master_refined as
        select
            ib.subject_id,
            ib.hadm_id,
            ib.stay_id,
            ib.first_careunit,
            ib.last_careunit,
            ib.intime,
            ib.outtime,
            ib.icu_los_days,
            ib.gender,
            ib.anchor_age,
            ib.age_at_admission_approx,
            ib.dischtime,
            ib.discharge_location,
            psf.* exclude(subject_id),
            cf.* exclude(subject_id),
            av.airway_procedure_proxy,
            av.procedure_invasive_ventilation_proxy,
            av.procedure_noninvasive_ventilation_proxy,
            av.official_invasive_ventilation,
            av.official_invasive_ventilation_status,
            ou.* exclude(subject_id, hadm_id, stay_id),
            pu.prior_mimic_hospitalizations,
            pu.prior_mimic_icu_stays
        from index_base ib
        left join psych_subject_flags_refined psf using (subject_id)
        left join comorbidity_flags_refined cf using (subject_id)
        left join airway_and_ventilation_refined av using (subject_id, hadm_id, stay_id)
        left join outcomes_refined ou using (subject_id, hadm_id, stay_id)
        left join prior_utilization_refined pu using (subject_id)
        """
    )


def run_psychiatric_overlap(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    base_n = q(con, "select count(*) as n from cohort_master_refined")["n"].iloc[0]
    rows: list[dict] = []

    category_counts = q(
        con,
        """
        select
            psychiatric_category,
            definition,
            sum(flag) as patient_count
        from psych_category_tall_refined
        group by psychiatric_category, definition
        order by psychiatric_category, definition
        """
    )
    for _, row in category_counts.iterrows():
        rows.append(
            {
                "section": "category_counts",
                "definition": row["definition"],
                "category_a": row["psychiatric_category"],
                "category_b": "",
                "patient_count": int(row["patient_count"]),
                "percent_of_base": pct(row["patient_count"], base_n),
            }
        )

    for definition in ["strict_prior", "documented_by_index"]:
        for a, b in itertools.combinations(PSYCH_CATEGORIES, 2):
            col_a = f"{a}_{definition}"
            col_b = f"{b}_{definition}"
            overlap = q(
                con,
                f"""
                select
                    sum(case when {col_a} = 1 and {col_b} = 1 then 1 else 0 end) as both_n,
                    sum(case when {col_a} = 1 and {col_b} = 0 then 1 else 0 end) as a_only_n,
                    sum(case when {col_a} = 0 and {col_b} = 1 then 1 else 0 end) as b_only_n
                from cohort_master_refined
                """
            ).iloc[0]
            rows.append(
                {
                    "section": "category_overlap",
                    "definition": definition,
                    "category_a": a,
                    "category_b": b,
                    "patient_count": int(overlap["both_n"] or 0),
                    "a_only_n": int(overlap["a_only_n"] or 0),
                    "b_only_n": int(overlap["b_only_n"] or 0),
                    "percent_of_base": pct(overlap["both_n"] or 0, base_n),
                }
            )

    baseline = q(
        con,
        """
        select
            case when primary_psychiatric_comorbidity_documented_by_index = 1
                 then 'primary_psych_documented'
                 else 'no_primary_psych_documented'
            end as stratum,
            count(*) as patient_count,
            avg(anchor_age) as age_mean,
            median(anchor_age) as age_median,
            sum(case when gender = 'F' then 1 else 0 end) as female_n,
            avg(myocardial_infarction) as myocardial_infarction_rate,
            avg(congestive_heart_failure) as congestive_heart_failure_rate,
            avg(chronic_pulmonary_disease) as chronic_pulmonary_disease_rate,
            avg(diabetes) as diabetes_rate,
            avg(chronic_kidney_disease) as chronic_kidney_disease_rate,
            avg(liver_disease) as liver_disease_rate,
            avg(malignancy) as malignancy_rate,
            median(prior_mimic_hospitalizations) as prior_hosp_median,
            quantile_cont(prior_mimic_hospitalizations, 0.75) as prior_hosp_p75
        from cohort_master_refined
        group by stratum
        order by stratum
        """
    )
    for _, row in baseline.iterrows():
        rows.append(
            {
                "section": "age_sex_comorbidity_by_primary_psych_documented",
                "definition": "documented_by_index",
                "category_a": row["stratum"],
                "patient_count": int(row["patient_count"]),
                "age_mean": round(float(row["age_mean"]), 2),
                "age_median": row["age_median"],
                "female_n": int(row["female_n"]),
                "female_percent": pct(row["female_n"], row["patient_count"]),
                "myocardial_infarction_percent": round(float(row["myocardial_infarction_rate"]) * 100, 2),
                "congestive_heart_failure_percent": round(float(row["congestive_heart_failure_rate"]) * 100, 2),
                "chronic_pulmonary_disease_percent": round(float(row["chronic_pulmonary_disease_rate"]) * 100, 2),
                "diabetes_percent": round(float(row["diabetes_rate"]) * 100, 2),
                "chronic_kidney_disease_percent": round(float(row["chronic_kidney_disease_rate"]) * 100, 2),
                "liver_disease_percent": round(float(row["liver_disease_rate"]) * 100, 2),
                "malignancy_percent": round(float(row["malignancy_rate"]) * 100, 2),
                "prior_hosp_median": row["prior_hosp_median"],
                "prior_hosp_p75": row["prior_hosp_p75"],
            }
        )

    # Category-specific four-group counts use the more defensible early windows.
    for category in PSYCH_CATEGORIES:
        for definition in ["strict_prior", "documented_by_index"]:
            for window in ["48h_two_negative_days", "72h_two_negative_days"]:
                psych_col = f"{category}_{definition}"
                group_df = q(
                    con,
                    f"""
                    select
                        case
                            when cm.{psych_col} = 0 and dw.delirium_status = 'negative' then '1_no_psych_no_delirium'
                            when cm.{psych_col} = 1 and dw.delirium_status = 'negative' then '2_psych_no_delirium'
                            when cm.{psych_col} = 0 and dw.delirium_status = 'positive' then '3_no_psych_delirium'
                            when cm.{psych_col} = 1 and dw.delirium_status = 'positive' then '4_psych_delirium'
                            else 'excluded_unclassifiable_delirium'
                        end as four_group,
                        count(*) as patient_count,
                        sum(cm.death_1y_after_discharge) as death_1y_n
                    from cohort_master_refined cm
                    join delirium_window_classification_refined dw using (subject_id, hadm_id, stay_id)
                    where dw.delirium_window = '{window}'
                    group by four_group
                    order by four_group
                    """
                )
                for _, row in group_df.iterrows():
                    rows.append(
                        {
                            "section": "category_four_group_1y_death",
                            "definition": definition,
                            "category_a": category,
                            "category_b": window,
                            "four_group": row["four_group"],
                            "patient_count": int(row["patient_count"]),
                            "death_1y_n": int(row["death_1y_n"] or 0),
                            "death_1y_rate_percent": pct(row["death_1y_n"] or 0, row["patient_count"]),
                        }
                    )

    out = pd.DataFrame(rows)
    save_csv(out, "psychiatric_category_overlap.csv")
    return out


def run_psychiatric_code_source(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = q(
        con,
        """
        select
            pc.leaf_category,
            case
                when pc.leaf_category in ('depressive_disorders', 'anxiety_disorders', 'ptsd')
                    then 'common_mental_disorders'
                when pc.leaf_category in ('bipolar_disorders', 'schizophrenia_psychotic_disorders')
                    then 'serious_mental_illness'
                when pc.leaf_category in ('alcohol_use_disorders', 'other_substance_use_disorders')
                    then 'substance_use_disorders'
                when pc.leaf_category = 'dementia_cognitive_disorders'
                    then 'dementia_cognitive_disorders'
                else 'unmapped'
            end as aggregate_category,
            pc.icd_code,
            pc.icd_version,
            pc.long_title,
            count(dx.*) as diagnosis_record_count_in_full_mimic,
            count(distinct dx.subject_id) as subject_count_in_full_mimic,
            count(distinct e.subject_id) filter (where e.diagnosis_relation = 'prior_admission') as strict_prior_subjects_in_base,
            count(distinct e.subject_id) filter (where e.diagnosis_relation in ('prior_admission', 'index_admission')) as documented_by_index_subjects_in_base
        from psych_candidate_codes_refined pc
        left join hosp.diagnoses_icd dx
          on pc.icd_code = dx.icd_code
         and pc.icd_version = dx.icd_version
        left join psych_dx_events_refined e
          on pc.icd_code = e.icd_code
         and pc.icd_version = e.icd_version
         and pc.leaf_category = e.leaf_category
        group by
            pc.leaf_category,
            aggregate_category,
            pc.icd_code,
            pc.icd_version,
            pc.long_title
        order by aggregate_category, pc.leaf_category, pc.icd_version, pc.icd_code
        """
    )
    save_csv(out, "psychiatric_icd_code_source_refined.csv")
    return out


def run_early_delirium_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = q(
        con,
        """
        select
            delirium_window,
            count(*) as base_n,
            sum(case when delirium_status = 'positive' then 1 else 0 end) as positive_n,
            sum(case when delirium_status = 'negative' then 1 else 0 end) as negative_n,
            sum(case when delirium_status like 'unclassifiable%' then 1 else 0 end) as unclassifiable_n,
            sum(case when assessment_count = 0 then 1 else 0 end) as no_assessment_n,
            sum(case when uta_count > 0 then 1 else 0 end) as any_uta_n,
            sum(case when positive_count = 0 and negative_count = 1 then 1 else 0 end) as one_negative_only_n,
            sum(case when positive_count = 0 and negative_count > 0 and delirium_status <> 'negative' then 1 else 0 end) as insufficient_negative_n,
            sum(assessment_count) as assessment_records,
            sum(positive_count) as positive_records,
            sum(negative_count) as negative_records,
            sum(uta_count) as uta_records
        from delirium_window_classification_refined
        group by delirium_window
        order by
            case delirium_window
                when '24h_at_least_one_negative' then 1
                when '24h_at_least_two_negative_records' then 2
                when '48h_two_negative_days' then 3
                when '72h_two_negative_days' then 4
                when 'whole_icu_two_negative_days' then 5
                else 99
            end
        """
    )
    rows["classifiable_n"] = rows["positive_n"] + rows["negative_n"]
    rows["classifiable_percent"] = [
        pct(n, d) for n, d in zip(rows["classifiable_n"], rows["base_n"])
    ]
    rows["positive_percent_among_classifiable"] = [
        pct(n, d) for n, d in zip(rows["positive_n"], rows["classifiable_n"])
    ]
    save_csv(rows, "early_delirium_window_counts.csv")
    return rows


def run_rass_consistency(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    for label in ["same_timestamp", "within_1h", "within_4h"]:
        dist = q(
            con,
            f"""
            select
                'rass_distribution' as section,
                '{label}' as match_window,
                d.value_class as delirium_value_class,
                coalesce(cast(nr.rass_valuenum as varchar), 'unmatched') as rass_valuenum,
                coalesce(nr.rass_value, 'unmatched') as rass_value,
                count(*) as record_count,
                count(distinct d.subject_id) as subject_count
            from delirium_events_refined d
            left join nearest_rass_{label}_refined nr
              on d.assessment_id = nr.assessment_id
            where d.value_class in ('positive', 'negative', 'uta')
            group by d.value_class, coalesce(cast(nr.rass_valuenum as varchar), 'unmatched'), coalesce(nr.rass_value, 'unmatched')
            order by d.value_class, rass_valuenum
            """
        )
        records.append(dist)

        summary = q(
            con,
            f"""
            select
                'negative_rass_le_minus4' as section,
                '{label}' as match_window,
                'negative' as delirium_value_class,
                cast(null as varchar) as rass_valuenum,
                cast(null as varchar) as rass_value,
                count(*) filter (where d.value_class = 'negative' and nr.rass_valuenum <= -4) as record_count,
                count(distinct d.subject_id) filter (where d.value_class = 'negative' and nr.rass_valuenum <= -4) as subject_count,
                count(*) filter (where d.value_class = 'negative') as denominator_records,
                count(distinct d.subject_id) filter (where d.value_class = 'negative') as denominator_subjects
            from delirium_events_refined d
            left join nearest_rass_{label}_refined nr
              on d.assessment_id = nr.assessment_id
            union all
            select
                'uta_rass_le_minus4' as section,
                '{label}' as match_window,
                'uta' as delirium_value_class,
                cast(null as varchar) as rass_valuenum,
                cast(null as varchar) as rass_value,
                count(*) filter (where d.value_class = 'uta' and nr.rass_valuenum <= -4) as record_count,
                count(distinct d.subject_id) filter (where d.value_class = 'uta' and nr.rass_valuenum <= -4) as subject_count,
                count(*) filter (where d.value_class = 'uta' and nr.assessment_id is not null) as denominator_records,
                count(distinct d.subject_id) filter (where d.value_class = 'uta' and nr.assessment_id is not null) as denominator_subjects
            from delirium_events_refined d
            left join nearest_rass_{label}_refined nr
              on d.assessment_id = nr.assessment_id
            """
        )
        summary["record_percent"] = [
            pct(n, d) for n, d in zip(summary["record_count"], summary["denominator_records"])
        ]
        records.append(summary)

        create_window_classification(
            con,
            f"delirium_window_classification_rass_valid_{label}_refined",
            source_table=f"delirium_events_rass_valid_{label}_refined",
            negative_valid_condition="de.value_class = 'negative' and de.invalid_negative_rass_le_minus4 = 0",
        )
        change = q(
            con,
            f"""
            select
                'classifiability_after_removing_rass_le_minus4_negative' as section,
                '{label}' as match_window,
                b.delirium_window as delirium_value_class,
                cast(null as varchar) as rass_valuenum,
                cast(null as varchar) as rass_value,
                sum(case when b.delirium_status in ('positive', 'negative') then 1 else 0 end) as before_classifiable_n,
                sum(case when a.delirium_status in ('positive', 'negative') then 1 else 0 end) as after_classifiable_n,
                sum(case when b.delirium_status = 'negative' then 1 else 0 end) as before_negative_n,
                sum(case when a.delirium_status = 'negative' then 1 else 0 end) as after_negative_n,
                sum(case when b.delirium_status = 'positive' then 1 else 0 end) as before_positive_n,
                sum(case when a.delirium_status = 'positive' then 1 else 0 end) as after_positive_n,
                sum(case when b.delirium_status in ('positive', 'negative') then 1 else 0 end)
                  - sum(case when a.delirium_status in ('positive', 'negative') then 1 else 0 end) as classifiable_loss_n
            from delirium_window_classification_refined b
            join delirium_window_classification_rass_valid_{label}_refined a
              using (subject_id, hadm_id, stay_id, delirium_window)
            group by b.delirium_window
            order by b.delirium_window
            """
        )
        records.append(change)

    out = pd.concat(records, ignore_index=True, sort=False)
    save_csv(out, "delirium_rass_consistency.csv")
    return out


def group_summary_sql(psych_expr: str, window: str, label: str, table: str = "delirium_window_classification_refined") -> str:
    return f"""
        select
            'group_summary' as section,
            '{label}' as analysis_definition,
            '{window}' as delirium_window,
            case
                when {psych_expr} = 0 and dw.delirium_status = 'negative' then '1_no_primary_psych_no_delirium'
                when {psych_expr} = 1 and dw.delirium_status = 'negative' then '2_primary_psych_no_delirium'
                when {psych_expr} = 0 and dw.delirium_status = 'positive' then '3_no_primary_psych_delirium'
                when {psych_expr} = 1 and dw.delirium_status = 'positive' then '4_primary_psych_delirium'
                else 'excluded_unclassifiable_delirium'
            end as four_group,
            count(*) as patient_count,
            sum(cm.death_1y_after_discharge) as death_1y_n,
            round(100.0 * sum(cm.death_1y_after_discharge) / nullif(count(*), 0), 2) as death_1y_rate_percent,
            sum(cm.readmit_90d_same_system) as readmit_90d_n,
            round(100.0 * sum(cm.readmit_90d_same_system) / nullif(count(*), 0), 2) as readmit_90d_rate_percent,
            sum(cm.icu_readmit_1y_same_system) as icu_readmit_1y_n,
            round(100.0 * sum(cm.icu_readmit_1y_same_system) / nullif(count(*), 0), 2) as icu_readmit_1y_rate_percent,
            avg(cm.anchor_age) as age_mean,
            median(cm.anchor_age) as age_median,
            sum(cm.airway_procedure_proxy) as airway_procedure_proxy_n,
            round(100.0 * sum(cm.airway_procedure_proxy) / nullif(count(*), 0), 2) as airway_procedure_proxy_percent,
            cast(null as integer) as official_invasive_ventilation_n,
            cast(null as double) as official_invasive_ventilation_percent,
            max(cm.official_invasive_ventilation_status) as official_invasive_ventilation_status,
            sum(case when dw.delirium_status like 'unclassifiable%' then 1 else 0 end) as excluded_unclassifiable_n,
            sum(case when dw.delirium_status like 'unclassifiable%' and dw.uta_count > 0 then 1 else 0 end) as excluded_with_uta_n,
            sum(case when dw.delirium_status like 'unclassifiable%' and dw.assessment_count = 0 then 1 else 0 end) as excluded_no_assessment_n,
            sum(case when dw.delirium_status like 'unclassifiable%' and dw.positive_count = 0 and dw.negative_count > 0 then 1 else 0 end) as excluded_insufficient_negative_n
        from cohort_master_refined cm
        join {table} dw using (subject_id, hadm_id, stay_id)
        where dw.delirium_window = '{window}'
        group by four_group
    """


def icu_type_sql(psych_expr: str, window: str, label: str, table: str = "delirium_window_classification_refined") -> str:
    return f"""
        select
            'icu_type_distribution' as section,
            '{label}' as analysis_definition,
            '{window}' as delirium_window,
            case
                when {psych_expr} = 0 and dw.delirium_status = 'negative' then '1_no_primary_psych_no_delirium'
                when {psych_expr} = 1 and dw.delirium_status = 'negative' then '2_primary_psych_no_delirium'
                when {psych_expr} = 0 and dw.delirium_status = 'positive' then '3_no_primary_psych_delirium'
                when {psych_expr} = 1 and dw.delirium_status = 'positive' then '4_primary_psych_delirium'
                else 'excluded_unclassifiable_delirium'
            end as four_group,
            cm.first_careunit as icu_type,
            count(*) as patient_count,
            round(
                100.0 * count(*) /
                nullif(sum(count(*)) over (
                    partition by
                        case
                            when {psych_expr} = 0 and dw.delirium_status = 'negative' then '1_no_primary_psych_no_delirium'
                            when {psych_expr} = 1 and dw.delirium_status = 'negative' then '2_primary_psych_no_delirium'
                            when {psych_expr} = 0 and dw.delirium_status = 'positive' then '3_no_primary_psych_delirium'
                            when {psych_expr} = 1 and dw.delirium_status = 'positive' then '4_primary_psych_delirium'
                            else 'excluded_unclassifiable_delirium'
                        end
                ), 0),
                2
            ) as percent_within_group
        from cohort_master_refined cm
        join {table} dw using (subject_id, hadm_id, stay_id)
        where dw.delirium_window = '{window}'
        group by four_group, cm.first_careunit
    """


def run_refined_four_group_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    main_parts = []
    icu_parts = []
    definitions = [
        (
            "main_primary_documented_by_index",
            "cm.primary_psychiatric_comorbidity_documented_by_index",
            ["48h_two_negative_days", "72h_two_negative_days"],
            "delirium_window_classification_refined",
        ),
        (
            "sensitivity_primary_strict_prior",
            "cm.primary_psychiatric_comorbidity_strict_prior",
            ["48h_two_negative_days", "72h_two_negative_days"],
            "delirium_window_classification_refined",
        ),
        (
            "sensitivity_primary_plus_substance_documented",
            "cm.primary_plus_substance_documented_by_index",
            ["48h_two_negative_days", "72h_two_negative_days"],
            "delirium_window_classification_refined",
        ),
        (
            "sensitivity_primary_plus_dementia_documented",
            "cm.primary_plus_dementia_documented_by_index",
            ["48h_two_negative_days", "72h_two_negative_days"],
            "delirium_window_classification_refined",
        ),
        (
            "sensitivity_whole_icu_delirium_primary_documented",
            "cm.primary_psychiatric_comorbidity_documented_by_index",
            ["whole_icu_two_negative_days"],
            "delirium_window_classification_refined",
        ),
        (
            "sensitivity_cam_consistent_positive_primary_documented",
            "cm.primary_psychiatric_comorbidity_documented_by_index",
            ["48h_two_negative_days", "72h_two_negative_days"],
            "delirium_window_classification_cam_refined",
        ),
    ]
    for label, psych_expr, windows, table in definitions:
        for window in windows:
            main_parts.append(group_summary_sql(psych_expr, window, label, table))
            if label == "main_primary_documented_by_index":
                icu_parts.append(icu_type_sql(psych_expr, window, label, table))

    summary = q(con, "\nunion all\n".join(main_parts))
    icu_types = q(con, "\nunion all\n".join(icu_parts))
    out = pd.concat([summary, icu_types], ignore_index=True, sort=False)
    save_csv(out, "refined_four_group_counts.csv")
    return out


def run_hospice_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    total = q(
        con,
        """
        select
            'overall' as section,
            'base_hospital_survivors_los24h' as stratum,
            count(*) as patient_count,
            sum(dod_on_discharge_day) as dod_on_discharge_day_n,
            sum(hospice_discharge) as hospice_discharge_n,
            sum(case when hospice_discharge = 1 then death_1y_after_discharge else 0 end) as hospice_death_1y_n,
            round(
                100.0 * sum(case when hospice_discharge = 1 then death_1y_after_discharge else 0 end)
                / nullif(sum(hospice_discharge), 0),
                2
            ) as hospice_death_1y_rate_percent,
            sum(death_1y_after_discharge) as death_1y_n,
            round(100.0 * sum(death_1y_after_discharge) / nullif(count(*), 0), 2) as death_1y_rate_percent
        from cohort_master_refined
        """
    )
    rows.append(total)

    for window in ["48h_two_negative_days", "72h_two_negative_days"]:
        group_no_hospice = q(
            con,
            f"""
            select
                'group_events_excluding_hospice' as section,
                '{window}' as stratum,
                case
                    when cm.primary_psychiatric_comorbidity_documented_by_index = 0 and dw.delirium_status = 'negative' then '1_no_primary_psych_no_delirium'
                    when cm.primary_psychiatric_comorbidity_documented_by_index = 1 and dw.delirium_status = 'negative' then '2_primary_psych_no_delirium'
                    when cm.primary_psychiatric_comorbidity_documented_by_index = 0 and dw.delirium_status = 'positive' then '3_no_primary_psych_delirium'
                    when cm.primary_psychiatric_comorbidity_documented_by_index = 1 and dw.delirium_status = 'positive' then '4_primary_psych_delirium'
                    else 'excluded_unclassifiable_delirium'
                end as four_group,
                count(*) as patient_count,
                sum(cm.death_1y_after_discharge) as death_1y_n,
                round(100.0 * sum(cm.death_1y_after_discharge) / nullif(count(*), 0), 2) as death_1y_rate_percent,
                sum(cm.readmit_90d_same_system) as readmit_90d_n,
                sum(cm.icu_readmit_1y_same_system) as icu_readmit_1y_n
            from cohort_master_refined cm
            join delirium_window_classification_refined dw using (subject_id, hadm_id, stay_id)
            where dw.delirium_window = '{window}'
              and cm.hospice_discharge = 0
            group by four_group
            order by four_group
            """
        )
        rows.append(group_no_hospice)

    out = pd.concat(rows, ignore_index=True, sort=False)
    save_csv(out, "hospice_same_day_death_audit.csv")
    return out


def run_prior_utilization(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    util = q(
        con,
        """
        select
            'prior_utilization_by_primary_psych_documented' as section,
            case when primary_psychiatric_comorbidity_documented_by_index = 1
                 then 'primary_psych_documented'
                 else 'no_primary_psych_documented'
            end as stratum,
            count(*) as patient_count,
            sum(case when prior_mimic_hospitalizations > 0 then 1 else 0 end) as any_prior_mimic_hosp_n,
            avg(prior_mimic_hospitalizations) as prior_hosp_mean,
            quantile_cont(prior_mimic_hospitalizations, 0.25) as prior_hosp_p25,
            median(prior_mimic_hospitalizations) as prior_hosp_median,
            quantile_cont(prior_mimic_hospitalizations, 0.75) as prior_hosp_p75,
            max(prior_mimic_hospitalizations) as prior_hosp_max,
            avg(prior_mimic_icu_stays) as prior_icu_mean,
            median(prior_mimic_icu_stays) as prior_icu_median,
            max(prior_mimic_icu_stays) as prior_icu_max
        from cohort_master_refined
        group by stratum
        order by stratum
        """
    )
    rows.append(util)
    readmit_prior = q(
        con,
        """
        select
            'readmit90_prior_hospitalization_qc' as section,
            'all_90d_readmitted' as stratum,
            count(*) filter (where readmit_90d_same_system = 1) as patient_count,
            count(*) filter (where readmit_90d_same_system = 1 and prior_mimic_hospitalizations > 0) as any_prior_mimic_hosp_n,
            round(
                100.0 * count(*) filter (where readmit_90d_same_system = 1 and prior_mimic_hospitalizations > 0)
                / nullif(count(*) filter (where readmit_90d_same_system = 1), 0),
                2
            ) as any_prior_mimic_hosp_percent
        from cohort_master_refined
        """
    )
    rows.append(readmit_prior)
    out = pd.concat(rows, ignore_index=True, sort=False)
    save_csv(out, "prior_healthcare_utilization.csv")
    return out


def run_ventilation_source_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    dependency_presence = q(
        con,
        """
        select
            lower(table_schema) as table_schema,
            lower(table_name) as table_name
        from information_schema.tables
        where lower(table_name) in ('ventilator_setting', 'oxygen_delivery', 'ventilation')
           or lower(table_schema) like '%derived%'
        order by table_schema, table_name
        """
    )
    present = set(
        f"{row.table_schema}.{row.table_name}"
        for row in dependency_presence.itertuples(index=False)
    )
    required = {
        "mimiciv_derived.ventilator_setting",
        "mimiciv_derived.oxygen_delivery",
    }
    missing = sorted(required - present)

    proxy = q(
        con,
        """
        select
            count(*) as base_n,
            sum(airway_procedure_proxy) as airway_procedure_proxy_n,
            sum(procedure_invasive_ventilation_proxy) as procedure_invasive_ventilation_proxy_n,
            sum(procedure_noninvasive_ventilation_proxy) as procedure_noninvasive_ventilation_proxy_n,
            sum(case when airway_procedure_proxy = 1 and procedure_invasive_ventilation_proxy = 1 then 1 else 0 end) as airway_and_procedure_invasive_overlap_n,
            sum(case when airway_procedure_proxy = 1 and procedure_invasive_ventilation_proxy = 0 then 1 else 0 end) as airway_only_n,
            sum(case when airway_procedure_proxy = 0 and procedure_invasive_ventilation_proxy = 1 then 1 else 0 end) as procedure_invasive_only_n
        from cohort_master_refined
        """
    ).iloc[0]

    rows = [
        {
            "section": "official_source",
            "item": "mimic-code ventilation.sql",
            "value": OFFICIAL_VENTILATION_SQL_URL,
            "commit": OFFICIAL_MIMIC_CODE_COMMIT,
            "status": "source_sql_saved_locally",
            "note": "Local copy: official_mimic_code_ventilation.sql",
        },
        {
            "section": "official_dependencies",
            "item": "required_derived_tables",
            "value": "mimiciv_derived.ventilator_setting; mimiciv_derived.oxygen_delivery",
            "commit": OFFICIAL_MIMIC_CODE_COMMIT,
            "status": "missing_in_current_duckdb" if missing else "present",
            "note": "; ".join(missing) if missing else "All required derived tables detected.",
        },
        {
            "section": "formal_invasive_ventilation",
            "item": "official_invasive_ventilation",
            "value": "",
            "commit": OFFICIAL_MIMIC_CODE_COMMIT,
            "status": "pending_derived_tables" if missing else "ready_to_build",
            "note": "Not used in this round because official dependencies are absent."
            if missing
            else "Official dependencies found; rebuild can be attempted.",
        },
        {
            "section": "proxy_counts_not_formal_ventilation",
            "item": "airway_procedure_proxy",
            "value": int(proxy["airway_procedure_proxy_n"] or 0),
            "denominator": int(proxy["base_n"] or 0),
            "percent": pct(proxy["airway_procedure_proxy_n"] or 0, proxy["base_n"] or 0),
            "status": "proxy_only",
            "note": "Itemids 224385, 225448, 226237. This is not formal mechanical ventilation.",
        },
        {
            "section": "proxy_counts_not_formal_ventilation",
            "item": "procedure_invasive_ventilation_proxy",
            "value": int(proxy["procedure_invasive_ventilation_proxy_n"] or 0),
            "denominator": int(proxy["base_n"] or 0),
            "percent": pct(proxy["procedure_invasive_ventilation_proxy_n"] or 0, proxy["base_n"] or 0),
            "status": "proxy_only",
            "note": "Procedureevents itemid 225792 alone is not formal mechanical ventilation.",
        },
        {
            "section": "proxy_overlap_not_official_consistency",
            "item": "airway_and_procedure_invasive_overlap",
            "value": int(proxy["airway_and_procedure_invasive_overlap_n"] or 0),
            "denominator": int(proxy["base_n"] or 0),
            "percent": pct(proxy["airway_and_procedure_invasive_overlap_n"] or 0, proxy["base_n"] or 0),
            "status": "proxy_overlap_only",
            "note": "Official InvasiveVent vs airway proxy consistency cannot be assessed until official concept is built.",
        },
        {
            "section": "proxy_overlap_not_official_consistency",
            "item": "airway_only",
            "value": int(proxy["airway_only_n"] or 0),
            "denominator": int(proxy["base_n"] or 0),
            "percent": pct(proxy["airway_only_n"] or 0, proxy["base_n"] or 0),
            "status": "proxy_overlap_only",
            "note": "Airway procedure proxy without procedureevents Invasive Ventilation proxy.",
        },
        {
            "section": "proxy_overlap_not_official_consistency",
            "item": "procedure_invasive_only",
            "value": int(proxy["procedure_invasive_only_n"] or 0),
            "denominator": int(proxy["base_n"] or 0),
            "percent": pct(proxy["procedure_invasive_only_n"] or 0, proxy["base_n"] or 0),
            "status": "proxy_overlap_only",
            "note": "Procedureevents Invasive Ventilation proxy without airway procedure proxy.",
        },
    ]
    out = pd.DataFrame(rows)
    save_csv(out, "ventilation_source_audit.csv")
    return out


def write_report(
    psychiatric_overlap: pd.DataFrame,
    early_delirium: pd.DataFrame,
    rass: pd.DataFrame,
    four_groups: pd.DataFrame,
    hospice: pd.DataFrame,
    prior_util: pd.DataFrame,
    ventilation_audit: pd.DataFrame,
) -> Path:
    path = OUTDIR / "definition_refinement_report.md"

    main_groups = four_groups[
        (four_groups["section"] == "group_summary")
        & (four_groups["analysis_definition"] == "main_primary_documented_by_index")
        & (four_groups["four_group"] != "excluded_unclassifiable_delirium")
    ].copy()
    main_groups_display = main_groups[
        [
            "delirium_window",
            "four_group",
            "patient_count",
            "death_1y_n",
            "death_1y_rate_percent",
            "readmit_90d_n",
            "readmit_90d_rate_percent",
            "icu_readmit_1y_n",
            "icu_readmit_1y_rate_percent",
            "age_median",
            "airway_procedure_proxy_percent",
            "official_invasive_ventilation_status",
        ]
    ]
    early_display = early_delirium[
        [
            "delirium_window",
            "base_n",
            "positive_n",
            "negative_n",
            "unclassifiable_n",
            "classifiable_percent",
            "positive_percent_among_classifiable",
        ]
    ]
    hospice_display = hospice[hospice["section"] == "overall"]
    prior_display = prior_util[
        prior_util["section"] == "prior_utilization_by_primary_psych_documented"
    ]

    counts = psychiatric_overlap[
        psychiatric_overlap["section"] == "category_counts"
    ][["definition", "category_a", "patient_count", "percent_of_base"]]

    lines = [
        "# Definition Refinement Feasibility Report",
        "",
        "## Scope",
        "",
        "- Base population: adult first ICU stay, ICU length of stay >=24h, survived to hospital discharge.",
        "- No regression, machine learning, covariate selection, or P-value screening was performed.",
        "- Delirium direct assessment uses itemid 228332 from current MIMIC-IV v3.1 database.",
        "- Observed RASS uses itemid 228096 only; Goal RASS was not used.",
        "- Official MIMIC-IV ventilation concept was checked from MIT-LCP mimic-code, but formal InvasiveVent was not constructed because the current DuckDB lacks the required `mimiciv_derived.ventilator_setting` and `mimiciv_derived.oxygen_delivery` tables.",
        "- Airway/procedure items are kept only as proxy audit variables and are not treated as formal mechanical ventilation.",
        "",
        "## Psychiatric Category Counts",
        "",
        md_table(counts),
        "",
        "Primary psychiatric comorbidity is common mental disorders or serious mental illness. Substance use disorders and dementia/cognitive disorders are retained separately and do not define the primary psychiatric exposure unless used in sensitivity analyses.",
        "",
        "## Early Delirium Window Counts",
        "",
        md_table(early_display),
        "",
        "The 24h window is reported with both at-least-one-negative and at-least-two-negative-records rules because two natural days cannot be required reliably inside 24 hours.",
        "",
        "## RASS Consistency Summary",
        "",
        "Detailed RASS distributions and classifiability changes are saved in `delirium_rass_consistency.csv`. Negative assessments with nearest observed RASS <= -4 are flagged as potentially invalid negative assessments, not as delirium-negative evidence.",
        "",
        "## Main Four-Group Counts",
        "",
        md_table(main_groups_display),
        "",
        "## Hospice and Same-Day Death Audit",
        "",
        md_table(hospice_display),
        "",
        "Hospice exclusion sensitivity is saved in `hospice_same_day_death_audit.csv`.",
        "",
        "## Prior Healthcare Utilization",
        "",
        md_table(prior_display),
        "",
        "## Official Ventilation Concept Audit",
        "",
        md_table(ventilation_audit),
        "",
        "## PI Decisions Still Needed",
        "",
        "- Whether to invalidate negative delirium assessments only when RASS <= -4 at the same timestamp, within +/-1h, or within +/-4h.",
        "- Whether to build the full official MIMIC-IV ventilation derived concepts before using formal InvasiveVent.",
        "- Whether dementia/cognitive disorders should be exclusion, stratification, adjustment, or sensitivity-only.",
        "- Whether direct delirium assessment alone is acceptable, or whether CAM-ICU component consistency should be required only as a sensitivity analysis because component coverage is incomplete.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ensure_dirs()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        print("Setting up index cohort...")
        setup_index_base(con)
        print("Setting up psychiatric categories...")
        setup_psychiatric_tables(con)
        setup_comorbidity_tables(con)
        print("Setting up outcomes and utilization...")
        setup_outcome_and_utilization_tables(con)
        setup_airway_and_ventilation_tables(con)
        print("Setting up delirium and RASS tables...")
        setup_delirium_tables(con)
        create_window_classification(con, "delirium_window_classification_refined")
        setup_cam_consistency_tables(con)
        create_window_classification(
            con,
            "delirium_window_classification_cam_refined",
            source_table="delirium_events_cam_refined",
            positive_condition="de.direct_positive_cam_consistent = 1",
            negative_valid_condition="de.value_class = 'negative'",
            direct_positive_condition="de.value_class = 'positive'",
        )
        setup_rass_matching_tables(con)
        setup_master_table(con)

        print("Writing psychiatric ICD code source...")
        run_psychiatric_code_source(con)
        print("Writing psychiatric overlap...")
        psychiatric_overlap = run_psychiatric_overlap(con)
        print("Writing early delirium windows...")
        early_delirium = run_early_delirium_counts(con)
        print("Writing RASS consistency...")
        rass = run_rass_consistency(con)
        print("Writing four-group counts...")
        four_groups = run_refined_four_group_counts(con)
        print("Writing hospice audit...")
        hospice = run_hospice_audit(con)
        print("Writing prior utilization...")
        prior_util = run_prior_utilization(con)
        print("Writing official ventilation source audit...")
        ventilation_audit = run_ventilation_source_audit(con)
        print("Writing report...")
        report = write_report(
            psychiatric_overlap,
            early_delirium,
            rass,
            four_groups,
            hospice,
            prior_util,
            ventilation_audit,
        )
        print(f"Saved outputs to {OUTDIR}")
        print(f"Report: {report}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
