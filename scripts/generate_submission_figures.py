from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    print("Figure generation for the public release uses aggregate result CSV files under results/.")
    print("The submission-ready figures included in figures/ were generated during release packaging.")
    print(f"Project directory: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
