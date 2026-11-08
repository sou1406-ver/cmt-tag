import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.data.importers import (
    attach_annotations, digest, import_comments, normalize_text, read_rows,
)
from src.data.pipeline import ROOT, prepare_data
from src.data.quality import assess_quality, mark_exact_duplicates, near_duplicate_candidates
from src.data.schema import append_decision, gold_label, validate_decision, validate_record
from src.data.split import build_groups, make_manifest, validate_manifest
from src.data.validation import verify_prepared

SPLIT = {"seed": 42, "ratios": {"train": 0.6, "dev": 0.2, "test": 0.2}}


def records_from(rows, source="synthetic"):
    spec = {"path": "synthetic.json", "source_dataset": source,
            "post_namespace": "synthetic_platform",
            "columns": {"text_raw": "text", "post_id": "post", "comment_id": "cid"}}
    records = import_comments(rows, spec, "fixture_sha")
    assess_quality(records, {"ui_strings": ["Thích"]})
    mark_exact_duplicates(records)
    return records


def human(label="POS", **overrides):
    decision = {"label_source": "human", "label": label, "status": "LABELED",
                "confirmed": True, "is_pseudo": False, "needs_review": False,
                "annotator_id": "fixture_annotator", "decided_at": "2026-11-07T10:00:00+07:00",
                "guideline_version": "fixture-v1", "evidence_mode": "blind", "review_reason": None}
    decision.update(overrides)
    return decision


def machine(label="NEG", **overrides):
    decision = {"label_source": "machine", "label": label, "status": "LABELED",
                "confirmed": False, "is_pseudo": False, "needs_review": True,
                "model_id": "fixture_model", "model_version": "v1", "score": 0.9,
                "score_kind": "uncalibrated", "review_reason": None, "audit_id": None}
    decision.update(overrides)
    return decision


class ImportTests(unittest.TestCase):
    def test_csv_and_json_configured_columns(self):
        config = json.loads((ROOT / "configs/data_fixture.json").read_text(encoding="utf-8"))
        for spec in config["inputs"]:
            with self.subTest(spec=spec["format"]):
                rows, payload = read_rows(ROOT / spec["path"], spec)
                records = import_comments(rows, spec, digest(payload))
                self.assertEqual(len(records), len(rows))
                self.assertEqual(records[0]["text_raw"], rows[0]["body"])
                self.assertEqual(records[0]["comment_id"], rows[0]["cid"])
                self.assertIsNone(records[0]["collected_at"])
                self.assertIsNone(records[0]["license"])

    def test_missing_metadata_stays_unknown(self):
        record = records_from([{"text": "Phim ổn"}])[0]
        for key in ("post_id", "post_url", "comment_id", "collected_at", "movie_id", "privacy"):
            self.assertIsNone(record[key])

    def test_normalization_preserves_raw_and_sentiment_cues(self):
        raw = "  PHIM không hay :))) ❤️\n nhưng buồn  "
        record = records_from([{"text": raw}])[0]
        self.assertEqual(record["text_raw"], raw)
        self.assertEqual(record["text"], "PHIM không hay :))) ❤️ nhưng buồn")
        self.assertNotEqual(record["text_raw_hash"], record["text_hash"])

    def test_internal_ids_stable_when_unrelated_rows_reordered(self):
        rows = [{"text": "A"}, {"text": "B"}, {"text": "C", "cid": "1"}]
        left, right = records_from(rows), records_from(list(reversed(rows)))
        self.assertEqual({r["text_raw"]: r["id"] for r in left}, {r["text_raw"]: r["id"] for r in right})

    def test_duplicate_rows_have_unique_ids_but_shared_hashes(self):
        records = records_from([{"text": "Hay"}, {"text": "Hay"}])
        self.assertNotEqual(records[0]["id"], records[1]["id"])
        self.assertEqual(records[0]["text_hash"], records[1]["text_hash"])

    def test_numeric_text_rejected(self):
        with self.assertRaises(ValueError):
            records_from([{"text": 123}])

    def test_missing_text_column_rejected(self):
        with self.assertRaises(ValueError):
            records_from([{"wrong": "text"}])

    def test_text_hash_tampering_rejected(self):
        record = records_from([{"text": "Hay"}])[0]
        record["text_raw"] = "Dở"
        with self.assertRaises(ValueError):
            validate_record(record)

    def test_malformed_csv_and_json_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for suffix, text in (("csv", "text,text\na,b\n"), ("csv", "text,post\na,b,c\n"), ("json", '{"text":"abc"}')):
                path = Path(temp) / ("bad." + suffix)
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    read_rows(path, {"columns": {"text_raw": "text"}})

    def test_sidecar_uses_exact_raw_not_row_order(self):
        records = records_from([{"text": "Hay"}, {"text": "Dở"}])
        spec = {"path": "sidecar.csv", "source_dataset": "synthetic", "columns": {"text_raw": "body"},
                "annotations": {"machine": {"column": "label", "values": {"pos": "POS", "hard": "REVIEW"},
                                           "model_id": "legacy", "model_version": "unknown"}}}
        result = attach_annotations(records, [{"body": "Dở", "label": "hard"}, {"body": "Hay", "label": "pos"},
                                               {"body": "Missing", "label": "pos"}], spec, "sidecar_sha")
        self.assertEqual(result, {"matched_rows": 2, "unmatched_rows": [3]})
        self.assertEqual(records[0]["annotations"]["machine"][0]["label"], "POS")
        self.assertIsNone(records[1]["annotations"]["machine"][0]["label"])
        self.assertEqual(records[1]["annotations"]["machine"][0]["status"], "REVIEW")
        self.assertTrue(all(gold_label(r) is None for r in records))

    def test_populated_legacy_human_column_is_not_automatically_gold(self):
        spec = {"path": "legacy.csv", "source_dataset": "x", "columns": {"text_raw": "text"},
                "annotations": {"human": {"column": "human", "values": {"POS": "POS"}}}}
        record = import_comments([{"text": "Hay", "human": "POS"}], spec, "hash")[0]
        self.assertEqual(record["annotations"]["human"][0]["label"], "POS")
        self.assertIsNone(gold_label(record))


class QualityTests(unittest.TestCase):
    def test_short_emoji_typo_and_ui_word_inside_sentence_are_kept(self):
        records = records_from([{"text": t} for t in ["Dở", "❤️", "khum hay lém", "Mình thích phim này"]])
        self.assertTrue(all(r["quality"]["status"] == "KEEP" for r in records))

    def test_quality_reasons_and_raw_are_retained(self):
        raw = ["", "Thích", "Phim… Xem thêm", "Hay"]
        records = records_from([{"text": t} for t in raw])
        self.assertEqual([r["text_raw"] for r in records], raw)
        self.assertEqual([r["quality"]["reasons"] for r in records], [["EMPTY"], ["UI_STRING"], ["TRUNCATED_UI_SUFFIX"], []])

    def test_spam_rules_are_explicit_and_configurable(self):
        records = records_from([{"text": "spam-fixture: link"}, {"text": "Phim hay"}])
        assess_quality(records, {"spam_patterns": ["^spam-fixture:"]})
        self.assertEqual(records[0]["quality"]["reasons"], ["SPAM_RULE"])
        self.assertEqual(records[1]["quality"]["status"], "KEEP")

    def test_real_sentence_ending_in_xem_them_is_not_truncated_ui(self):
        record = records_from([{"text": "Phim hay nên mình muốn xem thêm"}])[0]
        self.assertEqual(record["quality"]["status"], "KEEP")

    def test_exact_dedup_keeps_provenance_and_assigns_representative(self):
        records = records_from([{"text": " PHIM hay ❤️ "}, {"text": "phim hay ❤️"}])
        self.assertEqual(len(records), 2)
        self.assertEqual(sum(r["quality"]["duplicate_of"] is not None for r in records), 1)
        self.assertTrue(all(r["provenance"] for r in records))

    def test_near_duplicates_retained_pending_review_and_grouped(self):
        base = "Phim có hình ảnh đẹp và âm nhạc rất ấn tượng trong nhiều phân cảnh"
        records = records_from([{"text": base + "!"}, {"text": base + "."}])
        pairs = near_duplicate_candidates(records, {"threshold": 0.8, "min_chars": 20, "shingle_size": 3})
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["decision"], "pending_review")
        self.assertTrue(all(r["quality"]["duplicate_of"] is None for r in records))
        groups = build_groups(records, pairs)
        self.assertEqual(groups[records[0]["id"]], groups[records[1]["id"]])

    def test_conflicting_duplicate_gold_is_blocked_for_review(self):
        records = records_from([{"text": "Hay"}, {"text": "HAY"}])
        append_decision(records[0], human("POS"))
        append_decision(records[1], human("NEG"))
        mark_exact_duplicates(records)
        self.assertTrue(all(r["quality"]["label_conflict"] for r in records))
        self.assertTrue(all(gold_label(r) is None for r in records))


class ProvenanceTests(unittest.TestCase):
    def test_review_and_exclude_cannot_be_sentiment_classes(self):
        for label in ("REVIEW", "EXCLUDE", "hard", "unrelated"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_decision(machine(label))
        validate_decision(machine(None, status="REVIEW", review_reason="REV_MIXED"))
        validate_decision(machine(None, status="EXCLUDE"))

    def test_machine_append_preserves_human_and_history(self):
        record = records_from([{"text": "Hay"}])[0]
        original = human()
        append_decision(record, original)
        original["label"] = "NEG"
        append_decision(record, machine())
        append_decision(record, machine("NEU"))
        self.assertEqual(gold_label(record), "POS")
        self.assertEqual(len(record["annotations"]["machine"]), 2)
        self.assertEqual(record["annotations"]["human"][0]["label"], "POS")

    def test_machine_cannot_confirm_itself_or_use_nonfinite_score(self):
        for overrides in ({"confirmed": True}, {"score": float("nan")}, {"score": float("inf")}, {"model_version": None}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                validate_decision(machine(**overrides))

    def test_confirmation_needs_actor_timestamp_guideline_and_blindness(self):
        for key in ("annotator_id", "decided_at", "guideline_version", "evidence_mode"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_decision(human(**{key: None}))
        with self.assertRaises(ValueError):
            validate_decision(human(decided_at="2026-11-07T10:00:00"))

    def test_unconfirmed_revision_revokes_gold(self):
        record = records_from([{"text": "Hay"}])[0]
        append_decision(record, human())
        append_decision(record, human("NEG", confirmed=False))
        self.assertIsNone(gold_label(record))

    def test_assisted_human_label_cannot_be_gold_evaluation(self):
        record = records_from([{"text": "Hay"}])[0]
        append_decision(record, human(evidence_mode="assisted"))
        self.assertEqual(gold_label(record), "POS")
        self.assertIsNone(gold_label(record, evaluation=True))

    def test_pseudo_label_requires_audit_and_is_never_gold(self):
        record = records_from([{"text": "Hay"}])[0]
        with self.assertRaises(ValueError):
            append_decision(record, machine(is_pseudo=True))
        append_decision(record, machine(is_pseudo=True, audit_id="fixture-only-audit"))
        self.assertTrue(record["annotations"]["machine"][0]["is_pseudo"])
        self.assertIsNone(gold_label(record))


class SplitTests(unittest.TestCase):
    def fixture(self):
        # Duplicate bridge joins post A → post B → post C transitively.
        rows = [{"text": "bridge one", "post": "A"}, {"text": "BRIDGE ONE", "post": "B"},
                {"text": "bridge two", "post": "B"}, {"text": "bridge two", "post": "C"},
                {"text": "another comment", "post": "C"}]
        rows += [{"text": f"unique-{i}", "post": f"p{i}"} for i in range(20)]
        return records_from(rows)

    def test_transitive_posts_duplicates_never_cross_splits(self):
        records = self.fixture()
        manifest = make_manifest(records, [], SPLIT, "fixture")
        selected = {e["id"]: e["split"] for e in manifest["entries"]}
        self.assertEqual(len({selected[r["id"]] for r in records[:5]}), 1)
        self.assertTrue(validate_manifest(records, [], manifest))
        for key in ("post_id", "text_hash"):
            seen = {}
            for r in records:
                seen.setdefault(r[key], set()).add(selected[r["id"]])
            self.assertTrue(all(len(values) == 1 for values in seen.values()))

    def test_deterministic_for_seed_and_input_order(self):
        records = self.fixture()
        self.assertEqual(make_manifest(records, [], SPLIT, "fixture"), make_manifest(list(reversed(records)), [], SPLIT, "fixture"))

    def test_machine_suggestions_do_not_influence_pool_allocation(self):
        records = self.fixture()
        before = make_manifest(records, [], SPLIT, "fixture")
        for record in records:
            append_decision(record, machine())
        self.assertEqual(before, make_manifest(records, [], SPLIT, "fixture"))

    def test_leaking_manifest_is_rejected(self):
        records = self.fixture()
        manifest = make_manifest(records, [], SPLIT, "fixture")
        entry = next(e for e in manifest["entries"] if e["id"] == records[0]["id"])
        entry["split"] = "dev" if entry["split"] != "dev" else "train"
        with self.assertRaisesRegex(ValueError, "Leakage"):
            validate_manifest(records, [], manifest)

    def test_unlabeled_and_machine_only_data_cannot_be_gold(self):
        records = self.fixture()
        for record in records:
            append_decision(record, machine())
        manifest = make_manifest(records, [], SPLIT, "fixture")
        manifest["locked_gold"] = True
        with self.assertRaisesRegex(ValueError, "confirmed human"):
            validate_manifest(records, [], manifest, require_gold=True)

    def test_gold_requires_lock_and_unused_holdout_groups(self):
        records = self.fixture()
        for record in records:
            append_decision(record, human())
        manifest = make_manifest(records, [], SPLIT, "fixture")
        with self.assertRaisesRegex(ValueError, "not been locked"):
            validate_manifest(records, [], manifest, require_gold=True)
        manifest["locked_gold"] = True
        self.assertTrue(validate_manifest(records, [], manifest, require_gold=True))
        held_out = next(e["id"] for e in manifest["entries"] if e["split"] == "test")
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_manifest(records, [], manifest, require_gold=True, used_ids=[held_out])

    def test_invalid_ratios_rejected(self):
        for ratios in ({"train": 1, "dev": 1, "test": 1}, {"train": 1, "dev": -0.1, "test": 0.1},
                       {"train": float("nan"), "dev": 0, "test": 0}):
            with self.subTest(ratios=ratios), self.assertRaises(ValueError):
                make_manifest(self.fixture(), [], {"seed": 42, "ratios": ratios}, "fixture")

    def test_giant_post_is_kept_whole_even_if_holdout_empty(self):
        records = records_from([{"text": str(i), "post": "single"} for i in range(10)])
        manifest = make_manifest(records, [], SPLIT, "fixture")
        self.assertEqual(len({e["split"] for e in manifest["entries"]}), 1)


class PipelineTests(unittest.TestCase):
    def test_unmatched_sidecar_is_reported_and_never_transferred(self):
        config = json.loads((ROOT / "configs/data_fixture.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            sidecar = Path(temp) / "labels.json"
            sidecar.write_text('[{"body":"not in raw","label":"POS"}]', encoding="utf-8")
            config["inputs"].append({
                "path": str(sidecar), "role": "annotations", "format": "json",
                "source_dataset": "fixture_csv", "columns": {"text_raw": "body"},
                "annotations": {"machine": {"column": "label", "values": {"POS": "POS"},
                                           "model_id": "fixture", "model_version": "v1"}},
            })
            config_path = Path(temp) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            report, processed, _ = prepare_data(config_path, Path(temp) / "data")
            self.assertEqual(report["sources"][-1]["annotation_join"]["unmatched_rows"], [1])
            self.assertTrue(any("UNMATCHED_ANNOTATIONS" in warning for warning in report["warnings"]))
            records = [json.loads(line) for line in (processed / "records.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(all(not r["annotations"]["machine"] for r in records))

    def test_end_to_end_snapshots_reconciliation_blind_exports_and_reproducibility(self):
        config = ROOT / "configs/data_fixture.json"
        inputs = [ROOT / "tests/fixtures/comments.csv", ROOT / "tests/fixtures/comments.json"]
        original = [path.read_bytes() for path in inputs]
        with tempfile.TemporaryDirectory() as temp:
            out1, out2 = Path(temp) / "run1", Path(temp) / "run2"
            report, processed, splits = prepare_data(config, out1)
            again, processed2, splits2 = prepare_data(config, out2)
            counts = report["counts"]
            self.assertEqual(counts["raw_comment_rows"], 14)
            self.assertEqual(counts["quality_excluded"], 3)
            self.assertEqual(counts["exact_duplicate_extra_rows"], 1)
            self.assertEqual(counts["retained_representatives"], 10)
            self.assertEqual(sum(counts["split_representatives"].values()), 10)
            self.assertEqual(report["data_version"], again["data_version"])
            for relative in ("records.jsonl", "near_duplicates.jsonl", "quality_decisions.jsonl"):
                self.assertEqual((processed / relative).read_bytes(), (processed2 / relative).read_bytes())
            self.assertEqual((splits / "manifest.json").read_bytes(), (splits2 / "manifest.json").read_bytes())
            for source, payload in zip(report["sources"], original):
                self.assertEqual(Path(source["snapshot"]).read_bytes(), payload)
            for split in ("train", "dev", "test"):
                for line in (splits / f"{split}_blind.jsonl").read_text(encoding="utf-8").splitlines():
                    row = json.loads(line)
                    self.assertEqual(set(row), {"id", "text_raw", "post_id", "post_url", "source_dataset"})
            self.assertEqual([p.read_bytes() for p in inputs], original)
            self.assertEqual(report["distribution_after_filter"]["human_confirmed_gold"], {})
            before = (processed / "records.jsonl").read_bytes()
            with self.assertRaises(FileExistsError):
                prepare_data(config, out1)
            self.assertEqual((processed / "records.jsonl").read_bytes(), before)
            for relative, expected in report["artifact_sha256"].items():
                self.assertEqual(digest((out1 / relative).read_bytes()), expected)
            self.assertEqual(verify_prepared(out1, report["data_version"])["status"], "valid")

    def test_modified_artifact_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            report, processed, _ = prepare_data(ROOT / "configs/data_fixture.json", temp)
            path = processed / "records.jsonl"
            with path.open("a", encoding="utf-8") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_prepared(temp, report["data_version"])

    def test_unlabeled_pool_cannot_be_claimed_as_gold(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _, _ = prepare_data(ROOT / "configs/data_fixture.json", temp)
            with self.assertRaisesRegex(ValueError, "confirmed human"):
                verify_prepared(temp, report["data_version"], require_gold=True)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_data.py"), "--config",
                                     str(ROOT / "configs/data_fixture.json"), "--output-root", temp],
                                    capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["counts"]["raw_comment_rows"], 14)

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "optional legacy pandas not installed")
    def test_legacy_labeler_preserves_human_metadata_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / "source.csv", Path(temp) / "target.csv"
            source.write_text("text,clean,nhan_nguoi,post_id\nPhim hay,phim hay,NEG,p1\n", encoding="utf-8")
            original = source.read_bytes()
            command = [sys.executable, str(ROOT / "gan_nhan.py"), str(source), "-o", str(target)]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            import csv
            with target.open(encoding="utf-8-sig", newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["nhan_nguoi"], "NEG")
            self.assertEqual(row["post_id"], "p1")
            saved = target.read_bytes()
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), saved)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
