"""Read-only verification of a prepared version and its provenance."""

import json
from pathlib import Path

from .importers import digest
from .split import validate_manifest


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_prepared(data_root, version, require_gold=False, used_ids=()):
    root = Path(data_root).resolve()
    if not version or any(c not in "0123456789abcdef" for c in version):
        raise ValueError("Data version must be a hexadecimal identifier")
    processed = root / "processed" / version
    report_path = processed / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run = json.loads((processed / "run.json").read_text(encoding="utf-8"))
    if report["data_version"] != version or run["data_version"] != version or run["status"] != "complete":
        raise ValueError("Incomplete or mismatched data version")
    if run["report_sha256"] != digest(report_path.read_bytes()):
        raise ValueError("Report checksum mismatch")
    for relative, expected in report["artifact_sha256"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError(f"Artifact checksum mismatch: {relative}")
    for source in report["sources"]:
        snapshot = Path(source["snapshot"]).resolve()
        if not snapshot.is_relative_to(root / "raw") or digest(snapshot.read_bytes()) != source["sha256"]:
            raise ValueError("Raw snapshot checksum mismatch")
    records = read_jsonl(processed / "records.jsonl")
    pairs = read_jsonl(processed / "near_duplicates.jsonl")
    manifest = json.loads((root / "splits" / version / "manifest.json").read_text(encoding="utf-8"))
    if manifest["data_version"] != version:
        raise ValueError("Manifest data version mismatch")
    validate_manifest(records, pairs, manifest, require_gold=require_gold, used_ids=used_ids)
    counts = report["counts"]
    if counts["raw_comment_rows"] != len(records) or len(records) != sum(counts[key] for key in (
        "quality_excluded", "exact_duplicate_extra_rows", "retained_representatives",
    )):
        raise ValueError("Row reconciliation mismatch")
    return {"status": "valid", "data_version": version, "records": len(records),
            "locked_gold": manifest["locked_gold"], "require_gold": require_gold}
