"""Usage: python scripts/prepare_data.py --config configs/data_legacy.json"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.pipeline import prepare_data


def main():
    parser = argparse.ArgumentParser(description="prepare-data: immutable import and annotation-pool split")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    try:
        report, processed, splits = prepare_data(args.config, args.output_root)
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        parser.exit(2, f"prepare-data: {exc}\n")
    print(json.dumps({"data_version": report["data_version"], "counts": report["counts"],
                      "warnings": report["warnings"], "report": str(processed / "report.json"),
                      "manifest": str(splits / "manifest.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
