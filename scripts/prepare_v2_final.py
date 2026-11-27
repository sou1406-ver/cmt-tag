"""Merge three-way AI consensus and locked E/C/U labels into a train snapshot."""

import argparse
from collections import Counter
from pathlib import Path

from scripts.chuan_hoa_binh_luan_v2 import normalize_v2, technical_text
from src.annotation.pilot import fingerprints, near_any, reference_index
from src.dataset.common import ROOT, csv_rows, load, normal, read_jsonl, seal, sha, staged, write_jsonl
from src.models.core import LABELS


VOTES = ROOT / "outputs/01_T2_va_cho_gan"
SOURCES = ROOT / "outputs/02_Du_lieu_va_nhan"
OLDER = SOURCES / "Nguon_V2/Nhan_AI_chunk_01_50"
TECHNICAL = SOURCES / "05_Chuan_hoa_ky_thuat_V2"
FINAL = ROOT / "outputs/06_Du_lieu_cuoi_V2"
SNAPSHOT_KIND = "V2_FINAL_CONSENSUS_TRAIN"
ALL_LABELS = {*LABELS, "REVIEW", "EXCLUDE"}


def read_votes(paths, inputs):
    if not paths:
        raise ValueError("Missing vote files")
    result = {}
    for path in sorted(paths):
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
        for row in csv_rows(path.read_bytes())[0]:
            cid, label = row["comment_id"], row["label"]
            if not cid.isascii() or not cid.isdigit() or cid in result or label not in ALL_LABELS:
                raise ValueError(f"Invalid vote in {path.name}")
            result[cid] = label
    return result


def consensus(passes, size, *, require_full=True):
    shared = set.intersection(*(set(votes) for votes in passes))
    if len(shared) != size or (require_full and any(votes.keys() != shared for votes in passes)):
        raise ValueError("Vote coverage differs from the expected roster")
    return shared, {cid: passes[0][cid] for cid in shared
                    if all(votes[cid] == passes[0][cid] for votes in passes)}


def combine_rounds(first, second, prefix):
    return {cid: (label, f"{prefix}_R{round_no}_3OF3")
            for round_no, votes in enumerate((first, second), 1)
            for cid, label in votes.items()
            if label in LABELS and (round_no == 1 or cid not in first)}


def prepare(output):
    inputs = {}
    older_voters = ("chatgpt", "claude", "gemini")
    old_ids, old_first = consensus([
        read_votes(list((OLDER / "ai_round_1").glob(f"ai_{name}_U_chunk_[0-9][0-9].csv")), inputs)
        for name in older_voters
    ], 5000)
    old_retry_ids, old_second = consensus([
        read_votes(list((OLDER / "round_2/ai_round_2").glob(f"ai_{name}_U_recheck_*.csv")), inputs)
        for name in older_voters
    ], 1223, require_full=False)
    new_rounds = [consensus([
        read_votes(list((VOTES / folder).glob(f"{name}_[0-9][0-9].csv")), inputs)
        for name in ("gpt", "claude", "gemini")
    ], size) for folder, size in (("Nhan_AI_dang_nhan", 7758), ("Nhan_AI_turn_2", 2626))]
    (new_ids, new_first), (new_retry_ids, new_second) = new_rounds
    if old_ids & new_ids or not old_retry_ids <= old_ids or not new_retry_ids <= new_ids:
        raise ValueError("AI rosters overlap or contain an unexpected retry ID")
    older = combine_rounds(old_first, old_second, "OLD_AI")
    newer = combine_rounds(new_first, new_second, "AI_01_79")

    manifest = TECHNICAL / "manifest.json"
    source = TECHNICAL / "V2_chuan_hoa_va_giu_nhan.local.jsonl"
    inputs[manifest.relative_to(ROOT).as_posix()] = sha(manifest)
    inputs[source.relative_to(ROOT).as_posix()] = sha(source)
    if inputs[source.relative_to(ROOT).as_posix()] != load(manifest)["output_sha256"][source.name]:
        raise ValueError("Technical snapshot checksum mismatch")
    rows = read_jsonl(source)
    indexed = {row["comment_id"]: row for row in rows}
    if len(indexed) != len(rows) or not (old_ids | new_ids) <= indexed.keys():
        raise ValueError("Technical snapshot has duplicates or does not cover the AI rosters")

    locked = {cid: (row["label"], row["label_source"]) for cid, row in indexed.items()
              if row["split_role"] == "TRAIN_CANDIDATE" and row["label_source"] in {"E", "C", "U"}
              and row["label"] in LABELS}
    ai = {**older, **newer}
    if ai.keys() & locked.keys():
        raise ValueError("An AI roster overlaps an already locked E/C/U label")

    protected = [row for row in rows if row["split_role"] in {"T2_SCORE", "T2_REVIEW_OR_EXCLUDE"}]
    if len(protected) != 652:
        raise ValueError("T2 protection roster differs from the frozen set")
    protected_ids = {row["comment_id"] for row in protected}
    protected_posts = {row["post_id"] for row in protected}
    protected_views = [[fn(row["text_source"]) for row in protected] for fn in (technical_text, normalize_v2)]
    exact = [{normal(text) for text in views} for views in protected_views]
    near = [reference_index(fingerprints(text) for text in views) for views in protected_views]
    exclusions = Counter()
    train = []
    for cid, (label, origin) in sorted({**ai, **locked}.items()):
        row = indexed[cid]
        if not row["post_id"] or cid in protected_ids or row["post_id"] in protected_posts:
            exclusions["missing_post_or_shared_T2_identity"] += 1
            continue
        views = (technical_text(row["text_source"]), normalize_v2(row["text_source"]))
        if not views[1]:
            exclusions["empty_after_normalization"] += 1
        elif any(normal(text) in ref for text, ref in zip(views, exact, strict=True)):
            exclusions["exact_T2_text"] += 1
        elif any(near_any(text, ref) for text, ref in zip(views, near, strict=True)):
            exclusions["near_T2_text"] += 1
        else:
            train.append(dict(id=cid, post_id=row["post_id"], movie_id=row["movie_id"],
                              source=row["source_name"], origin=origin, label=label, text=views[1]))

    test_receipt = ROOT / "outputs/03_Dau_vao_chinh_thuc/manifest.json"
    test_metadata = load(test_receipt)
    inputs[test_receipt.relative_to(ROOT).as_posix()] = sha(test_receipt)
    script = Path(__file__).resolve()
    inputs[script.relative_to(ROOT).as_posix()] = sha(script)
    normalizer = ROOT / "scripts/chuan_hoa_binh_luan_v2.py"
    inputs[normalizer.relative_to(ROOT).as_posix()] = sha(normalizer)
    counts = Counter(row["label"] for row in train)
    if counts.keys() != set(LABELS) or len(train) + sum(exclusions.values()) != len(ai) + len(locked):
        raise ValueError("Train reconciliation failed")
    with staged(output) as folder:
        write_jsonl(folder / "train.local.jsonl", train)
        result = seal(folder, dict(kind=SNAPSHOT_KIND, input_view="normalize_v2", scored=False,
                                   ai_roster_size=len(old_ids | new_ids), strict_ai_consensus=len(ai),
                                   locked_ecu=len(locked), exclusions=dict(exclusions),
                                   train_size=len(train), train_labels=dict(counts),
                                   train_by_origin=dict(Counter(row["origin"] for row in train)),
                                   train_post_count=len({row["post_id"] for row in train}),
                                   test_size=test_metadata["test_size"], test_groups=test_metadata["test_groups"],
                                   test_manifest=test_receipt.relative_to(ROOT).as_posix(), inputs_sha256=inputs))
    print({key: result[key] for key in ("ai_roster_size", "strict_ai_consensus", "locked_ecu", "exclusions",
                                      "train_size", "train_labels", "train_by_origin", "train_post_count", "test_size")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FINAL)
    prepare(parser.parse_args().output)
