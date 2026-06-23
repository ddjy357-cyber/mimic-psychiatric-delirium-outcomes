# Readmission Outcomes Standardized CIF Centering Correction v1.2

- Created: 2026-06-22 23:49:40
- Scope: standardized CIF, percentile confidence intervals, and CIF-based additive interaction only.
- Original v1 and v1.1 directories were not modified.
- v1 used fixed-model bootstrap and underestimated uncertainty.
- v1.1 refit models in each bootstrap iteration but mixed centered baseline hazard with uncentered linear predictors.
- v1.2 uses uncentered baseline hazard with exp(X beta) for both original-sample point estimates and refitted bootstrap predictions.
- Cause-specific HRs, non-PH LRTs, and time-varying HRs are unchanged and are referenced from v1.
- v1 and v1.1 standardized CIF, RD, RR, and additive interaction outputs are deprecated; clinical interpretation should use v1.2.
- No ridge penalty, no covariate changes, no exposure/outcome changes, no cohort changes, and no model-structure selection inside bootstrap iterations.
- Fine-Gray remains not run because no available R environment was documented in v1.

## Centering Validation

| validation_type                    | outcome              | cause           | model   | interval_label   |   n_checked |   max_abs_error |   max_relative_error | passed   | details                                                                             |
|:-----------------------------------|:---------------------|:----------------|:--------|:-----------------|------------:|----------------:|---------------------:|:---------|:------------------------------------------------------------------------------------|
| non_time_varying_cumulative_hazard | readmission_90d      | target          | Model 1 | not_applicable   |        2500 |     3.33067e-16 |          5.23472e-16 | True     | uncentered baseline times exp(X beta) vs lifelines predict_cumulative_hazard        |
| non_time_varying_partial_hazard    | readmission_90d      | target          | Model 1 | not_applicable   |         100 |     0           |          0           | True     | exp((X - mean_X) beta) vs lifelines predict_partial_hazard                          |
| baseline_conversion                | readmission_90d      | target          | Model 1 | not_applicable   |        1718 |     2.77556e-17 |          1.32913e-16 | True     | uncentered baseline times exp(mean_X beta) vs lifelines centered baseline           |
| non_time_varying_cumulative_hazard | readmission_90d      | target          | Model 2 | not_applicable   |        2500 |     6.66134e-16 |          6.36732e-16 | True     | uncentered baseline times exp(X beta) vs lifelines predict_cumulative_hazard        |
| non_time_varying_partial_hazard    | readmission_90d      | target          | Model 2 | not_applicable   |         100 |     0           |          0           | True     | exp((X - mean_X) beta) vs lifelines predict_partial_hazard                          |
| baseline_conversion                | readmission_90d      | target          | Model 2 | not_applicable   |        1718 |     2.77556e-17 |          1.24672e-16 | True     | uncentered baseline times exp(mean_X beta) vs lifelines centered baseline           |
| time_varying_partial_hazard        | readmission_90d      | competing_death | Model 1 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | readmission_90d      | competing_death | Model 1 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | readmission_90d      | competing_death | Model 2 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | readmission_90d      | competing_death | Model 2 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 1 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 1 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 1 | 90_365_days      |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 2 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 2 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | target          | Model 2 | 90_365_days      |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 1 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 1 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 1 | 90_365_days      |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 2 | 0_30_days        |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 2 | 30_90_days       |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |
| time_varying_partial_hazard        | icu_readmission_365d | competing_death | Model 2 | 90_365_days      |         100 |     0           |          0           | True     | exp((X_interval - mean_X_long) beta) vs CoxTimeVaryingFitter predict_partial_hazard |

## Fixed Model Structure

| Outcome | Cause | Bootstrap model structure |
|---|---|---|
| readmission_90d | target | single average joint exposure coefficient |
| readmission_90d | competing_death | time-varying joint exposure across prespecified windows |
| icu_readmission_365d | target | time-varying joint exposure across prespecified windows |
| icu_readmission_365d | competing_death | time-varying joint exposure across prespecified windows |

## Bootstrap Diagnostics

| outcome              | model   |   planned_iterations |   successful_iterations |   failed_iterations |   minimum_success_threshold | threshold_met   |   target_model_success_n |   competing_death_model_success_n |   cif_success_n |   invalid_cif_n |   interaction_metrics_not_computable_n |   target_model_warning_iterations |   competing_death_model_warning_iterations | model_refit_each_iteration   | bootstrap_method                        |   weights_sum_per_iteration | used_ridge   |   failure_rows_recorded | status   |
|:---------------------|:--------|---------------------:|------------------------:|--------------------:|----------------------------:|:----------------|-------------------------:|----------------------------------:|----------------:|----------------:|---------------------------------------:|----------------------------------:|-------------------------------------------:|:-----------------------------|:----------------------------------------|----------------------------:|:-------------|------------------------:|:---------|
| readmission_90d      | Model 1 |                 1000 |                    1000 |                   0 |                         950 | True            |                     1000 |                              1000 |            1000 |               0 |                                      0 |                                 1 |                                          0 | True                         | patient_level_integer_frequency_weights |                       24033 | False        |                       0 | success  |
| readmission_90d      | Model 2 |                 1000 |                    1000 |                   0 |                         950 | True            |                     1000 |                              1000 |            1000 |               0 |                                      0 |                                 8 |                                          0 | True                         | patient_level_integer_frequency_weights |                       24033 | False        |                       0 | success  |
| icu_readmission_365d | Model 1 |                 1000 |                    1000 |                   0 |                         950 | True            |                     1000 |                              1000 |            1000 |               0 |                                      0 |                                 1 |                                          3 | True                         | patient_level_integer_frequency_weights |                       24033 | False        |                       0 | success  |
| icu_readmission_365d | Model 2 |                 1000 |                    1000 |                   0 |                         950 | True            |                     1000 |                              1000 |            1000 |               0 |                                      0 |                                 2 |                                          0 | True                         | patient_level_integer_frequency_weights |                       24033 | False        |                       0 | success  |

## Model 2 Standardized CIF

| outcome              | group                          |   standardized_cif |   ci95_lower |   ci95_upper |   risk_difference_vs_group1 |   risk_ratio_vs_group1 |
|:---------------------|:-------------------------------|-------------------:|-------------:|-------------:|----------------------------:|-----------------------:|
| readmission_90d      | 1_no_primary_psych_no_delirium |           0.251734 |     0.243856 |     0.259882 |                  0          |               1        |
| readmission_90d      | 2_primary_psych_no_delirium    |           0.274686 |     0.262918 |     0.28603  |                  0.0229518  |               1.09117  |
| readmission_90d      | 3_no_primary_psych_delirium    |           0.269007 |     0.255729 |     0.281412 |                  0.0172731  |               1.06862  |
| readmission_90d      | 4_primary_psych_delirium       |           0.274892 |     0.258078 |     0.291954 |                  0.0231574  |               1.09199  |
| icu_readmission_365d | 1_no_primary_psych_no_delirium |           0.131285 |     0.124859 |     0.137679 |                  0          |               1        |
| icu_readmission_365d | 2_primary_psych_no_delirium    |           0.129605 |     0.120553 |     0.138265 |                 -0.00168038 |               0.987201 |
| icu_readmission_365d | 3_no_primary_psych_delirium    |           0.149035 |     0.138973 |     0.160106 |                  0.0177494  |               1.1352   |
| icu_readmission_365d | 4_primary_psych_delirium       |           0.128767 |     0.117256 |     0.141851 |                 -0.00251829 |               0.980818 |

## Model 2 Additive Interaction

| outcome              | metric               |   estimate |   ci95_lower |   ci95_upper |
|:---------------------|:---------------------|-----------:|-------------:|-------------:|
| readmission_90d      | R00                  |  0.251734  |    0.243856  |  0.259882    |
| readmission_90d      | R10                  |  0.274686  |    0.262918  |  0.28603     |
| readmission_90d      | R01                  |  0.269007  |    0.255729  |  0.281412    |
| readmission_90d      | R11                  |  0.274892  |    0.258078  |  0.291954    |
| readmission_90d      | interaction_contrast | -0.0170675 |   -0.0403069 |  0.00657353  |
| readmission_90d      | RR10                 |  1.09117   |    1.03769   |  1.14469     |
| readmission_90d      | RR01                 |  1.06862   |    1.0065    |  1.12805     |
| readmission_90d      | RR11                 |  1.09199   |    1.01918   |  1.17339     |
| readmission_90d      | RERI                 | -0.0677996 |   -0.161045  |  0.0263673   |
| readmission_90d      | AP                   | -0.0620881 |   -0.150218  |  0.0237293   |
| readmission_90d      | synergy_index        |  0.575698  |    0.144773  |  1.32082     |
| icu_readmission_365d | R00                  |  0.131285  |    0.124859  |  0.137679    |
| icu_readmission_365d | R10                  |  0.129605  |    0.120553  |  0.138265    |
| icu_readmission_365d | R01                  |  0.149035  |    0.138973  |  0.160106    |
| icu_readmission_365d | R11                  |  0.128767  |    0.117256  |  0.141851    |
| icu_readmission_365d | interaction_contrast | -0.0185873 |   -0.0373193 |  0.000710628 |
| icu_readmission_365d | RR10                 |  0.987201  |    0.903002  |  1.0648      |
| icu_readmission_365d | RR01                 |  1.1352    |    1.03803   |  1.24572     |
| icu_readmission_365d | RR11                 |  0.980818  |    0.875666  |  1.09267     |
| icu_readmission_365d | RERI                 | -0.14158   |   -0.287021  |  0.00522184  |
| icu_readmission_365d | AP                   | -0.144348  |   -0.302388  |  0.00510229  |
| icu_readmission_365d | synergy_index        | -0.156717  |   -3.41747   |  2.24518     |

## v1.1 vs v1.2 CIF and CI Changes

| result_family        | outcome              | group_or_metric                | metric                    |   v1_1_point_estimate |   v1_2_point_estimate |   v1_2_minus_v1_1_point |   v1_1_ci_width |   v1_2_ci_width |   v1_2_vs_v1_1_ci_width_change_percent |
|:---------------------|:---------------------|:-------------------------------|:--------------------------|----------------------:|----------------------:|------------------------:|----------------:|----------------:|---------------------------------------:|
| standardized_cif     | readmission_90d      | 1_no_primary_psych_no_delirium | standardized_cif          |             0.240745  |            0.251734   |              0.0109893  |       0.112863  |       0.0160261 |                             -85.8004   |
| standardized_cif     | readmission_90d      | 1_no_primary_psych_no_delirium | risk_difference_vs_group1 |             0         |            0          |              0          |       0         |       0         |                             nan        |
| standardized_cif     | readmission_90d      | 1_no_primary_psych_no_delirium | risk_ratio_vs_group1      |             1         |            1          |              0          |       0         |       0         |                             nan        |
| standardized_cif     | readmission_90d      | 2_primary_psych_no_delirium    | standardized_cif          |             0.252695  |            0.274686   |              0.0219914  |       0.120727  |       0.0231118 |                             -80.8561   |
| standardized_cif     | readmission_90d      | 2_primary_psych_no_delirium    | risk_difference_vs_group1 |             0.0119496 |            0.0229518  |              0.0110021  |       0.0389759 |       0.0260664 |                             -33.1218   |
| standardized_cif     | readmission_90d      | 2_primary_psych_no_delirium    | risk_ratio_vs_group1      |             1.04964   |            1.09117    |              0.0415385  |       0.162003  |       0.106999  |                             -33.9524   |
| standardized_cif     | readmission_90d      | 3_no_primary_psych_delirium    | standardized_cif          |             0.204259  |            0.269007   |              0.0647486  |       0.111261  |       0.0256829 |                             -76.9165   |
| standardized_cif     | readmission_90d      | 3_no_primary_psych_delirium    | risk_difference_vs_group1 |            -0.0364862 |            0.0172731  |              0.0537593  |       0.036715  |       0.0302533 |                             -17.5996   |
| standardized_cif     | readmission_90d      | 3_no_primary_psych_delirium    | risk_ratio_vs_group1      |             0.848445  |            1.06862    |              0.220172   |       0.163737  |       0.121551  |                             -25.7641   |
| standardized_cif     | readmission_90d      | 4_primary_psych_delirium       | standardized_cif          |             0.204788  |            0.274892   |              0.0701034  |       0.117382  |       0.0338755 |                             -71.1407   |
| standardized_cif     | readmission_90d      | 4_primary_psych_delirium       | risk_difference_vs_group1 |            -0.0359568 |            0.0231574  |              0.0591142  |       0.0462979 |       0.0378603 |                             -18.2245   |
| standardized_cif     | readmission_90d      | 4_primary_psych_delirium       | risk_ratio_vs_group1      |             0.850644  |            1.09199    |              0.241348   |       0.195633  |       0.154208  |                             -21.1747   |
| standardized_cif     | icu_readmission_365d | 1_no_primary_psych_no_delirium | standardized_cif          |             0.157041  |            0.131285   |             -0.0257553  |       0.0913917 |       0.0128195 |                             -85.973    |
| standardized_cif     | icu_readmission_365d | 1_no_primary_psych_no_delirium | risk_difference_vs_group1 |             0         |            0          |              0          |       0         |       0         |                             nan        |
| standardized_cif     | icu_readmission_365d | 1_no_primary_psych_no_delirium | risk_ratio_vs_group1      |             1         |            1          |              0          |       0         |       0         |                             nan        |
| standardized_cif     | icu_readmission_365d | 2_primary_psych_no_delirium    | standardized_cif          |             0.144337  |            0.129605   |             -0.0147323  |       0.0834929 |       0.0177116 |                             -78.7868   |
| standardized_cif     | icu_readmission_365d | 2_primary_psych_no_delirium    | risk_difference_vs_group1 |            -0.0127034 |           -0.00168038 |              0.0110231  |       0.0316249 |       0.0215859 |                             -31.7441   |
| standardized_cif     | icu_readmission_365d | 2_primary_psych_no_delirium    | risk_ratio_vs_group1      |             0.919107  |            0.987201   |              0.0680932  |       0.189648  |       0.161798  |                             -14.6849   |
| standardized_cif     | icu_readmission_365d | 3_no_primary_psych_delirium    | standardized_cif          |             0.142743  |            0.149035   |              0.00629205 |       0.0898409 |       0.0211326 |                             -76.4777   |
| standardized_cif     | icu_readmission_365d | 3_no_primary_psych_delirium    | risk_difference_vs_group1 |            -0.014298  |            0.0177494  |              0.0320474  |       0.0320482 |       0.0259114 |                             -19.1486   |
| standardized_cif     | icu_readmission_365d | 3_no_primary_psych_delirium    | risk_ratio_vs_group1      |             0.908953  |            1.1352     |              0.226244   |       0.195127  |       0.207692  |                               6.43898  |
| standardized_cif     | icu_readmission_365d | 4_primary_psych_delirium       | standardized_cif          |             0.117328  |            0.128767   |              0.0114389  |       0.0765949 |       0.0245956 |                             -67.8888   |
| standardized_cif     | icu_readmission_365d | 4_primary_psych_delirium       | risk_difference_vs_group1 |            -0.0397125 |           -0.00251829 |              0.0371942  |       0.0393022 |       0.0287526 |                             -26.8423   |
| standardized_cif     | icu_readmission_365d | 4_primary_psych_delirium       | risk_ratio_vs_group1      |             0.747119  |            0.980818   |              0.233699   |       0.215585  |       0.217005  |                               0.658324 |
| additive_interaction | readmission_90d      | R00                            | R00                       |             0.240745  |            0.251734   |              0.0109893  |       0.112863  |       0.0160261 |                             -85.8004   |
| additive_interaction | readmission_90d      | R10                            | R10                       |             0.252695  |            0.274686   |              0.0219914  |       0.120727  |       0.0231118 |                             -80.8561   |
| additive_interaction | readmission_90d      | R01                            | R01                       |             0.204259  |            0.269007   |              0.0647486  |       0.111261  |       0.0256829 |                             -76.9165   |
| additive_interaction | readmission_90d      | R11                            | R11                       |             0.204788  |            0.274892   |              0.0701034  |       0.117382  |       0.0338755 |                             -71.1407   |
| additive_interaction | readmission_90d      | interaction_contrast           | interaction_contrast      |            -0.0114202 |           -0.0170675  |             -0.00564726 |       0.0577029 |       0.0468804 |                             -18.7555   |
| additive_interaction | readmission_90d      | RR10                           | RR10                      |             1.04964   |            1.09117    |              0.0415385  |       0.162003  |       0.106999  |                             -33.9524   |
| additive_interaction | readmission_90d      | RR01                           | RR01                      |             0.848445  |            1.06862    |              0.220172   |       0.163737  |       0.121551  |                             -25.7641   |
| additive_interaction | readmission_90d      | RR11                           | RR11                      |             0.850644  |            1.09199    |              0.241348   |       0.195633  |       0.154208  |                             -21.1747   |
| additive_interaction | readmission_90d      | RERI                           | RERI                      |            -0.0474371 |           -0.0677996  |             -0.0203626  |       0.238477  |       0.187413  |                             -21.4127   |
| additive_interaction | readmission_90d      | AP                             | AP                        |            -0.0557661 |           -0.0620881  |             -0.006322   |       0.281095  |       0.173947  |                             -38.1179   |
| additive_interaction | readmission_90d      | synergy_index                  | synergy_index             |             1.46544   |            0.575698   |             -0.889739   |      20.1273    |       1.17605   |                             -94.157    |
| additive_interaction | icu_readmission_365d | R00                            | R00                       |             0.157041  |            0.131285   |             -0.0257553  |       0.0913917 |       0.0128195 |                             -85.973    |
| additive_interaction | icu_readmission_365d | R10                            | R10                       |             0.144337  |            0.129605   |             -0.0147323  |       0.0834929 |       0.0177116 |                             -78.7868   |
| additive_interaction | icu_readmission_365d | R01                            | R01                       |             0.142743  |            0.149035   |              0.00629205 |       0.0898409 |       0.0211326 |                             -76.4777   |
| additive_interaction | icu_readmission_365d | R11                            | R11                       |             0.117328  |            0.128767   |              0.0114389  |       0.0765949 |       0.0245956 |                             -67.8888   |
| additive_interaction | icu_readmission_365d | interaction_contrast           | interaction_contrast      |            -0.0127111 |           -0.0185873  |             -0.00587625 |       0.0465718 |       0.0380299 |                             -18.3413   |
| additive_interaction | icu_readmission_365d | RR10                           | RR10                      |             0.919107  |            0.987201   |              0.0680932  |       0.189648  |       0.161798  |                             -14.6849   |
| additive_interaction | icu_readmission_365d | RR01                           | RR01                      |             0.908953  |            1.1352     |              0.226244   |       0.195127  |       0.207692  |                               6.43898  |
| additive_interaction | icu_readmission_365d | RR11                           | RR11                      |             0.747119  |            0.980818   |              0.233699   |       0.215585  |       0.217005  |                               0.658324 |
| additive_interaction | icu_readmission_365d | RERI                           | RERI                      |            -0.0809412 |           -0.14158    |             -0.0606383  |       0.297488  |       0.292242  |                              -1.76316  |
| additive_interaction | icu_readmission_365d | AP                             | AP                        |            -0.108338  |           -0.144348   |             -0.0360107  |       0.397021  |       0.30749   |                             -22.5506   |
| additive_interaction | icu_readmission_365d | synergy_index                  | synergy_index             |             1.47075   |           -0.156717   |             -1.62747    |       7.41165   |       5.66266   |                             -23.598    |

## Failures And Warnings

- No bootstrap failures were recorded.
- All outcome/model combinations met the prespecified minimum of 950 successful iterations.

## Interpretation

- Cause-specific Cox estimates, crude CIF, and time-varying HRs are unchanged from v1 and are referenced rather than regenerated here.
- The v1.2 percentile intervals include parameter-estimation uncertainty from refitting both cause-specific models.
- Synergy index rows are retained for technical audit only when marked not interpretable.
- Clinical interpretation should rely on v1.2 intervals for standardized absolute risks and CIF-based additive interaction.
