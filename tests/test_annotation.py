import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.annotation.core import GUIDELINE, agreement, export_tasks, import_human, load_release, prepared, release
from src.annotation.silver import annotate
from src.annotation.guidelines import GUIDELINE_VERSION, LEGACY_VERSION, LEGACY_SHA256
from src.data.importers import digest
from src.data.pipeline import prepare_data
from src.data.validation import read_jsonl


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        report,_,_=prepare_data(Path('configs/data_fixture.json'),self.root/'data')
        self.version=report['data_version']; self.data=self.root/'data'

    def task(self,name='task',split='train'):
        return export_tasks(self.data,self.version,self.root/name,split=split,count=500)

    def fill(self,task,name='a',label='POS',reverse=False):
        with (task/'blind.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        for row in rows: row.update(status='LABELED',label=label)
        if reverse: rows.reverse()
        path=self.root/(name+'.csv')
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
        out=self.root/(name+'.jsonl')
        import_human(task/'task.json',path,out,name,True)
        return out

    def test_blind_export_no_labels_or_scores_and_id_join(self):
        t=self.task(); events=self.fill(t,reverse=True)
        text=(t/'blind.csv').read_text(encoding='utf-8-sig')
        self.assertNotIn('model_id',text); self.assertNotIn('do_tin',text)
        rows=read_jsonl(events)
        self.assertEqual(len(rows),len(json.loads((t/'task.json').read_text(encoding='utf-8'))['rows']))
        self.assertTrue(all(r['decision']['evidence_mode']=='blind' for r in rows))

    def test_holdout_rejects_assisted_and_edited_text(self):
        task=self.task(split='test')
        self.fill(task)
        with self.assertRaises(ValueError): import_human(task/'task.json',self.root/'a.csv',self.root/'b.jsonl','b',False)
        with (self.root/'a.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        rows[0]['text_raw']='edited'
        with (self.root/'edit.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
        with self.assertRaises(ValueError): import_human(task/'task.json',self.root/'edit.csv',self.root/'c.jsonl','c',True)

    def test_current_guide_and_legacy_task_provenance(self):
        task=self.task()
        path=task/'task.json'
        contract=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(contract['guideline_version'],GUIDELINE_VERSION)
        contract.update(guideline_version=LEGACY_VERSION,guideline_sha256=LEGACY_SHA256)
        path.write_text(json.dumps(contract),encoding='utf-8')
        events=self.fill(task)
        result=release(self.data,self.version,[events],self.root/'legacy')
        meta=load_release(result)[2]
        self.assertEqual(meta['guideline_version'],LEGACY_VERSION)
        self.assertEqual(meta['guideline_sha256'],LEGACY_SHA256)
        current=self.fill(self.task('current'),'current')
        with self.assertRaisesRegex(ValueError,'Mixed guidelines'):
            release(self.data,self.version,[events,current],self.root/'mixed')
        contract['guideline_sha256']='0'*64
        path.write_text(json.dumps(contract),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Guideline'):
            import_human(path,self.root/'a.csv',self.root/'tampered.jsonl','a',True)

    def test_agreement_disagreements_and_adjudication_required(self):
        t=self.task(); a=self.fill(t,'a','POS'); b=self.fill(t,'b','NEG')
        result=agreement(a,b,self.root/'agreement')
        self.assertEqual(result['random']['agreement'],0)
        self.assertEqual(result['random']['kappa'],0)
        self.assertTrue(read_jsonl(self.root/'agreement/disagreements.jsonl'))
        with self.assertRaises(ValueError): release(self.data,self.version,[a,b],self.root/'bad')
        events=read_jsonl(b)
        for e in events: e['decision']['adjudication']=True
        adj=self.root/'adj.jsonl'; adj.write_text(''.join(json.dumps(e)+'\n' for e in events))
        release(self.data,self.version,[a,adj],self.root/'adjudicated')

    def test_release_checksums_draft_ready_and_phase_b_unchanged(self):
        originals={p:p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        train=self.fill(self.task(),'train')
        draft=release(self.data,self.version,[train],self.root/'draft')
        self.assertEqual(load_release(draft)[2]['status'],'draft')
        dev=self.fill(self.task('dev','dev'),'dev'); test=self.fill(self.task('test','test'),'test')
        ready=release(self.data,self.version,[train,dev,test],self.root/'ready')
        records,manifest,meta=load_release(ready)
        self.assertTrue(manifest['locked_gold']); self.assertEqual(meta['status'],'ready')
        self.assertTrue(all(p.read_bytes()==b for p,b in originals.items()))
        with (ready/'records.jsonl').open('a') as f: f.write('{}\n')
        with self.assertRaises(ValueError): load_release(ready)

    def test_hard_holdout_and_usage_rejected(self):
        _,_,manifest=prepared(self.data,self.version)
        rid=next(e['id'] for e in manifest['entries'] if e['eligible_for_annotation'] and e['split']=='test')
        with self.assertRaises(ValueError): export_tasks(self.data,self.version,self.root/'hard',hard_ids=[rid])
        with self.assertRaises(ValueError): release(self.data,self.version,[],self.root/'used',used_ids=[rid])

    def test_silver_replay_resume_train_only_and_permission_guard(self):
        records,_,manifest=prepared(self.data,self.version)
        ids={e['id'] for e in manifest['entries'] if e['split']=='train' and e['eligible_for_annotation']}
        responses=[{'comment_id':r['id'],'label':'POS','reason':'Synthetic fixture response','needs_review':False,'evidence':[]} for r in records if r['id'] in ids]
        (self.root/'responses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in responses))
        cfg=self.root/'provider.json'; cfg.write_text(json.dumps({'kind':'replay','model':'fixture','responses':'responses.jsonl'}))
        out=self.root/'silver'; result=annotate(self.data,self.version,cfg,out,retries=0)
        before=(out/'machine.jsonl').read_bytes()
        self.assertEqual(result['completed'],len(ids))
        self.assertEqual(annotate(self.data,self.version,cfg,out,retries=0),result)
        self.assertEqual((out/'machine.jsonl').read_bytes(),before)
        self.assertTrue(all(not e['decision']['confirmed'] for e in read_jsonl(out/'machine.jsonl')))
        with self.assertRaises(ValueError): release(self.data,self.version,[out/'machine.jsonl'],self.root/'fake_real')
        cfg.write_text(json.dumps({'kind':'command','model':'external','argv':['must-not-run'],'external':True}))
        with self.assertRaisesRegex(ValueError,'permission'): annotate(self.data,self.version,cfg,self.root/'blocked',retries=0)


if __name__=='__main__': unittest.main()
