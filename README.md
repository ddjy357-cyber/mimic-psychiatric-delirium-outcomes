# mimic-psychiatric-delirium-outcomes

Archival analysis code and aggregate-results release, version v1.0.3.

**Documented Psychiatric Comorbidity, Early ICU Delirium, and Long-Term Outcomes Among Survivors of Critical Illness: A Retrospective Cohort Study Using MIMIC-IV**

## Purpose

Version 1.0.3 corrects ORCID metadata only. Jieyang Dong's ORCID is 0000-0002-2798-9491, and Ge Zhang's ORCID is 0000-0002-5858-4825. No analytic code, statistical model, aggregate result, table, figure, or study conclusion was changed.


This repository preserves the actual analysis scripts, frozen study definitions, aggregate result files, figure source data, and final public figures used for the study. It contains no patient-level data, no MIMIC-IV database, no raw MIMIC files, and no subject-level identifiers.

This is an archival analysis-code and aggregate-results release. It is not an independently verified single-command complete-rebuild package. Complete rebuilding requires credentialed local access to MIMIC-IV v3.1, the official MIT-LCP mimic-code concept library, a compatible local DuckDB build, and the project-specific dependency environment.

## Joint Exposure Groups

- G1: no documented psychiatric comorbidity at or before the index hospitalization / no early ICU delirium.
- G2: documented psychiatric comorbidity at or before the index hospitalization / no early ICU delirium.
- G3: no documented psychiatric comorbidity at or before the index hospitalization / early ICU delirium.
- G4: documented psychiatric comorbidity at or before the index hospitalization / early ICU delirium.

## Outcomes

- One-year all-cause mortality after index hospital discharge.
- Ninety-day same-system readmission.
- One-year same-system ICU readmission.

## Data Availability and Restrictions

MIMIC-IV version 3.1 is available to credentialed users through PhysioNet under its data use agreement. MIMIC-IV data are not redistributed here and are not licensed by this repository. Users must obtain their own credentialed access and comply with the MIMIC-IV data use agreement.

The public repository URL is https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes. The Zenodo DOI placeholder remains until the archive DOI is created.

## Final Result Version Hierarchy

- Mortality: `primary_mortality_v1_1`.
- Readmission cause-specific Cox and time-varying analyses: validated `02_readmission_outcomes`.
- Readmission standardized CIF, RD, RR, and additive interaction: `02_readmission_outcomes_v1_2` only.
- Sensitivity analyses: `03_sensitivity_analyses`.
- Integrated results: `04_integrated_results`.

Deprecated outputs from mortality v1 and readmission CIF v1/v1.1 are audit history only and are not formal results.

## Local Use

The helper at `scripts/run_pipeline.py` is a project-stage index and environment-dependent entry point. It lists the scripts used in each stage and can execute a selected stage only after the user supplies the required local environment and MIMIC-IV database path. It is not a single-command complete-rebuild workflow from a blank environment.

```bash
python scripts/run_pipeline.py --list
python scripts/run_pipeline.py --stage figures --dry-run
```

## Directory Guide

- `config/`: frozen protocol, DAG, SAP, data dictionary, and study definitions.
- `scripts/`: archival analysis and figure scripts with environment-variable based local paths.
- `results/`: aggregate, non-patient-level final results and QC tables.
- `figures/`: final figures, supplementary figures, graphical abstract, and figure source data.
- `docs/`: reproducibility notes, privacy audit, code-list documentation, traceability, and manual release steps.
- `data/`: aggregate code lists and public audit tables only; no MIMIC data.

## Citation

Please cite this repository using `CITATION.cff`. For the MIMIC-IV database, cite the official PhysioNet/MIMIC-IV references separately.

## Authors

Jieyang Dong and Ge Zhang contributed equally to this work.

- Jieyang Dong (ORCID: 0000-0002-2798-9491)
- Ge Zhang (ORCID: 0000-0002-5858-4825)

Department of Critical Care Medicine, Sir Run Run Shaw Hospital, Zhejiang University School of Medicine, Hangzhou, 310016, China.

Corresponding author: Ge Zhang <3204091@zju.edu.cn>
