import unittest

from src.preprocessing.normalization import BASIC, inspect, normalize
from src.baseline.normalization_ablation import TRIALS, evaluate_trial


class BasicNormalizationTests(unittest.TestCase):
    def test_preserves_sentiment_tokens_and_entities_are_deterministic(self):
        text = '  KHÔNG   dở &amp;amp; #phim_a @user :)) 😭!!!  '
        once = normalize(text, BASIC)
        self.assertEqual(once, 'KHÔNG dở & #phim_a @user :)) 😭!!!')
        self.assertEqual(normalize(once, BASIC), once)
        self.assertIn('KHÔNG', once)
        self.assertIn('#phim_a', once)
        self.assertIn('😭', once)
        self.assertIn(':))', once)

    def test_urls_are_not_entity_decoded_or_rewritten(self):
        text = 'xem https://example.test/a?x=1&amp;y=2 và www.example.test/a_b'
        result = normalize(text)
        self.assertEqual(result, text)

    def test_audit_detects_no_loss_of_sentiment_information(self):
        text = 'chưa chắc phim hay?! 😭'
        result = normalize(text)
        audit = inspect(text, result)
        self.assertEqual(audit['sentiment_information_risks'], [])
        self.assertFalse(audit['empty_after'])

    def test_only_fixed_basic_config_is_accepted(self):
        with self.assertRaises(ValueError):
            normalize('văn bản', {**BASIC, 'teencode': 'normalize'})

    def test_strict_component_blocker_prevents_a_fold_fit(self):
        plans = [dict(view='original', fold=i, blockers=['MASTER_COMPONENT_OVERLAP']) for i in range(3)]
        with self.assertRaisesRegex(ValueError, 'Strict component preflight blocks'):
            evaluate_trial([], plans, TRIALS[0])


if __name__ == '__main__':
    unittest.main()
