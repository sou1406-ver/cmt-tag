from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from scripts.import_development_review import import_review, verify_reviewed_dataset
from scripts.prepare_development import grouped_records, load, read_csv, sha, write_csv
from scripts.development_baseline import prepare_or_run
from src.annotation import guidelines
from src.annotation.guidelines import GUIDELINE, GUIDELINE_VERSION, GUIDELINE_SHA256


class DevelopmentReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'prepared';self.source.mkdir()
        rows=[]
        for group in range(9):
            for label,text in [('POS','moving lovely film'),('NEG','weak dull plot'),('NEU','release runtime question')]:
                rows.append(dict(id=f'{group}_{label}',text_raw=f'{text} thread{group}',status='LABELED',label=label,
                                 review_reason='',reason='',source_round='fixture',movie_id=f'movie{group%3}',
                                 post_id=f'post{group}',post_url=f'https://example.test/{group}',comment_id=f'comment{group}_{label}',
                                 parent_comment_id='',selection_cohort='random',source_kind='group',validation_issues='',
                                 audit_pending='',original_guideline_version='V2.0',original_guideline_sha256=guidelines.LEGACY_SHA256))
        rows[6].update(status='REVIEW',label='',validation_issues='MISSING_REVIEW_REASON')
        selected=[rows[1],rows[3],rows[6]]
        for r in selected:r['audit_pending']='LABEL_REVIEW'
        _,_,groups=grouped_records(rows)
        for r in rows:r['group_id']=groups[r['id']]
        self.rows=rows
        self.template=[dict(id=r['id'],source_round='fixture',source_workbook_row=str(rows.index(r)+2),
                            movie_id=r['movie_id'],text_raw=r['text_raw'],current_label=r['label'] or r['status'],
                            proposal='POS',review_note='Synthetic audit suggestion',verified_parent_text='',
                            decision='',label='',review_reason='',reason='') for r in selected]
        write_csv(self.source/'annotations.csv',rows,list(rows[0]))
        write_csv(self.source/'review_decisions.csv',self.template,list(self.template[0]))
        (self.source/'statistics.json').write_text('{}')
        manifest=dict(purpose='exploratory_development_only',rows=len(rows),independent_test=False,
                      active_guideline=dict(version=GUIDELINE_VERSION,sha256=sha(GUIDELINE)),
                      all_human_review_resolved=False,pending_review_ids=[r['id'] for r in selected],
                      output_sha256={p.name:sha(p) for p in self.source.iterdir()})
        (self.source/'manifest.json').write_text(json.dumps(manifest))
        self.original={p.name:p.read_bytes() for p in self.source.iterdir()}

    def decisions(self,review='DEFER'):
        rows=deepcopy(self.template)
        rows[0].update(decision='KEEP')
        rows[1].update(decision='CHANGE',label='NEG',reason='Human explicitly chose NEG')
        rows[2].update(decision=review,reason='Need context' if review=='DEFER' else '',
                       review_reason='REV_CONTEXT' if review=='KEEP' else '')
        return rows

    def csv(self,rows,name='decisions.csv'):
        p=self.root/name;write_csv(p,rows,list(self.template[0]));return p

    def workbook(self,decisions,formula=False,edit_source=False):
        """Minimal XLSX parser fixture; no browser, Excel process or authoring dependency."""
        ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        def sheet(table,header):
            node=ET.Element('worksheet',xmlns=ns);data=ET.SubElement(node,'sheetData')
            for number,values in enumerate(table,header):
                row=ET.SubElement(data,'row',r=str(number))
                for index,value in enumerate(values):
                    c=ET.SubElement(row,'c',r=chr(65+index)+str(number),t='inlineStr')
                    ET.SubElement(ET.SubElement(c,'is'),'t').text=str(value)
                    if formula and header==5 and number==6 and index==5:ET.SubElement(c,'f').text='1+1'
            return ET.tostring(node,encoding='utf-8')
        fields=['source_round','movie_id','text_raw','status','label','review_reason','audit_pending','comment_id',
                'post_id','parent_comment_id','post_url','selection_cohort','id','original_guideline_version']
        snapshot=deepcopy(self.rows)
        if edit_source:snapshot[0]['label']='NEG'
        p=self.root/'decisions.xlsx'
        with zipfile.ZipFile(p,'w') as book:
            book.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Duyet nhan" sheetId="1" r:id="r1"/><sheet name="400 binh luan" sheetId="2" r:id="r2"/></sheets></workbook>')
            book.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
            keys=list(self.template[0])
            book.writestr('xl/worksheets/sheet1.xml',sheet([keys,*[[r[k] for k in keys] for r in decisions]],5))
            book.writestr('xl/worksheets/sheet2.xml',sheet([fields,*[[r[k] for k in fields] for r in snapshot]],1))
        return p

    def test_keep_change_defer_history_and_idempotency(self):
        p=self.csv(list(reversed(self.decisions())))
        out=self.root/'reviewed';result=import_review(self.source,p,out,'a')
        actual={r['id']:r for r in read_csv(out/'annotations.csv')}
        self.assertEqual(actual[self.rows[1]['id']]['label'],'NEG')  # Proposal POS was never applied.
        self.assertEqual(actual[self.rows[3]['id']]['label'],'NEG')
        deferred=actual[self.rows[6]['id']]
        self.assertEqual(deferred['status'],'REVIEW');self.assertEqual(deferred['review_reason'],'')
        self.assertEqual(deferred['validation_issues'],'MISSING_REVIEW_REASON')
        self.assertEqual(deferred['ready_for_development'],'False')
        self.assertTrue(result['all_human_review_resolved']);self.assertEqual(result['pending_review_ids'],[])
        self.assertFalse(result['independent_test']);self.assertFalse(result['models_trained'])
        events=load(out/'review_history.json')
        self.assertEqual(len(events),3)
        self.assertTrue(all(e['evidence_mode']=='assisted' for e in events))
        self.assertEqual(events[1]['previous_event_sha256'],events[0]['event_sha256'])
        before={p:p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertEqual(import_review(self.source,p,out,'a'),result)
        self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))
        self.assertTrue(all((self.source/name).read_bytes()==b for name,b in self.original.items()))
        altered=self.decisions();altered[0]['reason']='A different decision snapshot'
        with self.assertRaises(FileExistsError):import_review(self.source,self.csv(altered,'other.csv'),out,'a')

    def test_excel_header_row_and_explicit_missing_code_completion(self):
        p=self.workbook(self.decisions('KEEP'))
        out=self.root/'reviewed';manifest=import_review(self.source,p,out,'a')
        rows=read_csv(out/'annotations.csv')
        reviewed=next(r for r in rows if r['id']==self.rows[6]['id'])
        self.assertEqual(reviewed['status'],'REVIEW');self.assertEqual(reviewed['review_reason'],'REV_CONTEXT')
        self.assertEqual(reviewed['validation_issues'],'')
        self.assertEqual(reviewed['original_guideline_version'],'V2.0')
        self.assertEqual(reviewed['review_guideline_version'],'V2.1')
        verify_reviewed_dataset(out,rows,manifest)

    def test_missing_invalid_stale_and_invented_decisions_leave_no_output(self):
        variants=[]
        incomplete=self.decisions();incomplete[0]['decision']='';variants.append(incomplete)
        bad=self.decisions();bad[0]['decision']='AUTO';variants.append(bad)
        bad=self.decisions();bad[0]['label']='POS';variants.append(bad)
        bad=self.decisions();bad[1]['reason']='';variants.append(bad)
        bad=self.decisions();bad[1]['text_raw']='edited';variants.append(bad)
        bad=self.decisions();bad[1]['current_label']='NEG';variants.append(bad)
        bad=self.decisions();bad[1]['id']='unknown';variants.append(bad)
        bad=self.decisions();bad[1]=deepcopy(bad[0]);variants.append(bad)
        bad=self.decisions('KEEP');bad[2]['review_reason']='';variants.append(bad)
        bad=self.decisions();bad[2]['label']='NEU';variants.append(bad)
        for index,decisions in enumerate(variants):
            with self.subTest(index=index):
                p=self.csv(decisions,f'bad{index}.csv');out=self.root/f'out{index}'
                with self.assertRaises(ValueError):import_review(self.source,p,out,'a')
                self.assertFalse(out.exists())
        self.assertFalse(list(self.root.glob('.review-*')))

    def test_excel_formula_or_source_sheet_edit_is_rejected(self):
        for formula,source_edit in [(True,False),(False,True)]:
            with self.subTest(formula=formula):
                with self.assertRaises(ValueError):
                    import_review(self.source,self.workbook(self.decisions(),formula,source_edit),self.root/'out','a')

    def baseline_config(self):
        (self.root/'aliases.json').write_text('{"aliases":[]}')
        cfg=dict(dataset=str(self.source),seed=42,folds=3,models=['nb','lr','svm'],variants=['original','masked'],
                 ngram_max=2,class_weight='balanced',top_features=3,mask_lexicon=str(self.root/'aliases.json'))
        p=self.root/'baseline.json';p.write_text(json.dumps(cfg));return p

    def test_real_entrypoint_unlocked_by_fixture_human_receipt_only(self):
        out=self.root/'reviewed';manifest=import_review(self.source,self.csv(self.decisions()),out,'a')
        result=prepare_or_run(self.baseline_config(),self.root/'run',run=True,dataset=out)
        self.assertTrue(result['models_trained']);self.assertTrue(result['ready_to_run'])
        self.assertFalse(result['independent_test'])
        self.assertTrue(all(self.rows[6]['id'] not in f['train_ids']+f['validation_ids'] for f in result['folds']))
        self.assertEqual(len(load(self.root/'run'/'metrics.json')['results']),6)

    def test_flags_or_rehashed_label_edit_cannot_bypass_human_evidence(self):
        cfg=self.baseline_config()
        manifest=load(self.source/'manifest.json');manifest.update(all_human_review_resolved=True,pending_review_ids=[])
        rows=read_csv(self.source/'annotations.csv')
        for r in rows:r.update(audit_pending='',validation_issues='')
        (self.source/'annotations.csv').unlink();write_csv(self.source/'annotations.csv',rows,list(rows[0]))
        manifest['output_sha256']['annotations.csv']=sha(self.source/'annotations.csv')
        (self.source/'manifest.json').write_text(json.dumps(manifest))
        with patch('scripts.development_baseline.model') as estimator:
            with self.assertRaisesRegex(ValueError,'receipt'):prepare_or_run(cfg,self.root/'forged',run=True)
            estimator.assert_not_called()
        # Restore the real parent snapshot, import it, then alter the reviewed label and its checksum.
        for name,payload in self.original.items():(self.source/name).write_bytes(payload)
        out=self.root/'reviewed';result=import_review(self.source,self.csv(self.decisions()),out,'a')
        rows=read_csv(out/'annotations.csv');rows[0]['label']='NEG'
        (out/'annotations.csv').unlink();write_csv(out/'annotations.csv',rows,list(rows[0]))
        result['output_sha256']['annotations.csv']=sha(out/'annotations.csv')
        (out/'manifest.json').write_text(json.dumps(result))
        with patch('scripts.development_baseline.model') as estimator:
            with self.assertRaisesRegex(ValueError,'human decisions'):prepare_or_run(cfg,self.root/'tampered',run=True,dataset=out)
            estimator.assert_not_called()

    def test_guideline_hashes_pinned_and_modified_file_rejected(self):
        self.assertEqual(sha(GUIDELINE),GUIDELINE_SHA256)
        self.assertEqual(sha(guidelines.DIRECTORY/'MOVIE_SENTIMENT_V2_0.md'),guidelines.LEGACY_SHA256)
        modified=self.root/'modified.md';modified.write_bytes(GUIDELINE.read_bytes()+b'changed')
        with patch.object(guidelines,'GUIDELINE',modified):
            with self.assertRaisesRegex(ValueError,'Immutable'):
                guidelines.validate_guideline(GUIDELINE_VERSION,GUIDELINE_SHA256)


if __name__=='__main__':unittest.main()
