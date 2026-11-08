"""Conservative quality decisions: retain short comments, spelling, emoji and raw."""

import re
from collections import Counter, defaultdict

from .schema import effective_human


def assess_quality(records, config):
    ui = {value.casefold() for value in config.get("ui_strings", [])}
    spam = [re.compile(pattern, re.IGNORECASE) for pattern in config.get("spam_patterns", [])]
    for record in records:
        text = record["text"]
        reasons = []
        if not text:
            reasons.append("EMPTY")
        elif text.casefold() in ui:
            reasons.append("UI_STRING")
        if text and re.search(r"(?:…|\.{3})\s*(?:xem thêm|see more)\s*$", text, re.IGNORECASE):
            reasons.append("TRUNCATED_UI_SUFFIX")
        if text and any(pattern.search(text) for pattern in spam):
            reasons.append("SPAM_RULE")
        record["quality"] = {
            "status": "EXCLUDE" if reasons else "KEEP",
            "reasons": reasons, "duplicate_of": None, "label_conflict": False,
        }


def mark_exact_duplicates(records):
    """Retain every row and its provenance; only one representative is eligible."""
    buckets = defaultdict(list)
    for record in records:
        if record["quality"]["status"] == "KEEP":
            buckets[record["text_hash"]].append(record)
    for bucket in buckets.values():
        representative = min(bucket, key=lambda r: r["id"])
        human_decisions = [effective_human(r) for r in bucket]
        signatures = {(d["status"], d["label"]) for d in human_decisions if d is not None}
        conflict = len(signatures) > 1
        for record in bucket:
            record["quality"]["label_conflict"] = conflict
            if conflict:
                record["quality"]["reasons"].append("DUPLICATE_HUMAN_CONFLICT")
            if record is not representative:
                record["quality"]["duplicate_of"] = representative["id"]
                record["quality"]["reasons"].append("EXACT_DUPLICATE")


def near_duplicate_candidates(records, config):
    """Token-shingle Jaccard candidates, never automatic deletion or sentiment rules.

    Inverted postings enumerate pairs sharing a shingle. Every threshold match is
    kept for inspection and connected for conservative split isolation.
    """
    threshold = config.get("threshold", 0.9)
    minimum = config.get("min_chars", 40)
    width = config.get("shingle_size", 3)
    if not 0 < threshold <= 1 or minimum < 1 or width < 1:
        raise ValueError("Invalid near-duplicate configuration")
    representatives = sorted(
        (r for r in records if r["quality"]["status"] == "KEEP" and not r["quality"]["duplicate_of"]),
        key=lambda r: r["id"],
    )
    postings, sizes, candidates = defaultdict(list), {}, []
    for record in representatives:
        text = record["text"].casefold()
        if len(text) < minimum:
            continue
        tokens = re.findall(r"\w+|[^\w\s]", text)
        shingles = {tuple(tokens[i:i + width]) for i in range(len(tokens) - width + 1)}
        if not shingles:
            continue
        overlaps = Counter()
        for shingle in shingles:
            overlaps.update(postings[shingle])
        current = record["id"]
        for previous, intersection in sorted(overlaps.items()):
            union = len(shingles) + sizes[previous] - intersection
            score = intersection / union
            if score >= threshold:
                candidates.append({
                    "left": previous, "right": current, "score": round(score, 8),
                    "method": f"token_{width}gram_jaccard",
                    "decision": "pending_review", "policy": "keep_and_group",
                })
        sizes[current] = len(shingles)
        for shingle in shingles:
            postings[shingle].append(current)
    return candidates
