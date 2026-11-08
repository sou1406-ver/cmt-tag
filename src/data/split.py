"""Connected-component splitting across posts, exact/near duplicates and IDs."""

import math
import random
from collections import Counter, defaultdict

from .importers import canonical_json, digest
from .schema import gold_label, validate_record

SPLITS = ("train", "dev", "test")


class UnionFind:
    def __init__(self, ids):
        self.parent = {value: value for value in ids}

    def find(self, value):
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            previous = value
            value = self.parent[value]
            self.parent[previous] = root
        return root

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def build_groups(records, near_candidates):
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate internal IDs: combine each source once")
    uf = UnionFind(ids)
    keys = {}
    for record in records:
        values = []
        if record["text"]:
            values.append(("text", record["text_hash"]))
        # The explicit namespace lets multiple input files share a platform.
        for key in ("post_id", "post_url", "comment_id"):
            if record.get(key):
                values.append((key, record["post_namespace"], record[key]))
        for value in values:
            if value in keys:
                uf.union(record["id"], keys[value])
            else:
                keys[value] = record["id"]
    for pair in near_candidates:
        uf.union(pair["left"], pair["right"])
    components = defaultdict(list)
    for value in ids:
        components[uf.find(value)].append(value)
    groups = {}
    for members in components.values():
        group_id = "g_" + digest(canonical_json(sorted(members)))
        for value in members:
            groups[value] = group_id
    return groups


def make_manifest(records, candidates, config, version):
    ratios = config["ratios"]
    if set(ratios) != set(SPLITS) or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
        for v in ratios.values()
    ) or not math.isclose(sum(ratios.values()), 1.0):
        raise ValueError("Split ratios must be finite, nonnegative, sum to 1 and name train/dev/test")
    groups = build_groups(records, candidates)
    representatives = defaultdict(list)
    for record in records:
        if record["quality"]["status"] == "KEEP" and not record["quality"]["duplicate_of"]:
            representatives[groups[record["id"]]].append(record)
    total = sum(map(len, representatives.values()))
    rng = random.Random(config["seed"])
    ordered = list(sorted(representatives))
    rng.shuffle(ordered)
    ordered.sort(key=lambda g: -len(representatives[g]))
    counts, assignments = Counter(), {}
    # No labels (human or machine) are used to allocate the initial pools.
    # Annotators must be able to label reserved dev/test without predictions.
    for group in ordered:
        size = len(representatives[group])
        choices = [split for split in SPLITS if ratios[split] > 0]
        chosen = min(choices, key=lambda split: (
            sum((counts[s] + (size if s == split else 0) - total * ratios[s]) ** 2 for s in SPLITS),
            SPLITS.index(split),
        ))
        assignments[group] = chosen
        counts[chosen] += size
    entries = []
    for record in sorted(records, key=lambda r: r["id"]):
        usable = record["quality"]["status"] == "KEEP" and not record["quality"]["duplicate_of"]
        entries.append({
            "id": record["id"], "group_id": groups[record["id"]],
            "split": assignments.get(groups[record["id"]]) if record["quality"]["status"] == "KEEP" else None,
            "eligible_for_annotation": bool(usable),
        })
    manifest = {
        "schema_version": "1.0", "data_version": version,
        "seed": config["seed"], "ratios": ratios,
        "purpose": "annotation_pool_reservation", "locked_gold": False,
        "label_balancing": "none_before_blind_annotation",
        "entries": entries,
    }
    validate_manifest(records, candidates, manifest)
    return manifest


def validate_manifest(records, candidates, manifest, require_gold=False, used_ids=()):
    lookup = {r["id"]: validate_record(r) for r in records}
    entries = manifest["entries"]
    if len(lookup) != len(records) or len(entries) != len(lookup) or {e["id"] for e in entries} != set(lookup):
        raise ValueError("Manifest must cover each record exactly once")
    expected_groups = build_groups(records, candidates)
    assignment = {}
    connected_splits = defaultdict(set)
    used = set(used_ids)
    if require_gold and not used.issubset(lookup):
        raise ValueError("Usage history references unknown record IDs")
    for entry in entries:
        record = lookup[entry["id"]]
        split = entry["split"]
        if split is not None and split not in SPLITS:
            raise ValueError("Unknown split")
        if entry["group_id"] != expected_groups[record["id"]]:
            raise ValueError("Manifest group mismatch")
        eligible = record["quality"]["status"] == "KEEP" and not record["quality"]["duplicate_of"]
        if type(entry["eligible_for_annotation"]) is not bool or entry["eligible_for_annotation"] != bool(eligible):
            raise ValueError("Manifest eligibility mismatch")
        if record["quality"]["status"] != "KEEP" and split is not None:
            raise ValueError("Excluded quality record cannot have a split")
        if split is not None:
            connected_splits[expected_groups[record["id"]]].add(split)
        elif eligible:
            raise ValueError("Eligible record missing split")
        assignment[record["id"]] = split
        if require_gold and eligible:
            if gold_label(record, evaluation=split in {"dev", "test"}) is None:
                raise ValueError("Gold splits require confirmed human labels; dev/test require blind labels")
    if any(len(splits) > 1 for splits in connected_splits.values()):
        raise ValueError("Leakage across connected posts or duplicate groups")
    if require_gold:
        reserved_groups = {
            expected_groups[rid] for rid, split in assignment.items() if split in {"dev", "test"}
        }
        if any(expected_groups.get(rid) in reserved_groups for rid in used):
            raise ValueError("Gold holdout group contains a sample already used for tuning/training")
        if not manifest.get("locked_gold"):
            raise ValueError("Gold manifest has not been locked")
    return True
