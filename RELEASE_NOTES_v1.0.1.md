# Release Notes v1.0.1

This release fixes public-release and submission-package issues identified during independent pre-release audit. It does not rerun statistical models and does not change formal result numbers.

- Reframed the repository as archival analysis code and aggregate results rather than an independently verified one-command reproduction package.
- Restored graphical abstract files byte-for-byte from `Critical_Care_Final_Figures_v1.zip`.
- Isolated deprecated readmission CIF v1/v1.1 outputs from active result directories.
- Removed stale manuscript v1 draft files from the public release.
- Replaced local filesystem paths with `${PROJECT_DIR}`, `${MIMIC_DUCKDB}`, and `${MIMIC_RAW_DIR}` placeholders.
- Updated release metadata to v1.0.1.

Repository: https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes
