# Study Definition Freeze Log

## Project Status

Formal analysis dataset v1.1 hotfix built and frozen; ready for prespecified statistical modeling.

Formal outcome regression, adjusted interaction modeling, imputation, IPSW modeling, Fine-Gray modeling, automatic covariate selection, P-value screening, and manuscript results writing remain prohibited until formal derived-concept build, analysis-dataset QC, and data freeze are complete.

Historical selection-model `shifted admission_year` is deprecated. Future cross-patient calendar-period variables should use `patients.anchor_year_group`.

## Freeze

- Freeze version: study definitions v1
- Freeze date: 2026-06-19
- Frozen configuration: `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml`
- Frozen configuration SHA256: `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73`

## Psychiatric Mapping History

### Legacy Keyword Mapping Error

The original psychiatric code mapping used diagnosis-name keyword matching against `long_title`. This caused dementia codes with phrases such as `psychotic disturbance` or `anxiety` in their titles to enter anxiety and psychotic-disorder categories. Examples included F0390, F0150, and F0280.

The old code-count query also inflated diagnosis counts through a code-level many-to-many join before aggregation. The total `hosp.diagnoses_icd` row count was 6,364,488, yet old single-code counts exceeded this total, confirming count inflation.

### Validated v1 Mapping

The validated v1 mapping replaced keyword matching with AHRQ official mapping sources plus ICD code-family clinical priority rules:

- ICD-10-CM source: AHRQ CCSR v2026.1.
- ICD-9-CM source: AHRQ HCUP Single-Level CCS 2015.
- Dementia/cognitive disorders, alcohol-related disorders, and other substance-related disorders were retained as separate non-primary categories.
- Delirium, tobacco, symptom/history codes, and other non-prespecified mental categories were excluded from primary psychiatric comorbidity.

Validated v1 primary psychiatric comorbidity counts:

- documented-by-index: 13,926
- strict-prior: 4,529
- index-admission-only: 9,397

### v1.1 Final Mapping

v1.1 made only limited pre-freeze corrections:

- Excluded ICD-10 F06 family due to known physiological condition from primary psychiatric comorbidity and marked it as `secondary_psychiatric_due_to_physiological_condition`.
- Removed ICD-9 30921 separation anxiety disorder from `trauma_and_stressor_related_disorders` and marked it as `excluded_other_psychiatric_category`.
- Restricted main `trauma_and_stressor_related_disorders` to ICD-10 F43 and ICD-9 308/309 acute stress reaction, PTSD, or adjustment-family codes.
- Reclassified F44, F48.1, and F94 MBD007 codes as `other_psychiatric_disorders`, outside primary psychiatric comorbidity.

v1.1 primary psychiatric comorbidity counts:

- documented-by-index: 13,895
- strict-prior: 4,526
- index-admission-only: 9,369

## v1 to v1.1 Count Changes

| Quantity | v1 | v1.1 | Change |
|---|---:|---:|---:|
| Primary psychiatric comorbidity, documented-by-index | 13,926 | 13,895 | -31 |
| Primary psychiatric comorbidity, strict-prior | 4,529 | 4,526 | -3 |
| Primary psychiatric comorbidity, index-admission-only | 9,397 | 9,369 | -28 |
| No psych / no delirium | 13,890 | 13,909 | +19 |
| Psych / no delirium | 6,006 | 5,987 | -19 |
| No psych / delirium | 6,064 | 6,067 | +3 |
| Psych / delirium | 3,498 | 3,495 | -3 |

## Frozen Cohort Counts

- Base population: 46,316
- Final 72-hour delirium classifiable: 29,458
- Final 72-hour delirium unclassifiable: 16,858

Final v1.1 four groups:

| Group | n | 1-year death | 90-day same-system readmission | 1-year same-system ICU readmission |
|---|---:|---:|---:|---:|
| No psychiatric comorbidity / no delirium | 13,909 | 1,854 (13.33%) | 3,216 (23.12%) | 1,633 (11.74%) |
| Psychiatric comorbidity / no delirium | 5,987 | 972 (16.24%) | 1,723 (28.78%) | 807 (13.48%) |
| No psychiatric comorbidity / delirium | 6,067 | 1,452 (23.93%) | 1,548 (25.52%) | 829 (13.66%) |
| Psychiatric comorbidity / delirium | 3,495 | 827 (23.66%) | 1,032 (29.53%) | 478 (13.68%) |

## Freeze Rationale

The v1.1 psychiatric exposure mapping passed final quality checks:

- F06 family entering primary exposure: 0
- Secondary psychiatric due to physiological condition entering primary exposure: 0
- Substance-related categories entering primary exposure: 0
- Dementia/cognitive categories entering primary exposure: 0
- Delirium codes entering primary exposure: 0
- Same code/version entering multiple primary categories: 0
- Final four-group total equals final 72-hour classifiable cohort: 29,458

The corrected exposure no longer supports a directional prespecified claim that psychiatric comorbidity and delirium synergistically increase mortality. Therefore, any interaction should be framed in Protocol and SAP as a prespecified exploratory or effect-modification question rather than as a directional synergistic hypothesis.

## Resolved SAP Decisions

- Same-day DOD is not included in the main one-year death definition and is retained for sensitivity analysis.
- Hospice discharge is retained in the main analysis; excluding hospice is retained for sensitivity analysis.
- Same-system readmission and ICU readmission use the conservative approximate-year cohort for primary analyses.
- Non-neurologic SOFA uses the zero-imputed score plus observed component count.

## Frozen Items

The following may not be changed without Protocol and SAP amendment:

- Base population inclusion/exclusion criteria.
- First ICU stay selection rule.
- `psychiatric_code_mapping_validated_v1.1.csv` and clinical priority rules.
- Primary psychiatric included/excluded categories.
- documented-by-index, strict-prior, and index-admission-only definitions.
- 72-hour primary delirium definition.
- 48-hour sensitivity delirium definition.
- Observed RASS <= -4 within +/-1 hour invalid-negative rule.
- Four-group exposure definitions.
- Primary, secondary, and exploratory outcome definitions.
- Time zero at index hospital discharge.

## File Checksums

| File | SHA256 |
|---|---|
| `config\frozen_study_definitions_v1.yaml` | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` |
| `outputs\psychiatric_code_validation\psychiatric_code_mapping_validated_v1.1.csv` | `30297cf7415fe84e2a352adbf65e6310801034f64320310802f35db56baef954` |
| `outputs\psychiatric_code_validation\psychiatric_code_exclusions_v1.1.csv` | `f74b1505ef45cbeb0f7f450362849cf6292e56597b708f8e75fa3e863a811766` |
| `outputs\psychiatric_code_validation\psychiatric_mapping_provenance_v1.1.md` | `b840e31c0b0246803bce661f5116e031d516837144f0af7ce92d41e453c35345` |
| `outputs\psychiatric_code_validation\psychiatric_category_counts_v1.1.csv` | `2e242312598187b2a531f98fdc86faef8a8e72235657e4fcbc19b6d1b8575e9a` |
| `outputs\psychiatric_code_validation\psychiatric_timing_groups_v1.1.csv` | `5003591f12aaf573c491a5ca161a3320fcfa9827b217f70efabf546cea4ed7d0` |
| `outputs\psychiatric_code_validation\four_group_counts_v1.1.csv` | `4efe5231e723c704a3f21dde1484a4b4af7c3f5522c4c883f0ed17700dabe433` |
| `outputs\psychiatric_code_validation\crude_interaction_descriptive_v1.1.csv` | `4c0f2b5c40afd2268d7a28c9c967e6c73a0bdfa21e525c8d4a1026f8ac70410a` |
| `outputs\psychiatric_code_validation\psychiatric_mapping_v1_to_v1.1_changes.csv` | `f94b9cda502d00fd2800e008cae169a8be765460ce0958e959ff1fb2de74c70e` |
| `outputs\psychiatric_code_validation\psychiatric_mapping_freeze_qc_v1.1.csv` | `f04519d1d2401a61e87e1687796cba7897732c7f2af26600a7b1ac1d19adedb1` |
| `outputs\psychiatric_code_validation\psychiatric_mapping_error_audit.md` | `1361db8e3792ed9bd91de6a1283f881b4982971f653ac69830cf10bc5e63c514` |
| `outputs\psychiatric_code_validation\psychiatric_code_counts_validated.csv` | `3f7859b324f7d19f9dd05ba61536f19a3faa4e9ce9acf013134f483cc7fb25a5` |
| `outputs\psychiatric_code_validation\source_files\DXCCSR-v2026-1.zip` | `093EA8F925606EEA74A9342395EED440E7635293D0ABF031D8C89D1183CDE310` |
| `outputs\psychiatric_code_validation\source_files\Single_Level_CCS_2015.zip` | `A1E31709CC4FA7D67FC254A7421EC9686030098AF9225D5F7BA73AE28DEAA283` |
| `outputs\psychiatric_code_validation\source_files\DXREF_2008_Archive.csv` | `87CC47A33771965B50F7A1DB52D3F135E04C2054088506B88FC01D5F9D1EFE13` |
