# Psychiatric Mapping Provenance v1.1

- Frozen mapping file: `${PROJECT_DIR}\outputs\psychiatric_code_validation\psychiatric_code_mapping_validated_v1.1.csv`
- Frozen date: `2026-06-19`
- SHA256: `30297cf7415fe84e2a352adbf65e6310801034f64320310802f35db56baef954`
- ICD-10 source: AHRQ CCSR for ICD-10-CM Diagnoses, v2026.1
- ICD-9 source: AHRQ HCUP Single-Level CCS for ICD-9-CM Diagnoses, 2015

## v1.1 Rule Updates

- ICD-10 F06 family is assigned before MBD001/MBD002/MBD003/MBD005 and excluded from primary exposure as `secondary_psychiatric_due_to_physiological_condition`.
- ICD-9 30921 separation anxiety disorder is removed from trauma/stressor and marked `excluded_other_psychiatric_category`.
- Main trauma/stressor exposure is restricted to ICD-10 F43 and ICD-9 308/309 acute stress reaction/PTSD/adjustment-family codes; F44, F48.1, and F94 MBD007 codes are retained only as `other_psychiatric_disorders`.

## Changed Codes

| icd_code_norm   |   icd_version | mimic_long_title                                                                      | v1_clinical_priority_category                        | clinical_priority_category                           |   v1_primary_psychiatric_comorbidity_flag |   primary_psychiatric_comorbidity_flag |
|:----------------|--------------:|:--------------------------------------------------------------------------------------|:-----------------------------------------------------|:-----------------------------------------------------|------------------------------------------:|---------------------------------------:|
| F064            |            10 | Anxiety disorder due to known physiological condition                                 | anxiety_disorders                                    | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F0633           |            10 | Mood disorder due to known physiological condition with manic features                | bipolar_disorders                                    | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F0634           |            10 | Mood disorder due to known physiological condition with mixed features                | bipolar_disorders                                    | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F0631           |            10 | Mood disorder due to known physiological condition with depressive features           | depressive_disorders                                 | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F0632           |            10 | Mood disorder due to known physiological condition with major depressive-like episode | depressive_disorders                                 | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F060            |            10 | Psychotic disorder with hallucinations due to known physiological condition           | schizophrenia_spectrum_and_other_psychotic_disorders | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F061            |            10 | Catatonic disorder due to known physiological condition                               | schizophrenia_spectrum_and_other_psychotic_disorders | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| F062            |            10 | Psychotic disorder with delusions due to known physiological condition                | schizophrenia_spectrum_and_other_psychotic_disorders | secondary_psychiatric_due_to_physiological_condition |                                         1 |                                      0 |
| 30921           |             9 | Separation anxiety disorder                                                           | trauma_and_stressor_related_disorders                | excluded_other_psychiatric_category                  |                                         1 |                                      0 |
| F440            |            10 | Dissociative amnesia                                                                  | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F441            |            10 | Dissociative fugue                                                                    | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F442            |            10 | Dissociative stupor                                                                   | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F444            |            10 | Conversion disorder with motor symptom or deficit                                     | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F445            |            10 | Conversion disorder with seizures or convulsions                                      | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F446            |            10 | Conversion disorder with sensory symptom or deficit                                   | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F447            |            10 | Conversion disorder with mixed symptom presentation                                   | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F4481           |            10 | Dissociative identity disorder                                                        | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F4489           |            10 | Other dissociative and conversion disorders                                           | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F449            |            10 | Dissociative and conversion disorder, unspecified                                     | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F481            |            10 | Depersonalization-derealization syndrome                                              | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |
| F941            |            10 | Reactive attachment disorder of childhood                                             | trauma_and_stressor_related_disorders                | other_psychiatric_disorders                          |                                         1 |                                      0 |

## Quality Checks

| check                                    |   value | passed   |
|:-----------------------------------------|--------:|:---------|
| f06_family_in_primary                    |       0 | True     |
| secondary_category_in_primary            |       0 | True     |
| substance_related_in_primary             |       0 | True     |
| dementia_in_primary                      |       0 | True     |
| delirium_in_primary                      |       0 | True     |
| code_version_multiple_primary_categories |       0 | True     |
| four_group_classifiable_total            |   29458 | True     |

No adjusted model, formal interaction model, or P-value test was run.
