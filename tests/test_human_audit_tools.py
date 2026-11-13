"""Local diagnostics/import/plan tests, without actual friend workbook or fit."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch

from tests.test_ai_pilot import fixture,response
from src.annotation import pilot,web_labels
from src.annotation.audit import analyze_errors,import_friend,label_error
from src.annotation.gold import workbook
from src.annotation.guidelines import GUIDELINE
from src.dataset.common import load,save,sha,digest,read_jsonl,write_jsonl
from src.models.human_expansion import additional_fold_rows


def friend_fixture(p):
    items=fixture(p);owner=[dict(id='id2',text=items[2]['text'],text_sha256=digest(items[2]['text']))]
    save(p/'audit_coordinator.local.json',dict(rows=owner))
    refs=[dict(id=r['record_id'],text=r['text'],text_sha256=digest(r['text'])) for r in items[3:]]
    file=p/'friend.xlsx';workbook(file,[dict(id=r['id'],text=r['text'],label=['POS','REVIEW','EXCLUDE'][i],note='') for i,r in enumerate(refs)])
    save(p/'friend_task.local.json',dict(rows=refs,workbook=str(file),selection_manifest_sha256=sha(p/'selection_manifest.json'),
        guideline_sha256=sha(GUIDELINE),owner_audit_coordinator_sha256=sha(p/'audit_coordinator.local.json')))
    return file,refs


class HumanAuditToolsTests(TestCase):
    def test_label_error_categories_are_not_semantic_claims(self):
        self.assertEqual(label_error('EXCLUDE','POS'),'AI_SENTIMENT_ON_HUMAN_EXCLUDE')
        self.assertEqual(label_error('NEU','POS'),'AI_POLARITY_ON_HUMAN_NEU')
        self.assertEqual(label_error('POS','NEG'),'POS_NEG_REVERSAL')
        self.assertEqual(label_error('POS','REVIEW'),'AI_ABSTAIN_ON_HUMAN_SENTIMENT')

    def test_error_analysis_no_label_mutation_and_only_local_examples(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p)
            for provider in web_labels.SLOTS:web_labels.import_web(p,provider,response(p/(provider+'.json'),items))
            pilot.summarize(p)
            coord=load(p/'audit_coordinator.local.json')
            rows=[dict(id=r['id'],text=r['text'],label='POS' if i==0 else 'NEU',note='') for i,r in enumerate(coord['rows'])]
            write_jsonl(p/'human_audit.local.jsonl',rows);before=sha(p/'human_audit.local.jsonl')
            report=analyze_errors(p,p/'errors')
            self.assertEqual(report['n'],4);self.assertEqual(report['unanimous']['matched'],1)
            self.assertEqual(sha(p/'human_audit.local.jsonl'),before)
            self.assertFalse(report['silver_approved']);self.assertFalse(report['gold_used'])
            self.assertTrue(all(not r['semantic_error_cause_confirmed'] for r in read_jsonl(p/'errors/errors.local.jsonl')))
            with self.assertRaises(ValueError):analyze_errors(p,p.parent/'outside')

    def test_owner_import_repeat_or_revision_never_overwrites_history(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);items=fixture(p)
            for provider in web_labels.SLOTS:web_labels.import_web(p,provider,response(p/(provider+'.json'),items))
            pilot.summarize(p);coord=load(p/'audit_coordinator.local.json')
            file=p/'review_blind.xlsx';file.unlink()
            rows=[dict(id=r['id'],text=r['text'],label='POS',note='') for r in coord['rows']]
            workbook(file,rows);pilot.import_audit(p)
            before=sha(p/'human_audit.local.jsonl')
            self.assertTrue(pilot.import_audit(p)['already_imported'])
            file.unlink();rows[0]['label']='NEG';workbook(file,rows)
            with self.assertRaises(FileExistsError):pilot.import_audit(p)
            self.assertEqual(sha(p/'human_audit.local.jsonl'),before)

    def test_friend_import_origin_receipt_and_idempotence(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);f,refs=friend_fixture(p);before=sha(f)
            result=import_friend(p,'friend','human')
            self.assertTrue(result['human_confirmed']);self.assertEqual(result['records'],3)
            self.assertTrue(import_friend(p,'friend','human')['already_imported'])
            self.assertEqual(sha(f),before)
            self.assertFalse(load(p/'friend_import/receipt.json')['approved_release'])
            ai=import_friend(p,'chatbot','ai',output=p/'ai_copy')
            self.assertFalse(ai['human_confirmed'])
            self.assertTrue(all(r['label_scope']=='AI_SUGGESTION' for r in read_jsonl(p/'ai_copy/decisions.local.jsonl')))

    def test_friend_missing_labels_edited_text_and_overlap_refused(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);file,refs=friend_fixture(p)
            for rows in [refs[:2], [dict(r,text='changed') for r in refs], [dict(r,label='INVALID') for r in refs]]:
                file.unlink()
                workbook(file,[dict(id=r['id'],text=r['text'],label=r.get('label','POS'),note='') for r in rows])
                with self.assertRaises(ValueError):import_friend(p,'friend','human')
            c=load(p/'friend_task.local.json');c['rows'][0]['id']='id2'
            (p/'friend_task.local.json').write_text(__import__('json').dumps(c),encoding='utf-8')
            with self.assertRaises(ValueError):import_friend(p,'friend','human')
            self.assertFalse((p/'friend_import').exists())

    def base_plan(self):
        base=[dict(record_id='b'+str(i),source_dataset='facebook',post_id=str(100+i),post_url='https://www.facebook.com/p/posts/'+str(100+i),
                   comment_id=str(i+10),text='base'+str(i),label='POS') for i in range(6)]
        plan=dict(ids=[r['record_id'] for r in base],folds=[])
        for fold in range(5):
            va=[i for i in range(6) if i%5==fold]
            plan['folds'].append(dict(seed=42,fold=fold,train=[i for i in range(6) if i not in va],validation=va))
        return base,plan

    def test_paired_plan_holds_post_and_never_fits(self):
        base,plan=self.base_plan();extra=[dict(base[0],record_id='new',text='new text')]
        with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No fit allowed')):
            folds=additional_fold_rows(base,extra,plan)
        for f in folds:
            self.assertEqual(f['validation_ids'],[plan['ids'][i] for i in plan['folds'][f['fold']]['validation']])
            self.assertFalse(set(f['validation_ids'])&set(f['augmented_train_ids']))
        self.assertIn('new',folds[0]['additional_held_ids'])
        self.assertNotIn('new',folds[0]['augmented_train_ids'])

    def test_duplicate_validation_and_frozen_post_leak_blocked(self):
        base,plan=self.base_plan();extra=[dict(base[0],record_id='new',post_id='999',post_url='https://www.facebook.com/p/posts/999',text='base0')]
        folds=additional_fold_rows(base,extra,plan)
        self.assertNotIn('new',folds[0]['augmented_train_ids'])
        base[1].update(post_id=base[0]['post_id'],post_url=base[0]['post_url'])
        with self.assertRaises(ValueError):additional_fold_rows(base,[],plan)


if __name__=='__main__':main()
