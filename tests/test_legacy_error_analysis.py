import unittest

from src.baseline.legacy_error_analysis import _pair_stats, _legacy_quality


class LegacyErrorAnalysisTests(unittest.TestCase):
    def test_pair_comparison_counts_regressions_corrections_and_class_transitions(self):
        predictions = {
            'A': {'i1':dict(human_label='NEG',predicted_label='NEG'),
                  'i2':dict(human_label='POS',predicted_label='NEG'),
                  'i3':dict(human_label='NEU',predicted_label='NEU')},
            'B': {'i1':dict(human_label='NEG',predicted_label='POS'),
                  'i2':dict(human_label='POS',predicted_label='POS'),
                  'i3':dict(human_label='NEU',predicted_label='NEG')}}
        result = _pair_stats(predictions,'A','B')
        self.assertEqual(result['left_correct_right_wrong'],2)
        self.assertEqual(result['left_wrong_right_correct'],1)
        self.assertEqual(result['prediction_transitions'],{'NEG->POS':2,'NEU->NEG':1})

    def test_legacy_quality_flags_short_text_without_changing_label(self):
        rows=[dict(id='legacyhuman::a',label='POS',text_view='Hay'),
              dict(id='legacyhuman::b',label='NEG',text_view='Kịch bản triển khai dài và nhiều chi tiết nhưng không có bản sao.')]
        result=_legacy_quality(rows)
        self.assertEqual(result['labels'],{'POS':1,'NEG':1})
        self.assertEqual(result['under_20_chars'],1)
        self.assertEqual(result['candidate_reasons']['legacyhuman::a'],['SHORT_TEXT_POSSIBLE_CONTEXT_DEPENDENCE'])


if __name__ == '__main__':
    unittest.main()
