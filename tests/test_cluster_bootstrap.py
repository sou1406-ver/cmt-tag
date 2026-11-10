from collections import Counter
import unittest
from src.dataset.bootstrap import cluster_draws, evaluate


def fixture():
    return [dict(id=str(i),post_id=str(i//3),movie_id='m'+str(i//3),label=['POS','NEG','NEU'][i%3],
                 prediction=['POS','NEG','NEU'][i%3]) for i in range(12)]


class BootstrapTests(unittest.TestCase):
    def test_every_draw_resamples_whole_clusters_with_multiplicity(self):
        rows=fixture();a=list(cluster_draws(rows));b=list(cluster_draws(rows))
        self.assertEqual(a,b);self.assertEqual(len(a),2000)
        duplicate_seen=False
        for draw in a:
            counts=Counter(draw)
            for post in range(4):self.assertEqual(len({counts[i] for i in range(post*3,post*3+3)}),1)
            duplicate_seen |= max(counts.values()) > 1
        self.assertTrue(duplicate_seen)

    def test_perfect_predictions_have_exact_unit_percentile_ci(self):
        r=evaluate(fixture())
        for item in r['metrics'].values():
            self.assertEqual(item['point'],1);self.assertEqual(item['ci95'],[1,1]);self.assertEqual(item['valid_replicates'],2000)

    def test_formula_matches_manually_calculated_confusion(self):
        rows=fixture()
        for r in rows:r['prediction']='POS'
        # POS TP=4, FP=8, FN=0 => F1=.5; NEG=NEU=0 => macro=1/6.
        result=evaluate(rows)
        self.assertAlmostEqual(result['metrics']['POS']['point'],.5)
        self.assertAlmostEqual(result['metrics']['macro_f1']['point'],1/6)
        self.assertEqual(result['metrics']['NEG']['point'],0)

    def test_missing_class_replicates_are_counted_and_never_replaced_by_zero(self):
        rows=fixture()
        for r in rows:r['label']=['POS','NEG','NEU'][int(r['post_id'])%3];r['prediction']=r['label']
        result=evaluate(rows)
        self.assertGreater(result['metrics']['macro_f1']['invalid_replicates'],0)
        self.assertEqual(result['metrics']['macro_f1']['ci95'],[1,1])
        for m in result['metrics'].values():self.assertEqual(m['valid_replicates']+m['invalid_replicates'],2000)

    def test_class_absent_from_original_has_null_point_and_ci(self):
        rows=fixture()
        for r in rows:r['label']='POS';r['prediction']='POS'
        result=evaluate(rows)
        self.assertIsNone(result['metrics']['macro_f1']['point']);self.assertIsNone(result['metrics']['NEG']['ci95'])
        self.assertEqual(result['metrics']['NEG']['invalid_replicates'],2000)

    def test_invalid_inputs_fail_without_implicit_row_bootstrap(self):
        with self.assertRaises(ValueError):list(cluster_draws(fixture(),1999))
        rows=fixture()
        for r in rows:r['post_id']='same'
        with self.assertRaises(ValueError):evaluate(rows)
        rows=fixture();rows[0]['label']='REVIEW'
        with self.assertRaises(ValueError):evaluate(rows)


if __name__=='__main__':unittest.main()
