import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.sax.saxutils import escape

from src.annotation import sentiment_pilot as p
from src.annotation.pilot import fingerprints, reference_index
from src.dataset.common import digest, sha


def fixture():
    return [dict(comment_id=str(10000+i), post_id=str(100+i//30), source_name='source_'+str(i//150),
                 record_type='reply' if i%2 else 'comment', movie_id='movie_'+str(i//60), text_raw=f'raw {i}',
                 text_clean=f'Text fixture {i} ko rõ?', clean_status='KEEP') for i in range(600)]


def empty_guard():
    return dict(ids=set(), posts=set(), comments=set(), text_hashes=set(), shingles=reference_index([]), checksums={})


def workbook(path, rows, formula=False, fields=None, sheet_name='Gán nhãn'):
    fields=fields or p.FIELDS
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; xml=[]
    for i,values in enumerate([fields,*[[r[k] for k in fields] for r in rows]],1):
        cells=[]
        for j,value in enumerate(values):
            f='<f>1+1</f>' if formula and i==2 and j==2 else ''
            cells.append(f'<c r="{chr(65+j)}{i}" t="inlineStr">{f}<is><t xml:space="preserve">{escape(value)}</t></is></c>')
        xml.append(f'<row r="{i}">{"".join(cells)}</row>')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{sheet_name}" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml)}</sheetData></worksheet>')


class SentimentPilotTests(unittest.TestCase):
    def final_fixture(self, complete=False):
        a=[dict(comment_id=str(i),text_clean=f'Synthetic full pilot {i}',sentiment_label=p.LABELS[i%5],note='context' if i%5==3 else '') for i in range(200)]
        b=copy.deepcopy(a);b[0]['sentiment_label']='NEG'
        selected=p.adjudication_selection(a,b)
        reviews=[dict(**r['data'],review_type=r['review_type'],adjudicator_id='user' if complete else '') for r in selected['rows']]
        if complete:
            for r in reviews:r.update(final_label=r['label_A'],adjudication_note='fixture review')
        return a,b,reviews

    def test_full_200_pending_does_not_inherit_required_labels(self):
        a,b,reviews=self.final_fixture();original=copy.deepcopy((a,b));kappa=p.metrics([r['sentiment_label'] for r in a],[r['sentiment_label'] for r in b])
        rows,summary=p.final_decisions(a,b,reviews)
        self.assertEqual(len(rows),200);self.assertEqual(len({r['comment_id'] for r in rows}),200)
        self.assertEqual(summary['label_sources'],dict(AB_AGREE=179,ADJUDICATED=0,PENDING_REVIEW=21))
        self.assertEqual(summary['status'],'INCOMPLETE_ADJUDICATION')
        required={r['comment_id'] for r in reviews}
        self.assertTrue(all(not r['final_label'] for r in rows if r['comment_id'] in required))
        self.assertTrue(all(r['final_label']==r['label_A']==r['label_B'] for r in rows if r['comment_id'] not in required))
        self.assertEqual((a,b),original)
        self.assertEqual(p.metrics([r['sentiment_label'] for r in a],[r['sentiment_label'] for r in b]),kappa)

    def test_full_200_complete_keeps_changed_agreement_provenance(self):
        a,b,reviews=self.final_fixture(complete=True)
        agreement=next(r for r in reviews if r['review_type']=='AGREEMENT_AUDIT')
        agreement['final_label']='NEG' if agreement['label_A']!='NEG' else 'POS'
        rows,summary=p.final_decisions(a,b,reviews)
        self.assertEqual(summary['status'],'PILOT_ADJUDICATION_COMPLETE')
        self.assertEqual(summary['label_sources'],dict(AB_AGREE=179,ADJUDICATED=21,PENDING_REVIEW=0))
        self.assertEqual(sum(summary['final_label_counts'].values()),200)
        self.assertEqual(summary['trainable']+summary['review_exclude'],200)
        self.assertEqual(summary['changed_agreements'],1)
        actual=next(r for r in rows if r['comment_id']==agreement['comment_id'])
        self.assertEqual(actual['label_A'],actual['label_B']);self.assertNotEqual(actual['final_label'],actual['label_A'])
        self.assertEqual(actual['adjudicator_id'],'user');self.assertEqual(actual['label_source'],'ADJUDICATED')

    def test_full_partial_disagreement_and_audited_agreement_stay_pending(self):
        a,b,reviews=self.final_fixture(complete=True)
        reviews[0]['final_label']=''
        next(r for r in reviews if r['review_type']=='AGREEMENT_AUDIT')['final_label']=''
        rows,summary=p.final_decisions(a,b,reviews)
        self.assertEqual(summary['label_sources']['PENDING_REVIEW'],2)
        self.assertEqual(summary['status'],'INCOMPLETE_ADJUDICATION')
        self.assertTrue(all(not r['adjudicator_id'] for r in rows if r['label_source']=='PENDING_REVIEW'))

    def test_full_merge_rejects_identity_source_edits_and_review_without_note(self):
        a,b,reviews=self.final_fixture(complete=True)
        for kind in ('missing_ab','duplicate_ab','unknown_review','duplicate_review','missing_disagreement','text','label_A','review_note'):
            left,right,decisions=copy.deepcopy((a,b,reviews))
            if kind=='missing_ab':right.pop()
            if kind=='duplicate_ab':left.append(left[0])
            if kind=='unknown_review':decisions[0]['comment_id']='unknown'
            if kind=='duplicate_review':decisions.append(decisions[0])
            if kind=='missing_disagreement':decisions.pop(0)
            if kind=='text':decisions[0]['text_clean']+=' edited'
            if kind=='label_A':decisions[0]['label_A']='EXCLUDE'
            if kind=='review_note':decisions[0].update(final_label='REVIEW',adjudication_note='')
            with self.subTest(kind=kind),self.assertRaises(ValueError):p.final_decisions(left,right,decisions)

    def test_adjudication_keeps_all_disagreements_and_random_agreement_audit(self):
        a=[dict(comment_id=str(i),text_clean=f'Synthetic {i}',sentiment_label='POS',note='') for i in range(100)]
        b=copy.deepcopy(a)
        for i in range(7):b[i]['sentiment_label']='NEG'
        before=copy.deepcopy((a,b));r=p.adjudication_selection(a,b)
        self.assertEqual(r['disagreements'],7);self.assertEqual(r['agreement_audit_selected'],20)
        self.assertEqual(len(r['rows']),27);self.assertEqual((a,b),before)
        self.assertTrue(all(not row['data']['final_label'] and not row['data']['adjudication_note'] for row in r['rows']))
        self.assertEqual({row['data']['comment_id'] for row in r['rows'] if row['review_type']=='DISAGREEMENT'},set(map(str,range(7))))
        reversed_rows=p.adjudication_selection(a[::-1],b[::-1])
        self.assertEqual({x['data']['comment_id'] for x in r['rows']},{x['data']['comment_id'] for x in reversed_rows['rows']})
        self.assertEqual(p.adjudication_selection(a,b),r)
        self.assertEqual(p.adjudication_selection(a[:3],a[:3])['agreement_audit_selected'],3)
        self.assertEqual(p.adjudication_selection(a,a,0)['rows'],[])
        self.assertEqual(p.adjudication_selection(a,b,0)['disagreements'],7)
        with self.assertRaises(ValueError):p.adjudication_selection(a,b,-1)

    def test_official_and_proposal_are_distinct_no_automatic_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            official=Path(tmp)/'SENTIMENT_GUIDELINE_V3_1.md'
            proposal=Path(tmp)/'SENTIMENT_GUIDELINE_V3_1_PROPOSED.md'
            proposal.write_text('Synthetic proposed guideline',encoding='utf8')
            with patch.object(p,'OFFICIAL',official),patch.object(p,'PROPOSAL',proposal),patch.object(p,'APPROVED_GUIDELINE_SHA256',None):
                contract=p.guideline_contract()
                self.assertEqual(contract['status'],'DRAFT_GUIDELINE_SOURCE_MISSING')
                self.assertEqual(contract['guideline_status'],'PROPOSAL_NOT_APPROVED')
                official.write_bytes(b'Synthetic official guideline supplied by user\r\n')
                before=official.read_bytes()
                self.assertEqual(p.guideline_contract()['guideline_status'],'OFFICIAL_PENDING_VERIFICATION')
                with patch.object(p,'APPROVED_GUIDELINE_SHA256',sha(official)):
                    contract=p.guideline_contract()
                    self.assertEqual(contract['status'],'READY')
                    self.assertEqual(contract['guideline_status'],'APPROVED_FOR_PILOT')
                    self.assertEqual(contract['guideline_sha256'],sha(official))
                    official.write_bytes(before+b'changed')
                    with self.assertRaises(ValueError):p.guideline_contract()
                    official.write_bytes(before)
                self.assertEqual(official.read_bytes(),before)
                self.assertEqual(proposal.read_text(encoding='utf8'),'Synthetic proposed guideline')
                official.write_bytes(b'')
                with self.assertRaises(FileNotFoundError):p.guideline_contract()

    def test_determinism_cohorts_and_no_labels(self):
        rows=fixture(); original=copy.deepcopy(rows)
        a,strata=p.select(rows); b,_=p.select(rows[::-1])
        self.assertEqual(a,b);self.assertEqual(rows,original)
        self.assertEqual(len(a),200);self.assertEqual(len({r['comment_id'] for r in a}),200)
        self.assertEqual(sum(r['sample_type']=='random' for r in a),160)
        self.assertEqual(sum(r['sample_type']=='hard' for r in a),40)
        self.assertTrue(all(r['n']>=1 for r in strata))
        self.assertTrue(all('sentiment_label' not in r for r in a))

    def test_protection_identity_exact_near_and_clean_status(self):
        rows=fixture()[:8];guard=empty_guard()
        guard['posts'].add(rows[0]['post_id'])
        # Separate post IDs to test each rejection independently.
        for i,r in enumerate(rows):r['post_id']=str(100+i)
        guard['comments'].add(rows[1]['comment_id'])
        guard['text_hashes'].add(digest(p.normal(rows[2]['text_clean'])))
        text='Đây là một nội dung rất dài đủ để tạo nhiều shingle từ khác nhau cho kiểm tra trùng lặp chắc chắn'
        rows[3]['text_clean']=text
        guard['shingles']=reference_index([fingerprints(text)])
        rows[4]['clean_status']='REVIEW';rows[5]['text_clean']='';rows[6]['text_clean']=rows[7]['text_clean']
        pool,rejected=p.eligible(rows,guard)
        self.assertEqual(len(pool),1)
        reasons={r['reason'] for r in rejected}
        self.assertTrue({'TEST_RESERVED_HOLDOUT_IDENTITY','EXACT_RESERVED_TEXT','NEAR_RESERVED_TEXT','EXACT_WITHIN_BATCH','CLEAN_STATUS_NOT_KEEP','EMPTY_CLEAN'}<=reasons)

    def test_kappa_manual_example_and_review_disagreement(self):
        r=p.metrics(p.LABELS,['POS','NEG','NEU','NEU','EXCLUDE'])
        self.assertAlmostEqual(r['kappa'],.75);self.assertAlmostEqual(r['agreement'],.8)
        self.assertEqual(r['sentiment_pair_count'],3);self.assertEqual(r['sentiment_retention'],.6)
        self.assertEqual(r['sentiment_only']['kappa'],1.)
        self.assertEqual(r['review_exclude_disagreements'],1)
        self.assertEqual(r['confusion_matrix'][3][2],1)

    def test_agreement_and_pos_neg_disagreement(self):
        labels=p.LABELS*2
        self.assertEqual(p.metrics(labels,labels)['kappa'],1.)
        r=p.metrics(['POS','NEG'],['NEG','POS'])
        self.assertEqual(r['kappa'],-1.);self.assertEqual(r['sentiment_only']['kappa'],-1.)

    def test_degenerate_and_insufficient_kappa(self):
        self.assertIsNone(p.metrics([],[])['kappa'])
        r=p.metrics(['POS','POS'],['POS','POS'])
        self.assertIsNone(r['kappa']);self.assertEqual(r['sentiment_only']['kappa_reason'],'SINGLE_OBSERVED_CLASS')
        r=p.metrics(['REVIEW','NEG'],['NEU','REVIEW'])
        self.assertIsNone(r['sentiment_only']);self.assertEqual(r['sentiment_pair_count'],0)
        self.assertEqual(r['sentiment_kappa_reason'],'NO_SENTIMENT_PAIRS')
        self.assertIsNone(p.metrics(['POS'],['NEG'])['sentiment_only']['kappa'])

    def test_workbook_validation(self):
        values=[dict(comment_id=str(i),text_clean=f'Đúng nguyên văn :)) {i}',sentiment_label=label,
                     note='thiếu ngữ cảnh' if label=='REVIEW' else '',annotator_id='A',cleaning_issue='') for i,label in enumerate(p.LABELS)]
        m=dict(selected_rows=[dict(comment_id=r['comment_id'],text_sha256=digest(r['text_clean'])) for r in values])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.xlsx';workbook(path,values)
            self.assertEqual(p.read_labels(path,m,'A'),values)
            for kind in ('missing_note','id','text','duplicate','missing','empty_id_row','invalid_label','annotator','formula'):
                rows=copy.deepcopy(values)
                if kind=='missing_note':rows[3]['note']=''
                if kind=='id':rows[0]['comment_id']='changed'
                if kind=='text':rows[0]['text_clean']+=' '
                if kind=='duplicate':rows.append(rows[0])
                if kind=='missing':rows.pop()
                if kind=='empty_id_row':rows.append({**rows[0],'comment_id':''})
                if kind=='invalid_label':rows[0]['sentiment_label']='MIXED'
                if kind=='annotator':rows[0]['annotator_id']='B'
                workbook(path,rows,formula=kind=='formula')
                with self.subTest(kind=kind),self.assertRaises(ValueError):p.read_labels(path,m,'A')

    def test_prepare_compare_fixture_immutable_and_no_auto_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.csv';directory=root/'pilot'
            rows=fixture()
            with source.open('w',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=source.read_bytes()
            with patch.object(p,'protection',return_value=empty_guard()),patch.object(p,'assert_allowed'),patch.object(Path,'glob',return_value=iter([root/'fixture_registry.json'])):
                result=p.prepare(source,directory)
            self.assertEqual(result['selected'],200);self.assertEqual(source.read_bytes(),before)
            m=p.verify_manifest(directory);original_manifest=(directory/'sampling_manifest.json').read_bytes()
            input_rows=json.loads((directory/'workbook_input.local.json').read_text(encoding='utf8'))
            for person in ('A','B'):
                annotated=[dict(**r,sentiment_label=p.LABELS[i%5],note='context' if i%5==3 else '',annotator_id=person,cleaning_issue='') for i,r in enumerate(input_rows)]
                if person=='B':annotated[0]['sentiment_label']='NEG'
                workbook(directory/f'pilot_sentiment_annotator_{person}.xlsx',annotated)
            out=p.compare(directory)
            self.assertEqual(out['n'],200)
            self.assertTrue((directory/'comparison/annotator_A.local.jsonl').is_file())
            with (directory/'comparison/adjudication.local.csv').open(encoding='utf-8-sig') as f:
                adjudication=list(csv.DictReader(f))
            self.assertEqual(len(adjudication),21)
            self.assertEqual(list(adjudication[0]),p.ADJUDICATION_FIELDS)
            self.assertTrue(all(not r['final_label'] for r in adjudication))
            self.assertEqual(adjudication[0]['label_A'],'POS');self.assertEqual(adjudication[0]['label_B'],'NEG')
            frozen={str(file):sha(file) for file in [directory/'pilot_sentiment_annotator_A.xlsx',directory/'pilot_sentiment_annotator_B.xlsx',directory/'comparison/agreement.json']}
            for row in adjudication:
                row['final_label']=row['label_A'];row['adjudication_note']='fixture adjudicator decision'
            adjudication[0]['final_label']='NEU'
            decisions=directory/'filled.csv'
            def decisions_csv(rows):
                with decisions.open('w',encoding='utf-8-sig',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=p.ADJUDICATION_FIELDS);w.writeheader();w.writerows(rows)
            decisions_csv(adjudication)
            imported=p.import_adjudication(directory,directory/'comparison',decisions)
            self.assertEqual(imported['label_sources']['ADJUDICATED'],21);self.assertEqual(imported['label_sources']['AB_AGREE'],179)
            self.assertEqual(imported['status'],'PILOT_ADJUDICATION_COMPLETE')
            with (directory/'comparison/adjudicated/pilot_final_decisions.local.csv').open(encoding='utf-8-sig') as f:full=list(csv.DictReader(f))
            with (directory/'comparison/adjudicated/pilot_trainable.local.csv').open(encoding='utf-8-sig') as f:train=list(csv.DictReader(f))
            self.assertEqual(len(full),200);self.assertEqual(len({r['comment_id'] for r in full}),200)
            self.assertEqual({r['comment_id'] for r in full},{r['comment_id'] for r in input_rows})
            self.assertTrue(all(r['final_label'] in p.LABELS[:3] and r['label_source']!='PENDING_REVIEW' for r in train))
            self.assertEqual(len(train),imported['trainable'])
            self.assertEqual({str(file):sha(file) for file in map(Path,frozen)},frozen)
            self.assertEqual(json.loads((directory/'comparison/agreement.json').read_text())['kappa'],out['kappa'])
            partial=copy.deepcopy(adjudication);partial[0]['final_label']='';partial[1]['final_label']=''
            decisions_csv(partial)
            partial_summary=p.import_adjudication(directory,directory/'comparison',decisions,root/'partial')
            self.assertEqual(partial_summary['label_sources']['PENDING_REVIEW'],2)
            self.assertEqual(partial_summary['status'],'INCOMPLETE_ADJUDICATION')
            with (root/'partial/pilot_trainable.local.csv').open(encoding='utf-8-sig') as f:partial_train=list(csv.DictReader(f))
            self.assertFalse({partial[0]['comment_id'],partial[1]['comment_id']}&{r['comment_id'] for r in partial_train})
            for issue in ('text','label_A','note_B','id','missing','duplicate','invalid_final','review_note'):
                changed=copy.deepcopy(adjudication)
                if issue=='text':changed[0]['text_clean']+=' edit'
                if issue=='label_A':changed[0]['label_A']='EXCLUDE'
                if issue=='note_B':changed[0]['note_B']='changed original note'
                if issue=='id':changed[0]['comment_id']='wrong'
                if issue=='missing':changed.pop()
                if issue=='duplicate':changed.append(changed[0])
                if issue=='invalid_final':changed[0]['final_label']='MIXED'
                if issue=='review_note':changed[0].update(final_label='REVIEW',adjudication_note='')
                decisions_csv(changed)
                with self.subTest(issue=issue),self.assertRaises(ValueError):p.import_adjudication(directory,directory/'comparison',decisions,root/'invalid')
                self.assertFalse((root/'invalid').exists())
            review_xlsx=directory/'filled.xlsx'
            workbook(review_xlsx,adjudication,fields=p.ADJUDICATION_FIELDS,sheet_name='Đối soát')
            self.assertEqual(p.import_adjudication(directory,directory/'comparison',review_xlsx,root/'xlsx_review')['label_sources']['ADJUDICATED'],21)
            self.assertEqual((directory/'sampling_manifest.json').read_bytes(),original_manifest)
            with self.assertRaises(FileExistsError):p.compare(directory)
            (directory/'sampling_manifest.json').write_text('{}',encoding='utf8')
            with self.assertRaises(ValueError):p.verify_manifest(directory)


if __name__=='__main__':unittest.main()
