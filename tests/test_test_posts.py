"""New-source intake tests use only synthetic IDs and a fake crawler runner."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from src.dataset.common import load,save,seal,sha,write_csv,write_jsonl
from src.dataset.exposure import references
from src.dataset.test_posts import INPUT_FIELDS,assert_intakes_allowed,crawl,preflight,reserve,verify_run


class TestPostIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';self.root.mkdir();self.registry=self.root/'registry'
        self.data=self.root/'data';self.master=self.root/'master';self.master.mkdir()
        write_jsonl(self.master/'master.jsonl',[]);save(self.master/'inventory.json',[])
        save(self.master/'exposure_ledger.json',dict(known_exposed_post_ids=[],attested_unused_posts=[]))
        save(self.master/'config.json',dict(dataset_version='fixture'))
        seal(self.master,dict(status='MASTER_CREATED',input_sha256={}))
        self.patch=patch('src.dataset.test_posts.ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def inputs(self,count=2,change=None):
        rows=[]
        for i in range(count):
            pid=str(1000+i);movie='film'+str(i//2);url='https://www.facebook.com/groups/fixture/posts/'+pid
            proof=self.root/f'evidence_{i}.json'
            save(proof,dict(post_id=pid,post_url=url,movie_id=movie,selected_from_post_content_only=True,
                comments_not_inspected=True,not_used_for_guideline_or_model_selection=True,
                attested_by='fixture coordinator',evidence='Synthetic selection receipt only',recorded_at='2020-01-01T00:00:00+00:00'))
            rows.append(dict(candidate_id='P'+str(i),movie_slot='F'+str(i//2),movie_id=movie,post_url=url,post_id=pid,
                selected_from_post_content_only='true',unused_exposure_evidence=proof.name,notes=''))
        if change:change(rows)
        path=self.root/'test_posts.csv';write_csv(path,rows,INPUT_FIELDS)
        return path,rows

    def plan(self,count=2):
        path,rows=self.inputs(count);plan=self.root/'plan'
        result=preflight(path,self.master,plan,self.registry,self.data)
        self.assertEqual(result['status'],'READY_FOR_CRAWL')
        return plan,path,rows

    def run_config(self,plan,rows,run_id='fb_fixture',**overrides):
        path=self.data/'crawl_runs'/run_id;path.mkdir(parents=True)
        manifest=load(plan/'manifest.json')
        cfg=dict(source_dataset=manifest['source_dataset'],max_comments=None,posts=[dict(post_url=r['post_url'],movie_id=r['movie_id']) for r in rows],
                 created_at=(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat())
        cfg.update(overrides);save(path/'config.json',cfg)
        return path

    def test_blank_template_is_blocked_and_never_reaches_browser(self):
        rows=[dict.fromkeys(INPUT_FIELDS,'') for _ in range(25)]
        for i,r in enumerate(rows):r.update(candidate_id='P'+str(i),movie_slot='F'+str(i))
        path=self.root/'test_posts.csv';write_csv(path,rows,INPUT_FIELDS);before=sha(path)
        plan=self.root/'blocked';r=preflight(path,self.master,plan,self.registry,self.data)
        self.assertEqual((r['status'],r['blocked_rows']),('BLOCKED',25));self.assertEqual(sha(path),before)
        self.assertFalse((plan/'crawl_posts.csv').exists());self.assertFalse(self.registry.exists())
        runner=Mock()
        with self.assertRaises(ValueError):crawl(plan,self.data,runner=runner,registry=self.registry)
        runner.assert_not_called()

    def test_valid_input_is_quarantined_before_existing_crawler_cli_is_called(self):
        plan,path,rows=self.plan();runner=Mock(return_value=SimpleNamespace(returncode=0));before=sha(path)
        self.assertEqual(crawl(plan,self.data,runner=runner,registry=self.registry),0)
        argv=runner.call_args.args[0]
        self.assertEqual(argv[1:4],['-m','src.crawler','crawl-batch'])
        self.assertNotIn(rows[0]['post_url'],argv);self.assertIn('--input',argv)
        self.assertEqual(argv[argv.index('--max-comments')+1],'all')
        self.assertFalse(runner.call_args.kwargs.get('shell',False));self.assertEqual(sha(path),before)
        for purpose in ('train','validation','pseudo_labeling','threshold_tuning'):
            with self.assertRaises(ValueError):assert_intakes_allowed([dict(post_id=rows[0]['post_id'])],purpose,self.registry)

    def test_url_mismatch_and_duplicate_aliases_fail_without_inventing_ids(self):
        def change(rows):
            rows[1]['post_url']=rows[0]['post_url']+'/?fbclid=tracking'
            rows[0]['post_id']='9999'
        path,_=self.inputs(change=change);plan=self.root/'bad';preflight(path,self.master,plan,self.registry,self.data)
        report=load(plan/'rows.json')
        self.assertIn('POST_ID_URL_MISMATCH',report[0]['reasons'])
        self.assertTrue(all('DUPLICATE_POST_ID_IN_INPUT' in r['reasons'] for r in report))

    def test_missing_or_nonaffirmative_evidence_cannot_be_promoted(self):
        path,_=self.inputs();proof=self.root/'evidence_0.json';v=load(proof);v['comments_not_inspected']=False
        proof.write_text(__import__('json').dumps(v))
        r=preflight(path,self.master,self.root/'blocked',self.registry,self.data)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertIn('UNVERIFIED_EXPOSURE_RECEIPT',load(self.root/'blocked/rows.json')[0]['reasons'])

    def test_input_or_receipt_changes_after_preflight_stop_crawl(self):
        plan,path,_=self.plan();runner=Mock()
        with path.open('a') as f:f.write('\n')
        with self.assertRaisesRegex(ValueError,'post list changed'):crawl(plan,self.data,runner=runner,registry=self.registry)
        runner.assert_not_called()

    def test_old_selection_metadata_reference_blocks_even_with_receipt(self):
        path,rows=self.inputs()
        with patch('src.dataset.test_posts.history_references',return_value=({rows[0]['post_id']:[dict(kind='metadata_reference_only')]},[],1)):
            r=preflight(path,self.master,self.root/'old',self.registry,self.data)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertIn('POST_HAS_PREEXISTING_METADATA_HISTORY',load(self.root/'old/rows.json')[0]['reasons'])

    def test_metadata_scan_never_treats_comment_text_as_exposure_evidence(self):
        value=[dict(text_raw='1000 https://www.facebook.com/groups/g/posts/1000',label='NEG'),
               dict(post_url='https://www.facebook.com/groups/g/posts/1001',text_raw='irrelevant')]
        self.assertEqual([pid for pid,_ in references(value,{'1000','1001'})],['1001'])

    def test_post_scheduled_after_preflight_is_rechecked_before_browser(self):
        plan,_,rows=self.plan();self.run_config(plan,rows,source_dataset='unrelated')
        runner=Mock()
        with self.assertRaisesRegex(ValueError,'scheduled/crawled'):crawl(plan,self.data,runner=runner,registry=self.registry)
        runner.assert_not_called()

    def test_resume_cannot_attach_an_unrelated_or_older_run(self):
        plan,_,rows=self.plan();self.run_config(plan,rows,created_at='2000-01-01T00:00:00+00:00')
        with self.assertRaisesRegex(ValueError,'predates'):verify_run(plan,self.data,'fb_fixture')

    def test_postcollection_reserves_180_with_same_quota_and_protects_all_members(self):
        plan,_,posts=self.plan(20);run=self.run_config(plan,posts);write_jsonl(run/'raw_comments.jsonl',[])
        parent_sha=sha(self.master/'manifest.json');records=[]
        for post in posts:
            for i in range(10):
                records.append(dict(id=post['post_id']+'_'+str(i),comment_id=str(int(post['post_id'])*100+i),
                    post_id=post['post_id'],post_url=post['post_url'],movie_id=post['movie_id'],
                    text_raw='RAW '+post['post_id']+' '+str(i),text_view='VIEW '+post['post_id']+' '+str(i),
                    text_variants=['RAW '+post['post_id']+' '+str(i)],source_platform='facebook',
                    group_id='g'+post['post_id'],development=False,development_ids=[],review_flags=[],
                    exposure_status='unknown_not_attested_unused',human_decisions=[],annotation_status='UNLABELED'))
        def fake_build(config,output):
            output.mkdir();cfg=load(config)
            write_jsonl(output/'master.jsonl',records);save(output/'development_mapping.json',[])
            save(output/'exposure_ledger.json',load(cfg['exposure_ledger']))
            seal(output,dict(dataset_version='fixture',input_sha256={}))
        out=self.root/'reserved'
        with patch('src.dataset.master.build',side_effect=fake_build):r=reserve(plan,self.data,'fb_fixture',out,self.registry)
        self.assertEqual(r['selected'],180);self.assertEqual(sha(self.master/'manifest.json'),parent_sha)
        payload=load(out/'blind_test/workbook_input.json')
        self.assertEqual((len(payload['a']),len(payload['b'])),(180,50))
        self.assertTrue(all('text_view' in r and 'text_raw' not in r for r in payload['a']))
        self.assertEqual(load(out/'blind_config.json')['max_per_post'],10)
        with self.assertRaises(ValueError):assert_intakes_allowed([dict(group_id=records[0]['group_id'])],'train',self.registry)
        # A partial crawl uses the exact same quota and cannot emit an undersized task.
        del records[20:]
        partial=self.root/'partial'
        with patch('src.dataset.master.build',side_effect=fake_build):r=reserve(plan,self.data,'fb_fixture',partial,self.registry)
        self.assertEqual((r['status'],r['selected'],r['attainable_under_quota']),('PARTIAL',0,20))
        self.assertFalse((partial/'blind_test/workbook_input.json').exists())


if __name__=='__main__':unittest.main()
