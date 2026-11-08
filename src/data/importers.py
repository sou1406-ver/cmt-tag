"""CSV/JSON import with explicit column maps and append-only provenance."""

import csv
import hashlib
import io
import json
from collections import Counter

from .schema import METADATA, SCHEMA_VERSION, append_decision, validate_record


def digest(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_text(text):
    import unicodedata
    return " ".join(unicodedata.normalize("NFC", text).split())


def read_rows(path, spec):
    payload = path.read_bytes()
    text = payload.decode("utf-8-sig")
    fmt = spec.get("format", path.suffix.lstrip(".").lower())
    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Missing/duplicate CSV headers: {path}")
        if spec["columns"]["text_raw"] not in reader.fieldnames:
            raise ValueError(f"Missing text column in {path}")
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError(f"Malformed CSV row: {path}")
    elif fmt == "json":
        rows = json.loads(text)
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("JSON input must be an array of objects")
    else:
        raise ValueError("Only CSV and JSON inputs are supported")
    return rows, payload


def mapped(row, spec, key):
    column = spec.get("columns", {}).get(key)
    return row.get(column) if column is not None else None


def text_value(row, spec):
    key = spec["columns"]["text_raw"]
    if key not in row:
        raise ValueError(f"Missing text column: {key}")
    value = row[key]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("text_raw must be string/null; do not silently coerce values")
    return value


def metadata_value(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Metadata must be string, integer, or null")
    return str(value)


def import_comments(rows, spec, input_hash):
    source = spec["source_dataset"]
    namespace = spec.get("post_namespace", source)
    occurrences = Counter()
    records = []
    for position, row in enumerate(rows, 1):
        raw = text_value(row, spec)
        text = normalize_text(raw)
        metadata = {key: metadata_value(mapped(row, spec, key)) for key in METADATA}
        for key in ("license", "privacy", "movie_id"):
            if metadata[key] is None:
                metadata[key] = metadata_value(spec.get(key))
        identity = [source, "comment_id", metadata["comment_id"]] if metadata["comment_id"] else [source, "raw_hash", digest(raw)]
        identity_key = canonical_json(identity)
        occurrences[identity_key] += 1
        record = {
            "schema_version": SCHEMA_VERSION,
            "id": "c_" + digest(canonical_json([identity, occurrences[identity_key]])),
            "source_dataset": source, "post_namespace": namespace,
            "text_raw": raw, "text": text,
            "text_raw_hash": digest(raw), "text_hash": digest(text.casefold()),
            **metadata,
            "provenance": [{"input_sha256": input_hash, "input_path": spec["path"],
                            "row_number": position, "role": "comments"}],
            "annotations": {"human": [], "machine": []},
        }
        import_row_annotations(record, row, spec, input_hash, position)
        records.append(validate_record(record))
    return records


def import_row_annotations(record, row, spec, input_hash, position):
    for origin in ("human", "machine"):
        cfg = spec.get("annotations", {}).get(origin)
        if cfg is None:
            continue
        raw_label = row.get(cfg["column"])
        if raw_label is None or raw_label == "":
            continue
        if raw_label not in cfg["values"]:
            raise ValueError(f"Unknown {origin} annotation: {raw_label!r}")
        target = cfg["values"][raw_label]
        status = target if target in {"REVIEW", "EXCLUDE"} else "LABELED"
        decision = {
            "label_source": origin, "label": target if status == "LABELED" else None,
            "status": status, "original_value": raw_label,
            "confirmed": False, "is_pseudo": False, "needs_review": True,
            "review_reason": "REV_OTHER" if status == "REVIEW" else None,
            "guideline_version": None, "decided_at": None,
            "provenance": {"input_sha256": input_hash, "input_path": spec["path"],
                           "row_number": position, "column": cfg["column"]},
        }
        if origin == "machine":
            score = row.get(cfg.get("score_column"))
            decision.update({
                "model_id": cfg["model_id"], "model_version": cfg["model_version"],
                "score": float(score) if score not in (None, "") else None,
                "score_kind": cfg.get("score_kind", "uncalibrated"), "audit_id": None,
            })
        else:
            # A populated legacy human column alone is not proof of confirmation.
            decision.update({"annotator_id": None, "evidence_mode": None})
        append_decision(record, decision)


def attach_annotations(records, rows, spec, input_hash):
    """Join sidecars on exact raw text or explicit ID, never cleaned-text position."""
    join = spec.get("join_on", "text_raw_hash")
    if join not in {"text_raw_hash", "comment_id"}:
        raise ValueError("Annotation join_on must be text_raw_hash or comment_id")
    index = {}
    for record in records:
        if record["source_dataset"] == spec["source_dataset"] and record[join] is not None:
            index.setdefault(record[join], []).append(record)
    unmatched = []
    matched = 0
    for position, row in enumerate(rows, 1):
        key = digest(text_value(row, spec)) if join == "text_raw_hash" else metadata_value(mapped(row, spec, "comment_id"))
        targets = index.get(key, [])
        if not targets:
            unmatched.append(position)
            continue
        for record in targets:
            import_row_annotations(record, row, spec, input_hash, position)
            validate_record(record)
        matched += 1
    return {"matched_rows": matched, "unmatched_rows": unmatched}
