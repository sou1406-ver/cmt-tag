import unittest

from src.transformer import LABELS
from src.transformer.data import fold_training_rows, validate_frozen_fold
from src.transformer.models import prepare_phobert, prepare_visobert
from src.transformer.runner import compare_oof_to_svm
from src.transformer.training import LABEL_TO_ID, encode_batch, validate_logits


class FakeTensor:
    def __init__(self, shape): self.shape = shape


class FakeTokenizer:
    def __call__(self, texts, **kwargs):
        return {"input_ids": FakeTensor((len(texts), 4)), "attention_mask": FakeTensor((len(texts), 4))}


class FakeLogits:
    shape = (2, 3)


class TransformerPhaseHTests(unittest.TestCase):
    def test_fixed_three_class_order(self):
        self.assertEqual(LABELS, ("POS", "NEG", "NEU"))
        self.assertEqual(LABEL_TO_ID, {"POS": 0, "NEG": 1, "NEU": 2})

    def test_legacy_is_train_only(self):
        fb = {"a": {"id": "fbdev::a", "source_dataset": "facebook_development", "label": "POS"},
              "b": {"id": "fbdev::b", "source_dataset": "facebook_development", "label": "NEG"}}
        legacy = [{"id": "legacyhuman::l", "source_dataset": "legacy_human", "label": "NEU"}]
        train, valid = fold_training_rows(fb, legacy, {"train_ids": ["a"], "validation_ids": ["b"]}, True)
        self.assertEqual([r["source_dataset"] for r in train], ["facebook_development", "legacy_human"])
        self.assertEqual([r["source_dataset"] for r in valid], ["facebook_development"])

    def test_frozen_fold_rejects_overlap_duplicate_and_unknown_id(self):
        fb = {"a": {"label": "POS", "frozen_group_id": "post-a"},
              "b": {"label": "NEG", "frozen_group_id": "post-b"}}
        self.assertTrue(validate_frozen_fold(fb, {"train_ids": ["a"], "validation_ids": ["b"]}))
        for fold in ({"train_ids": ["a"], "validation_ids": ["a"]},
                     {"train_ids": ["a", "a"], "validation_ids": ["b"]},
                     {"train_ids": ["a"], "validation_ids": ["reserved-test"]},
                     {"train_ids": [], "validation_ids": ["b"]}):
            with self.assertRaises(ValueError): validate_frozen_fold(fb, fold)
        fb["b"]["frozen_group_id"] = "post-a"
        with self.assertRaises(ValueError):
            validate_frozen_fold(fb, {"train_ids": ["a"], "validation_ids": ["b"]})

    def test_review_exclude_overall_and_unknown_rejected(self):
        for label in ("REVIEW", "EXCLUDE", "overall", ""):
            fb = {"a": {"id": "fbdev::a", "source_dataset": "facebook_development", "label": label},
                  "b": {"id": "fbdev::b", "source_dataset": "facebook_development", "label": "NEG"}}
            with self.assertRaises(ValueError):
                fold_training_rows(fb, [], {"train_ids": ["a"], "validation_ids": ["b"]}, False)

    def test_phobert_resegments_legacy_underscore_text(self):
        seen = []
        class Segmenter:
            def word_segment(self, text):
                seen.append(text); return "kịch_bản tốt"
        source = "kịch_bản tốt"
        self.assertEqual(prepare_phobert(source, Segmenter(), legacy_source=True), "kịch_bản tốt")
        self.assertEqual(seen, ["kịch bản tốt"])

    def test_visobert_preserves_text_view(self):
        text = "Phim hay :))) emoji 😭 phủ_định không"
        self.assertEqual(prepare_visobert(text), text)

    def test_encoding_checks_attention_mask_and_label(self):
        encoded = encode_batch(FakeTokenizer(), ["câu"], ["NEU"], 8)
        self.assertEqual(encoded["input_ids"].shape, encoded["attention_mask"].shape)
        with self.assertRaises(KeyError): encode_batch(FakeTokenizer(), ["câu"], ["REVIEW"], 8)

    def test_output_has_three_logits(self):
        validate_logits(FakeLogits(), 2)
        class Bad: shape = (2, 2)
        with self.assertRaises(ValueError): validate_logits(Bad(), 2)

    def test_paired_comparison_requires_exact_ids(self):
        current = [{"id": "fbdev::1", "model": "visobert", "dataset": "fb_only",
                    "human_label": "NEG", "prediction": "NEG"},
                   {"id": "fbdev::2", "model": "visobert", "dataset": "fb_only",
                    "human_label": "POS", "prediction": "POS"},
                   {"id": "fbdev::3", "model": "visobert", "dataset": "fb_only",
                    "human_label": "NEU", "prediction": "NEU"}]
        baseline = [{"id": "fbdev::1", "experiment": "A", "human_label": "NEG", "predicted_label": "POS"},
                    {"id": "fbdev::2", "experiment": "A", "human_label": "POS", "predicted_label": "POS"},
                    {"id": "fbdev::3", "experiment": "A", "human_label": "NEU", "predicted_label": "NEG"}]
        result = compare_oof_to_svm(current, baseline, "visobert", "fb_only", "A")
        self.assertEqual(result["support"], 3)
        self.assertEqual(result["transformer_corrected_svm_errors"], 2)
        self.assertEqual(result["transformer_regressed_svm_correct"], 0)
        self.assertIsNone(compare_oof_to_svm(current[:1], baseline, "visobert", "fb_only", "A"))


if __name__ == "__main__": unittest.main()
