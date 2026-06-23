# Primary Mortality Model Report v1.1

- Dataset: `mental_delirium_analysis.analysis_dataset_v1_1`
- Output directory: `${PROJECT_DIR}\analysis\formal_models_v1\01_primary_mortality_v1_1`
- Run timestamp: 2026-06-21T18:22:18
- Random seed: `20260621`
- Bootstrap iterations requested: `1000`

## Implementation Corrections

- Original v1 age spline implementation produced an effective Cox design/Hessian rank problem with unstable age-spline inference and required automatic ridge stabilization.
- v1.1 uses a centered full-rank natural cubic spline: `cr(age_at_index_admission, knots=(60,72), lower_bound=31, upper_bound=89, constraints='center')`.
- Explicit intercept is removed from Cox design matrices; age contributes 3 independent centered spline columns.
- `nonneurologic_sofa_observed_components_n` uses reference level 5.
- CoxPHFitter was first run with `penalizer=0`; no automatic ridge is used for primary Cox results when convergence succeeds.
- Exposures, outcomes, analysis population, and prespecified covariate set were not changed.
- Full-year Cox HRs are interpreted as average associations over 0-365 days because PH is not satisfied.

## Cohort Accounting

| metric                                    |     n |
|:------------------------------------------|------:|
| table1_population_n                       | 29458 |
| primary_mortality_model_n                 | 29366 |
| excluded_same_day_dod_n                   |    89 |
| excluded_death_date_logic_abnormal_n      |     3 |
| primary_mortality_model_1y_death_events_n |  5105 |

## Design Matrix QC

| model   |   design_matrix_columns_n |   matrix_rank | full_rank   |   age_spline_columns_n |
|:--------|--------------------------:|--------------:|:------------|-----------------------:|
| Model 0 |                         3 |             3 | True        |                      0 |
| Model 1 |                        33 |            33 | True        |                      3 |
| Model 2 |                        38 |            38 | True        |                      3 |

## Condition Number QC

| model   |   condition_number |   min_singular_value |   max_singular_value |
|:--------|-------------------:|---------------------:|---------------------:|
| Model 0 |            1.31585 |             58.9746  |              77.6015 |
| Model 1 |           79.7962  |              8.69059 |             693.476  |
| Model 2 |          211.012   |              4.55623 |             961.42   |

## Corrected Cox Joint Exposure Models

| model   | contrast                                                      | term                                                                                                           |      HR |   CI95_lower |   CI95_upper |     p_value |   analysis_n |   event_n |   AIC_partial |   concordance |   penalizer | converged_without_ridge   | fit_error_if_any   |
|:--------|:--------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|--------:|-------------:|-------------:|------------:|-------------:|----------:|--------------:|--------------:|------------:|:--------------------------|:-------------------|
| Model 0 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.23957 |      1.147   |      1.33961 | 5.85356e-08 |        29366 |      5105 |      103634   |      0.580946 |           0 | True                      |                    |
| Model 0 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.96037 |      1.83023 |      2.09976 | 3.281e-82   |        29366 |      5105 |      103634   |      0.580946 |           0 | True                      |                    |
| Model 0 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.92832 |      1.77657 |      2.09303 | 1.46028e-55 |        29366 |      5105 |      103634   |      0.580946 |           0 | True                      |                    |
| Model 1 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.12196 |      1.03518 |      1.216   | 0.00508042  |        29366 |      5105 |       98604.4 |      0.793088 |           0 | True                      |                    |
| Model 1 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.47569 |      1.37458 |      1.58423 | 6.22022e-27 |        29366 |      5105 |       98604.4 |      0.793088 |           0 | True                      |                    |
| Model 1 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.46605 |      1.34336 |      1.59995 | 9.54806e-18 |        29366 |      5105 |       98604.4 |      0.793088 |           0 | True                      |                    |
| Model 2 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.12542 |      1.0384  |      1.21973 | 0.00400636  |        29366 |      5105 |       98577.8 |      0.793704 |           0 | True                      |                    |
| Model 2 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.46595 |      1.36104 |      1.57895 | 5.73068e-24 |        29366 |      5105 |       98577.8 |      0.793704 |           0 | True                      |                    |
| Model 2 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.4646  |      1.33844 |      1.60265 | 1.01643e-16 |        29366 |      5105 |       98577.8 |      0.793704 |           0 | True                      |                    |

## v1 vs v1.1 Cox Comparison

| model   | contrast                                                      |   HR_v1 |   CI95_lower_v1 |   CI95_upper_v1 |   HR_v1_1 |   CI95_lower_v1_1 |   CI95_upper_v1_1 |   absolute_HR_difference |   relative_HR_difference |
|:--------|:--------------------------------------------------------------|--------:|----------------:|----------------:|----------:|------------------:|------------------:|-------------------------:|-------------------------:|
| Model 0 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 1.23957 |         1.147   |         1.33961 |   1.23957 |           1.147   |           1.33961 |              5.48935e-09 |              4.42844e-09 |
| Model 0 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 1.96037 |         1.83023 |         2.09976 |   1.96037 |           1.83023 |           2.09976 |              1.09712e-08 |              5.59648e-09 |
| Model 0 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 1.92832 |         1.77657 |         2.09303 |   1.92832 |           1.77657 |           2.09303 |              1.12069e-08 |              5.81174e-09 |
| Model 1 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 1.12196 |         1.03518 |         1.216   |   1.12196 |           1.03518 |           1.216   |              2.85457e-09 |              2.54428e-09 |
| Model 1 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 1.47569 |         1.37458 |         1.58423 |   1.47569 |           1.37458 |           1.58423 |              2.74199e-09 |              1.85811e-09 |
| Model 1 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 1.46605 |         1.34336 |         1.59995 |   1.46605 |           1.34336 |           1.59995 |              4.41283e-09 |              3.01002e-09 |
| Model 2 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 1.12542 |         1.0384  |         1.21973 |   1.12542 |           1.0384  |           1.21973 |              1.98292e-09 |              1.76194e-09 |
| Model 2 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 1.46595 |         1.36104 |         1.57895 |   1.46595 |           1.36104 |           1.57895 |              1.03052e-09 |              7.02967e-10 |
| Model 2 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 1.4646  |         1.33844 |         1.60265 |   1.4646  |           1.33844 |           1.60265 |              2.03438e-09 |              1.38904e-09 |

## Time-Varying Cox Joint Exposure Effects

| time_window   | contrast                                                      | group                       |   coefficient |   standard_error |      HR |   CI95_lower |   CI95_upper |
|:--------------|:--------------------------------------------------------------|:----------------------------|--------------:|-----------------:|--------:|-------------:|-------------:|
| 0_30_days     | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |     0.180143  |        0.077414  | 1.19739 |     1.02882  |      1.39358 |
| 30_90_days    | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |     0.201476  |        0.0798318 | 1.22321 |     1.04603  |      1.43039 |
| 90_365_days   | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |     0.0464677 |        0.0581435 | 1.04756 |     0.934734 |      1.17401 |
| 0_30_days     | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |     0.769161  |        0.0640024 | 2.15796 |     1.90354  |      2.44637 |
| 30_90_days    | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |     0.377103  |        0.0734448 | 1.45805 |     1.26257  |      1.6838  |
| 90_365_days   | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |     0.103679  |        0.0559358 | 1.10924 |     0.994063 |      1.23777 |
| 0_30_days     | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |     0.787724  |        0.0742812 | 2.19839 |     1.90053  |      2.54293 |
| 30_90_days    | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |     0.300299  |        0.090663  | 1.35026 |     1.13043  |      1.61284 |
| 90_365_days   | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |     0.128296  |        0.0677311 | 1.13689 |     0.995553 |      1.29829 |

## Formal Non-PH LRT

| test                                  |   reduced_log_likelihood |   full_log_likelihood |   chisq |   df |     p_value | interpretation                                                    |
|:--------------------------------------|-------------------------:|----------------------:|--------:|-----:|------------:|:------------------------------------------------------------------|
| joint_exposure_time_varying_nonph_lrt |                 -49250.9 |              -49203.8 | 94.1811 |    6 | 4.09373e-18 | formal global non-PH test for joint exposure time-varying effects |

## Fixed-Horizon 365-Day Standardized Risk

| model   | group                          | label                                    |   standardized_365d_mortality_risk |   risk_ci95_lower |   risk_ci95_upper |   risk_difference_vs_group1 |   risk_difference_ci95_lower |   risk_difference_ci95_upper |   risk_ratio_vs_group1 |   risk_ratio_ci95_lower |   risk_ratio_ci95_upper |   bootstrap_successful_iterations |
|:--------|:-------------------------------|:-----------------------------------------|-----------------------------------:|------------------:|------------------:|----------------------------:|-----------------------------:|-----------------------------:|-----------------------:|------------------------:|------------------------:|----------------------------------:|
| Model 1 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |                           0.152029 |          0.146119 |          0.158028 |                   0         |                   0          |                    0         |                1       |                 1       |                 1       |                              1000 |
| Model 1 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |                           0.166342 |          0.157312 |          0.17576  |                   0.0143122 |                   0.00390705 |                    0.0256457 |                1.09414 |                 1.02513 |                 1.17111 |                              1000 |
| Model 1 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |                           0.204064 |          0.195928 |          0.213727 |                   0.0520344 |                   0.0416903  |                    0.0633711 |                1.34227 |                 1.2689  |                 1.4235  |                              1000 |
| Model 1 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |                           0.202552 |          0.19065  |          0.214523 |                   0.0505229 |                   0.037046   |                    0.063332  |                1.33232 |                 1.23914 |                 1.42551 |                              1000 |
| Model 2 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |                           0.152551 |          0.146542 |          0.158569 |                   0         |                   0          |                    0         |                1       |                 1       |                 1       |                              1000 |
| Model 2 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |                           0.167352 |          0.158515 |          0.176637 |                   0.0148014 |                   0.0041526  |                    0.0260561 |                1.09703 |                 1.02668 |                 1.17379 |                              1000 |
| Model 2 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |                           0.202352 |          0.194065 |          0.212389 |                   0.0498006 |                   0.039502   |                    0.0612092 |                1.32645 |                 1.25292 |                 1.41228 |                              1000 |
| Model 2 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |                           0.20194  |          0.189188 |          0.213632 |                   0.0493892 |                   0.0357317  |                    0.0627176 |                1.32376 |                 1.23017 |                 1.42265 |                              1000 |

## Fixed-Horizon Additive Interaction

| model   | metric               |   estimate |   ci95_lower |   ci95_upper |   bootstrap_successful_iterations |
|:--------|:---------------------|-----------:|-------------:|-------------:|----------------------------------:|
| Model 1 | R00                  |  0.152029  |    0.146119  |   0.158028   |                              1000 |
| Model 1 | R10                  |  0.166342  |    0.157312  |   0.17576    |                              1000 |
| Model 1 | R01                  |  0.204064  |    0.195928  |   0.213727   |                              1000 |
| Model 1 | R11                  |  0.202552  |    0.19065   |   0.214523   |                              1000 |
| Model 1 | interaction_contrast | -0.0158236 |   -0.0343766 |   0.0017698  |                              1000 |
| Model 1 | RR10                 |  1.09414   |    1.02513   |   1.17111    |                              1000 |
| Model 1 | RR01                 |  1.34227   |    1.2689    |   1.4235     |                              1000 |
| Model 1 | RR11                 |  1.33232   |    1.23914   |   1.42551    |                              1000 |
| Model 1 | RERI                 | -0.104083  |   -0.229018  |   0.0113921  |                              1000 |
| Model 1 | AP                   | -0.0781211 |   -0.177007  |   0.00838096 |                              1000 |
| Model 1 | synergy_index        |  0.761501  |    0.544378  |   1.03275    |                              1000 |
| Model 2 | R00                  |  0.152551  |    0.146542  |   0.158569   |                              1000 |
| Model 2 | R10                  |  0.167352  |    0.158515  |   0.176637   |                              1000 |
| Model 2 | R01                  |  0.202352  |    0.194065  |   0.212389   |                              1000 |
| Model 2 | R11                  |  0.20194   |    0.189188  |   0.213632   |                              1000 |
| Model 2 | interaction_contrast | -0.0152128 |   -0.0337402 |   0.00250206 |                              1000 |
| Model 2 | RR10                 |  1.09703   |    1.02668   |   1.17379    |                              1000 |
| Model 2 | RR01                 |  1.32645   |    1.25292   |   1.41228    |                              1000 |
| Model 2 | RR11                 |  1.32376   |    1.23017   |   1.42265    |                              1000 |
| Model 2 | RERI                 | -0.0997229 |   -0.223792  |   0.0160542  |                              1000 |
| Model 2 | AP                   | -0.0753333 |   -0.176344  |   0.0118854  |                              1000 |
| Model 2 | synergy_index        |  0.764515  |    0.537499  |   1.04109    |                              1000 |

## Full-Year Multiplicative Interaction

| model   | term                                              |       HR |   CI95_lower |   CI95_upper |   wald_p_value |   interaction_lrt_chisq |   interaction_lrt_df |   interaction_lrt_p_value |   analysis_n |   event_n |   penalizer |
|:--------|:--------------------------------------------------|---------:|-------------:|-------------:|---------------:|------------------------:|---------------------:|--------------------------:|-------------:|----------:|------------:|
| Model 1 | psych_primary_documented_by_index                 | 1.12196  |     1.03518  |     1.216    |    0.00508042  |               nan       |                  nan |               nan         |        29366 |      5105 |           0 |
| Model 1 | delirium_binary                                   | 1.47569  |     1.37458  |     1.58423  |    6.22022e-27 |                 4.24904 |                    1 |                 0.0392725 |        29366 |      5105 |           0 |
| Model 1 | psych_primary_documented_by_index:delirium_binary | 0.885478 |     0.78875  |     0.994068 |    0.0393252   |                 4.24904 |                    1 |                 0.0392725 |        29366 |      5105 |           0 |
| Model 2 | psych_primary_documented_by_index                 | 1.12542  |     1.0384   |     1.21973  |    0.00400636  |               nan       |                  nan |               nan         |        29366 |      5105 |           0 |
| Model 2 | delirium_binary                                   | 1.46595  |     1.36104  |     1.57895  |    5.73068e-24 |                 4.07203 |                    1 |                 0.0435988 |        29366 |      5105 |           0 |
| Model 2 | psych_primary_documented_by_index:delirium_binary | 0.887735 |     0.790749 |     0.996616 |    0.0436546   |                 4.07203 |                    1 |                 0.0435988 |        29366 |      5105 |           0 |

## Time-Specific Multiplicative Interaction

| time_window   | term                                              |       HR |   CI95_lower |   CI95_upper |   wald_p_value |   analysis_n |   event_n |   penalizer |
|:--------------|:--------------------------------------------------|---------:|-------------:|-------------:|---------------:|-------------:|----------:|------------:|
| 0_30_days     | psych_primary_documented_by_index:delirium_binary | 0.865786 |     0.706941 |     1.06032  |      0.163447  |        29366 |      1639 |           0 |
| 30_90_days    | psych_primary_documented_by_index:delirium_binary | 0.757439 |     0.596516 |     0.961774 |      0.0226191 |        27727 |      1213 |           0 |
| 90_365_days   | psych_primary_documented_by_index:delirium_binary | 0.966774 |     0.808408 |     1.15616  |      0.711228  |        26514 |      2253 |           0 |

## Same-Day DOD Sensitivity

| model                            | contrast                                                      | term                                                                                                           |      HR |   CI95_lower |   CI95_upper |     p_value |   analysis_n |   event_n |   AIC_partial |   concordance |   penalizer | converged_without_ridge   | fit_error_if_any   | sensitivity                        |   same_day_dod_included_n |
|:---------------------------------|:--------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|--------:|-------------:|-------------:|------------:|-------------:|----------:|--------------:|--------------:|------------:|:--------------------------|:-------------------|:-----------------------------------|--------------------------:|
| Model 2 same-day DOD sensitivity | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.11682 |      1.03081 |      1.21002 | 0.0068936   |        29455 |      5194 |        100312 |      0.793595 |           0 | True                      |                    | include_same_day_dod_time_0_5_days |                        89 |
| Model 2 same-day DOD sensitivity | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.48206 |      1.37707 |      1.59506 | 9.13447e-26 |        29455 |      5194 |        100312 |      0.793595 |           0 | True                      |                    | include_same_day_dod_time_0_5_days |                        89 |
| Model 2 same-day DOD sensitivity | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.4646  |      1.3395  |      1.60138 | 5.46153e-17 |        29455 |      5194 |        100312 |      0.793595 |           0 | True                      |                    | include_same_day_dod_time_0_5_days |                        89 |

## Clinical Conclusion Compared With v1

The implementation correction changes numerical stability and the formal handling of non-PH, but the qualitative pattern remains: delirium groups show higher one-year mortality risk than the no-psychiatric/no-delirium reference; psychiatric comorbidity without delirium shows a smaller increase; the combined psychiatric-plus-delirium group is not higher than the delirium-without-psychiatric group in the fixed-horizon risk estimates. This is descriptive/prognostic language, not causal language.

## Warnings And Deviations

- No warnings were recorded.
