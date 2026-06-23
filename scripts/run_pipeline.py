from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


STAGE_SCRIPTS = {
    "cohort": ["build_analysis_dataset_v1_1.py"],
    "mortality": ["analysis/run_primary_mortality_v1_1.py"],
    "readmission": ["analysis/run_readmission_outcomes_v1.py", "analysis/run_readmission_cif_bootstrap_v1_2.py"],
    "sensitivity": ["analysis/run_final_sensitivity_and_integration_v1.py"],
    "figures": ["generate_submission_figures.py"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the public reproducibility pipeline.")
    parser.add_argument("--stage", choices=["cohort", "mortality", "readmission", "sensitivity", "figures", "all"], required=True)
    parser.add_argument("--project-dir", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--mimic-duckdb", default=os.environ.get("MIMIC_DUCKDB", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    env = os.environ.copy()
    env["PROJECT_DIR"] = str(project)
    if args.mimic_duckdb:
        env["MIMIC_DUCKDB"] = str(Path(args.mimic_duckdb).resolve())

    if args.stage != "figures" and not args.mimic_duckdb:
        print("MIMIC-IV v3.1 data are not included in this repository.")
        print("Provide a local DuckDB path with --mimic-duckdb or MIMIC_DUCKDB.")
        print("See docs/reproducibility_guide.md for data preparation instructions.")
        return 2

    stages = ["cohort", "mortality", "readmission", "sensitivity", "figures"] if args.stage == "all" else [args.stage]
    for stage in stages:
        for rel in STAGE_SCRIPTS[stage]:
            script = project / "scripts" / rel
            print(f"[{stage}] {script}")
            if args.dry_run:
                continue
            subprocess.run([sys.executable, str(script)], check=True, env=env, cwd=str(project))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
