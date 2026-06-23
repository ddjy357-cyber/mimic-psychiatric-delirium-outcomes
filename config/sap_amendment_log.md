# SAP Amendment Log

## File information

- Project: Mental Delirium Long-term Outcomes Study
- SAP version: v1.0
- SAP date: 2026-06-20
- SAP file: `sap/sap_v1.md`
- Linked Protocol: `protocol/protocol_v1.md`
- Linked DAG: `dag/dag_v1.md`
- Linked Data Dictionary: `data_dictionary/data_dictionary_v1.md`
- Frozen configuration: `config/frozen_study_definitions_v1.yaml`
- Frozen configuration SHA256: `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73`

## Status

SAP v1.0 drafted; ready for formal derived-concept build, analysis-dataset construction, QC, and data freeze.

## Amendments

### Pre-model implementation amendment v1.1

- Date: 2026-06-21
- Status: Implemented before any formal statistical model.
- Competing-risk combined time and three-state variables were corrected for 90-day same-system readmission and one-year same-system ICU readmission.
- Model 1 will use `charlson_comorbidity_only_documented_by_index`, excluding the Charlson age score because age is modeled separately.
- `prior_mimic_icu_stays` is retained for description but excluded from Model 1, Model 2, Model 3, and IPSW because it is constant by design.
- `pre_admission_care_proxy` is retained for description but excluded from Model 1 and IPSW because it is redundant with `admission_location_group`.
- Trauma ICU mapping order was corrected so Trauma/TSICU is evaluated before SICU.
- Official MIT-LCP first-day SOFA and OASIS names were clarified as `full_sofa_official_first_day` and `oasis_official_first_day`; old strict-looking names are deprecated.
- All decisions were completed before any Cox, Fine-Gray, multiple-imputation, IPSW, interaction, bootstrap, P value, or confidence-interval model was run.

### Primary mortality implementation correction v1.1

- Date: 2026-06-21
- Status: Implemented after independent code audit and before subsequent model batches.
- Age spline basis-function rank deficiency was identified in the initial primary mortality implementation.
- v1.1 uses a centered full-rank natural cubic spline: `cr(age_at_index_admission, knots=(60,72), lower_bound=31, upper_bound=89, constraints='center')`.
- `nonneurologic_sofa_observed_components_n` reference level was corrected to 5.
- Formal joint-exposure non-PH assessment was changed to a start-stop time-varying Cox likelihood-ratio test.
- Fixed-horizon 365-day absolute risks and additive interaction are now estimated primarily using logistic-model g-computation.
- These corrections did not change the exposure, outcome, analysis population, or prespecified covariate set.
- Original v1 primary mortality outputs were fully preserved.

### Readmission CIF implementation correction v1.2

- Date: 2026-06-22
- Status: Implemented after independent code audit and before manuscript Results or Discussion drafting.
- The standardized CIF implementation for readmission outcomes was found to mix lifelines centered baseline hazards with uncentered linear predictors.
- v1 used fixed-model bootstrap and therefore underestimated uncertainty.
- v1.1 refit target-event and competing-death models in each bootstrap iteration, but still used an inconsistent baseline/linear-predictor scale.
- v1.2 uses a unified uncentered baseline hazard with `exp(X beta)` for original-sample standardized CIFs and refitted patient-level bootstrap estimates.
- Centering validation was added for cumulative hazard, partial hazard, baseline conversion, and time-varying partial hazards before formal CIF output.
- The correction did not change the analysis population, exposure definition, outcome definitions, covariate set, or prespecified time-varying model structure.
- Cause-specific HRs, non-PH LRTs, and time-varying HRs from the readmission batch are not affected by this CIF implementation correction.
- v1 and v1.1 standardized CIF, RD, RR, and additive-interaction outputs are deprecated for clinical interpretation; v1.2 is the active implementation.

