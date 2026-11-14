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


def workbook(path, rows, formula=False):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; xml=[]
    for i,values in enumerate([p.FIELDS,*[[r[k] for k in p.FIELDS] for r in rows]],1):
        cells=[]
        for j,value in enumerate(values):
            f='<f>1+1</f>' if formula and i==2 and j==2 else ''
            cells.append(f'<c r="{chr(65+j)}{i}" t="inlineStr">{f}<is><t xml:space="preserve">{escape(value)}</t></is></c>')
        xml.append(f'<row r="{i}">{"".join(cells)}</row>')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Gán nhãn" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml)}</sheetData></worksheet>')


class SentimentPilotTests(unittest.TestCase):
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
            self.assertEqual(len(adjudication),1);self.assertEqual(adjudication[0]['label_final'],'')
            self.assertEqual((directory/'sampling_manifest.json').read_bytes(),original_manifest)
            with self.assertRaises(FileExistsError):p.compare(directory)
            (directory/'sampling_manifest.json').write_text('{}',encoding='utf8')
            with self.assertRaises(ValueError):p.verify_manifest(directory)


if __name__=='__main__':unittest.main()
