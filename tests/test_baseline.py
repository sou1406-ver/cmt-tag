import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_SKLEARN=bool(importlib.util.find_spec('sklearn'))
if HAS_SKLEARN:
    import joblib
    from src.models.core import dataset, evaluate, metrics, train
from src.annotation.core import GUIDELINE, GUIDELINE_VERSION, now, release, save
from src.data.importers import canonical_json, digest
from src.data.pipeline import ROOT, prepare_data
def make(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    source=ROOT/'tests/fixtures/baseline_synthetic.json'
    cfg={'schema_version':'1.0','inputs':[{'path':str(source),'source_dataset':'synthetic_210',
         'format':'json','post_namespace':'synthetic','columns':{'text_raw':'body','post_id':'pid'},
         'license':'synthetic fixture','privacy':'no real people'}],
         'quality':{'ui_strings':[],'spam_patterns':[]},
         'near_duplicate':{'threshold':0.9,'min_chars':10000,'shingle_size':3},
         'split':{'seed':42,'ratios':{'train':0.6,'dev':0.2,'test':0.2}}}
    save(output/'config.json',cfg)
    report,processed,_=prepare_data(output/'config.json',output/'phase_b')
    labels={r['body']:r['expected_label'] for r in json.loads(source.read_text(encoding='utf-8'))}
    event_path=output/'synthetic_events.jsonl'
    with event_path.open('x',encoding='utf-8') as f:
        for r in read_jsonl(processed/'records.jsonl'):
            # Human-shaped provenance is deliberately marked fixture-only.
            # These are authored synthetic expected outputs, never real humans.
            e={'id':r['id'],'dataset_version':report['data_version'],'guideline_sha256':digest(GUIDELINE.read_bytes()),
               'cohort':'synthetic','decision':{'label_source':'human','label':labels[r['text_raw']],
               'status':'LABELED','confirmed':True,'is_pseudo':False,'needs_review':False,
               'annotator_id':'SYNTHETIC_EXPECTED_OUTPUT','evidence_mode':'blind','decided_at':now(),
               'guideline_version':GUIDELINE_VERSION,'fixture_only':True}}
            f.write(canonical_json(e)+'\n')
    return release(output/'phase_b',report['data_version'],[event_path],output/'release',synthetic=True)

from src.annotation.core import save
from src.data.importers import digest
from src.data.validation import read_jsonl


@unittest.skipUnless(HAS_SKLEARN,'Install requirements/classical-base.txt for Phase D tests')
class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.release=make(self.root/'fixture')

    def test_end_to_end_cross_table_vocab_and_deterministic(self):
        pools,_=dataset(self.release)
        self.assertEqual(sum(map(len,pools.values())),210)
        a=train(self.release,self.root/'run_a',self.root/'usage')
        b=train(self.release,self.root/'run_b',self.root/'usage')
        self.assertEqual([(r['cell'],r['ngram'],r['class_weight'],r['dev']) for r in a['selected']],
                         [(r['cell'],r['ngram'],r['class_weight'],r['dev']) for r in b['selected']])
        pipeline=joblib.load(self.root/'run_a/bow_nb.joblib')
        # A token present only in a held-out text cannot enter the fitted vocabulary.
        holdout=pools['test'][0]['text'].split()[-1]
        self.assertNotIn(holdout,pipeline['vectorizer'].vocabulary_)
        table=evaluate(self.root/'run_a',self.root/'final')
        self.assertEqual(len(table),7)
        self.assertEqual({r['cell'] for r in table}, {'bow_nb','bow_lr','bow_svm','tfidf_nb','tfidf_lr','tfidf_svm','majority'})
        self.assertTrue(all(len(r['confusion_matrix'])==3 and all(len(x)==3 for x in r['confusion_matrix']) for r in table))
        self.assertTrue(json.loads((self.root/'final/metrics.json').read_text())['synthetic'])
        with self.assertRaises(FileExistsError): evaluate(self.root/'run_b',self.root/'again')
        with self.assertRaises(ValueError): train(self.release,self.root/'run_c',self.root/'usage')

    def test_missing_prediction_class_and_machine_test_rejected(self):
        m=metrics(['POS','NEG','NEU'],['POS']*3)
        self.assertEqual(m['per_class']['NEG']['precision'],0)
        self.assertEqual(len(m['confusion_matrix']),3)
        manifest=json.loads((self.release/'manifest.json').read_text())
        test_ids={e['id'] for e in manifest['entries'] if e['split']=='test'}
        rows=read_jsonl(self.release/'records.jsonl')
        for r in rows:
            if r['id'] in test_ids:
                d=dict(r['annotations']['human'][-1]); d.update(label_source='machine',confirmed=False,
                     model_id='fixture_teacher',model_version='1',score=None,score_kind='not_calibrated')
                r['annotations']['human']=[]; r['annotations']['machine']=[d]
        path=self.release/'records.jsonl'
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        meta=json.loads((self.release/'release.json').read_text())
        meta['checksums']['records.jsonl']=digest(path.read_bytes())
        (self.release/'release.json').write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError,'gold'): dataset(self.release)

    def test_silver_train_allowed_but_never_renamed_gold(self):
        manifest=json.loads((self.release/'manifest.json').read_text())
        train_ids={e['id'] for e in manifest['entries'] if e['split']=='train'}
        rows=read_jsonl(self.release/'records.jsonl')
        for r in rows:
            if r['id'] in train_ids:
                d=dict(r['annotations']['human'][-1]); d.update(label_source='machine',confirmed=False,
                     model_id='fixture_teacher',model_version='1',score=None,score_kind='not_calibrated')
                r['annotations']['human']=[]; r['annotations']['machine']=[d]
        path=self.release/'records.jsonl'; path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        meta=json.loads((self.release/'release.json').read_text()); meta['checksums']['records.jsonl']=digest(path.read_bytes())
        (self.release/'release.json').write_text(json.dumps(meta))
        pools,_=dataset(self.release,'silver-only')
        self.assertTrue(all(r['origin']=='silver' for r in pools['train']))
        self.assertTrue(all(r['origin']=='gold' for r in pools['test']))
        with self.assertRaises(ValueError): dataset(self.release,'gold-only')

    def test_model_tamper_rejected_before_exposing_test(self):
        train(self.release,self.root/'run',self.root/'usage')
        with (self.root/'run/bow_nb.joblib').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'): evaluate(self.root/'run',self.root/'final')
        self.assertFalse((self.root/'usage').exists())


if __name__=='__main__': unittest.main()
