import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

from src.dataset.common import load,save,seal,sha,verify,write_csv,write_jsonl
from src.dataset.legacy_audit import audit,near_groups,quality,select
from scripts.import_legacy_train_annotations import import_labels
from src.dataset.blind import BLIND_FIELDS


class LegacyAuditTests(unittest.TestCase):
    def test_short_or_no_movie_keyword_is_not_discarded(self):
        for text in ('hay','không phải vậy','tui khóc suốt','bình thường'):
            self.assertNotEqual(quality(text,'pos')['trust_status'],'EXCLUDE')
        self.assertEqual(quality('https://example.com','neu')['trust_status'],'EXCLUDE')

    def test_ambiguous_spam_emoji_corruption_remains_review_not_auto_sentiment(self):
        self.assertEqual(quality('inbox zalo 0912345678','pos')['trust_status'],'NEEDS_REVIEW')
        self.assertEqual(quality('😭','neg')['trust_status'],'NEEDS_REVIEW')
        self.assertEqual(quality('text\ufffd','pos')['trust_status'],'NEEDS_REVIEW')
        self.assertEqual(quality('phim hay','pos')['trust_status'],'LEGACY_LABELED_UNVERIFIED')

    def pool(self):
        return [dict(id=str(i),group_id='master'+str(i//2),text_view='fixture '+str(i),
            train_candidate=True,positive_cues=i%3,neutral_cues=i%4,hard_cues=i%5,legacy_label='pos') for i in range(60)]

    def test_dedup_groups_are_transitive_and_one_candidate_per_component(self):
        rows=self.pool();near_groups(rows,dict(threshold=.9,min_chars=40,shingle_size=3))
        chosen=select(rows,25,42)
        self.assertEqual(len(chosen),25);self.assertEqual(len({r['annotation_group'] for r in chosen}),25)

    def test_sampling_is_deterministic_and_blind_to_legacy_labels(self):
        rows=self.pool();near_groups(rows,dict(threshold=.9,min_chars=40,shingle_size=3))
        a=select(rows,25,42);changed=copy.deepcopy(list(reversed(rows)))
        for r in changed:r['legacy_label']='neg'
        self.assertEqual([r['id'] for r in a],[r['id'] for r in select(changed,25,42)])
        self.assertEqual(select(rows,0,42),[])

    def test_excluded_or_quarantined_candidates_never_selected(self):
        rows=self.pool();near_groups(rows,dict(threshold=.9,min_chars=40,shingle_size=3))
        for r in rows[:10]:r['train_candidate']=False
        self.assertFalse({r['id'] for r in select(rows,20,42)} & {r['id'] for r in rows[:10]})

    def test_real_audit_contract_preserves_source_and_never_recovers_identity_from_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'legacy.csv';master=root/'master';master.mkdir()
            originals=[dict(id=str(i),comment=t,overall='pos') for i,t in enumerate(['hay quá','không phải vậy','bình thường','https://example.com'])]
            write_csv(source,originals,['id','comment','overall']);source_sha=sha(source)
            records=[dict(id='m'+str(i),group_id='g'+str(i),exposure_status='unknown_not_attested_unused',
                observations=[dict(input_sha256=source_sha,source_file='../legacy.csv',source_row=i+1,text_raw=r['comment'],original_label=r['overall'])]) for i,r in enumerate(originals)]
            write_jsonl(master/'master.jsonl',records);seal(master,dict(input_sha256={}))
            dev=root/'dev.csv';write_csv(dev,[dict(id='d1',text_raw='hay quá')],['id','text_raw'])
            cfg=root/'cfg.json';save(cfg,dict(input=str(source),input_sha256=source_sha,expected_rows=4,master_root=str(master),
                master_manifest_sha256=sha(master/'manifest.json'),master_source_file='../legacy.csv',development_csv=str(dev),annotation_count=2,
                seed=42,near_duplicate=dict(threshold=.9,min_chars=40,shingle_size=3)))
            with patch('src.dataset.legacy_audit.reservation_contracts',return_value=[]):report,result=audit(cfg,root/'out')
            self.assertEqual(sha(source),source_sha);self.assertEqual(report['exact_content_overlap_development'],1)
            self.assertEqual(report['verified_movies'],0);self.assertEqual(report['identity_verified_agreement_pairs'],0)
            self.assertEqual(report['independent_test_candidates'],0);self.assertFalse(result['gold_created'])
            task=load(root/'out/workbook_input.json')
            self.assertTrue(all(set(r)==set(BLIND_FIELDS) and not r['label'] for r in task))

    def test_import_keeps_review_exclude_and_cannot_create_gold(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);task=root/'task';coordinator=task/'coordinator';coordinator.mkdir(parents=True)
            rows=[dict(id=str(i),text_view='fixture'+str(i),status='',label='',review_reason='',reason='') for i in range(3)]
            save(coordinator/'task.json',dict(rows=rows,guideline_version='V2.1',guideline_sha256='fixture'))
            save(coordinator/'coordinator_mapping.json',rows);seal(task,dict(status='READY_FOR_HUMAN_TRAIN_ANNOTATION'))
            decisions=copy.deepcopy(rows);decisions[0]['label']='POS';decisions[1].update(label='REVIEW',review_reason='REV_CONTEXT');decisions[2].update(label='EXCLUDE',reason='Off topic')
            path=root/'labels.csv';write_csv(path,decisions,BLIND_FIELDS)
            r=import_labels(task,path,root/'imported','fixture_annotator')
            self.assertEqual((r['sentiment'],r['review'],r['excluded']),(1,1,1));self.assertFalse(r['gold_created'])
            write_csv(root/'blank.csv',rows,BLIND_FIELDS)
            with self.assertRaises(ValueError):import_labels(task,root/'blank.csv',root/'bad','fixture')

    def test_editing_workbook_in_place_is_allowed_but_coordinator_tampering_is_not(self):
        from test_blind_workbooks import fixture
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);task=root/'task';coordinator=task/'coordinator';coordinator.mkdir(parents=True)
            workbook=task/'legacy_train_candidates.xlsx';rows=fixture(workbook)
            save(coordinator/'task.json',dict(rows=rows,guideline_version='V2.1',guideline_sha256='fixture'))
            save(coordinator/'coordinator_mapping.json',rows);seal(task,dict(status='READY_FOR_HUMAN_TRAIN_ANNOTATION'))
            with zipfile.ZipFile(workbook) as z:parts={name:z.read(name) for name in z.namelist()}
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            xml=ET.fromstring(parts['xl/worksheets/sheet1.xml'])
            xml.find('.//s:c[@r="D2"]/s:is/s:t',ns).text='POS'
            parts['xl/worksheets/sheet1.xml']=ET.tostring(xml,encoding='utf-8')
            with zipfile.ZipFile(workbook,'w') as z:
                for name,payload in parts.items():z.writestr(name,payload)
            with self.assertRaises(ValueError):verify(task) # default verification remains immutable
            self.assertEqual(import_labels(task,workbook,root/'imported','fixture')['sentiment'],1)
            with (coordinator/'task.json').open('a') as f:f.write(' ')
            with self.assertRaises(ValueError):import_labels(task,workbook,root/'bad','fixture')


if __name__=='__main__':unittest.main()
