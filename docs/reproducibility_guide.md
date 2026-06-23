# Reproducibility Notes

## Scope

This release is an archival analysis-code and aggregate-results package. It preserves the scripts, frozen definitions, aggregate result files, figure source data, and final figures. It does not claim a single-command complete rebuild from a blank environment.

## Data access

MIMIC-IV v3.1 must be obtained directly from PhysioNet by credentialed users. This repository does not redistribute MIMIC-IV data or local DuckDB databases.

## Local database

Full rebuilding requires a local DuckDB database containing the expected MIMIC-IV v3.1 `hosp` and `icu` schemas, MIT-LCP mimic-code derived concepts adapted to DuckDB, and the project dependency environment. Paths should be supplied through environment variables such as `${MIMIC_DUCKDB}`, `${PROJECT_DIR}`, and `${MIMIC_RAW_DIR}`.

## Stage index

`scripts/run_pipeline.py` is a stage index and environment-dependent helper. It can list the major project stages and optionally execute a selected stage in a prepared local environment. It is not an independently verified complete-rebuild pipeline.

```bash
python scripts/run_pipeline.py --list
python scripts/run_pipeline.py --stage mortality --dry-run
```

## Expected key counts

- Base population: 46,316.
- Primary 72-hour delirium classifiable cohort: 29,458.
- Conservative readmission cohort: 24,033.
- Four groups: 13,909; 5,987; 6,067; 3,495.

## Expected key final results

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
