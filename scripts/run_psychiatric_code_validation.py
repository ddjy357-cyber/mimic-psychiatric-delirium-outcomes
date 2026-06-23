from __future__ import annotations

import importlib.util
import re
from pathlib import Path
import os
from zipfile import ZipFile

import duckdb
import numpy as np
import pandas as pd


PROJECT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1]))
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", PROJECT.parent))
DB_PATH = Path(os.environ.get("MIMIC_DUCKDB", WORKSPACE / "data" / "mimiciv.duckdb"))
OUTDIR = PROJECT / "outputs" / "psychiatric_code_validation"
SOURCE_DIR = OUTDIR / "source_files"
OLD_MAPPING = (
    PROJECT
    / "outputs"
    / "definition_refinement"
    / "psychiatric_icd_code_source_refined.csv"
)
DEFREF_SCRIPT = PROJECT / "scripts" / "run_definition_refinement.py"
PRE_MODEL_SCRIPT = PROJECT / "scripts" / "run_pre_model_bias_audit.py"

CCSR_ZIP = SOURCE_DIR / "DXCCSR-v2026-1.zip"
CCS9_ZIP = SOURCE_DIR / "Single_Level_CCS_2015.zip"

CCSR_VERSION = "AHRQ CCSR for ICD-10-CM Diagnoses, v2026.1"
CCS9_VERSION = "AHRQ HCUP Single-Level CCS for ICD-9-CM Diagnoses, 2015"

MIMIC_CODE_COMMIT = "57069783095e7770e66ea97da264c0200078ddbf"

PRIMARY_CATEGORIES = {
    "depressive_disorders",
    "anxiety_disorders",
    "trauma_and_stressor_related_disorders",
    "bipolar_disorders",
    "schizophrenia_spectrum_and_other_psychotic_disorders",
}

ALL_VALIDATED_CATEGORIES = PRIMARY_CATEGORIES | {
    "dementia_cognitive_disorders",
    "alcohol_related_disorders",
    "other_substance_related_disorders",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_dirs() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)


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


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def norm_code(code: str | float | int | None) -> str:
    if code is None or pd.isna(code):
        return ""
    return str(code).strip().strip("'").replace(".", "").upper()


def clean_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().strip("'")


def setup_base_tables(con: duckdb.DuckDBPyConnection) -> None:
    defref = load_module(DEFREF_SCRIPT, "definition_refinement_validation")
    pre = load_module(PRE_MODEL_SCRIPT, "pre_model_validation")
    defref.setup_index_base(con)
    # Creates legacy psychiatric temp tables required by the pre-model helper.
    # These are replaced by validated psychiatric flags before outputs are saved.
    defref.setup_psychiatric_tables(con)
    defref.setup_outcome_and_utilization_tables(con)
    defref.setup_delirium_tables(con)
    defref.setup_rass_matching_tables(con)
    defref.create_window_classification(
        con,
        "delirium_window_classification_original_pre_model",
    )
    defref.create_window_classification(
        con,
        "delirium_window_classification_final_pre_model",
        source_table="delirium_events_rass_valid_within_1h_refined",
        negative_valid_condition=(
            "de.value_class = 'negative' "
            "and de.invalid_negative_rass_le_minus4 = 0"
        ),
    )
    # Only for non-psychiatric variables/proxies in downstream summaries.
    defref.setup_airway_and_ventilation_tables(con)
    pre.setup_pre_model_tables(con)


def audit_old_mapping(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    old = pd.read_csv(OLD_MAPPING, dtype=str)
    old["icd_code_norm"] = old["icd_code"].map(norm_code)
    old["icd_version"] = old["icd_version"].astype(str)

    multi = (
        old.groupby(["icd_code_norm", "icd_version"])
        .agg(
            n_leaf_categories=("leaf_category", "nunique"),
            leaf_categories=("leaf_category", lambda x: "; ".join(sorted(set(x)))),
            aggregate_categories=("aggregate_category", lambda x: "; ".join(sorted(set(x)))),
            long_title=("long_title", "first"),
            max_old_diagnosis_record_count=(
                "diagnosis_record_count_in_full_mimic",
                lambda x: pd.to_numeric(x, errors="coerce").max(),
            ),
        )
        .reset_index()
    )
    multi = multi[multi["n_leaf_categories"] > 1].sort_values(
        ["n_leaf_categories", "icd_version", "icd_code_norm"], ascending=[False, True, True]
    )
    save_csv(multi, "psychiatric_multicategory_codes_old.csv")

    old_dupes = old.duplicated(["leaf_category", "icd_code_norm", "icd_version"]).sum()
    dx_total = int(q(con, "select count(*) as n from hosp.diagnoses_icd")["n"].iloc[0])
    true_counts = q(
        con,
        """
        select
            icd_code,
            icd_version::varchar as icd_version,
            count(*) as true_record_count
        from hosp.diagnoses_icd
        group by icd_code, icd_version
        """
    )
    true_counts["icd_code_norm"] = true_counts["icd_code"].map(norm_code)
    compare = old.merge(
        true_counts[["icd_code_norm", "icd_version", "true_record_count"]],
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    compare["old_count_numeric"] = pd.to_numeric(
        compare["diagnosis_record_count_in_full_mimic"], errors="coerce"
    )
    inflated = compare[
        compare["old_count_numeric"] > compare["true_record_count"].fillna(dx_total)
    ].copy()
    inflated["inflation_ratio_vs_true"] = (
        inflated["old_count_numeric"] / inflated["true_record_count"]
    )

    special = old[
        old["icd_code_norm"].isin(["F0390", "F0150", "F0280"])
        & (old["icd_version"] == "10")
    ].copy()

    stats = {
        "old_rows": int(len(old)),
        "old_unique_code_versions": int(
            old[["icd_code_norm", "icd_version"]].drop_duplicates().shape[0]
        ),
        "old_multicategory_code_versions": int(len(multi)),
        "old_duplicate_leaf_code_versions": int(old_dupes),
        "diagnoses_icd_total_rows": dx_total,
        "inflated_old_rows": int(len(inflated)),
        "inflated_unique_code_versions": int(
            inflated[["icd_code_norm", "icd_version"]].drop_duplicates().shape[0]
        ),
        "max_old_count": float(compare["old_count_numeric"].max()),
        "max_true_single_code_count": int(true_counts["true_record_count"].max()),
    }

    lines = [
        "# Psychiatric Mapping Error Audit",
        "",
        "## Findings",
        "",
        f"- Old mapping rows: {stats['old_rows']:,}.",
        f"- Unique old ICD code/version pairs: {stats['old_unique_code_versions']:,}.",
        f"- ICD code/version pairs assigned to multiple leaf categories: {stats['old_multicategory_code_versions']:,}.",
        f"- Rows where old diagnosis_record_count exceeded the true code count: {stats['inflated_old_rows']:,}.",
        f"- Total rows in `hosp.diagnoses_icd`: {dx_total:,}.",
        f"- Maximum true single-code count in `hosp.diagnoses_icd`: {stats['max_true_single_code_count']:,}.",
        f"- Maximum old reported single-code count: {stats['max_old_count']:,.0f}.",
        "",
        "## Specific Dementia Codes",
        "",
        md_table(
            special[
                [
                    "leaf_category",
                    "aggregate_category",
                    "icd_code",
                    "icd_version",
                    "long_title",
                    "diagnosis_record_count_in_full_mimic",
                    "subject_count_in_full_mimic",
                ]
            ]
        ),
        "",
        "## Explanation",
        "",
        "- The old mapping was generated from diagnosis-name keyword matching against `long_title`.",
        "- ICD-10-CM dementia titles such as F0390, F0150, and F0280 contain phrases such as `without ... psychotic disturbance ... and anxiety`.",
        "- Keyword matching therefore falsely matched the words `psychotic` and `anxiety`, causing dementia codes to enter anxiety and psychotic disorder categories.",
        "- This method is discontinued. The validated mapping below uses official AHRQ CCSR/CCS categories plus ICD code-family clinical priority rules.",
        "",
        "## Count Inflation Explanation",
        "",
        "- The old code-count query joined the code table to full `hosp.diagnoses_icd`, and also joined to base-cohort diagnosis events by code/version/category before aggregation.",
        "- For a code with N full-MIMIC diagnosis rows and M base-cohort event rows, this creates an N x M many-to-many expansion before `COUNT(dx.*)`.",
        "- The join included `icd_version`, but the many-to-many code-level join still inflated counts because event rows were not pre-aggregated/deduplicated before joining.",
        "- No evidence was found that a missing `icd_version` condition was the primary problem; the core issue was code-level many-to-many multiplication.",
        "",
        "## Output",
        "",
        "- All multi-category old codes are saved in `psychiatric_multicategory_codes_old.csv`.",
        "",
    ]
    (OUTDIR / "psychiatric_mapping_error_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return old, multi, stats


def load_ahrq_mappings() -> tuple[pd.DataFrame, pd.DataFrame]:
    with ZipFile(CCSR_ZIP) as z:
        with z.open("DXCCSR-v2026-1/DXCCSR_v2026-1.csv") as f:
            ccsr = pd.read_csv(f, dtype=str)
    ccsr.columns = [clean_text(c) for c in ccsr.columns]
    for col in ccsr.columns:
        ccsr[col] = ccsr[col].map(clean_text)
    ccsr["icd_code_norm"] = ccsr["ICD-10-CM CODE"].map(norm_code)
    ccsr["icd_version"] = 10

    category_cols = [
        c
        for c in ccsr.columns
        if re.match(r"CCSR CATEGORY [1-6]$", c)
    ]
    desc_cols = [f"{c} DESCRIPTION" for c in category_cols]
    ccsr["all_ccsr_categories"] = ccsr[category_cols].apply(
        lambda row: "; ".join(
            [x for x in row.tolist() if isinstance(x, str) and x.strip()]
        ),
        axis=1,
    )
    ccsr["all_ccsr_descriptions"] = ccsr[desc_cols].apply(
        lambda row: "; ".join(
            [x for x in row.tolist() if isinstance(x, str) and x.strip()]
        ),
        axis=1,
    )

    with ZipFile(CCS9_ZIP) as z:
        with z.open("$dxref 2015.csv") as f:
            ccs9 = pd.read_csv(f, skiprows=1, dtype=str)
    ccs9.columns = [clean_text(c) for c in ccs9.columns]
    for col in ccs9.columns:
        ccs9[col] = ccs9[col].map(clean_text)
    ccs9["icd_code_norm"] = ccs9["ICD-9-CM CODE"].map(norm_code)
    ccs9["icd_version"] = 9
    return ccsr, ccs9


def ccsr_has(row: pd.Series, *cats: str) -> bool:
    all_cats = set(str(row.get("all_ccsr_categories", "")).split("; "))
    default_ip = str(row.get("Default CCSR CATEGORY IP", ""))
    return bool(all_cats.intersection(cats) or default_ip in cats)


def starts_any(code: str, prefixes: tuple[str, ...]) -> bool:
    return any(code.startswith(p) for p in prefixes)


def classify_icd10(row: pd.Series) -> tuple[str | None, str, str]:
    code = row["icd_code_norm"]
    # Disease ontology/code-family priority: organic neurocognitive and
    # substance-induced families must be removed before primary psychiatric
    # disorders are assigned.
    if code.startswith("F05"):
        return None, "excluded_delirium", "ICD-10 F05 delirium excluded from psychiatric exposure."
    if ccsr_has(row, "NVS011") and not code.startswith("F05"):
        return (
            "dementia_cognitive_disorders",
            "included_non_primary",
            "AHRQ CCSR NVS011; dementia/cognitive category. Excluded from primary exposure.",
        )
    if code.startswith("F10") or ccsr_has(row, "MBD017"):
        return (
            "alcohol_related_disorders",
            "included_non_primary",
            "ICD-10 F10/AHRQ MBD017 alcohol-related. Excluded from primary exposure.",
        )
    if (
        starts_any(code, ("F11", "F12", "F13", "F14", "F15", "F16", "F18", "F19"))
        or ccsr_has(row, "MBD018", "MBD019", "MBD020", "MBD021", "MBD022", "MBD023", "MBD025", "MBD028", "MBD029", "MBD030", "MBD031", "MBD032", "MBD033")
    ):
        return (
            "other_substance_related_disorders",
            "included_non_primary",
            "ICD-10 F11-F16/F18-F19 or AHRQ substance CCSR. Excluded from primary exposure.",
        )
    if code.startswith("F17") or ccsr_has(row, "MBD024"):
        return None, "excluded_tobacco", "Tobacco/nicotine disorder not part of requested exposure."
    if starts_any(code, ("F20", "F21", "F22", "F23", "F24", "F25", "F28", "F29")) or ccsr_has(row, "MBD001"):
        return (
            "schizophrenia_spectrum_and_other_psychotic_disorders",
            "included_primary",
            "ICD-10 F20-F29/AHRQ MBD001 psychotic disorder family.",
        )
    if starts_any(code, ("F30", "F31")) or ccsr_has(row, "MBD003"):
        return (
            "bipolar_disorders",
            "included_primary",
            "ICD-10 F30-F31/AHRQ MBD003 bipolar family.",
        )
    if starts_any(code, ("F32", "F33")) or (
        ccsr_has(row, "MBD002") and not starts_any(code, ("F34",))
    ):
        return (
            "depressive_disorders",
            "included_primary",
            "ICD-10 F32-F33/AHRQ MBD002 depressive disorder family.",
        )
    if code.startswith("F341") or code.startswith("F3481"):
        return (
            "depressive_disorders",
            "included_primary",
            "ICD-10 persistent depressive disorder family.",
        )
    if starts_any(code, ("F40", "F41")) or ccsr_has(row, "MBD005"):
        return (
            "anxiety_disorders",
            "included_primary",
            "ICD-10 F40-F41/AHRQ MBD005 anxiety and fear-related disorders.",
        )
    if code.startswith("F43") or ccsr_has(row, "MBD007"):
        return (
            "trauma_and_stressor_related_disorders",
            "included_primary",
            "ICD-10 F43/AHRQ MBD007 trauma- and stressor-related disorders.",
        )
    mental_cats = {
        "MBD004",
        "MBD006",
        "MBD008",
        "MBD009",
        "MBD010",
        "MBD011",
        "MBD012",
        "MBD013",
        "MBD014",
        "MBD026",
        "MBD027",
        "MBD034",
        "SYM008",
        "SYM009",
    }
    if ccsr_has(row, *mental_cats):
        return None, "excluded_other_mental_or_symptom_category", "AHRQ CCSR mental/symptom category outside prespecified exposure."
    return None, "not_candidate", "Not in a prespecified psychiatric category."


def classify_icd9(row: pd.Series) -> tuple[str | None, str, str]:
    code = row["icd_code_norm"]
    ccs = str(row.get("CCS CATEGORY", "")).strip()
    # Organic cognitive conditions: include dementia/cognitive but exclude
    # delirium due to acute conditions.
    if ccs == "653":
        if starts_any(code, ("2930", "2931")):
            return None, "excluded_delirium", "ICD-9 delirium codes excluded from psychiatric exposure."
        if starts_any(code, ("290", "2940", "2941", "2942", "3310", "3311", "3312", "33182", "33183")):
            return (
                "dementia_cognitive_disorders",
                "included_non_primary",
                "AHRQ CCS 653 plus ICD-9 dementia/cognitive code family. Excluded from primary exposure.",
            )
        return None, "excluded_other_cognitive_or_delirium", "AHRQ CCS 653 code outside dementia/cognitive analytic definition."
    if ccs == "660" or starts_any(code, ("291", "303", "3050")):
        return (
            "alcohol_related_disorders",
            "included_non_primary",
            "AHRQ CCS 660 or ICD-9 alcohol-related family. Excluded from primary exposure.",
        )
    if starts_any(code, ("292", "304", "3052", "3053", "3054", "3055", "3056", "3057", "3058", "3059")) or (ccs == "661" and not code.startswith("3051")):
        return (
            "other_substance_related_disorders",
            "included_non_primary",
            "AHRQ CCS 661/ICD-9 substance family, excluding tobacco. Excluded from primary exposure.",
        )
    if code.startswith("3051"):
        return None, "excluded_tobacco", "Tobacco use disorder not part of requested exposure."
    if ccs == "659" and starts_any(code, ("295", "297", "298")):
        return (
            "schizophrenia_spectrum_and_other_psychotic_disorders",
            "included_primary",
            "AHRQ CCS 659 plus ICD-9 295/297/298 psychotic disorder family.",
        )
    if ccs == "657" and (
        starts_any(code, ("2960", "2961", "2964", "2965", "2966", "2967"))
        or re.match(r"^2968[0-9]?$", code)
    ):
        return (
            "bipolar_disorders",
            "included_primary",
            "AHRQ CCS 657 mood disorder split by ICD-9 bipolar/manic family.",
        )
    if (ccs == "657" and starts_any(code, ("2962", "2963"))) or code in {"3004", "311"}:
        return (
            "depressive_disorders",
            "included_primary",
            "AHRQ CCS 657 mood disorder split by ICD-9 depressive family.",
        )
    if ccs == "651" and starts_any(code, ("3000", "3002", "3003")):
        return (
            "anxiety_disorders",
            "included_primary",
            "AHRQ CCS 651 anxiety disorder family.",
        )
    if starts_any(code, ("308", "309")):
        return (
            "trauma_and_stressor_related_disorders",
            "included_primary",
            "ICD-9 308/309 stress reaction/adjustment/PTSD family using CCS mental disorder boundary.",
        )
    if ccs in {"650", "651", "657", "658", "662", "663", "670"}:
        return None, "excluded_other_mental_or_symptom_category", "AHRQ CCS mental category outside prespecified analytic categories."
    return None, "not_candidate", "Not in a prespecified psychiatric category."


def build_validated_mapping(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ccsr, ccs9 = load_ahrq_mappings()

    observed = q(
        con,
        """
        select distinct
            dx.icd_code,
            dx.icd_version,
            dd.long_title as mimic_long_title
        from hosp.diagnoses_icd dx
        left join hosp.d_icd_diagnoses dd
          on dx.icd_code = dd.icd_code
         and dx.icd_version = dd.icd_version
        """
    )
    observed["icd_code_norm"] = observed["icd_code"].map(norm_code)
    observed["icd_version"] = observed["icd_version"].astype(int)

    icd10 = observed[observed["icd_version"] == 10].merge(
        ccsr,
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    icd10["official_source"] = CCSR_VERSION
    icd10["official_code_description"] = icd10["ICD-10-CM CODE DESCRIPTION"]
    icd10["official_default_category"] = icd10["Default CCSR CATEGORY IP"]
    icd10["official_default_category_description"] = icd10[
        "Default CCSR CATEGORY DESCRIPTION IP"
    ]
    icd10[["clinical_priority_category", "mapping_status", "mapping_reason"]] = icd10.apply(
        lambda row: pd.Series(classify_icd10(row)), axis=1
    )

    icd9 = observed[observed["icd_version"] == 9].merge(
        ccs9,
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    icd9["official_source"] = CCS9_VERSION
    icd9["official_code_description"] = icd9["ICD-9-CM CODE DESCRIPTION"]
    icd9["official_default_category"] = icd9["CCS CATEGORY"]
    icd9["official_default_category_description"] = icd9["CCS CATEGORY DESCRIPTION"]
    icd9["all_ccsr_categories"] = ""
    icd9["all_ccsr_descriptions"] = ""
    icd9[["clinical_priority_category", "mapping_status", "mapping_reason"]] = icd9.apply(
        lambda row: pd.Series(classify_icd9(row)), axis=1
    )

    common_cols = [
        "icd_code",
        "icd_code_norm",
        "icd_version",
        "mimic_long_title",
        "official_source",
        "official_code_description",
        "official_default_category",
        "official_default_category_description",
        "all_ccsr_categories",
        "all_ccsr_descriptions",
        "clinical_priority_category",
        "mapping_status",
        "mapping_reason",
    ]
    all_mapped = pd.concat([icd9[common_cols], icd10[common_cols]], ignore_index=True)
    included = all_mapped[
        all_mapped["clinical_priority_category"].isin(ALL_VALIDATED_CATEGORIES)
    ].copy()
    included["primary_psychiatric_comorbidity_flag"] = included[
        "clinical_priority_category"
    ].isin(PRIMARY_CATEGORIES).astype(int)
    included["dementia_flag"] = (
        included["clinical_priority_category"] == "dementia_cognitive_disorders"
    ).astype(int)
    included["substance_flag"] = included["clinical_priority_category"].isin(
        {"alcohol_related_disorders", "other_substance_related_disorders"}
    ).astype(int)
    included = included.sort_values(
        ["clinical_priority_category", "icd_version", "icd_code_norm"]
    )
    save_csv(included, "psychiatric_code_mapping_validated.csv")

    exclusions = all_mapped[
        (all_mapped["mapping_status"].astype(str).str.startswith("excluded"))
        | (
            all_mapped["clinical_priority_category"].isin(
                {
                    "dementia_cognitive_disorders",
                    "alcohol_related_disorders",
                    "other_substance_related_disorders",
                }
            )
        )
    ].copy()
    exclusions["excluded_from_primary_psychiatric_comorbidity"] = 1
    exclusions["exclusion_type"] = np.where(
        exclusions["clinical_priority_category"].isin(
            {
                "dementia_cognitive_disorders",
                "alcohol_related_disorders",
                "other_substance_related_disorders",
            }
        ),
        "kept_as_separate_non_primary_category",
        "excluded_from_all_validated_categories",
    )
    exclusions = exclusions.sort_values(
        ["exclusion_type", "clinical_priority_category", "icd_version", "icd_code_norm"]
    )
    save_csv(exclusions, "psychiatric_code_exclusions.csv")

    code_counts = q(
        con,
        """
        select
            dx.icd_code,
            dx.icd_version,
            count(*) as diagnosis_record_count,
            count(distinct dx.subject_id) as subject_count,
            count(distinct dx.hadm_id) as hadm_count
        from hosp.diagnoses_icd dx
        group by dx.icd_code, dx.icd_version
        """
    )
    code_counts["icd_code_norm"] = code_counts["icd_code"].map(norm_code)
    code_counts["icd_version"] = code_counts["icd_version"].astype(int)
    validated_counts = included.merge(
        code_counts[
            [
                "icd_code_norm",
                "icd_version",
                "diagnosis_record_count",
                "subject_count",
                "hadm_count",
            ]
        ],
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    validated_counts["diagnosis_record_count"] = validated_counts[
        "diagnosis_record_count"
    ].fillna(0)
    validated_counts["subject_count"] = validated_counts["subject_count"].fillna(0)
    validated_counts["hadm_count"] = validated_counts["hadm_count"].fillna(0)
    total_dx = int(q(con, "select count(*) as n from hosp.diagnoses_icd")["n"].iloc[0])
    validated_counts.insert(0, "diagnoses_icd_total_rows", total_dx)
    validated_counts["record_count_le_total_rows"] = (
        validated_counts["diagnosis_record_count"] <= total_dx
    ).astype(int)
    save_csv(validated_counts, "psychiatric_code_counts_validated.csv")

    return included, exclusions, validated_counts


def register_mapping(con: duckdb.DuckDBPyConnection, mapping: pd.DataFrame) -> None:
    reg = mapping[
        [
            "icd_code_norm",
            "icd_version",
            "clinical_priority_category",
            "primary_psychiatric_comorbidity_flag",
            "dementia_flag",
            "substance_flag",
        ]
    ].drop_duplicates()
    con.register("validated_psych_mapping_df", reg)
    con.execute(
        """
        create or replace temp table validated_psych_mapping as
        select * from validated_psych_mapping_df
        """
    )


def setup_validated_exposure_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        create or replace temp table psych_dx_events_validated as
        select
            ib.subject_id,
            ib.hadm_id as index_hadm_id,
            ib.admittime as index_admittime,
            vpm.clinical_priority_category,
            vpm.primary_psychiatric_comorbidity_flag,
            vpm.dementia_flag,
            vpm.substance_flag,
            dx.hadm_id as dx_hadm_id,
            adm.admittime as dx_admittime,
            dx.icd_code,
            dx.icd_version,
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
        join validated_psych_mapping vpm
          on upper(replace(dx.icd_code, '.', '')) = vpm.icd_code_norm
         and dx.icd_version = vpm.icd_version
        """
    )
    con.execute(
        """
        create or replace temp table psych_flags_validated as
        select
            ib.subject_id,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as primary_strict_prior,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as primary_documented_by_index,
            max(case when e.primary_psychiatric_comorbidity_flag = 1
                      and e.diagnosis_relation = 'index_admission'
                     then 1 else 0 end) as primary_index_admission,
            max(case when e.dementia_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as dementia_strict_prior,
            max(case when e.dementia_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as dementia_documented_by_index,
            max(case when e.substance_flag = 1
                      and e.diagnosis_relation = 'prior_admission'
                     then 1 else 0 end) as substance_strict_prior,
            max(case when e.substance_flag = 1
                      and e.diagnosis_relation in ('prior_admission', 'index_admission')
                     then 1 else 0 end) as substance_documented_by_index
        from index_base ib
        left join psych_dx_events_validated e
          on ib.subject_id = e.subject_id
        group by ib.subject_id
        """
    )
    con.execute(
        """
        create or replace temp table pre_model_patient_validated as
        select
            pma.* exclude(
                primary_psych_documented_by_index,
                primary_psych_strict_prior,
                dementia_documented_by_index,
                substance_use_documented_by_index,
                psychiatric_timing_group
            ),
            coalesce(pfv.primary_documented_by_index, 0) as primary_psych_documented_by_index,
            coalesce(pfv.primary_strict_prior, 0) as primary_psych_strict_prior,
            coalesce(pfv.primary_index_admission, 0) as primary_psych_index_admission,
            coalesce(pfv.dementia_documented_by_index, 0) as dementia_documented_by_index,
            coalesce(pfv.substance_documented_by_index, 0) as substance_use_documented_by_index,
            case
                when coalesce(pfv.primary_documented_by_index, 0) = 0
                    then 'no_documented_psychiatric_comorbidity'
                when coalesce(pfv.primary_strict_prior, 0) = 1
                    then 'strict_prior_psychiatric_comorbidity'
                else 'index_admission_only_psychiatric_comorbidity'
            end as psychiatric_timing_group
        from pre_model_patient_audit pma
        left join psych_flags_validated pfv
          on pma.subject_id = pfv.subject_id
        """
    )


def run_validated_category_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows: list[dict] = []
    base_n = int(q(con, "select count(*) as n from index_base")["n"].iloc[0])
    category = q(
        con,
        """
        select
            clinical_priority_category,
            count(distinct subject_id) filter (where diagnosis_relation = 'prior_admission') as strict_prior_n,
            count(distinct subject_id) filter (where diagnosis_relation in ('prior_admission', 'index_admission')) as documented_by_index_n,
            count(distinct subject_id) filter (where diagnosis_relation = 'index_admission') as index_admission_n
        from psych_dx_events_validated
        group by clinical_priority_category
        order by clinical_priority_category
        """
    )
    for _, row in category.iterrows():
        for definition, col in [
            ("strict_prior", "strict_prior_n"),
            ("documented_by_index", "documented_by_index_n"),
            ("index_admission_recorded", "index_admission_n"),
        ]:
            rows.append(
                {
                    "section": "category_count",
                    "category": row["clinical_priority_category"],
                    "definition": definition,
                    "patient_count": int(row[col] or 0),
                    "percent_of_base": pct(row[col] or 0, base_n),
                }
            )

    overall = q(
        con,
        """
        select
            sum(primary_strict_prior) as primary_strict_prior_n,
            sum(primary_documented_by_index) as primary_documented_by_index_n,
            sum(case when primary_documented_by_index = 1 and primary_strict_prior = 0 then 1 else 0 end) as primary_index_only_n,
            sum(dementia_strict_prior) as dementia_strict_prior_n,
            sum(dementia_documented_by_index) as dementia_documented_n,
            sum(substance_strict_prior) as substance_strict_prior_n,
            sum(substance_documented_by_index) as substance_documented_n,
            sum(case when primary_documented_by_index = 1 and dementia_documented_by_index = 1 then 1 else 0 end) as primary_dementia_overlap_n,
            sum(case when primary_documented_by_index = 1 and substance_documented_by_index = 1 then 1 else 0 end) as primary_substance_overlap_n,
            sum(case when dementia_documented_by_index = 1 and substance_documented_by_index = 1 then 1 else 0 end) as dementia_substance_overlap_n
        from psych_flags_validated
        """
    ).iloc[0]
    for item in [
        "primary_strict_prior_n",
        "primary_documented_by_index_n",
        "primary_index_only_n",
        "dementia_strict_prior_n",
        "dementia_documented_n",
        "substance_strict_prior_n",
        "substance_documented_n",
        "primary_dementia_overlap_n",
        "primary_substance_overlap_n",
        "dementia_substance_overlap_n",
    ]:
        rows.append(
            {
                "section": "overall_or_overlap",
                "category": item,
                "definition": "documented_by_index" if "strict" not in item else "strict_prior",
                "patient_count": int(overall[item] or 0),
                "percent_of_base": pct(overall[item] or 0, base_n),
            }
        )
    out = pd.DataFrame(rows)
    save_csv(out, "psychiatric_category_counts_validated.csv")
    return out


def run_validated_timing_groups(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = q(con, "select * from pre_model_patient_validated")
    rows: list[dict] = []
    group_order = [
        "no_documented_psychiatric_comorbidity",
        "strict_prior_psychiatric_comorbidity",
        "index_admission_only_psychiatric_comorbidity",
    ]
    for group in group_order:
        sub = df[df["psychiatric_timing_group"] == group]
        n = len(sub)
        rows.append(
            {
                "section": "group_summary",
                "psychiatric_timing_group": group,
                "level": "",
                "patient_count": n,
                "age_mean": round(float(sub["anchor_age"].mean()), 3) if n else None,
                "age_median": round(float(sub["anchor_age"].median()), 3) if n else None,
                "female_n": int((sub["gender"] == "F").sum()),
                "female_percent": pct(int((sub["gender"] == "F").sum()), n),
                "prior_mimic_admissions_mean": round(float(sub["prior_mimic_hospitalizations"].mean()), 3) if n else None,
                "prior_mimic_admissions_median": round(float(sub["prior_mimic_hospitalizations"].median()), 3) if n else None,
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
    save_csv(out, "psychiatric_timing_groups_validated.csv")
    return out


def run_validated_four_groups(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
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
            sum(hospice_discharge) as hospice_discharge_n
        from pre_model_patient_validated
        group by four_group
        order by four_group
        """
    )
    save_csv(out, "four_group_counts_validated.csv")
    return out


def classifiable_smd_binary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = q(
        con,
        """
        with base as (
            select
                delirium_classifiable_final_72h,
                primary_psych_documented_by_index,
                dementia_documented_by_index,
                substance_use_documented_by_index
            from pre_model_patient_validated
        ),
        sums as (
            select
                count(*) filter (where delirium_classifiable_final_72h = 1) as classifiable_n,
                count(*) filter (where delirium_classifiable_final_72h = 0) as unclassifiable_n,
                sum(primary_psych_documented_by_index) filter (where delirium_classifiable_final_72h = 1) as primary_classifiable_n,
                sum(primary_psych_documented_by_index) filter (where delirium_classifiable_final_72h = 0) as primary_unclassifiable_n,
                sum(dementia_documented_by_index) filter (where delirium_classifiable_final_72h = 1) as dementia_classifiable_n,
                sum(dementia_documented_by_index) filter (where delirium_classifiable_final_72h = 0) as dementia_unclassifiable_n,
                sum(substance_use_documented_by_index) filter (where delirium_classifiable_final_72h = 1) as substance_classifiable_n,
                sum(substance_use_documented_by_index) filter (where delirium_classifiable_final_72h = 0) as substance_unclassifiable_n
            from base
        )
        select * from sums
        """
    ).iloc[0]

    rows = []
    for label, prefix in [
        ("primary_psychiatric_comorbidity_validated", "primary"),
        ("dementia_cognitive_disorders_validated", "dementia"),
        ("substance_related_disorders_validated", "substance"),
    ]:
        c_n = int(out["classifiable_n"])
        u_n = int(out["unclassifiable_n"])
        c_evt = int(out[f"{prefix}_classifiable_n"] or 0)
        u_evt = int(out[f"{prefix}_unclassifiable_n"] or 0)
        p1 = c_evt / c_n if c_n else 0
        p0 = u_evt / u_n if u_n else 0
        denom = ((p1 * (1 - p1) + p0 * (1 - p0)) / 2) ** 0.5
        smd = 0 if denom == 0 else (p1 - p0) / denom
        rows.append(
            {
                "variable": label,
                "classifiable_n": c_n,
                "classifiable_event_n": c_evt,
                "classifiable_percent": pct(c_evt, c_n),
                "unclassifiable_n": u_n,
                "unclassifiable_event_n": u_evt,
                "unclassifiable_percent": pct(u_evt, u_n),
                "smd": round(smd, 4),
                "abs_smd": round(abs(smd), 4),
            }
        )
    out_df = pd.DataFrame(rows)
    save_csv(out_df, "classifiable_psychiatric_smd_validated.csv")
    return out_df


def write_validation_report(
    old_stats: dict,
    mapping: pd.DataFrame,
    counts: pd.DataFrame,
    category_counts: pd.DataFrame,
    timing: pd.DataFrame,
    four_groups: pd.DataFrame,
    smd: pd.DataFrame,
) -> Path:
    old_pre_model = PROJECT / "outputs" / "pre_model_bias_audit" / "final_72h_delirium_counts.csv"
    old_four = pd.read_csv(old_pre_model)
    old_four = old_four[
        (old_four["section"] == "four_group_counts")
        & (
            old_four["rule"]
            == "final_72h_exclude_negative_with_observed_rass_le_minus4_within_1h"
        )
    ].copy()
    primary_old = PROJECT / "outputs" / "pre_model_bias_audit" / "psychiatric_timing_groups.csv"
    old_timing = pd.read_csv(primary_old)
    old_timing_summary = old_timing[old_timing["section"] == "group_summary"]
    old_primary_doc = int(
        old_timing_summary[
            old_timing_summary["psychiatric_timing_group"]
            != "no_documented_psychiatric_comorbidity"
        ]["patient_count"].sum()
    )
    new_primary_doc = int(
        category_counts[
            (category_counts["section"] == "overall_or_overlap")
            & (category_counts["category"] == "primary_documented_by_index_n")
        ]["patient_count"].iloc[0]
    )
    new_primary_strict = int(
        category_counts[
            (category_counts["section"] == "overall_or_overlap")
            & (category_counts["category"] == "primary_strict_prior_n")
        ]["patient_count"].iloc[0]
    )
    old_map = pd.read_csv(OLD_MAPPING, dtype=str)
    old_map["icd_code_norm"] = old_map["icd_code"].map(norm_code)
    old_map["icd_version"] = old_map["icd_version"].astype(str)
    old_primary_codes = old_map[
        old_map["aggregate_category"].isin(
            ["common_mental_disorders", "serious_mental_illness"]
        )
    ][["icd_code_norm", "icd_version"]].drop_duplicates()
    new_all = mapping[
        ["icd_code_norm", "icd_version", "clinical_priority_category", "primary_psychiatric_comorbidity_flag"]
    ].copy()
    new_all["icd_version"] = new_all["icd_version"].astype(str)
    new_primary_codes = new_all[
        new_all["primary_psychiatric_comorbidity_flag"].astype(int) == 1
    ][["icd_code_norm", "icd_version"]].drop_duplicates()
    removed = old_primary_codes.merge(
        new_primary_codes,
        on=["icd_code_norm", "icd_version"],
        how="left",
        indicator=True,
    )
    old_primary_removed_n = int((removed["_merge"] == "left_only").sum())
    removed_detail = old_primary_codes.merge(
        new_all.drop(columns=["primary_psychiatric_comorbidity_flag"]),
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    removed_detail = removed_detail.merge(
        new_primary_codes.assign(still_primary=1),
        on=["icd_code_norm", "icd_version"],
        how="left",
    )
    removed_summary = (
        removed_detail[removed_detail["still_primary"].isna()]
        .assign(
            new_status=lambda d: d["clinical_priority_category"].fillna(
                "excluded_or_not_in_validated_mapping"
            )
        )
        .groupby("new_status")
        .size()
        .reset_index(name="old_primary_code_versions_removed_from_primary")
        .sort_values("old_primary_code_versions_removed_from_primary", ascending=False)
    )
    save_csv(removed_summary, "old_primary_code_reclassification_summary.csv")

    f_special = mapping[
        mapping["icd_code_norm"].isin(["F0390", "F0150", "F0280"])
    ][
        [
            "icd_code_norm",
            "icd_version",
            "clinical_priority_category",
            "primary_psychiatric_comorbidity_flag",
            "mapping_reason",
        ]
    ]

    count_qc = pd.DataFrame(
        [
            {
                "diagnoses_icd_total_rows": int(counts["diagnoses_icd_total_rows"].max()),
                "max_validated_code_record_count": int(counts["diagnosis_record_count"].max()),
                "any_validated_count_exceeds_total": int(
                    (counts["record_count_le_total_rows"] == 0).sum()
                ),
                "validated_mapping_rows": int(len(mapping)),
                "validated_unique_code_versions": int(
                    mapping[["icd_code_norm", "icd_version"]].drop_duplicates().shape[0]
                ),
                "validated_duplicate_code_versions": int(
                    mapping.duplicated(["icd_code_norm", "icd_version"]).sum()
                ),
            }
        ]
    )

    lines = [
        "# Psychiatric Mapping Validation Report",
        "",
        "## Source",
        "",
        f"- ICD-10-CM source: {CCSR_VERSION}.",
        f"- ICD-9-CM source: {CCS9_VERSION}.",
        "- Mapping was not assigned by diagnosis-title keyword matching.",
        "- Clinical priority category was assigned by official category plus ICD code family.",
        "",
        "## Old Mapping Error Summary",
        "",
        f"- Old code/version pairs assigned to multiple categories: {old_stats['old_multicategory_code_versions']:,}.",
        f"- Old rows with inflated diagnosis record counts: {old_stats['inflated_old_rows']:,}.",
        f"- Total `hosp.diagnoses_icd` rows: {old_stats['diagnoses_icd_total_rows']:,}.",
        f"- Maximum old reported count: {old_stats['max_old_count']:,.0f}.",
        f"- Maximum true single-code count: {old_stats['max_true_single_code_count']:,}.",
        "",
        "## F0390/F0150/F0280 Validation",
        "",
        md_table(f_special),
        "",
        "## Count QC",
        "",
        md_table(count_qc),
        "",
        "## Primary Psychiatric Comorbidity Counts",
        "",
        md_table(
            category_counts[
                (category_counts["section"] == "overall_or_overlap")
                & (
                    category_counts["category"].isin(
                        [
                            "primary_strict_prior_n",
                            "primary_documented_by_index_n",
                            "primary_index_only_n",
                            "primary_dementia_overlap_n",
                            "primary_substance_overlap_n",
                        ]
                    )
                )
            ]
        ),
        "",
        f"- Old primary documented-by-index count: {old_primary_doc:,}.",
        f"- New primary documented-by-index count: {new_primary_doc:,}.",
        f"- New primary strict-prior count: {new_primary_strict:,}.",
        f"- Old unique primary code/version pairs: {len(old_primary_codes):,}.",
        f"- New unique primary code/version pairs: {len(new_primary_codes):,}.",
        f"- Old primary code/version pairs removed from primary exposure after validation: {old_primary_removed_n:,}.",
        "",
        "### Old Primary Code Reclassification Summary",
        "",
        md_table(removed_summary),
        "",
        "## Validated Four Groups",
        "",
        md_table(four_groups),
        "",
        "## Old Four Groups for Comparison",
        "",
        md_table(old_four[["group", "patient_count", "death_1y_n", "death_1y_percent", "readmit_90d_n", "icu_readmit_1y_n"]]),
        "",
        "## Validated Psychiatric Timing Groups",
        "",
        md_table(timing[timing["section"] == "group_summary"]),
        "",
        "## Classifiable vs Unclassifiable Psychiatric SMD",
        "",
        md_table(smd),
        "",
        "## Interpretation",
        "",
        "- The original mapping is not valid for defining psychiatric comorbidity exposure.",
        "- The validated mapping substantially reduces primary psychiatric comorbidity prevalence, mostly by removing dementia/substance/secondary wording artifacts from primary exposure.",
        "- Despite this correction, four-group sample sizes and one-year death events remain sufficient for protocol development.",
        "",
    ]
    path = OUTDIR / "psychiatric_mapping_validation_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ensure_dirs()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        print("Setting up base in-memory tables...")
        setup_base_tables(con)
        print("Auditing old mapping...")
        _, _, old_stats = audit_old_mapping(con)
        print("Building validated mapping...")
        mapping, exclusions, counts = build_validated_mapping(con)
        register_mapping(con, mapping)
        print("Recomputing validated exposures...")
        setup_validated_exposure_tables(con)
        category_counts = run_validated_category_counts(con)
        timing = run_validated_timing_groups(con)
        four_groups = run_validated_four_groups(con)
        smd = classifiable_smd_binary(con)
        print("Writing validation report...")
        write_validation_report(
            old_stats,
            mapping,
            counts,
            category_counts,
            timing,
            four_groups,
            smd,
        )
        print(f"Saved outputs to {OUTDIR}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
