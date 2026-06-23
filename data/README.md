# Data Directory

This public repository does not contain MIMIC-IV data, a DuckDB database, raw CSV files, or patient-level derived files.

To reproduce the analyses, users must:

1. Obtain credentialed access to MIMIC-IV v3.1 through PhysioNet.
2. Download the dataset under the MIMIC-IV data use agreement.
3. Build a local DuckDB database with the expected `hosp` and `icu` schemas.
4. Provide the local database path to the pipeline with `--mimic-duckdb` or `MIMIC_DUCKDB`.
