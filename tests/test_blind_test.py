from collections import Counter
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.dataset.blind import assert_allowed, eligible, prepare, sample, validate_selection
from src.dataset.common import load, save, seal, sha, write_jsonl
from scripts.import_blind_annotations import import_labels
from src.dataset.common import write_csv
from src.dataset.blind import BLIND_FIELDS


def candidates(posts=24, comments=14):
    return [dict(id=f'c{post:02}_{i:02}',comment_id=str(post*1000+i+1),post_id=str(post),
        post_url=f'https://www.facebook.com/groups/g/posts/{post}',movie_id=f'm{post//2}',
        group_id=f'g{post}',text_raw=f'fixture {post} {i}',text_view=f'fixture {post} {i}',
        text_variants=[f'fixture {post} {i}'],source_platform='facebook',review_flags=[],
        development=False,development_ids=[],human_decisions=[],annotation_status='UNLABELED',
        exposure_status='unknown_not_attested_unused') for post in range(posts) for i in range(comments)]


def attest(rows):
    posts={r['post_id']:r for r in rows}
    return dict(known_exposed_post_ids=[],attested_unused_posts=[dict(post_id=r['post_id'],post_url=r['post_url'],
        evidence='Synthetic fixture only',not_used_for_guideline_or_model_selection=True) for r in posts.values()])


class BlindTests(unittest.TestCase):
    def test_seeded_quota_selection_is_deterministic_order_independent_and_diverse(self):
        rows=candidates();original=copy.deepcopy(rows)
        a=sample(rows,180,10,20,20261111);b=sample(list(reversed(rows)),180,10,20,20261111)
        self.assertEqual([r['id'] for r in a],[r['id'] for r in b]);self.assertEqual(rows,original)
        self.assertEqual(len(a),180);self.assertLessEqual(max(Counter(r['post_id'] for r in a).values()),10)
        self.assertLessEqual(max(Counter(r['movie_id'] for r in a).values()),20)
        self.assertEqual(len({r['post_id'] for r in a}),24)

    def test_sentiment_length_predictions_do_not_change_sampling(self):
        rows=candidates();changed=copy.deepcopy(rows)
        for i,r in enumerate(changed):r.update(label='NEG',prediction='POS',text_raw='x'*(i+1))
        self.assertEqual([r['id'] for r in sample(rows,180,10,20,42)],
                         [r['id'] for r in sample(changed,180,10,20,42)])

    def test_unknown_exposure_is_not_assumed_independent(self):
        usable,rejected=eligible(candidates(),[],dict(attested_unused_posts=[]))
        self.assertFalse(usable);self.assertTrue(all('EXPOSURE_UNKNOWN_NOT_ATTESTED_UNUSED' in e['reasons'] for e in rejected))

    def test_missing_metadata_exposed_bridge_and_empty_text_fail_closed(self):
        rows=candidates(3,2);rows[0]['development']=True
        rows[1]['group_id']=rows[0]['group_id'];rows[2]['post_url']='';rows[4]['text_view']='  '
        usable,rejected=eligible(rows,[],attest(rows))
        self.assertNotIn(rows[1]['id'],{r['id'] for r in usable})
        self.assertNotIn(rows[2]['id'],{r['id'] for r in usable})
        self.assertNotIn(rows[4]['id'],{r['id'] for r in usable})

    def test_invalid_attestation_and_duplicates_rejected(self):
        with self.assertRaises(ValueError):eligible(candidates(),[],dict(attested_unused_posts=[dict(post_id='1')]))
        rows=candidates(1,1)
        with self.assertRaises(ValueError):sample(rows+rows,10,10,20,42)
        rows[0]['development']=True
        with self.assertRaises(ValueError):validate_selection(rows,rows,dict(max_per_post=10,max_per_movie=20))

    def test_insufficient_test_is_partial_no_workbooks_or_reservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);master=root/'master';master.mkdir()
            write_jsonl(master/'master.jsonl',candidates(1,1));save(master/'exposure_ledger.json',attest(candidates(1,1)))
            save(master/'development_mapping.json',[])
            seal(master,dict(dataset_version='fixture',input_sha256={}))
            cfg=root/'config.json';save(cfg,dict(master_root=str(master),master_manifest_sha256=sha(master/'manifest.json'),
                target=180,max_per_post=10,max_per_movie=20,seed=42,second_annotator_count=50))
            result=prepare(cfg,root/'blind')
            self.assertEqual(result['status'],'PARTIAL');self.assertEqual(result['selected'],0)
            self.assertEqual(result['attainable_under_quota'],1)
            self.assertFalse((root/'blind/reservation.json').exists());self.assertFalse(list((root/'blind').glob('*.xlsx')))
            self.assertFalse(list((root/'blind').glob('test_annotator*.csv')))

    def test_complete_fixture_blind_payload_has_only_allowed_fields_and_blank_decisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);master=root/'master';master.mkdir();rows=candidates()
            write_jsonl(master/'master.jsonl',rows);save(master/'exposure_ledger.json',attest(rows));save(master/'development_mapping.json',[])
            seal(master,dict(dataset_version='fixture',input_sha256={}))
            cfg=root/'cfg.json';save(cfg,dict(master_root=str(master),master_manifest_sha256=sha(master/'manifest.json'),
                target=180,max_per_post=10,max_per_movie=20,seed=42,second_annotator_count=50))
            r=prepare(cfg,root/'blind');self.assertEqual(r['selected'],180)
            payload=load(root/'blind/workbook_input.json');self.assertEqual(len(payload['a']),180);self.assertEqual(len(payload['b']),50)
            for row in payload['a']+payload['b']:
                self.assertEqual(set(row),set(BLIND_FIELDS));self.assertTrue(all(not row[k] for k in BLIND_FIELDS[2:]))
            self.assertTrue({r['id'] for r in payload['b']} <= {r['id'] for r in payload['a']})
            reserved=load(root/'blind/reservation.json')
            self.assertEqual(len(reserved['ids']),len(rows)) # all component members, not just 180 selected
            assert_allowed([dict(id='unrelated',text_raw='new text')],'train',root/'blind')
            for purpose in ('train','validation','pseudo_labeling','model_selection','threshold_tuning'):
                with self.assertRaises(ValueError):assert_allowed([rows[0]],purpose,root/'blind')
            # New internal identity cannot evade post or normalized text quarantine.
            with self.assertRaises(ValueError):assert_allowed([dict(id='alias',text_raw=rows[0]['text_raw'].upper())],'train',root/'blind')

    def test_corrupted_guard_manifest_never_silently_disables_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);save(root/'manifest.json',dict(status='PARTIAL',selected=0,output_sha256={'missing.json':'0'*64}))
            with self.assertRaises(ValueError):assert_allowed([], 'train',root)

    def test_import_preserves_review_and_exclude_and_refuses_missing_decisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);task=root/'task';task.mkdir();rows=[dict(id=str(i),text_raw='fixture'+str(i),status='',label='',review_reason='',reason='') for i in range(3)]
            write_csv(task/'test_annotator_a.csv',rows,BLIND_FIELDS)
            seal(task,dict(status='RESERVED_PENDING_WORKBOOKS',guideline_sha256='fixture'))
            a=copy.deepcopy(rows);a[0]['label']='POS';a[1].update(label='REVIEW',review_reason='REV_CONTEXT');a[2].update(label='EXCLUDE',reason='Off topic')
            path=root/'a.csv';write_csv(path,a,BLIND_FIELDS)
            r=import_labels(task,path,root/'imported','fixture_annotator')
            self.assertEqual((r['sentiment'],r['review'],r['excluded']),(1,1,1));self.assertFalse(r['gold_created'])
            write_csv(root/'missing.csv',rows,BLIND_FIELDS)
            with self.assertRaises(ValueError):import_labels(task,root/'missing.csv',root/'bad','fixture')
            self.assertFalse((root/'bad').exists())


if __name__=='__main__':unittest.main()
