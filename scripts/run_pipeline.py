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
    parser = argparse.ArgumentParser(
        description="Project-stage index for an already prepared local MIMIC-IV analysis environment."
    )
    parser.add_argument("--list", action="store_true", help="List stage scripts and exit.")
    parser.add_argument("--stage", choices=sorted(STAGE_SCRIPTS), help="Prepared-environment stage to inspect or run.")
    parser.add_argument("--project-dir", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--mimic-duckdb", default=os.environ.get("MIMIC_DUCKDB", ""))
    parser.add_argument("--execute", action="store_true", help="Execute the selected stage in the prepared environment.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected scripts without executing them.")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    if args.list or not args.stage:
        for stage, scripts in STAGE_SCRIPTS.items():
            print(f"{stage}:")
            for rel in scripts:
                print(f"  scripts/{rel}")
        print("\nThis helper is not a single-command complete-rebuild pipeline.")
        return 0

    env = os.environ.copy()
    env["PROJECT_DIR"] = str(project)
    if args.mimic_duckdb:
        env["MIMIC_DUCKDB"] = str(Path(args.mimic_duckdb).resolve())

    if args.stage != "figures" and not args.mimic_duckdb:
        print("MIMIC-IV v3.1 data are not included in this repository.")
        print("Provide a local DuckDB path with --mimic-duckdb or MIMIC_DUCKDB in a prepared environment.")
        return 2

    for rel in STAGE_SCRIPTS[args.stage]:
        script = project / "scripts" / rel
        print(f"[{args.stage}] {script}")
        if args.dry_run or not args.execute:
            continue
        subprocess.run([sys.executable, str(script)], check=True, env=env, cwd=str(project))
    if not args.execute:
        print("Dry index mode only. Add --execute in a prepared environment to run a selected stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
