# Documented Psychiatric Comorbidity, Early ICU Delirium, and Long-Term Outcomes Among Survivors of Critical Illness: A Retrospective Cohort Study Using MIMIC-IV

Draft: Methods and Results v1.0

## Methods

### Study design and data source

We conducted a retrospective cohort study using MIMIC-IV version 3.1, a deidentified critical care database containing hospital and intensive care unit (ICU) data from Beth Israel Deaconess Medical Center. The study was designed and reported as a prognostic association study, with attention to STROBE and RECORD principles for observational research using routinely collected health data. All exposure definitions, outcome definitions, covariate sets, sensitivity analyses, and implementation corrections were finalized before manuscript drafting. No model was added or modified during preparation of this Methods and Results draft.

### Ethical considerations

MIMIC-IV is a deidentified public research database. The original database release was approved under the data-use governance of the database maintainers, and individual patient consent was waived because the data are deidentified. Access to the local copy used for this study required credentialed PhysioNet access and completion of required human-subjects research training. The current analysis used only deidentified data.

### Study population

The base population consisted of adult patients in MIMIC-IV v3.1 with a first ICU stay, ICU length of stay of at least 24 hours, and survival to hospital discharge. Adult status was based on the MIMIC-IV age variable. For each patient, the index ICU stay was the first ICU stay in the database, ordered by ICU admission time. The index hospitalization was the hospital admission containing the index ICU stay. Patients who died before hospital discharge were not part of the target population, because all outcomes were defined from hospital discharge.

The primary analysis population further required that 72-hour early ICU delirium status be classifiable according to the prespecified delirium rule. Patients who could not be classified because of insufficient or uninterpretable delirium assessment information were excluded from primary outcome models, and this restriction was evaluated in prespecified inverse probability of selection weighting (IPSW) sensitivity analyses.

### Index hospitalization and index ICU stay

The index hospital admission was the hospitalization linked to the patient's first eligible ICU stay. Time zero for all long-term outcomes was the discharge date of the index hospitalization. Same-admission repeat ICU stays were not counted as post-discharge ICU readmissions. Hospital and ICU length of stay and discharge destination were not included in the primary regression models because they may occur after, or be influenced by, early ICU delirium or subsequent care processes.

### Documented psychiatric comorbidity

The main psychiatric exposure was documented psychiatric comorbidity at or before the index hospitalization. Diagnosis codes were derived from hospital ICD diagnosis records and mapped using a frozen, validated v1.1 psychiatric code mapping. The primary psychiatric comorbidity definition included five prespecified categories: depressive disorders, anxiety disorders, trauma and stressor-related disorders, bipolar disorders, and schizophrenia spectrum and other psychotic disorders. The primary exposure explicitly excluded delirium, dementia and other cognitive disorders, alcohol-related disorders, other substance-related disorders, secondary psychiatric disorders due to physiological conditions, substance-induced psychiatric disorders, symptom-only codes, and other nonprimary psychiatric categories.

The primary timing definition was documented-by-index, defined as a qualifying psychiatric diagnosis recorded before the index admission or during the index hospitalization. Two timing variables were also retained: strict-prior psychiatric comorbidity, requiring documentation before the index admission, and index-admission-only psychiatric comorbidity, defined as documented-by-index without a strict-prior diagnosis. Strict-prior psychiatric comorbidity was evaluated as a prespecified sensitivity analysis.

### Early ICU delirium definition

The primary delirium exposure was early ICU delirium within 72 hours of ICU admission. Delirium assessments were identified from the frozen MIMIC-IV item for Delirium assessment. A patient was classified as delirium-positive if at least one assessment within the 72-hour window was recorded as Positive. A patient was classified as delirium-negative if there was no Positive assessment and at least two different natural days with valid Negative assessments within the same window. Unable-to-assess entries were not counted as Negative. Negative delirium assessments were not considered valid negative evidence when an observed Richmond Agitation-Sedation Scale (RASS) score of <= -4 was recorded within 1 hour of the delirium assessment. Goal RASS was not used to define consciousness state. Patients who did not meet either the positive or negative definition were considered unclassifiable for the primary delirium exposure.

A prespecified 48-hour delirium sensitivity definition used the same logic within 48 hours of ICU admission. Whole-ICU delirium was not added as a new analysis because it was not part of the final prespecified analysis set used for this manuscript draft.

### Joint exposure groups

The primary analysis used four mutually exclusive joint exposure groups: no documented psychiatric comorbidity and no early ICU delirium (reference group), documented psychiatric comorbidity without early ICU delirium, no documented psychiatric comorbidity with early ICU delirium, and both documented psychiatric comorbidity and early ICU delirium. These groups were used to describe joint prognostic associations, not causal estimands.

### Outcomes

The primary outcome was all-cause mortality within 365 days after discharge from the index hospitalization. The main mortality analysis excluded deaths recorded on the same calendar date as discharge; same-day date of death was evaluated in sensitivity analysis. Secondary outcome analysis focused on 90-day same-system readmission after index hospital discharge. One-year same-system ICU readmission was prespecified as an exploratory outcome. Readmissions outside the MIMIC health system were not observable and were not included. Stand-alone emergency department visits without hospitalization were not analyzed.

### Covariates

Model 0 included only the four-level joint exposure. Model 1 adjusted for baseline demographic, admission, and chronic comorbidity variables: age at index admission modeled by a centered full-rank natural cubic spline with knots at 60 and 72 years and boundary knots at 31 and 89 years; recorded sex; race group; anchor year group; admission type group; admission location group; first ICU careunit group; log-transformed number of prior MIMIC hospitalizations; Charlson comorbidity score excluding the age component and documented by index; documented dementia; documented substance use disorder; and chronic neurologic disease. Model 2 added early acute severity using the project-specific non-neurologic SOFA score from 0 to 24 hours and the number of observed non-neurologic SOFA components, with 5 observed components as the reference level. The non-neurologic SOFA score included respiratory, coagulation, liver, cardiovascular, and renal components and excluded the central nervous system and Glasgow Coma Scale components.

### Follow-up strategy

All mortality follow-up was measured from index hospital discharge. For same-system readmission and same-system ICU readmission, exact patient-level administrative database end dates were not identifiable because MIMIC dates are shifted independently by patient. The primary readmission analyses therefore used a conservative follow-up cohort with approximate discharge-year upper bound no later than 2021. Analyses in the full 72-hour classifiable cohort were reported as sensitivity analyses and explicitly interpreted as same-system events with administrative follow-up completeness not guaranteed.

### Statistical analysis

Baseline characteristics were summarized by joint exposure group using medians with interquartile ranges, means with standard deviations, and counts with percentages. No P values were used to select variables. Cox proportional hazards models were used to estimate average hazard ratios (HRs) for one-year mortality and cause-specific HRs for readmission outcomes. For one-year mortality, proportional hazards diagnostics indicated non-proportionality of the joint exposure terms; therefore, the full-year Cox HRs were interpreted as average associations across follow-up, and prespecified start-stop time-varying Cox models estimated HRs separately for 0-30, 30-90, and 90-365 days.

Because 365-day mortality status was available for the primary mortality cohort, standardized 365-day mortality risks were estimated using fixed-horizon logistic regression with the same Model 1 and Model 2 covariates as the Cox models. G-computation was used by setting each patient to each of the four joint exposure groups in turn while retaining observed covariates and averaging predicted probabilities. Percentile 95% confidence intervals were estimated using 1,000 patient-level bootstrap resamples.

### Competing-risk analysis

For 90-day same-system readmission and one-year same-system ICU readmission, death before the target event was treated as a competing event. Cause-specific Cox models used the prespecified composite time-to-target-event-or-death variables and target-event status indicators. Crude cumulative incidence was described using Aalen-Johansen methods. Standardized cumulative incidence functions (CIFs) were estimated using target-event and competing-death cause-specific models, with CIF integration over the union of target and competing event times. The final CIF implementation used an uncentered baseline hazard with exp(X beta) predictions and 1,000 patient-level bootstrap resamples in which both target-event and competing-death models were refit. Fine-Gray models were not run because a validated R environment was not available; no unvalidated Fine-Gray implementation was substituted.

### Interaction analysis

Multiplicative interaction was evaluated using product terms between documented psychiatric comorbidity and delirium status. Additive interaction was evaluated using standardized absolute risks for 365-day mortality and standardized CIFs for readmission outcomes. Interaction contrast, relative excess risk due to interaction (RERI), attributable proportion, and synergy index were calculated descriptively with bootstrap confidence intervals when available. These analyses were interpreted as interaction analyses of joint association and not as evidence of biological interaction or causal synergy.

### Missing-data handling

Categorical missingness and unknown categories were retained as explicit categories when appropriate. For non-neurologic SOFA, missing organ components were assigned 0 points in the main severity score, and the observed component count was included in Model 2. Complete-case non-neurologic SOFA was not used as the primary approach. No multiple imputation was performed in this analysis version.

### Selection-bias IPSW sensitivity

To assess possible selection bias from restricting the primary analysis to patients with classifiable 72-hour delirium status, a 5-fold out-of-fold logistic selection model was fit in the base population. Candidate predictors were restricted to variables available at ICU admission or within the first 24 hours and did not include outcomes, length of stay, discharge destination, hospice status, psychiatric comorbidity documented only during the index admission, delirium status, or post-72-hour variables. Stable selection weights were calculated as the overall probability of being classifiable divided by the out-of-fold predicted probability. Untrimmed, 1st/99th percentile trimmed, and 5th/95th percentile trimmed weights were evaluated; 1st/99th percentile trimming was the main IPSW sensitivity strategy.

### Other sensitivity analyses

Prespecified sensitivity analyses used strict-prior psychiatric comorbidity, the 48-hour delirium definition, the full 72-hour classifiable cohort for readmission outcomes, exclusion of hospice discharges for mortality, inclusion of same-day date of death in mortality analysis, and alternative severity adjustment strategies. Severity alternatives included official first-day SOFA, official OASIS, early organ-support indicators, and the main non-neurologic SOFA approach. A 0-6-hour non-neurologic SOFA sensitivity model was not run because the required frozen variables were not present in the formal analysis table.

### Software and reproducibility

Analyses were performed using Python with lifelines, statsmodels, patsy, numpy, pandas, scipy, matplotlib, and DuckDB. All analysis scripts and result files were versioned locally with SHA256 checksums. Deprecated outputs from the original mortality v1 model and readmission CIF v1/v1.1 were not used for formal manuscript results.

## Results

### Cohort derivation

The base cohort included 46,316 adult patients with a first ICU stay of at least 24 hours who survived to hospital discharge. Among these patients, 29,458 had classifiable 72-hour early ICU delirium status and formed the primary analysis cohort. The four joint exposure groups included 13,909 patients with neither documented psychiatric comorbidity nor early ICU delirium, 5,987 with documented psychiatric comorbidity without early ICU delirium, 6,067 with early ICU delirium without documented psychiatric comorbidity, and 3,495 with both documented psychiatric comorbidity and early ICU delirium. The conservative readmission cohort included 24,033 patients.

### Baseline characteristics

Baseline characteristics differed across the four joint exposure groups. Median age was 67 years in the reference group, 63 years in the documented psychiatric comorbidity without delirium group, 70 years in the delirium without psychiatric comorbidity group, and 64 years in the joint comorbidity-delirium group. Female sex was more common in the documented psychiatric comorbidity groups (54.4% and 52.9%) than in the groups without documented psychiatric comorbidity (39.3% and 38.6%). Urgent or emergency admissions were more frequent in delirium groups, accounting for 71.1% and 72.0% of patients in the delirium-only and joint comorbidity-delirium groups, respectively. Non-neurologic SOFA scores were higher in delirium groups, with median scores of 4 in both delirium groups compared with 2 in both non-delirium groups. Early invasive ventilation, vasopressor use, renal replacement therapy, and Sepsis-3 classification were also more common in delirium groups.

The documented psychiatric comorbidity groups had a higher mean number of prior MIMIC hospitalizations than their counterparts without documented psychiatric comorbidity, although the median number of prior hospitalizations was 0 in all four groups. The distribution of ICU type also varied. MICU admission was most common in the joint comorbidity-delirium group (46.6%), whereas CCU-CVICU admission was most common in the reference group (36.6%). These patterns were consistent with greater acute illness burden among patients with early ICU delirium and greater prior documented health-system contact among patients with psychiatric comorbidity.

### One-year all-cause mortality

The primary mortality model included 29,366 patients and 5,105 deaths within 365 days after index hospital discharge. In the Model 2 average Cox model, compared with patients with neither documented psychiatric comorbidity nor early ICU delirium, the HR for mortality was 1.125 (95% CI, 1.038-1.220) for documented psychiatric comorbidity without early ICU delirium, 1.466 (95% CI, 1.361-1.579) for early ICU delirium without documented psychiatric comorbidity, and 1.465 (95% CI, 1.338-1.603) for both documented psychiatric comorbidity and early ICU delirium. Fixed-horizon logistic g-computation estimated standardized 365-day mortality risks of 15.26%, 16.74%, 20.24%, and 20.19%, respectively. Thus, the two groups with early ICU delirium had higher standardized mortality risk than the reference group, whereas the standardized risk in the joint comorbidity-delirium group was similar to that in the delirium-only group.

On the absolute risk scale, the Model 2 standardized mortality risk difference relative to the reference group was +1.48 percentage points for documented psychiatric comorbidity without delirium, +4.98 percentage points for delirium without documented psychiatric comorbidity, and +4.94 percentage points for the joint comorbidity-delirium group. These standardized estimates paralleled the adjusted Cox results and showed a larger mortality contrast for delirium-containing groups than for documented psychiatric comorbidity alone.

### Time-varying mortality associations

The proportional hazards assumption for the joint exposure terms was not supported by the prespecified likelihood-ratio test comparing the reduced and time-varying mortality models (chi-square=94.18, df=6, P=4.09 x 10^-18). In time-varying Model 2 Cox analyses, the HRs for documented psychiatric comorbidity without delirium were 1.197 during 0-30 days, 1.223 during 30-90 days, and 1.048 during 90-365 days. For delirium without psychiatric comorbidity, the corresponding HRs were 2.158, 1.458, and 1.109. For the joint comorbidity-delirium group, the HRs were 2.198, 1.350, and 1.137. These results indicate that the mortality association for delirium-containing groups was strongest early after discharge and attenuated over time.

### Ninety-day same-system readmission

In the conservative readmission cohort of 24,033 patients, 6,321 same-system readmissions occurred within 90 days. In the Model 2 cause-specific Cox model, compared with the reference group, the cause-specific HRs were 1.118 (95% CI, 1.046-1.194) for documented psychiatric comorbidity without delirium, 1.121 (95% CI, 1.044-1.204) for delirium without documented psychiatric comorbidity, and 1.154 (95% CI, 1.060-1.258) for both documented psychiatric comorbidity and delirium. Standardized 90-day CIFs were 25.17%, 27.47%, 26.90%, and 27.49%. Relative to the reference group, standardized risk differences were +2.30 percentage points, +1.73 percentage points, and +2.32 percentage points, respectively.

### One-year same-system ICU readmission

In the same conservative readmission cohort, 3,228 same-system ICU readmissions occurred within 365 days. In the Model 2 cause-specific Cox model, the HR was 0.997 (95% CI, 0.906-1.096) for documented psychiatric comorbidity without delirium, 1.229 (95% CI, 1.116-1.354) for delirium without documented psychiatric comorbidity, and 1.039 (95% CI, 0.920-1.174) for the joint comorbidity-delirium group. Standardized 365-day CIFs were 13.13%, 12.96%, 14.90%, and 12.88%. The signal for same-system ICU readmission was concentrated in the delirium-only group rather than in the psychiatric comorbidity alone or joint comorbidity-delirium groups.

### Multiplicative and additive interaction

Interaction analyses did not provide robust evidence of positive interaction between documented psychiatric comorbidity and early ICU delirium. For 365-day mortality, the Model 2 fixed-horizon additive interaction contrast was -0.0152 (95% CI, -0.0337 to 0.0025), and RERI was -0.0997 (95% CI, -0.2238 to 0.0161). For 90-day same-system readmission, the Model 2 interaction contrast was -0.0171 (95% CI, -0.0403 to 0.0066). For one-year same-system ICU readmission, the Model 2 interaction contrast was -0.0186 (95% CI, -0.0373 to 0.0007). Although some multiplicative product terms had P values near or below 0.05 in selected models or time windows, the overall pattern of standardized risks and additive interaction estimates did not support a positive joint interaction.

### Sensitivity analyses

IPSW analyses for delirium classifiability were generally consistent with the main analysis. The 1st/99th percentile trimmed weights had an effective sample size of approximately 23,740, and the maximum absolute standardized mean difference decreased from 0.400 before weighting to 0.114 after weighting. Weighted point estimates retained the main pattern for mortality, 90-day same-system readmission, and one-year same-system ICU readmission. Robust sandwich standard errors for weighted Cox models did not complete within feasible runtime; therefore, IPSW interval estimates were retained only as technical references.

Using strict-prior psychiatric comorbidity attenuated the mortality association for psychiatric comorbidity without delirium (HR, 1.06; 95% CI, 0.95-1.19), while mortality associations for delirium-containing groups remained elevated. The 48-hour delirium sensitivity definition preserved the main mortality and same-system readmission directions. Excluding hospice discharges reduced the number of mortality events but retained elevated mortality HRs for the delirium groups, with HRs of approximately 1.37 for both delirium without documented psychiatric comorbidity and joint comorbidity-delirium. Severity alternative models using official first-day SOFA, official OASIS, or organ-support indicators were broadly consistent with the main results. Results for one-year same-system ICU readmission were less stable, particularly for the psychiatric comorbidity without delirium and joint comorbidity-delirium groups. Fine-Gray models were not run.

In the full 72-hour classifiable cohort, which did not apply the conservative readmission follow-up restriction, 90-day same-system readmission associations remained modestly above the reference group for all three exposed groups, whereas one-year same-system ICU readmission remained most evident in the delirium-only group. The same-day date-of-death sensitivity analysis and hospice-exclusion analysis did not materially change the ranking of mortality associations. Across sensitivity analyses, the most consistent finding was higher post-discharge mortality among delirium-containing groups; the least consistent finding was the association of the joint comorbidity-delirium group with later same-system ICU readmission.
