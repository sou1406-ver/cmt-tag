"""Separate sentiment, workflow state, and the origin of every decision."""

from copy import deepcopy
from datetime import datetime
import hashlib
import math
import unicodedata

SCHEMA_VERSION = "1.0"
LABELS = frozenset({"POS", "NEG", "NEU"})
STATES = frozenset({"LABELED", "REVIEW", "EXCLUDE"})
REVIEW_REASONS = frozenset({
    "REV_MIXED", "REV_SARCASM", "REV_TARGET", "REV_CONTEXT", "REV_OTHER",
})
METADATA = (
    "comment_id", "post_id", "post_url", "parent_comment_id", "collected_at",
    "movie_id", "license", "privacy",
)


def validate_decision(decision):
    source = decision.get("label_source")
    if source not in {"human", "machine"}:
        raise ValueError("label_source must be human or machine")
    label, status = decision.get("label"), decision.get("status")
    if status not in STATES:
        raise ValueError("Unknown annotation status")
    if status == "LABELED" and label not in LABELS:
        raise ValueError("Only POS/NEG/NEU are sentiment labels")
    if status != "LABELED" and label is not None:
        raise ValueError("REVIEW/EXCLUDE must have label=null")
    reason = decision.get("review_reason")
    if reason is not None and reason not in REVIEW_REASONS:
        raise ValueError("Unknown review_reason")
    if status == "REVIEW" and reason is None:
        raise ValueError("REVIEW needs a review_reason")
    if type(decision.get("confirmed")) is not bool:
        raise ValueError("confirmed must be a boolean")
    if type(decision.get("is_pseudo")) is not bool:
        raise ValueError("is_pseudo must be a boolean")
    if type(decision.get("needs_review")) is not bool:
        raise ValueError("needs_review must be a boolean")
    if source == "machine":
        if decision["confirmed"]:
            raise ValueError("Machine decisions cannot be human-confirmed")
        if not decision.get("model_id") or not decision.get("model_version"):
            raise ValueError("Machine decision needs model_id and model_version")
        score = decision.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))
                                  or not math.isfinite(score)):
            raise ValueError("Machine score must be finite or null")
        if decision["is_pseudo"]:
            if status != "LABELED" or score is None or not decision.get("audit_id"):
                raise ValueError("Pseudo-label needs sentiment, score and empirical audit_id")
    elif decision["is_pseudo"]:
        raise ValueError("Human decisions cannot be pseudo-labels")
    elif decision["confirmed"]:
        for key in ("annotator_id", "decided_at", "guideline_version", "evidence_mode"):
            if not decision.get(key):
                raise ValueError(f"Confirmed human label needs {key}")
        if decision["evidence_mode"] not in {"blind", "assisted"}:
            raise ValueError("evidence_mode must be blind or assisted")
        try:
            timestamp = datetime.fromisoformat(decision["decided_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError("decided_at must be an ISO timestamp") from exc
        if timestamp.tzinfo is None:
            raise ValueError("decided_at must include timezone")
    return decision


def validate_record(record):
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported record schema_version")
    for key in ("id", "source_dataset", "post_namespace", "text_raw_hash", "text_hash"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"Missing record field: {key}")
    if not isinstance(record.get("text_raw"), str) or not isinstance(record.get("text"), str):
        raise ValueError("Texts must be strings")
    normalized = " ".join(unicodedata.normalize("NFC", record["text_raw"]).split())
    if record["text"] != normalized:
        raise ValueError("Processed text does not match conservative normalization of raw")
    for key, value in (("text_raw_hash", record["text_raw"]), ("text_hash", record["text"].casefold())):
        if record[key] != hashlib.sha256(value.encode("utf-8")).hexdigest():
            raise ValueError(f"Text integrity mismatch: {key}")
    for key in METADATA:
        if key not in record or (record[key] is not None and not isinstance(record[key], str)):
            raise ValueError(f"Metadata must be string/null: {key}")
    for source in ("human", "machine"):
        for decision in record["annotations"][source]:
            validate_decision(decision)
            if decision["label_source"] != source:
                raise ValueError("Annotation stored under the wrong origin")
    return record


def append_decision(record, decision):
    """Append-only history: machine updates never replace a human decision."""
    validate_decision(decision)
    record["annotations"][decision["label_source"]].append(deepcopy(decision))


def effective_human(record):
    """Latest human event wins; an unconfirmed revision withdraws older gold."""
    events = record["annotations"]["human"]
    if not events:
        return None
    latest = validate_decision(events[-1])
    return latest if latest["confirmed"] else None


def gold_label(record, evaluation=False):
    if record.get("quality", {}).get("label_conflict", False):
        return None
    decision = effective_human(record)
    if decision is None or decision["status"] != "LABELED":
        return None
    if evaluation and decision["evidence_mode"] != "blind":
        return None
    return decision["label"]
