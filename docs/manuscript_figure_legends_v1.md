# Manuscript Figure Legends v1.0

## Figure 1. Study population flow diagram

Flow diagram showing derivation of the analytic cohort from the MIMIC-IV v3.1 base population. The base cohort included adult patients with a first ICU stay, ICU length of stay of at least 24 hours, and survival to index hospital discharge (n=46,316). Patients with classifiable 72-hour early ICU delirium status formed the primary analysis cohort (n=29,458). The four joint exposure groups were: no documented psychiatric comorbidity/no delirium (n=13,909), documented psychiatric comorbidity/no delirium (n=5,987), no documented psychiatric comorbidity/delirium (n=6,067), and documented psychiatric comorbidity/delirium (n=3,495). The conservative readmission cohort included 24,033 patients.

## Figure 2. One-year all-cause mortality Kaplan-Meier curves by joint exposure group

Kaplan-Meier curves for all-cause mortality within 365 days after index hospital discharge, stratified by the four joint exposure groups. Curves are descriptive and should be interpreted with the adjusted average and time-varying Cox models. The main mortality model excluded same-day date of death records, which were evaluated in sensitivity analysis.

## Figure 3. Time-varying mortality hazard ratios

Adjusted Model 2 hazard ratios for one-year all-cause mortality estimated in start-stop Cox models over 0-30, 30-90, and 90-365 days after index hospital discharge. The reference group was patients with neither documented psychiatric comorbidity nor early ICU delirium. Model 2 adjusted for demographic, admission, comorbidity, and early non-neurologic SOFA covariates. The formal likelihood-ratio test supported time-varying joint exposure associations.

## Figure 4. Standardized 365-day mortality risk by joint exposure group

Model 2 standardized 365-day mortality risks estimated using fixed-horizon logistic regression and g-computation. Each patient was set in turn to each joint exposure group while observed covariates were retained, and predicted risks were averaged over the analytic cohort. Error bars show percentile 95% confidence intervals from 1,000 patient-level bootstrap resamples.

## Figure 5. Standardized 90-day same-system readmission cumulative incidence

Model 2 standardized cumulative incidence of 90-day same-system readmission after index hospital discharge in the conservative readmission cohort. Death before readmission was modeled as a competing event. Standardized CIFs were estimated using the final v1.2 implementation, which refit target-event and competing-death cause-specific models within each patient-level bootstrap resample.

## Figure 6. Standardized one-year same-system ICU readmission cumulative incidence

Model 2 standardized cumulative incidence of same-system ICU readmission within 365 days after index hospital discharge in the conservative readmission cohort. Same-admission repeat ICU stays were not counted as post-discharge ICU readmissions. Death before ICU readmission was treated as a competing event. Error bars show percentile 95% confidence intervals from 1,000 patient-level bootstrap resamples.

## Supplementary Figure 1. IPSW balance for 72-hour delirium classifiability

Covariate balance comparing the full base population with the unweighted and weighted 72-hour delirium-classifiable cohort. Stable selection weights were estimated from an out-of-fold logistic model for delirium classifiability. The main IPSW sensitivity used 1st/99th percentile trimmed weights.

## Supplementary Figure 2. Sensitivity analysis forest plots

Forest plots summarizing prespecified sensitivity analyses for one-year all-cause mortality, 90-day same-system readmission, and one-year same-system ICU readmission. Sensitivity analyses included strict-prior psychiatric comorbidity, 48-hour delirium definition, IPSW for delirium classifiability, hospice exclusion, full classifiable readmission cohorts, and alternative severity adjustment strategies.
