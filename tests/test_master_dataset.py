import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.dataset.common import load, save, seal, sha, staged, verify
from src.dataset.master import inventory, normal, post_url, reconcile


def observation(cid='1', post='10', text='A comment', file='raw1', number=1, **extra):
    return dict(text_raw=text, text_view=text, source_dataset='fixture', source_file=file, source_row=number,
        comment_id=cid, post_id=post, post_url='https://www.facebook.com/groups/g/posts/'+post,
        parent_comment_id='', movie_id='fixture_movie', collected_at='', source_platform='facebook',
        original_label='', original_label_source='', extraction_version='dom_text_v2', extraction_status='complete',
        original_internal_id='', **extra)


NEAR = dict(threshold=.9, min_chars=40, shingle_size=3)


class MasterTests(unittest.TestCase):
    def test_same_identity_merges_all_provenance_and_retains_text_variants(self):
        a=observation();b=observation(file='export',text='A comment edited')
        original=copy.deepcopy([a,b]);rows,_,_,_,stats=reconcile([a,b],[],NEAR)
        self.assertEqual(len(rows),1);self.assertEqual(stats['provenance_observations'],2)
        self.assertEqual(set(rows[0]['text_variants']),{'A comment','A comment edited'})
        self.assertEqual([a,b],original)

    def test_same_text_different_comment_ids_or_missing_identity_never_merge(self):
        rows,_,_,_,_=reconcile([observation(),observation(cid='2'),observation(cid='',file='unknown')],[],NEAR)
        self.assertEqual(len(rows),3);self.assertEqual(len({r['group_id'] for r in rows}),1)

    def test_same_comment_id_conflicting_post_is_reviewed_not_merged(self):
        rows,_,_,conflicts,_=reconcile([observation(),observation(post='11')],[],NEAR)
        self.assertEqual(len(rows),2);self.assertEqual(conflicts[0]['kind'],'COMMENT_ID_IDENTITY_UNRESOLVED')
        self.assertEqual(len({r['group_id'] for r in rows}),1)

    def test_human_labels_original_text_review_history_and_old_groups_preserved(self):
        dev=[dict(id='dev1',comment_id='1',post_id='10',text_raw='A comment',group_id='old',status='LABELED',label='POS',review_event_id='event19'),
             dict(id='dev2',comment_id='2',post_id='11',text_raw='Different text',group_id='old',status='REVIEW',label='')]
        rows,mapping,_,_,_=reconcile([observation(),observation(cid='2',post='11',text='Different text')],dev,NEAR)
        self.assertEqual(len(mapping),2);self.assertEqual(len({r['group_id'] for r in rows}),1)
        decisions=[d for r in rows for d in r['human_decisions']]
        self.assertCountEqual(decisions,dev)
        self.assertIn('event19',[d.get('review_event_id') for d in decisions])

    def test_conflicting_human_labels_across_text_duplicates_go_to_review(self):
        dev=[dict(id='a',comment_id='1',post_id='10',text_raw='A comment',group_id='g1',status='LABELED',label='POS'),
             dict(id='b',comment_id='2',post_id='11',text_raw='A comment',group_id='g2',status='LABELED',label='NEG')]
        rows,_,_,queue,_=reconcile([observation(),observation(cid='2',post='11')],dev,NEAR)
        self.assertEqual({r['label'] for r in rows},{'POS','NEG'})
        self.assertEqual(queue[0]['kind'],'EXACT_TEXT_HUMAN_LABEL_CONFLICT')

    def test_exact_and_near_bridges_are_transitive_and_no_rows_deleted(self):
        text=' '.join('token'+str(i) for i in range(80))
        values=[observation(text=text),observation(cid='2',post='11',text=text+' ending'),
                observation(cid='3',post='12',text=text+' ending')]
        rows,_,pairs,_,_=reconcile(values,[],NEAR)
        self.assertTrue(pairs);self.assertEqual(len(rows),3);self.assertEqual(len({r['group_id'] for r in rows}),1)

    def test_unverified_external_overall_is_never_human_or_train_label(self):
        item=observation(cid='',source_platform_override='unused')
        item.update(source_platform='unknown',original_label='positive',original_label_source='unverified_external')
        rows,_,_,_,_=reconcile([item],[],NEAR)
        self.assertEqual(rows[0]['label'],'');self.assertEqual(rows[0]['annotation_status'],'UNLABELED')
        self.assertEqual(rows[0]['original_labels'][0]['value'],'positive')

    def test_url_comment_parameters_do_not_create_new_posts(self):
        a='https://m.facebook.com/groups/g/posts/10/?comment_id=3&fbclid=ignored'
        self.assertEqual(post_url(a),'https://www.facebook.com/groups/g/posts/10')
        self.assertEqual(post_url('https://example.com/10'),'')

    def test_inventory_honors_gitignored_sources_and_never_reads_browser_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'data/crawl_runs/fixture';raw.mkdir(parents=True)
            (raw/'raw_comments.jsonl').write_text(json.dumps(observation())+'\n',encoding='utf-8')
            hidden=root/'data/browser_profile';hidden.mkdir();(hidden/'secret.json').write_text('INVALID SECRET')
            (root/'credentials.json').write_text('INVALID SECRET')
            (root/'.gitignore').write_text('/data/')
            entries,rows,inputs=inventory([root],root,[])
            self.assertEqual(len(rows),1);self.assertEqual(len(entries),1)
            self.assertFalse(any('secret' in path for path in inputs))
            self.assertFalse(any('credential' in path for path in inputs))

    def test_incomplete_journal_is_reported_not_repaired(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'data/crawl_runs/fixture';raw.mkdir(parents=True)
            path=raw/'raw_comments.jsonl';path.write_bytes(b'{"text_raw":"not committed"}')
            before=sha(path);entries,rows,_=inventory([root],root,[])
            self.assertEqual(entries[0]['status'],'ValueError');self.assertEqual(rows,[]);self.assertEqual(sha(path),before)

    def test_manifest_detects_tampering_and_atomic_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'master'
            with staged(out) as work:
                save(work/'data.json',{'rows':2});seal(work,{'dataset_version':'fixture'})
            verify(out)
            with self.assertRaises(FileExistsError):
                with staged(out):pass
            (out/'data.json').write_text('{}')
            with self.assertRaises(ValueError):verify(out)


if __name__=='__main__':unittest.main()
