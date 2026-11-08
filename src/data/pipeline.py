"""Versioned preparation, immutable input snapshots, reproducible audit artifacts."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

from .importers import attach_annotations, canonical_json, digest, import_comments, read_rows
from .quality import assess_quality, mark_exact_duplicates, near_duplicate_candidates
from .schema import gold_label
from .split import make_manifest

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(canonical_json(value) + "\n")


def fingerprint_code(root=ROOT):
    paths = sorted(list((root / "src").rglob("*.py")) + list((root / "scripts").glob("*.py")))
    return {path.relative_to(root).as_posix(): digest(path.read_bytes()) for path in paths}


def prepare_data(config_path, output_root=None, workspace=ROOT):
    config_path = Path(config_path)
    workspace = Path(workspace)
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    output_root = Path(output_root) if output_root else workspace / "data"
    if not config.get("inputs"):
        raise ValueError("Configuration needs at least one input")
    if config.get("schema_version") != "1.0":
        raise ValueError("Unsupported config schema_version")
    loaded, sources, records, sidecars = [], [], [], []
    source_ids = set()
    for spec in config["inputs"]:
        if not spec.get("source_dataset") or not spec.get("columns", {}).get("text_raw"):
            raise ValueError("Every input needs source_dataset and an explicit text_raw column map")
        role = spec.get("role", "comments")
        if role not in {"comments", "annotations"}:
            raise ValueError("Input role must be comments or annotations")
        path = Path(spec["path"])
        if not path.is_absolute():
            path = workspace / path
        rows, payload = read_rows(path, spec)
        sha = digest(payload)
        if any(item["sha256"] == sha and item["role"] == role for item in sources):
            raise ValueError("Same input content imported twice; configure one source only")
        source = {
            "path": spec["path"], "source_dataset": spec["source_dataset"],
            "role": role, "sha256": sha, "bytes": len(payload), "rows": len(rows),
            "columns": sorted(rows[0]) if rows else [],
        }
        sources.append(source)
        loaded.append((path, payload, source))
        if role == "comments":
            if spec["source_dataset"] in source_ids:
                raise ValueError("Use a unique source_dataset per comment input and shared post_namespace where appropriate")
            source_ids.add(spec["source_dataset"])
            records.extend(import_comments(rows, spec, sha))
        else:
            sidecars.append((rows, spec, sha, source))
    if not records:
        raise ValueError("No comment rows to prepare")
    for rows, spec, sha, source in sidecars:
        if spec["source_dataset"] not in source_ids:
            raise ValueError("Annotation sidecar references an unknown source_dataset")
        source["annotation_join"] = attach_annotations(records, rows, spec, sha)
    assess_quality(records, config.get("quality", {}))
    mark_exact_duplicates(records)
    candidates = near_duplicate_candidates(records, config.get("near_duplicate", {}))
    code_hashes = fingerprint_code()
    runtime = {"python": platform.python_version(), "implementation": platform.python_implementation(),
               "platform": sys.platform}
    version_basis = {"config": config, "inputs": [s["sha256"] for s in sources],
                     "code_sha256": code_hashes, "runtime": runtime}
    version = digest(canonical_json(version_basis))[:20]
    processed = output_root / "processed" / version
    split_dir = output_root / "splits" / version
    if processed.exists() or split_dir.exists():
        raise FileExistsError(f"Version {version} already exists; refusing to overwrite artifacts")
    manifest = make_manifest(records, candidates, config["split"], version)
    entries = {entry["id"]: entry for entry in manifest["entries"]}
    warnings = []
    for source in sources:
        unmatched = source.get("annotation_join", {}).get("unmatched_rows", [])
        if unmatched:
            warnings.append(f"UNMATCHED_ANNOTATIONS: {len(unmatched)} rows in {source['path']}; retained in raw snapshot, no inferred transfer")
    if any(r["post_id"] is None and r["post_url"] is None for r in records):
        warnings.append("MISSING_POST_METADATA: text/duplicate isolation only for rows with unknown posts; post independence cannot be verified")
    if any(r["license"] is None or r["privacy"] is None for r in records):
        warnings.append("UNKNOWN_LICENSE_OR_PRIVACY: review conditions before sharing or external use")
    if not any(gold_label(r) for r in records):
        warnings.append("NO_CONFIRMED_GOLD: annotation pools only; training/evaluation blocked")
    if any(r["annotations"]["machine"] for r in records):
        warnings.append("UNVERIFIED_MACHINE_LABELS: do not show suggestions to blind dev/test annotators; legacy scores are not probabilities")
    split_counts = Counter(e["split"] for e in entries.values() if e["eligible_for_annotation"])
    for split, ratio in config["split"]["ratios"].items():
        if ratio > 0 and not split_counts[split]:
            warnings.append(f"EMPTY_SPLIT_{split.upper()}: cannot break groups to satisfy requested ratios")
    quality_excluded = [r for r in records if r["quality"]["status"] == "EXCLUDE"]
    duplicates = [r for r in records if r["quality"]["duplicate_of"]]
    retained = [r for r in records if entries[r["id"]]["eligible_for_annotation"]]
    machine_counts = Counter()
    for record in retained:
        if record["annotations"]["machine"]:
            decision = record["annotations"]["machine"][-1]
            machine_counts[decision["label"] or decision["status"]] += 1
    distribution = {
        "machine_suggestions_unverified": dict(sorted(machine_counts.items())),
        "human_confirmed_gold": dict(sorted(Counter(gold_label(r) for r in retained if gold_label(r)).items())),
        "no_machine_suggestion": sum(not r["annotations"]["machine"] for r in retained),
        "review_machine_is_not_sentiment": True,
    }
    metadata_missing = {key: sum(r[key] is None for r in records) for key in (
        "comment_id", "post_id", "post_url", "parent_comment_id", "collected_at", "movie_id", "license", "privacy",
    )}
    # All transformations finish before creating output files.
    for path, payload, source in loaded:
        snapshot = output_root / "raw" / source["sha256"] / path.name
        if snapshot.exists():
            if snapshot.read_bytes() != payload:
                raise ValueError("Raw snapshot integrity failure")
        else:
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            with snapshot.open("xb") as stream:
                stream.write(payload)
        source["snapshot"] = str(snapshot.resolve())
    ordered = sorted(records, key=lambda r: r["id"])
    write_jsonl(processed / "records.jsonl", ordered)
    write_jsonl(processed / "near_duplicates.jsonl", candidates)
    write_jsonl(processed / "quality_decisions.jsonl", [
        {"id": r["id"], **r["quality"]} for r in ordered if r["quality"]["reasons"]
    ])
    write_json(processed / "config.json", config)
    write_json(split_dir / "manifest.json", manifest)
    # Exports contain no machine suggestion, score, or human decision.
    for split in ("train", "dev", "test"):
        write_jsonl(split_dir / f"{split}_blind.jsonl", [
            {"id": r["id"], "text_raw": r["text_raw"], "post_id": r["post_id"],
             "post_url": r["post_url"], "source_dataset": r["source_dataset"]}
            for r in ordered if entries[r["id"]]["eligible_for_annotation"] and entries[r["id"]]["split"] == split
        ])
    artifact_paths = sorted(list(processed.glob("*")) + list(split_dir.glob("*")))
    artifact_hashes = {str(path.relative_to(output_root)): digest(path.read_bytes()) for path in artifact_paths}
    report = {
        "phase": "B", "data_version": version, "seed": config["split"]["seed"],
        "sources": sources, "config_sha256": digest(canonical_json(config)),
        "runtime": runtime,
        "code_sha256": code_hashes, "artifact_sha256": artifact_hashes,
        "git_commit": None, "git_note": "No commit claimed; code checksums identify implementation",
        "counts": {
            "raw_comment_rows": len(records), "quality_excluded": len(quality_excluded),
            "exact_duplicate_extra_rows": len(duplicates), "retained_representatives": len(retained),
            "near_duplicate_pairs_pending_review": len(candidates),
            "duplicate_human_conflict_rows": sum(r["quality"]["label_conflict"] for r in records),
            "quality_reasons": dict(Counter(reason for r in quality_excluded for reason in r["quality"]["reasons"])),
            "split_representatives": {s: split_counts[s] for s in ("train", "dev", "test")},
            "connected_groups": len({e["group_id"] for e in entries.values() if e["split"] is not None}),
        },
        "metadata_missing": metadata_missing, "distribution_after_filter": distribution,
        "warnings": warnings,
        "split_status": "annotation_pool_reservation; not locked gold; no model trained or evaluated",
        "reconciliation": "raw_comment_rows = quality_excluded + exact_duplicate_extra_rows + retained_representatives",
    }
    write_json(processed / "report.json", report)
    write_json(processed / "run.json", {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "data_version": version, "report_sha256": digest((processed / "report.json").read_bytes()),
        "status": "complete",
    })
    return report, processed, split_dir
