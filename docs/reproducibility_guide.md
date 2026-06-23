# Reproducibility Guide

## Data access

MIMIC-IV v3.1 must be obtained directly from PhysioNet by credentialed users. This repository does not redistribute MIMIC-IV data.

## Local database

The scripts expect a local DuckDB database containing the MIMIC-IV v3.1 `hosp` and `icu` schemas. Provide the database path with:

```bash
python scripts/run_pipeline.py --stage all --mimic-duckdb /path/to/mimiciv.duckdb
```

## Execution order

1. `--stage cohort`
2. `--stage mortality`
3. `--stage readmission`
4. `--stage sensitivity`
5. `--stage figures`

## Expected key counts

- Base population: 46,316.
- Primary 72-hour delirium classifiable cohort: 29,458.
- Conservative readmission cohort: 24,033.
- Four groups: 13,909; 5,987; 6,067; 3,495.

## Expected key results

- Mortality Model 2 HRs: G2 1.125; G3 1.466; G4 1.465.
- 90-day same-system readmission Model 2 cause-specific HRs: G2 1.118; G3 1.121; G4 1.154.
- One-year same-system ICU readmission Model 2 cause-specific HRs: G2 0.997; G3 1.229; G4 1.039.

## Random seed

The prespecified random seed is 20260621.

## SHA256 checks

Use `SHA256SUMS.txt` to verify files:

```bash
sha256sum -c SHA256SUMS.txt
```

## Computational notes

Readmission CIF v1.2 refits target-event and competing-death models inside bootstrap resamples and is computationally intensive.

## Fine-Gray

Fine-Gray models were not run because a validated R environment was unavailable. No unvalidated substitute implementation is included.
