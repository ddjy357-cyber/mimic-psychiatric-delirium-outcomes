# Analysis Dataset Manifest

- Analysis table: `mental_delirium_analysis.analysis_dataset_v1_1`
- Database: `${MIMIC_DUCKDB}`
- Derived schema: `mental_delirium_derived`
- Analysis schema: `mental_delirium_analysis`
- Rows: 46,316
- Columns: 105
- Primary analysis cohort: 29,458
- Conservative readmission cohort: 24,033
- Internal fingerprint MD5: `cd6b47ec23c8a0fdea39f1f4de794674`
- Build script SHA256: `D0F803D887B538FF65DCE5BC899B31B9496DFC5B8CA3CE069904557294831E9B`

## Included Variable Blocks

- Internal IDs: subject_id, hadm_id, stay_id.
- Cohort flags: base_population, delirium_classifiable_72h, primary_analysis_cohort, conservative_readmission_cohort.
- Frozen exposures: psychiatric v1.1 documented-by-index, strict-prior, index-only, five primary categories, 48h/72h delirium status, four-level joint exposure.
- Frozen outcomes: one-year death, 90-day same-system readmission, one-year same-system ICU readmission, competing death indicators.
- Model variables: Model 1, Model 2, Model 3, sensitivity/descriptive variables specified in SAP v1.0.

## Non-patient-level QC Files

- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_row_count_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_key_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_missingness.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_range_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_time_logic_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_time_logic_warning_summary.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_category_levels.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_cohort_counts.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_four_group_counts.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_outcome_counts.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_competing_risk_status_counts.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_competing_risk_time_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_icu_type_mapping_v1_to_v1_1.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_charlson_hotfix_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_model_variable_hotfix_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_derived_concept_qc.csv`
- `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_discrepancy_report.md`
