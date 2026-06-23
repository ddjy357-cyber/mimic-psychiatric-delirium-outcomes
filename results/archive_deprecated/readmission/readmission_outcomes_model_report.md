# Readmission Outcomes Model Report

- Dataset: `mental_delirium_analysis.analysis_dataset_v1_1`
- Output directory: `${PROJECT_DIR}\analysis\formal_models_v1\02_readmission_outcomes`
- Run timestamp: 2026-06-21T20:04:40
- Random seed: `20260621`
- Bootstrap iterations requested: `1000`
- Analysis population: primary analysis cohort restricted to conservative readmission follow-up cohort.
- Terminology: outcomes are same-system readmission and same-system ICU readmission, not all readmissions across all health systems.

## Cohort Accounting

| metric                |     n |   expected_n | pass   |
|:----------------------|------:|-------------:|:-------|
| analysis_population_n | 24033 |        24033 | True   |

## Three-State Counts

### 90-day same-system readmission

| outcome         | group                          | label                                    |   status | status_label                       |    n |   denominator |   percent |
|:----------------|:-------------------------------|:-----------------------------------------|---------:|:-----------------------------------|-----:|--------------:|----------:|
| readmission_90d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        0 | no_target_event_no_competing_death | 8217 |         11455 |  71.7329  |
| readmission_90d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        1 | target_event                       | 2742 |         11455 |  23.9371  |
| readmission_90d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        2 | competing_death_before_target      |  496 |         11455 |   4.32999 |
| readmission_90d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        0 | no_target_event_no_competing_death | 3191 |          4917 |  64.8973  |
| readmission_90d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        1 | target_event                       | 1474 |          4917 |  29.9776  |
| readmission_90d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        2 | competing_death_before_target      |  252 |          4917 |   5.12508 |
| readmission_90d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        0 | no_target_event_no_competing_death | 3083 |          4909 |  62.803   |
| readmission_90d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        1 | target_event                       | 1285 |          4909 |  26.1764  |
| readmission_90d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        2 | competing_death_before_target      |  541 |          4909 |  11.0206  |
| readmission_90d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        0 | no_target_event_no_competing_death | 1641 |          2752 |  59.6294  |
| readmission_90d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        1 | target_event                       |  820 |          2752 |  29.7965  |
| readmission_90d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        2 | competing_death_before_target      |  291 |          2752 |  10.5741  |

### 365-day same-system ICU readmission

| outcome              | group                          | label                                    |   status | status_label                       |    n |   denominator |   percent |
|:---------------------|:-------------------------------|:-----------------------------------------|---------:|:-----------------------------------|-----:|--------------:|----------:|
| icu_readmission_365d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        0 | no_target_event_no_competing_death | 8961 |         11455 |   78.2278 |
| icu_readmission_365d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        1 | target_event                       | 1414 |         11455 |   12.344  |
| icu_readmission_365d | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |        2 | competing_death_before_target      | 1080 |         11455 |    9.4282 |
| icu_readmission_365d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        0 | no_target_event_no_competing_death | 3636 |          4917 |   73.9475 |
| icu_readmission_365d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        1 | target_event                       |  700 |          4917 |   14.2363 |
| icu_readmission_365d | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |        2 | competing_death_before_target      |  581 |          4917 |   11.8161 |
| icu_readmission_365d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        0 | no_target_event_no_competing_death | 3278 |          4909 |   66.7753 |
| icu_readmission_365d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        1 | target_event                       |  723 |          4909 |   14.7281 |
| icu_readmission_365d | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |        2 | competing_death_before_target      |  908 |          4909 |   18.4966 |
| icu_readmission_365d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        0 | no_target_event_no_competing_death | 1853 |          2752 |   67.3328 |
| icu_readmission_365d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        1 | target_event                       |  391 |          2752 |   14.2078 |
| icu_readmission_365d | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |        2 | competing_death_before_target      |  508 |          2752 |   18.4593 |

## Cause-Specific Cox Target Event Models

| outcome              | cause   | model   | contrast                                                      | term                                                                                                           |       HR |   CI95_lower |   CI95_upper |     p_value |   analysis_n |   event_n |   AIC_partial |   concordance |   penalizer | converged_without_ridge   | fit_error_if_any   |
|:---------------------|:--------|:--------|:--------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|---------:|-------------:|-------------:|------------:|-------------:|----------:|--------------:|--------------:|------------:|:--------------------------|:-------------------|
| readmission_90d      | target  | Model 0 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.3069   |     1.22673  |      1.39231 | 1.16237e-16 |        24033 |      6321 |      125063   |      0.535201 |           0 | True                      |                    |
| readmission_90d      | target  | Model 0 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.17186  |     1.09672  |      1.25214 | 2.72312e-06 |        24033 |      6321 |      125063   |      0.535201 |           0 | True                      |                    |
| readmission_90d      | target  | Model 0 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.37792  |     1.27451  |      1.48973 | 8.04907e-16 |        24033 |      6321 |      125063   |      0.535201 |           0 | True                      |                    |
| readmission_90d      | target  | Model 1 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.11115  |     1.03996  |      1.18721 | 0.00181027  |        24033 |      6321 |      123542   |      0.640627 |           0 | True                      |                    |
| readmission_90d      | target  | Model 1 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.20809  |     1.1286   |      1.29317 | 5.21371e-08 |        24033 |      6321 |      123542   |      0.640627 |           0 | True                      |                    |
| readmission_90d      | target  | Model 1 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.23637  |     1.13771  |      1.34358 | 5.71305e-07 |        24033 |      6321 |      123542   |      0.640627 |           0 | True                      |                    |
| readmission_90d      | target  | Model 2 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.11788  |     1.04624  |      1.19441 | 0.000974034 |        24033 |      6321 |      123481   |      0.643166 |           0 | True                      |                    |
| readmission_90d      | target  | Model 2 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.12098  |     1.04397  |      1.20368 | 0.00166203  |        24033 |      6321 |      123481   |      0.643166 |           0 | True                      |                    |
| readmission_90d      | target  | Model 2 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.15449  |     1.05971  |      1.25774 | 0.00101327  |        24033 |      6321 |      123481   |      0.643166 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 0 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 1.17784  |     1.07584  |      1.28951 | 0.000397539 |        24033 |      3228 |       64163.7 |      0.531834 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 0 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.31063  |     1.19829  |      1.43352 | 3.29863e-09 |        24033 |      3228 |       64163.7 |      0.531834 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 0 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.25454  |     1.12162  |      1.40321 | 7.23424e-05 |        24033 |      3228 |       64163.7 |      0.531834 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 1 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 0.992695 |     0.902941 |      1.09137 | 0.879468    |        24033 |      3228 |       63185   |      0.662267 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 1 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.29928  |     1.18495  |      1.42464 | 2.53589e-08 |        24033 |      3228 |       63185   |      0.662267 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 1 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.09425  |     0.971566 |      1.23242 | 0.137677    |        24033 |      3228 |       63185   |      0.662267 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 2 | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.2_primary_psych_no_delirium] | 0.996507 |     0.906427 |      1.09554 | 0.942304    |        24033 |      3228 |       63163.2 |      0.664611 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 2 | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.3_no_primary_psych_delirium] | 1.22897  |     1.11578  |      1.35365 | 2.88812e-05 |        24033 |      3228 |       63163.2 |      0.664611 |           0 | True                      |                    |
| icu_readmission_365d | target  | Model 2 | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | C(joint_exposure_4level, Treatment(reference='1_no_primary_psych_no_delirium'))[T.4_primary_psych_delirium]    | 1.03902  |     0.919542 |      1.17403 | 0.539082    |        24033 |      3228 |       63163.2 |      0.664611 |           0 | True                      |                    |

## Non-PH Time-Varying Effects

| outcome              | cause           | model   | time_window   | contrast                                                      | group                       |   coefficient |   standard_error |       HR |   CI95_lower |   CI95_upper |
|:---------------------|:----------------|:--------|:--------------|:--------------------------------------------------------------|:----------------------------|--------------:|-----------------:|---------:|-------------:|-------------:|
| readmission_90d      | target          | Model 2 | 0_30_days     | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.0235523  |        0.0415193 | 1.02383  |     0.943815 |      1.11063 |
| readmission_90d      | target          | Model 2 | 30_90_days    | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.186092   |        0.0572239 | 1.20453  |     1.07673  |      1.3475  |
| readmission_90d      | target          | Model 2 | 0_30_days     | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.0729473  |        0.0436505 | 1.07567  |     0.987471 |      1.17175 |
| readmission_90d      | target          | Model 2 | 30_90_days    | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.170949   |        0.0608456 | 1.18643  |     1.05305  |      1.3367  |
| readmission_90d      | target          | Model 2 | 0_30_days     | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.0218887  |        0.053495  | 1.02213  |     0.920387 |      1.13512 |
| readmission_90d      | target          | Model 2 | 30_90_days    | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.173056   |        0.0738339 | 1.18893  |     1.02875  |      1.37406 |
| readmission_90d      | competing_death | Model 2 | 0_30_days     | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.10631    |        0.0995417 | 1.11217  |     0.915036 |      1.35177 |
| readmission_90d      | competing_death | Model 2 | 30_90_days    | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.177457   |        0.128101  | 1.19418  |     0.929024 |      1.53501 |
| readmission_90d      | competing_death | Model 2 | 0_30_days     | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.679741   |        0.0806907 | 1.97337  |     1.6847   |      2.3115  |
| readmission_90d      | competing_death | Model 2 | 30_90_days    | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.397461   |        0.111117  | 1.48804  |     1.19682  |      1.85012 |
| readmission_90d      | competing_death | Model 2 | 0_30_days     | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.736488   |        0.0945253 | 2.08859  |     1.73537  |      2.5137  |
| readmission_90d      | competing_death | Model 2 | 30_90_days    | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.273734   |        0.14288   | 1.31486  |     0.993709 |      1.73981 |
| icu_readmission_365d | target          | Model 2 | 0_30_days     | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |   -0.150925   |        0.0793535 | 0.859912 |     0.736049 |      1.00462 |
| icu_readmission_365d | target          | Model 2 | 30_90_days    | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.161567   |        0.0901452 | 1.17535  |     0.984996 |      1.40249 |
| icu_readmission_365d | target          | Model 2 | 90_365_days   | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.0213844  |        0.0768094 | 1.02161  |     0.878832 |      1.1876  |
| icu_readmission_365d | target          | Model 2 | 0_30_days     | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.260214   |        0.0741086 | 1.29721  |     1.12183  |      1.5     |
| icu_readmission_365d | target          | Model 2 | 30_90_days    | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.216986   |        0.0945618 | 1.24233  |     1.03215  |      1.4953  |
| icu_readmission_365d | target          | Model 2 | 90_365_days   | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.118485   |        0.0802704 | 1.12579  |     0.9619   |      1.3176  |
| icu_readmission_365d | target          | Model 2 | 0_30_days     | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |   -0.0705405  |        0.097862  | 0.93189  |     0.769242 |      1.12893 |
| icu_readmission_365d | target          | Model 2 | 30_90_days    | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.231331   |        0.11099   | 1.26028  |     1.01389  |      1.56654 |
| icu_readmission_365d | target          | Model 2 | 90_365_days   | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.00335333 |        0.0998198 | 1.00336  |     0.825065 |      1.22018 |
| icu_readmission_365d | competing_death | Model 2 | 0_30_days     | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.102385   |        0.0937864 | 1.10781  |     0.921792 |      1.33137 |
| icu_readmission_365d | competing_death | Model 2 | 30_90_days    | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.280373   |        0.104485  | 1.32362  |     1.07851  |      1.62444 |
| icu_readmission_365d | competing_death | Model 2 | 90_365_days   | 2_primary_psych_no_delirium vs 1_no_primary_psych_no_delirium | 2_primary_psych_no_delirium |    0.213219   |        0.078308  | 1.23766  |     1.06156  |      1.44297 |
| icu_readmission_365d | competing_death | Model 2 | 0_30_days     | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.740325   |        0.0753896 | 2.09662  |     1.80861  |      2.43048 |
| icu_readmission_365d | competing_death | Model 2 | 30_90_days    | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.432344   |        0.0954283 | 1.54087  |     1.27801  |      1.85778 |
| icu_readmission_365d | competing_death | Model 2 | 90_365_days   | 3_no_primary_psych_delirium vs 1_no_primary_psych_no_delirium | 3_no_primary_psych_delirium |    0.143013   |        0.076698  | 1.15374  |     0.992711 |      1.3409  |
| icu_readmission_365d | competing_death | Model 2 | 0_30_days     | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.820718   |        0.0870241 | 2.27213  |     1.91583  |      2.6947  |
| icu_readmission_365d | competing_death | Model 2 | 30_90_days    | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.280267   |        0.122242  | 1.32348  |     1.04151  |      1.68179 |
| icu_readmission_365d | competing_death | Model 2 | 90_365_days   | 4_primary_psych_delirium vs 1_no_primary_psych_no_delirium    | 4_primary_psych_delirium    |    0.200457   |        0.0929467 | 1.22196  |     1.01845  |      1.46614 |

## Formal Non-PH LRT

| outcome              | cause           | model   | test                            |   reduced_log_likelihood |   full_log_likelihood |    chisq |   df |     p_value |
|:---------------------|:----------------|:--------|:--------------------------------|-------------------------:|----------------------:|---------:|-----:|------------:|
| readmission_90d      | target          | Model 2 | joint_exposure_time_varying_lrt |                 -60100.9 |              -60097.5 |  6.92323 |    3 | 0.0743854   |
| readmission_90d      | competing_death | Model 2 | joint_exposure_time_varying_lrt |                 -14457.7 |              -14451.2 | 12.9087  |    3 | 0.00483828  |
| icu_readmission_365d | target          | Model 2 | joint_exposure_time_varying_lrt |                 -31428.7 |              -31421.5 | 14.431   |    6 | 0.0251755   |
| icu_readmission_365d | competing_death | Model 2 | joint_exposure_time_varying_lrt |                 -28689.9 |              -28656.5 | 66.8366  |    6 | 1.81777e-12 |

## Standardized CIF

| outcome              | model   | group                          | label                                    |   standardized_cif |   ci95_lower |   ci95_upper |   risk_difference_vs_group1 |   risk_difference_ci95_lower |   risk_difference_ci95_upper |   risk_ratio_vs_group1 |   risk_ratio_ci95_lower |   risk_ratio_ci95_upper |   bootstrap_successful_iterations |
|:---------------------|:--------|:-------------------------------|:-----------------------------------------|-------------------:|-------------:|-------------:|----------------------------:|-----------------------------:|-----------------------------:|-----------------------:|------------------------:|------------------------:|----------------------------------:|
| readmission_90d      | Model 1 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |           0.247444 |     0.246001 |     0.248812 |                  0          |                    0         |                   0          |               1        |                1        |                1        |                              1000 |
| readmission_90d      | Model 1 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |           0.259915 |     0.258366 |     0.261381 |                  0.0124712  |                    0.0123586 |                   0.0125826  |               1.0504   |                1.05007  |                1.05073  |                              1000 |
| readmission_90d      | Model 1 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |           0.226556 |     0.224978 |     0.228024 |                 -0.0208877  |                   -0.02134   |                  -0.0204184  |               0.915586 |                0.913654 |                0.917507 |                              1000 |
| readmission_90d      | Model 1 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |           0.227119 |     0.225526 |     0.228621 |                 -0.0203249  |                   -0.020811  |                  -0.0198225  |               0.917861 |                0.915798 |                0.919918 |                              1000 |
| readmission_90d      | Model 2 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |           0.240745 |     0.239313 |     0.242114 |                  0          |                    0         |                   0          |               1        |                1        |                1        |                              1000 |
| readmission_90d      | Model 2 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |           0.252695 |     0.251174 |     0.254171 |                  0.0119496  |                    0.0118312 |                   0.0120667  |               1.04964  |                1.04928  |                1.04999  |                              1000 |
| readmission_90d      | Model 2 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |           0.204259 |     0.202796 |     0.205675 |                 -0.0364862  |                   -0.0368972 |                  -0.0360719  |               0.848445 |                0.846577 |                0.850294 |                              1000 |
| readmission_90d      | Model 2 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |           0.204788 |     0.203286 |     0.206224 |                 -0.0359568  |                   -0.0364012 |                  -0.0355041  |               0.850644 |                0.84859  |                0.852646 |                              1000 |
| icu_readmission_365d | Model 1 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |           0.162511 |     0.161698 |     0.163347 |                  0          |                    0         |                   0          |               1        |                1        |                1        |                              1000 |
| icu_readmission_365d | Model 1 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |           0.150248 |     0.149468 |     0.151042 |                 -0.0122626  |                   -0.0123627 |                  -0.0121591  |               0.924543 |                0.923945 |                0.925116 |                              1000 |
| icu_readmission_365d | Model 1 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |           0.159309 |     0.158417 |     0.160183 |                 -0.00320245 |                   -0.0035244 |                  -0.00286869 |               0.980294 |                0.978285 |                0.982326 |                              1000 |
| icu_readmission_365d | Model 1 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |           0.131976 |     0.131187 |     0.132746 |                 -0.030535   |                   -0.0308899 |                  -0.0301819  |               0.812105 |                0.810004 |                0.814229 |                              1000 |
| icu_readmission_365d | Model 2 | 1_no_primary_psych_no_delirium | No psychiatric comorbidity / no delirium |           0.157041 |     0.15623  |     0.157854 |                  0          |                    0         |                   0          |               1        |                1        |                1        |                              1000 |
| icu_readmission_365d | Model 2 | 2_primary_psych_no_delirium    | Psychiatric comorbidity / no delirium    |           0.144337 |     0.143562 |     0.145114 |                 -0.0127034  |                   -0.0128025 |                  -0.0125982  |               0.919107 |                0.918492 |                0.919714 |                              1000 |
| icu_readmission_365d | Model 2 | 3_no_primary_psych_delirium    | No psychiatric comorbidity / delirium    |           0.142743 |     0.141871 |     0.14357  |                 -0.014298   |                   -0.0145921 |                  -0.0139868  |               0.908953 |                0.907    |                0.910948 |                              1000 |
| icu_readmission_365d | Model 2 | 4_primary_psych_delirium       | Psychiatric comorbidity / delirium       |           0.117328 |     0.116556 |     0.118086 |                 -0.0397125  |                   -0.0400471 |                  -0.0393502  |               0.747119 |                0.745024 |                0.749229 |                              1000 |

## Additive Interaction

| outcome              | model   | metric               |   estimate |   ci95_lower |   ci95_upper |   bootstrap_successful_iterations |
|:---------------------|:--------|:---------------------|-----------:|-------------:|-------------:|----------------------------------:|
| readmission_90d      | Model 1 | R00                  |  0.247444  |    0.246001  |    0.248812  |                              1000 |
| readmission_90d      | Model 1 | R10                  |  0.259915  |    0.258366  |    0.261381  |                              1000 |
| readmission_90d      | Model 1 | R01                  |  0.226556  |    0.224978  |    0.228024  |                              1000 |
| readmission_90d      | Model 1 | R11                  |  0.227119  |    0.225526  |    0.228621  |                              1000 |
| readmission_90d      | Model 1 | interaction_contrast | -0.0119084 |   -0.0119906 |   -0.0118265 |                              1000 |
| readmission_90d      | Model 1 | RR10                 |  1.0504    |    1.05007   |    1.05073   |                              1000 |
| readmission_90d      | Model 1 | RR01                 |  0.915586  |    0.913654  |    0.917507  |                              1000 |
| readmission_90d      | Model 1 | RR11                 |  0.917861  |    0.915798  |    0.919918  |                              1000 |
| readmission_90d      | Model 1 | RERI                 | -0.0481255 |   -0.0483244 |   -0.0479354 |                              1000 |
| readmission_90d      | Model 1 | AP                   | -0.0524322 |   -0.0525398 |   -0.0523124 |                              1000 |
| readmission_90d      | Model 1 | synergy_index        |  2.41487   |    2.32272   |    2.51855   |                              1000 |
| readmission_90d      | Model 2 | R00                  |  0.240745  |    0.239313  |    0.242114  |                              1000 |
| readmission_90d      | Model 2 | R10                  |  0.252695  |    0.251174  |    0.254171  |                              1000 |
| readmission_90d      | Model 2 | R01                  |  0.204259  |    0.202796  |    0.205675  |                              1000 |
| readmission_90d      | Model 2 | R11                  |  0.204788  |    0.203286  |    0.206224  |                              1000 |
| readmission_90d      | Model 2 | interaction_contrast | -0.0114202 |   -0.0115067 |   -0.0113344 |                              1000 |
| readmission_90d      | Model 2 | RR10                 |  1.04964   |    1.04928   |    1.04999   |                              1000 |
| readmission_90d      | Model 2 | RR01                 |  0.848445  |    0.846577  |    0.850294  |                              1000 |
| readmission_90d      | Model 2 | RR11                 |  0.850644  |    0.84859   |    0.852646  |                              1000 |
| readmission_90d      | Model 2 | RERI                 | -0.0474371 |   -0.0476339 |   -0.0472458 |                              1000 |
| readmission_90d      | Model 2 | AP                   | -0.0557661 |   -0.0558929 |   -0.0556279 |                              1000 |
| readmission_90d      | Model 2 | synergy_index        |  1.46544   |    1.45379   |    1.47728   |                              1000 |
| icu_readmission_365d | Model 1 | R00                  |  0.162511  |    0.161698  |    0.163347  |                              1000 |
| icu_readmission_365d | Model 1 | R10                  |  0.150248  |    0.149468  |    0.151042  |                              1000 |
| icu_readmission_365d | Model 1 | R01                  |  0.159309  |    0.158417  |    0.160183  |                              1000 |
| icu_readmission_365d | Model 1 | R11                  |  0.131976  |    0.131187  |    0.132746  |                              1000 |
| icu_readmission_365d | Model 1 | interaction_contrast | -0.0150699 |   -0.0151765 |   -0.0149602 |                              1000 |
| icu_readmission_365d | Model 1 | RR10                 |  0.924543  |    0.923945  |    0.925116  |                              1000 |
| icu_readmission_365d | Model 1 | RR01                 |  0.980294  |    0.978285  |    0.982326  |                              1000 |
| icu_readmission_365d | Model 1 | RR11                 |  0.812105  |    0.810004  |    0.814229  |                              1000 |

## Multiplicative Interaction

| outcome              | model   | term                                              |       HR |   CI95_lower |   CI95_upper |   wald_p_value |   interaction_lrt_chisq |   interaction_lrt_df |   interaction_lrt_p_value |   analysis_n |   event_n |   penalizer |
|:---------------------|:--------|:--------------------------------------------------|---------:|-------------:|-------------:|---------------:|------------------------:|---------------------:|--------------------------:|-------------:|----------:|------------:|
| readmission_90d      | Model 1 | psych_primary_documented_by_index:delirium_binary | 0.92104  |     0.826464 |     1.02644  |      0.136776  |                 2.21725 |                    1 |                 0.136476  |        24033 |      6321 |           0 |
| readmission_90d      | Model 2 | psych_primary_documented_by_index:delirium_binary | 0.921289 |     0.826676 |     1.02673  |      0.138121  |                 2.20212 |                    1 |                 0.137821  |        24033 |      6321 |           0 |
| icu_readmission_365d | Model 1 | psych_primary_documented_by_index:delirium_binary | 0.848393 |     0.72788  |     0.988859 |      0.0354406 |                 4.44207 |                    1 |                 0.0350638 |        24033 |      3228 |           0 |
| icu_readmission_365d | Model 2 | psych_primary_documented_by_index:delirium_binary | 0.848405 |     0.727885 |     0.988881 |      0.0354655 |                 4.44086 |                    1 |                 0.0350885 |        24033 |      3228 |           0 |

## Time-Specific Multiplicative Interaction

| outcome              | time_window   | term                                              |       HR |   CI95_lower |   CI95_upper |   wald_p_value |   analysis_n |   event_n |   penalizer |
|:---------------------|:--------------|:--------------------------------------------------|---------:|-------------:|-------------:|---------------:|-------------:|----------:|------------:|
| readmission_90d      | 0_30_days     | psych_primary_documented_by_index:delirium_binary | 0.925293 |     0.807705 |      1.06    |      0.262845  |        23877 |      4126 |           0 |
| readmission_90d      | 30_90_days    | psych_primary_documented_by_index:delirium_binary | 0.839303 |     0.692473 |      1.01727 |      0.0741843 |        18681 |      2039 |           0 |
| icu_readmission_365d | 0_30_days     | psych_primary_documented_by_index:delirium_binary | 0.822946 |     0.639538 |      1.05895 |      0.129843  |        24021 |      1220 |           0 |
| icu_readmission_365d | 30_90_days    | psych_primary_documented_by_index:delirium_binary | 0.858685 |     0.639894 |      1.15228 |      0.30995   |        21623 |       832 |           0 |
| icu_readmission_365d | 90_365_days   | psych_primary_documented_by_index:delirium_binary | 0.89014  |     0.686754 |      1.15376 |      0.379239  |        20087 |      1164 |           0 |

## Bootstrap Diagnostics

| outcome              | model   |   successful_iterations |   planned_iterations |   failed_iterations | status                         | model_refit_each_iteration   |
|:---------------------|:--------|------------------------:|---------------------:|--------------------:|:-------------------------------|:-----------------------------|
| icu_readmission_365d | Model 1 |                    1000 |                 1000 |                   0 | success_fixed_model_resampling | False                        |
| icu_readmission_365d | Model 2 |                    1000 |                 1000 |                   0 | success_fixed_model_resampling | False                        |
| readmission_90d      | Model 1 |                    1000 |                 1000 |                   0 | success_fixed_model_resampling | False                        |
| readmission_90d      | Model 2 |                    1000 |                 1000 |                   0 | success_fixed_model_resampling | False                        |

## Fine-Gray

- Fine-Gray status is recorded in `fine_gray_implementation_status.md`.

## Warnings And Deviations

- Standardized CIF bootstrap used patient-level resampling of fixed fitted cause-specific models; target and competing-death models were not refit inside each bootstrap iteration because time-varying Cox refitting was computationally infeasible in this runtime.
