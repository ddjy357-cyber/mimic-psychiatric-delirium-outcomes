# mimic-psychiatric-delirium-outcomes

Public code and aggregate results for:

**Documented Psychiatric Comorbidity, Early ICU Delirium, and Long-Term Outcomes Among Survivors of Critical Illness: A Retrospective Cohort Study Using MIMIC-IV**

## Purpose

This repository contains reproducible code, frozen study definitions, aggregate result files, figure source data, and manuscript support materials for a prognostic association study using MIMIC-IV v3.1. It does **not** contain patient-level data.

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

This repository contains no MIMIC patient-level rows, no DuckDB database, no raw CSV exports, and no subject-level identifiers.

## Final Result Version Hierarchy

- Mortality: `primary_mortality_v1_1`.
- Readmission cause-specific Cox and time-varying analyses: validated `02_readmission_outcomes`.
- Readmission standardized CIF, RD, RR, and additive interaction: `02_readmission_outcomes_v1_2` only.
- Sensitivity analyses: `03_sensitivity_analyses`.
- Integrated results: `04_integrated_results`.

Deprecated outputs from mortality v1 and readmission CIF v1/v1.1 are not formal results.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r environment/requirements.txt
python scripts/run_pipeline.py --stage all --project-dir . --mimic-duckdb <path-to-local-mimiciv.duckdb>
```

Without a local MIMIC-IV v3.1 DuckDB database, the pipeline prints data-preparation guidance and does not pretend to reproduce patient-level analyses.

## Directory Guide

- `config/`: frozen protocol, DAG, SAP, data dictionary, and study definitions.
- `scripts/`: public reproducibility scripts using environment variables or command-line arguments for local paths.
- `results/`: aggregate, non-patient-level final results and QC tables.
- `figures/`: final figures, supplementary figures, graphical abstract, and figure source data.
- `docs/`: reproducibility guide, privacy audit, code-list documentation, and Zenodo/GitHub manual steps.
- `data/`: README only; no MIMIC data.

## Reproduction Requirements

A local MIMIC-IV v3.1 DuckDB database with the expected `hosp` and `icu` schemas is required for end-to-end reproduction. See `docs/reproducibility_guide.md`.

## Citation

Please cite this repository using `CITATION.cff`. For the MIMIC-IV database, cite the official PhysioNet/MIMIC-IV references separately.

## Authors

Xuan Long and Ge Zhang contributed equally.

- Xuan Long
- Ge Zhang
- Jieyang Dong (ORCID: 0000-0002-5858-4825)

Department of Critical Care Medicine, Sir Run Run Shaw Hospital, Zhejiang University School of Medicine, Hangzhou, 310016, China.

Contact: Jieyang Dong <3324253@zju.edu.cn>
