"""Fail-closed adapters for the locked Facebook folds and human legacy rows."""
from src.dataset.common import ROOT, load, read_jsonl, sha, verify
from src.dataset.parent_thread_audit import audit as run_parent_audit
from src.transformer import LABELS


def load_phase_h_data(config_path="configs/phase_h/data.json"):
    cfg = load(ROOT / config_path)
    unified_dir = ROOT / cfg["unified_root"]
    unified_manifest = verify(unified_dir)
    if sha(unified_dir / "manifest.json") != cfg["unified_manifest_sha256"]:
        raise ValueError("Pinned unified dataset changed")
    audit_dir = ROOT / cfg["direct_audit_root"]
    audit_manifest = verify(audit_dir)
    if sha(audit_dir / "manifest.json") != cfg["direct_audit_manifest_sha256"]:
        raise ValueError("Pinned direct leakage audit changed")
    if audit_manifest.get("status") != "PASS":
        raise ValueError("G.3.1 direct leakage audit is not PASS")
    parent = run_parent_audit(cfg["unified_root"], cfg["master_root"])
    if parent["status"] != "PASS" or parent["facebook_rows"] != cfg["facebook_rows"]:
        raise ValueError("G.3.2 parent/thread audit blocks Phase H")

    rows = read_jsonl(unified_dir / "unified.jsonl")
    if len(rows) != cfg["total_rows"]:
        raise ValueError("Unified row count changed")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate unified ID")
    labels = set(LABELS)
    fb = {r["original_id"]: r for r in rows if r["source_dataset"] == "facebook_development"}
    legacy = [r for r in rows if r["source_dataset"] == "legacy_human"]
    if len(fb) != cfg["facebook_rows"] or len(legacy) != cfg["legacy_rows"]:
        raise ValueError("Expected 346 Facebook and 186 human legacy rows")
    if any(r.get("label") not in labels for r in rows):
        raise ValueError("REVIEW/EXCLUDE/unknown labels cannot enter Phase H")
    if any(r.get("annotation_source") != "human_single_annotator" for r in rows):
        raise ValueError("Non-human labels are prohibited")
    if any(not r.get("text_view") for r in rows):
        raise ValueError("Empty model input")
    if any(r.get("platform") != "facebook" or not r.get("post_id") for r in fb.values()):
        raise ValueError("Facebook development provenance is incomplete")
    if any(r.get("platform") != "unknown" or r.get("post_id") for r in legacy):
        raise ValueError("Legacy source provenance changed; do not invent post IDs")

    # Frozen plans are protected by the unified manifest. Never construct replacement folds.
    frozen = load(unified_dir / "frozen_plan.json")
    folds = frozen["folds"]
    seen = []
    for fold in folds:
        validate_frozen_fold(fb, fold)
        train, valid = fold["train_ids"], fold["validation_ids"]
        seen.extend(valid)
    if len(seen) != cfg["facebook_rows"] or len(set(seen)) != cfg["facebook_rows"] or set(seen) != set(fb):
        raise ValueError("Frozen validation folds must cover every Facebook ID exactly once")

    # Recheck identities, exact text, direct near text and parent/thread edges per fold.
    from src.dataset.parent_thread_audit import _selected_source_record, verified_parent, _fold_thread_overlaps
    master_dir = ROOT / cfg["master_root"]
    verify(master_dir)
    if sha(master_dir / "manifest.json") != cfg["master_manifest_sha256"]:
        raise ValueError("Pinned master source manifest changed")
    master_rows = {r["id"]: r for r in read_jsonl(master_dir / "master.jsonl")}
    verified = {}
    for oid, row in fb.items():
        parent_id, state, record_type = verified_parent(row, master_rows.get(row["master_id"]))
        if state != "VERIFIED":
            raise ValueError("Parent metadata not verifiable: " + state)
        verified[oid] = dict(id=oid, source_platform="facebook", post_id=row["post_id"],
            comment_id=row["comment_id"], verified_parent_comment_id=parent_id,
            verified_record_type=record_type)
    for fold in folds:
        train_ids, valid_ids = fold["train_ids"], fold["validation_ids"]
        train_rows = [verified[i] for i in train_ids]
        valid_rows = [verified[i] for i in valid_ids]
        if any(_fold_thread_overlaps(train_rows, valid_rows).values()):
            raise ValueError("Parent/thread identity overlaps a frozen boundary")
        exact = {r["text_view"] for r in (fb[i] for i in train_ids)}
        if exact & {r["text_view"] for r in (fb[i] for i in valid_ids)}:
            raise ValueError("Exact text overlaps frozen boundary")

    return cfg, rows, fb, legacy, folds


def validate_frozen_fold(fb, fold):
    train, valid = fold["train_ids"], fold["validation_ids"]
    if (len(train) != len(set(train)) or len(valid) != len(set(valid)) or set(train) & set(valid)
            or any(i not in fb for i in train + valid) or set(train) | set(valid) != set(fb)):
        raise ValueError("Fold IDs must be unique Facebook rows with disjoint train/validation")
    if ({fb[i].get("frozen_group_id") for i in train}
            & {fb[i].get("frozen_group_id") for i in valid}):
        raise ValueError("Frozen post/duplicate group crosses train/validation")
    if any(fb[i].get("label") not in LABELS for i in train + valid):
        raise ValueError("Only human POS/NEG/NEU labels are allowed")
    return True


def fold_training_rows(fb, legacy, fold, augmented):
    train = [fb[i] for i in fold["train_ids"]]
    valid = [fb[i] for i in fold["validation_ids"]]
    if augmented:
        train += list(legacy)
    if any(r["source_dataset"] != "facebook_development" for r in valid):
        raise ValueError("Validation must be Facebook only")
    if any(r["source_dataset"] not in {"facebook_development", "legacy_human"} for r in train):
        raise ValueError("Unexpected training source")
    if any(r.get("label") not in LABELS for r in train + valid):
        raise ValueError("Only POS/NEG/NEU are valid training/evaluation labels")
    return train, valid
