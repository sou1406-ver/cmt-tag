"""Manual web pilot fixtures. No HTTP calls, real gold or credentials."""
import json
import random
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main

from src.annotation import pilot,web_labels
from src.annotation.guidelines import GUIDELINE
from src.dataset.common import save,seal,sha,digest,write_jsonl,read_jsonl,read_sheet,load


def fixture(p,n=6,export=False):
    rows=[dict(record_id='id'+str(i),text='Bình luận phim '+str(i)) for i in range(n)]
    meta=[dict(record_id=r['record_id'],source='facebook',post_id=str(i),movie_id='movie',text_sha256=digest(r['text'])) for i,r in enumerate(rows)]
    write_jsonl(p/'pilot_input.local.jsonl',rows)
    save(p/'coordinator.local.json',dict(rows=meta,calibration_labels={'id0':'POS','id1':'NEG'},unlabeled_ids=['id'+str(i) for i in range(2,n)],summary={}))
    save(p/'selection_manifest.json',dict(repository_root=str(p),rows=meta,input_sha256=sha(p/'pilot_input.local.jsonl'),
        coordinator_sha256=sha(p/'coordinator.local.json'),guideline_sha256=sha(GUIDELINE),source_sha256={}))
    seal(p,dict(status='FIXTURE'))
    if export:web_labels.export_web(p)
    else:
        d=p/'web_upload';d.mkdir();save(d/'pilot_600.json',rows);(d/'PROMPT.txt').write_text('fixture',encoding='utf-8')
        seal(d,dict(selection_manifest_sha256=sha(p/'selection_manifest.json')))
    return rows


def response(p,items,label='POS'):
    rows=[dict(record_id=r['record_id'],predicted_label=label,reason='fixture') for r in items]
    p.write_text(json.dumps({'decisions':rows}),encoding='utf-8');return p


class PilotTests(TestCase):
    def test_seed_caps_and_quality_human_exclusions(self):
        rows=[dict(record_id=str(i),source_dataset='facebook',post_id=str(i//20),movie_id=str(i//80),text_annotation_view='phim '+str(i)) for i in range(400)]
        rows += [dict(rows[0],record_id='human',human_label='POS'),dict(rows[0],record_id='review',quality_decision='REVIEW')]
        a=pilot.sample_unlabeled(rows,200);self.assertEqual(a,pilot.sample_unlabeled(rows,200))
        self.assertTrue(all(n<=12 for n in Counter(r['post_id'] for r in a).values()))
        self.assertTrue(all(n<=36 for n in Counter(r['movie_id'] for r in a).values()))
        self.assertFalse({'human','review'} & {r['record_id'] for r in a})

    def test_proportional_calibration(self):
        rows=[dict(record_id=str(i),label='POS' if i<142 else 'NEG' if i<318 else 'NEU') for i in range(425)]
        a=pilot.stratified(rows,150,lambda r:r['label'],random.Random(1))
        self.assertEqual(Counter(r['label'] for r in a),{'POS':50,'NEG':62,'NEU':38})

    def test_reserved_post_exact_near_guards(self):
        text='bộ phim này có kịch bản và diễn xuất tuyệt vời trong toàn bộ hành trình'
        guard=dict(ids={'old'},posts={'test'},comments={'reserved'},text_hashes={digest('exact')},shingles=pilot.reference_index([pilot.fingerprints(text)]))
        r=dict(record_id='new',post_id='dev',comment_id='a',text_raw='new',text_minimal='new',text_annotation_view='new')
        self.assertIsNone(pilot.guard_reason(r,guard))
        self.assertEqual(pilot.guard_reason(dict(r,post_id='test'),guard),'TEST_RESERVED_HOLDOUT_IDENTITY')
        self.assertEqual(pilot.guard_reason(dict(r,text_annotation_view='exact'),guard),'EXACT_RESERVED_TEXT')
        self.assertEqual(pilot.guard_reason(dict(r,text_annotation_view=text),guard),'NEAR_RESERVED_TEXT')

    def test_one_complete_600_file_blinded_and_idempotent_export(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);fixture(p,600,True)
            rows=load(p/'web_upload/pilot_600.json')
            self.assertEqual(len(rows),600);self.assertTrue(all(set(r)=={'record_id','text'} for r in rows))
            self.assertFalse((p/'web_upload/batch_002.json').exists())
            self.assertIn('KHÔNG ĐÁNG TIN',(p/'web_upload/PROMPT.txt').read_text(encoding='utf-8'))
            self.assertTrue(web_labels.export_web(p)['already_exported'])
            self.assertFalse((p/'model_predictions.local.jsonl').exists())

    def test_import_resume_and_model_trace(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p);r=response(p/'gpt.json',items)
            self.assertEqual(web_labels.import_web(p,'GPT',r,model='web version')['imported'],6)
            self.assertEqual(web_labels.import_web(p,'GPT',r,model='web version')['imported'],0)
            self.assertEqual(next(iter(web_labels.successes(p).values()))['model_version'],'web version')
            response(r,items,'NEG')
            with self.assertRaises(ValueError):web_labels.import_web(p,'GPT',r,model='web version')

    def test_missing_unknown_duplicate_invalid_label_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p)
            for rows,label in [(items[:2],'POS'),(items+[items[0]],'POS'),([dict(record_id='unknown')],'POS'),(items,'BAD')]:
                r=response(p/'bad.json',rows,label)
                with self.assertRaises(ValueError):web_labels.import_web(p,'GPT',r)
            self.assertFalse((p/'model_predictions.local.jsonl').exists())

    def test_explicit_partial_recovery_preserves_missing_status(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p);r=response(p/'part.json',items[:2])
            result=web_labels.import_web(p,'Claude',r,allow_partial=True)
            self.assertEqual(result['missing'],4)
            result=web_labels.import_web(p,'Claude',response(p/'rest.json',items[2:]),allow_partial=True)
            self.assertEqual(result['missing'],0)

    def test_agreement_calibration_never_silver_and_blind_audit(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p)
            for provider in web_labels.SLOTS:web_labels.import_web(p,provider,response(p/(provider+'.json'),items))
            report=pilot.summarize(p)
            self.assertEqual(report['counts']['3_OF_3'],6);self.assertEqual(report['silver_candidates'],4)
            self.assertFalse(report['approved'])
            self.assertFalse({'id0','id1'} & {r['record_id'] for r in read_jsonl(p/'silver_candidates.local.jsonl')})
            _,rows,_=read_sheet(p/'review_blind.xlsx','Annotation')
            self.assertTrue(all(not r['label'] and not r['note'] for r in rows))
            self.assertEqual(report['usage']['api_requests'],0)

    def test_2_of_3_not_silver_no_unanimous_empty_metric(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p)
            for provider in web_labels.SLOTS:web_labels.import_web(p,provider,response(p/(provider+'.json'),items,'NEG' if provider=='Gemini' else 'POS'))
            report=pilot.summarize(p)
            self.assertEqual(report['counts']['2_OF_3'],6);self.assertEqual(report['silver_candidates'],0)
            self.assertEqual(report['calibration']['consensus_3_of_3']['coverage'],0)
            self.assertIsNone(report['calibration']['consensus_3_of_3']['conditional']['macro_f1'])

    def test_no_results_before_import_and_text_tamper_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);fixture(p)
            with self.assertRaises(ValueError):pilot.summarize(p)
            self.assertFalse((p/'silver_candidates.local.jsonl').exists())
            (p/'pilot_input.local.jsonl').write_text('{}\n',encoding='utf-8')
            with self.assertRaises(ValueError):web_labels.export_web(p)

    def test_csv_and_jsonl_import(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'r.csv';p.write_text('record_id,predicted_label,reason\na,POS,hay\n',encoding='utf-8-sig')
            self.assertEqual(web_labels.read_predictions(p)[0]['predicted_label'],'POS')
            p=p.with_suffix('.jsonl');p.write_text('{"record_id":"a","predicted_label":"NEU","reason":"info"}\n',encoding='utf-8')
            self.assertEqual(web_labels.read_predictions(p)[0]['predicted_label'],'NEU')


if __name__=='__main__':main()
