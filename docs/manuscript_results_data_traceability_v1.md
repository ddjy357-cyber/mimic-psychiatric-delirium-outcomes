# Manuscript Results Data Traceability v1.0

This file records the source of each key definition and reported result used in `manuscript_methods_results_v1.md`, `manuscript_tables_v1.md`, and `manuscript_figure_legends_v1.md`. Deprecated result files are listed separately and were not used for formal manuscript results.

## Frozen definitions

| Item | Source file | Version | SHA256 | Manuscript use |
|---|---|---|---|---|
| Base population, first ICU stay, adult status, ICU LOS >=24 h, survival to discharge | `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml` | frozen definitions v1 | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` | Methods: study population, index hospitalization |
| Psychiatric comorbidity mapping v1.1, included and excluded categories, documented-by-index and strict-prior timing | `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml` | frozen definitions v1 / psychiatric mapping v1.1 | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` | Methods: documented psychiatric comorbidity |
| 72-hour delirium definition, UTA rule, RASS <= -4 invalid-negative rule, 48-hour sensitivity definition | `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml` | frozen definitions v1 | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` | Methods: early ICU delirium definition |
| Four joint exposure group definitions and counts | `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml` | frozen definitions v1 | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` | Methods and Results: joint exposure groups and cohort derivation |
| Outcome definitions and time zero | `${PROJECT_DIR}\config\frozen_study_definitions_v1.yaml` | frozen definitions v1 | `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73` | Methods: outcomes and follow-up |

## Formal mortality results

| Result | Source file | Version | SHA256 | Manuscript location |
|---|---|---|---|---|
| Model 0, Model 1, Model 2 one-year mortality average Cox HRs; n=29,366; events=5,105 | `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1\cox_joint_exposure_models_v1_1.csv` | primary mortality v1.1 | `C6EE16B3FB608D929F4A000FD449855679CF5F9A8A4A89F30E2ED9EE6A237DB9` | Results: one-year all-cause mortality; Table 2 |
| Time-varying mortality HRs over 0-30, 30-90, and 90-365 days | `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1\time_varying_cox_exposure_effects.csv` | primary mortality v1.1 | `B8188AFD394B37EF7D9995FF5472C58D0CF6694233E01FA8BF11470FC929E3F4` | Results: time-varying mortality associations; Table 2 |
| Non-PH LRT for mortality joint exposure | `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1\time_varying_cox_nonph_lrt.csv` | primary mortality v1.1 | `357C257907B664050EFF9D09C2472B11EF658DC0D0F881BA9570D6886F10EE69` | Results: time-varying mortality associations |
| Fixed-horizon 365-day standardized mortality risks | `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1\fixed_horizon_365d_standardized_risk.csv` | primary mortality v1.1 | `6BF6D358F5ECF5FCE2D05D50882FAB31CAC8A36690EA614B672C50393E761A25` | Results: one-year all-cause mortality; Table 2; Figure 4 |
| Fixed-horizon mortality additive interaction | `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1\fixed_horizon_365d_additive_interaction.csv` | primary mortality v1.1 | `DD26A6693BF76488B70ADC7F7F5A0399330F97FEC3DADB97423CB654AB8F6A2E` | Results: interaction analysis; Table 4 |

## Formal readmission and ICU readmission results

| Result | Source file | Version | SHA256 | Manuscript location |
|---|---|---|---|---|
| 90-day same-system readmission cause-specific Cox HRs | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes\readmission_90d_cause_specific_cox.csv` | validated readmission formal model | `5CE0F6BF1F4DA1832D3685E47BBFD0D17A2FAD8A00F6CC2EA3CF0E86D2DC933A` | Results: 90-day same-system readmission; Table 3 |
| One-year same-system ICU readmission cause-specific Cox HRs | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes\icu_readmission_365d_cause_specific_cox.csv` | validated readmission formal model | `59F4275CCA6967FAEC70B90DB01E81942988E196A0FA5B7C913F29BD4A4F118B` | Results: one-year same-system ICU readmission; Table 3 |
| 90-day same-system readmission standardized CIF v1.2 | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes_v1_2\standardized_90d_readmission_cif_v1_2.csv` | readmission CIF v1.2 | `ED32CF2D03E9C6586C2C798EEE5F12C58EA16D9EE09702A984F77A3F3408F4E0` | Results: 90-day same-system readmission; Table 3; Figure 5 |
| One-year same-system ICU readmission standardized CIF v1.2 | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes_v1_2\standardized_365d_icu_readmission_cif_v1_2.csv` | readmission CIF v1.2 | `C0E54CACA796CD5FB0E63F81F49DB39DE12EC4841C9963A4306D06F5544C2E6D` | Results: one-year same-system ICU readmission; Table 3; Figure 6 |
| 90-day same-system readmission additive interaction v1.2 | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes_v1_2\additive_interaction_readmission_90d_v1_2.csv` | readmission CIF v1.2 | `2262ECD776025E0DE589CE7B74F91295A7FFB1D95FA889592BCC3BB4D0AA0E98` | Results: interaction analysis; Table 4 |
| One-year same-system ICU readmission additive interaction v1.2 | `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes_v1_2\additive_interaction_icu_readmission_365d_v1_2.csv` | readmission CIF v1.2 | `AF14354B5D8A2B2A2E07A5DD06BB57C9870489E62F4D9D61929A15BC5848F1E9` | Results: interaction analysis; Table 4 |

## Sensitivity and integrated results

| Result | Source file | Version | SHA256 | Manuscript location |
|---|---|---|---|---|
| Integrated relative associations | `${PROJECT_DIR}\analysis\formal_models_v1\04_integrated_results\master_relative_effects.csv` | integrated final results | `B8E7CE2ED7E77203F52617C9B4D0B6DE1797F3E163D8A459BA17363EEAF726A4` | Tables 2-3 cross-check |
| Integrated absolute risks | `${PROJECT_DIR}\analysis\formal_models_v1\04_integrated_results\master_absolute_risks.csv` | integrated final results | `8C2D1754486D60B95BC05361930A770698365FD1A29F85471A22604C7F3BBD06` | Tables 2-3 cross-check |
| Final Table 1 source | `${PROJECT_DIR}\analysis\formal_models_v1\04_integrated_results\final_table1.csv` | integrated final results | `740E9AE18D245706E31334FEC2049FB1FAD3D21640F29E0E6AD4BDBCE155480F` | Table 1 and baseline Results |
| Sensitivity report | `${PROJECT_DIR}\analysis\formal_models_v1\03_sensitivity_analyses\sensitivity_analysis_report.md` | final sensitivity analyses | `D941FC727B9725802E80CBE0AA3F35F99F77651CB9E7EF229BDAC27296F1C58B` | Results: sensitivity analyses |
| Sensitivity summary table | `${PROJECT_DIR}\analysis\formal_models_v1\03_sensitivity_analyses\sensitivity_analysis_summary.csv` | final sensitivity analyses | `7D11992BBD43201BD8C384F7308AB1FCAC6B17300FC9CB42C2B874C15283C617` | Table 4 and sensitivity Results |
| Integrated manifest | `${PROJECT_DIR}\analysis\formal_models_v1\04_integrated_results\integrated_results_manifest.md` | final integrated results | `7FA5F47FC560CDA655430FD069851E15CA3CC69AD849B6DE4BCF86DDDE826A73` | Version control and formal source hierarchy |

## Deprecated files not cited for formal results

| Deprecated output | Reason |
|---|---|
| Original primary mortality v1 Cox model results | Age spline design matrix had rank deficiency; formal mortality results use v1.1. |
| Readmission CIF v1 standardized CIF, RD, RR, additive interaction | Bootstrap did not refit target and competing death models; deprecated after v1.1/v1.2 corrections. |
| Readmission CIF v1.1 standardized CIF, RD, RR, additive interaction | Centered baseline and uncentered linear predictor scale mismatch; deprecated after v1.2 correction. |
| Fine-Gray results | Not run because a validated R environment was unavailable; no substitute implementation was used. |

## Consistency check

The manuscript numbers were checked against the integrated and source files listed above. No numerical inconsistency was identified among the values used in the manuscript draft. Differences between the 29,458 primary classifiable cohort and the 29,366 mortality model sample reflect prespecified mortality data handling and are not treated as an inconsistency.
