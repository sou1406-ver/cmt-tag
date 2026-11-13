"""Manual web pilot fixtures. No HTTP calls, real gold or credentials."""
import json
import random
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch

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
    def test_expansion_returns_unread_assignment_and_reuses_web_import(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);previous=root/'outputs/ai_labeling/previous';previous.mkdir(parents=True)
            items=fixture(previous)
            write_jsonl(previous/'human_audit.local.jsonl',[dict(id='id2',label='POS')])
            save(previous/'human_audit_receipt.local.json',dict(human_decisions_sha256=sha(previous/'human_audit.local.jsonl')))
            save(previous/'friend_task.local.json',dict(rows=[dict(id='id'+str(i)) for i in (3,4,5)],
                selection_manifest_sha256=sha(previous/'selection_manifest.json'),workbook='DO_NOT_OPEN.xlsx'))
            source=root/'outputs/source';source.mkdir()
            rows=[]
            for i in range(90):
                rows.append(dict(record_id='id'+str(i),source_dataset='facebook',post_id=str(i//15),movie_id=str(i//45),
                    comment_id=str(i),text_raw='short movie '+str(i),text_minimal='short movie '+str(i),
                    text_annotation_view='short movie '+str(i),quality_decision='KEEP',annotation_eligibility='ELIGIBLE_PROPOSED',
                    human_decisions=[{'label':'POS'}] if i<2 else [],human_label='POS' if i<2 else None))
            rows += [dict(rows[-1],record_id='legacy',source_dataset='legacy_29k_unverified'),
                     dict(rows[-1],record_id='reserved',post_id='reserved')]
            write_jsonl(source/'candidate.local.jsonl',rows);save(source/'protected_inputs.local.json',{});seal(source,dict(kind='FIXTURE'))
            guard=dict(ids=set(),posts={'reserved'},comments=set(),text_hashes=set(),shingles=pilot.reference_index([]),checksums={})
            output=root/'outputs/ai_labeling/expansion'
            before=sha(previous/'human_audit.local.jsonl')
            with patch.object(pilot,'protection',return_value=guard),patch('src.data.quality.verified_post',return_value=True):
                report=pilot.prepare_expansion(output,source,previous,root)
            self.assertEqual(report['returned_assignment'],3)
            self.assertEqual(report['returned_in_web'],3)
            self.assertEqual(report['legacy_unlabeled_local_only'],1)
            self.assertEqual(sha(previous/'human_audit.local.jsonl'),before)
            self.assertEqual(load(previous/'friend_assignment_status.json')['status'],'RETURNED_TO_UNLABELED')
            selected=[]
            for batch in sorted(output.glob('batch_*')):
                _,part,c=pilot.task(batch);selected.extend(r['record_id'] for r in part)
                self.assertFalse(c['calibration_labels'])
                self.assertLessEqual(len(part),600)
                self.assertTrue(all(set(r)=={'record_id','text'} for r in load(batch/f'web_upload/{batch.name}_comments_{len(part)}.json')))
            self.assertEqual(len(selected),len(set(selected)))
            self.assertFalse({'id0','id1','id2','reserved','legacy'}&set(selected))
            first=next(output.glob('batch_*'));part=read_jsonl(first/'pilot_input.local.jsonl')
            for provider in web_labels.SLOTS:web_labels.import_web(first,provider,response(root/(provider+'.json'),part))
            agreement=pilot.summarize(first)
            self.assertEqual(agreement['calibration']['GPT']['n'],0)
            self.assertIsNone(agreement['calibration']['consensus_3_of_3']['coverage'])
            from src.dataset.common import verify
            verify(output)
            from src.annotation.audit import import_friend
            with self.assertRaisesRegex(ValueError,'returned to unlabeled'):import_friend(previous,'friend','human')

    def test_expansion_full_corpus_batches_are_seeded_and_no_post_cap(self):
        rows=[dict(record_id=str(i),post_id=str(i%3)) for i in range(1249)]
        a=pilot.expansion_batches(rows)
        self.assertEqual(a,pilot.expansion_batches(list(reversed(rows))))
        self.assertEqual([len(b) for b in a],[600,600,49])
        self.assertEqual(len({r['record_id'] for b in a for r in b}),1249)
        self.assertGreater(max(Counter(r['post_id'] for r in a[0]).values()),12)

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
