import unittest
import numpy as np
import tempfile
import json
from pathlib import Path
from scripts.run_ranking_diagnostics import aligned_scores,ranking,run


class RankingTests(unittest.TestCase):
    def test_class_order_is_explicit(self):
        raw=np.array([[9.,2.,4.]])
        self.assertEqual(aligned_scores(raw,['NEG','NEU','POS']).tolist(),[[4.,9.,2.]])
        with self.assertRaises(ValueError):aligned_scores(raw,['POS','NEG','NEG'])
        with self.assertRaises(ValueError):aligned_scores([1,2,3],['POS','NEG','NEU'])

    def test_auc_and_ap_support_and_prevalence(self):
        y=['POS','POS','NEG','NEU'];s=np.array([[4,0,0],[3,0,0],[0,4,0],[0,0,4]])
        r=ranking(y,s)
        self.assertEqual(r['POS']['support'],2);self.assertEqual(r['POS']['prevalence'],.5)
        self.assertEqual(r['POS']['roc_auc'],1);self.assertEqual(r['POS']['average_precision'],1)
        self.assertEqual(r['NEG']['status'],'limited_support')

    def test_missing_binary_class_is_undefined_not_zero(self):
        r=ranking(['POS','POS'],np.ones((2,3)))
        self.assertIsNone(r['POS']['roc_auc']);self.assertIsNone(r['NEG']['average_precision'])

    def test_high_ovr_rank_does_not_guarantee_argmax_classification(self):
        y=['POS','POS','NEG','NEU'];scores=np.array([[2,10,0],[1,9,0],[0,11,0],[-1,8,2]])
        self.assertEqual(ranking(y,scores)['POS']['roc_auc'],1)
        self.assertTrue(all(i!=0 for i in scores[:2].argmax(axis=1)))

    def test_nonfinite_scores_rejected(self):
        with self.assertRaises(ValueError):aligned_scores([[np.nan,0,1]],['POS','NEG','NEU'])

    def test_changed_reference_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'e1';source.mkdir();(source/'manifest.json').write_text('{}')
            cfg=root/'cfg.json';cfg.write_text(json.dumps(dict(e1_root=str(source),e1_manifest_sha256='0'*64,
                model_id='tfidf_char_svm',threshold_tuning=False)))
            with self.assertRaisesRegex(ValueError,'manifest changed'):run(cfg,root/'e2')
            self.assertFalse((root/'e2').exists())


if __name__=='__main__':unittest.main()
