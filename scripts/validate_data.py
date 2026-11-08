"""Verify checksums, row accounting, provenance and group isolation."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.validation import verify_prepared


def main():
    parser = argparse.ArgumentParser(description="Validate a version without changing any artifacts")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--version", required=True)
    parser.add_argument("--require-gold", action="store_true")
    parser.add_argument("--used-ids", type=Path, help="JSON array of IDs already used for training/tuning")
    args = parser.parse_args()
    try:
        used = json.loads(args.used_ids.read_text(encoding="utf-8")) if args.used_ids else []
        if not isinstance(used, list) or any(not isinstance(value, str) for value in used):
            raise ValueError("--used-ids must contain a JSON array of strings")
        result = verify_prepared(args.data_root, args.version, args.require_gold, used)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"validate-data: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
