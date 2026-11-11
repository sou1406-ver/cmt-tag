import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.dataset.common import ROOT, sha
from src.dataset.phase_i import (clean_record, consensus, duplicate_groups, sample_stratified,
                                 candidate_reason, validate_predictions)


class PhaseIUnitTests(unittest.TestCase):
    def test_cleaning_is_deterministic_and_preserves_sentiment_signals(self):
        raw = '  Phim&nbsp;này KHÔNG hay :))) 😭  '
        first, _ = clean_record(raw)
        second, _ = clean_record(raw)
        self.assertEqual(first, second)
        self.assertIn('KHÔNG', first)
        self.assertIn(':)))', first)
        self.assertIn('😭', first)
        self.assertEqual(raw, '  Phim&nbsp;này KHÔNG hay :))) 😭  ')

    def test_cleaning_preserves_teencode_underscore_and_long_text(self):
        raw = ('ko khum đc j vch kịch_bản ' * 60).strip()
        cleaned, audit = clean_record(raw)
        self.assertEqual(cleaned, raw)
        self.assertGreater(len(cleaned), 256)
        self.assertGreater(audit['after']['underscore_tokens'], 0)

    def test_invalid_control_chars_removed_without_truncating(self):
        raw = 'không\x01 hay ' + ('x' * 1500)
        cleaned, _ = clean_record(raw)
        self.assertNotIn('\x01', cleaned)
        self.assertTrue(cleaned.endswith('x' * 1500))
        self.assertEqual(len(cleaned), 1510)

    def test_exact_and_near_duplicate_groups_are_direct_diagnostics(self):
        texts = [
            {'record_id': 'a', 'text_clean': 'Phim này có kịch bản rất hay và diễn xuất tốt trong từng cảnh.'},
            {'record_id': 'b', 'text_clean': 'Phim này có kịch bản rất hay và diễn xuất tốt trong từng cảnh.'},
            {'record_id': 'c', 'text_clean': 'Phim này có kịch bản rất hay và diễn xuất tốt trong từng cảnh hôm nay.'},
            {'record_id': 'd', 'text_clean': 'Một bình luận hoàn toàn khác không có nội dung trùng lặp gì cả.'},
        ]
        groups, exact_dupes, result = duplicate_groups(texts, threshold=.7, min_chars=30, shingle_size=2, max_posting=256)
        self.assertEqual(groups['a'], groups['b'])
        self.assertIn('b', exact_dupes)
        self.assertIn('a', result['neighbors']['c'])
        self.assertNotEqual(groups['a'], groups['d'])

    def test_stratified_sampler_respects_source_quota_and_near_duplicate_edges(self):
        rows = []
        for source in ('facebook', 'legacy_29k_unverified'):
            for i in range(8):
                rows.append(dict(record_id=f'{source}-{i}', source_dataset=source, text_annotation=f'{i}',
                    flags=dict(emoji_present=bool(i%2), teencode_present=False, negation_present=False, underscore_present=False)))
        neighbors = {'facebook-0': {'facebook-1'}, 'facebook-1': {'facebook-0'}}
        picked = sample_stratified(rows, neighbors, 6, 7, {'facebook': 3, 'legacy_29k_unverified': 3})
        self.assertEqual(len(picked), 6)
        self.assertEqual(sum(r['source_dataset']=='facebook' for r in picked), 3)
        self.assertFalse({'facebook-0','facebook-1'} <= {r['record_id'] for r in picked})

    def test_human_test_and_development_posts_are_held_out(self):
        row=dict(record_id='fb-1',post_id='post-x',comment_id='comment-x',source_platform='facebook',quality_status='KEEP',review_flags=[])
        reasons=candidate_reason(row,{'fb-1':[dict(status='LABELED')]},set(),set(),{'fb-1'},set(),set(),{'post-x'},set())
        self.assertIn('HUMAN_DECISION_PRESENT',reasons)
        self.assertIn('TEST_RESERVED',reasons)
        self.assertIn('DEVELOPMENT_POST_HELD_OUT',reasons)

    def test_prediction_validator_requires_exact_ids_and_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); prediction=root/'pred.csv'; metadata=root/'meta.json'
            with prediction.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['id','status','label','review_reason','reason'])
                writer.writeheader();writer.writerow(dict(id='a',status='LABELED',label='NEG',review_reason='',reason=''))
            metadata.write_text(json.dumps(dict(annotator='claude',provider='provider',model_id='model',model_version='1',
                guideline_version='V2.1',guideline_sha256=sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md'),
                prompt_sha256=sha(ROOT/'docs/annotation/CLAUDE_ANNOTATION_INSTRUCTIONS.md'),
                labeled_at='2026-11-11',label_source='automatic')))
            result=validate_predictions(prediction,metadata,['a'])
            self.assertEqual(result['rows'],1)
            with self.assertRaises(ValueError):
                validate_predictions(prediction,metadata,['a','b'])

    def test_prediction_validator_rejects_invalid_exclude_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); prediction=root/'pred.csv'; metadata=root/'meta.json'
            with prediction.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['id','status','label','review_reason','reason'])
                writer.writeheader();writer.writerow(dict(id='a',status='EXCLUDE',label='',review_reason='EXC_OUT_OF_SCOPE',reason=''))
            metadata.write_text(json.dumps(dict(annotator='claude',provider='provider',model_id='model',model_version='1',
                guideline_version='V2.1',guideline_sha256=sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md'),
                prompt_sha256=sha(ROOT/'docs/annotation/CLAUDE_ANNOTATION_INSTRUCTIONS.md'),
                labeled_at='2026-11-11',label_source='automatic')))
            with self.assertRaises(ValueError):
                validate_predictions(prediction,metadata,['a'])

    def test_consensus_needs_three_sources_and_never_calls_result_gold(self):
        one=[dict(id='a',status='LABELED',label='POS')]
        with self.assertRaises(ValueError):
            consensus({'codex':one,'claude':one})
        result=consensus({'codex':one,'claude':one,'gemini':one})
        self.assertEqual(result[0]['status'],'SILVER_3_OF_3')
        self.assertEqual(result[0]['label_source'],'silver_candidate_not_gold')


if __name__=='__main__':
    unittest.main()
