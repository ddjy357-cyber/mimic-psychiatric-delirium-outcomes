# Additional File: RECORD Algorithms and Code Lists

This file documents the frozen computable definitions used in the analysis.

## Psychiatric comorbidity

The validated v1.1 psychiatric mapping is in `data/psychiatric_code_mapping_validated_v1.1.csv`. Excluded codes and clinical priority rules are in `data/psychiatric_code_exclusions_v1.1.csv` and `config/frozen_study_definitions_v1.yaml`.

The primary psychiatric comorbidity definition includes depressive disorders, anxiety disorders, trauma and stressor-related disorders, bipolar disorders, and schizophrenia spectrum and other psychotic disorders. It excludes delirium, dementia/cognitive disorders, alcohol-related disorders, other substance-related disorders, secondary psychiatric disorders due to physiological conditions, and substance-induced psychiatric disorders.

## Early ICU delirium

Delirium classification uses the frozen Delirium assessment item and the 72-hour rule in `config/frozen_study_definitions_v1.yaml`. UTA is not counted as negative, and negative assessments near observed RASS <= -4 are invalid negative evidence.

## Severity and derived concepts

Derived concept dependency and feasibility summaries are included under `results/qc/`. Public scripts include DuckDB-adapted SQL and project-specific non-neurologic SOFA scripts.
