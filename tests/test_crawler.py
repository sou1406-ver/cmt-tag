import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.crawler.parser import comment_identity, facebook_url, observations, post_id
from src.crawler.store import Store, export_run, load_lines, validate
from src.crawler.browser import run_posts, collect, EXTRACT
from src.data.pipeline import prepare_data

POST={'movie_id':'film_a','post_url':'https://www.facebook.com/example/posts/123'}
CONFIG={'posts':[POST], 'source_dataset':'batch_a','max_posts':10,'max_comments':100,
        'post_timeout':5,'max_rounds':4,'max_actions':10,'wait_ms':300,
        'settle_ms':50,'idle_rounds':2,'retries':1}


def observation(cid='100',text='Phim hay 😍!\nko chê.',**changes):
    row=observations([{'text_raw':text,'permalink':POST['post_url']+'?comment_id='+cid,
                       'observation_id':cid}],POST['post_url'])[0][0]
    row.update(changes)
    return row


class ParserTests(unittest.TestCase):
    def test_ids_and_canonical_urls(self):
        self.assertEqual(post_id(POST['post_url']),'123')
        self.assertIsNone(post_id('https://www.facebook.com/share/p/unknown'))
        self.assertEqual(comment_identity(POST['post_url']+'?comment_id=7&reply_comment_id=8',POST['post_url'])[:2],('8','7'))
        self.assertEqual(comment_identity('https://www.facebook.com/x/posts/999?comment_id=7',POST['post_url']),(None,None,None))
        self.assertNotIn('token',facebook_url(POST['post_url']+'?access_token=SECRET'))
        with self.assertRaises(ValueError): facebook_url('https://facebook.com.evil.test/a')

    def test_missing_ids_and_created_time(self):
        rows,errors=observations([{'text_raw':'😅','observation_id':'x','created_at':'3 hours ago'}], 'https://www.facebook.com/share/p/unknown')
        self.assertEqual(errors,0)
        self.assertIsNone(rows[0]['comment_id'])
        self.assertIsNone(rows[0]['post_id'])
        self.assertIsNone(rows[0]['comment_created_at'])
        self.assertEqual(observations([{'text_raw':None}],POST['post_url'])[1],1)

    def test_incomplete_or_invalid_mention_metadata_rejected(self):
        base={'text_raw':'Phim hay!','observation_id':'x','text_without_mentions':'Phim hay!'}
        self.assertEqual(observations([base],POST['post_url'])[1],1)
        row=dict(base,mention_count=True,non_text_media_count=0,text_extraction_version='dom_text_v2')
        self.assertEqual(observations([row],POST['post_url'])[1],1)
        row['mention_count']=0
        self.assertEqual(observations([row],POST['post_url'])[1],0)

    def test_clean_metadata_requires_version_types_and_consistent_status(self):
        row={'text_raw':'An phim hay http://example.org','observation_id':'x',
             'text_without_mentions':'phim hay http://example.org','mention_count':1,
             'non_text_media_count':0,'text_extraction_version':'dom_text_v3',
             'text_clean':'phim hay','clean_status':'KEEP','url_count':1,'clean_review_reasons':[]}
        parsed,errors=observations([row],POST['post_url'])
        self.assertEqual(errors,0);self.assertEqual(parsed[0]['text_clean'],'phim hay')
        for changes in ({'text_clean':None},{'clean_status':'EXCLUDE'},{'url_count':True},
                        {'clean_review_reasons':['unknown']},{'text_extraction_version':'dom_text_v2'}):
            with self.subTest(changes=changes):
                self.assertEqual(observations([{**row,**changes}],POST['post_url'])[1],1)
        for field in ('text_clean','url_count','clean_review_reasons','clean_status'):
            incomplete={k:v for k,v in row.items() if k!=field}
            self.assertEqual(observations([incomplete],POST['post_url'])[1],1)
        reviewed={**row,'clean_status':'REVIEW','clean_review_reasons':['media_context_required'],
                  'non_text_media_count':1}
        self.assertEqual(observations([reviewed],POST['post_url'])[1],0)
        self.assertEqual(observations([{**reviewed,'non_text_media_count':0}],POST['post_url'])[1],1)
        evidence=[{'kind':'mention','rule':'identity_link','raw_start':0,'raw_end':2},
                  {'kind':'url','rule':'explicit_url_text','raw_start':12,'raw_end':30}]
        self.assertEqual(observations([{**row,'clean_evidence':evidence}],POST['post_url'])[1],0)
        for invalid in (None,evidence[:1],[{**evidence[0],'raw_end':999},evidence[1]],
                        [{**evidence[0],'kind':[]},evidence[1]]):
            self.assertEqual(observations([{**row,'clean_evidence':invalid}],POST['post_url'])[1],1)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=Store(self.root/'crawl_runs',CONFIG)

    def test_identical_text_different_ids_and_unknown_ids_retained(self):
        s=self.store
        for cid in ('1','2'):
            self.assertTrue(s.add(observation(cid,'same'),POST,'page'))
        row=observation('3','same',comment_id=None,comment_permalink=None)
        self.assertTrue(s.add(row,POST,'page'))
        row=dict(row,dom_observation_id='different-node')
        self.assertTrue(s.add(row,POST,'page'))
        self.assertEqual(len(s.rows),4)
        self.assertEqual(validate(s.path)['possible_duplicates_unresolved'],2)

    def test_resume_rebuilds_ids_from_journal_not_checkpoint(self):
        s=self.store
        s.add(observation(),POST,'first')
        s.checkpoint('interrupted')
        resumed=Store(self.root/'crawl_runs',resume=s.run_id)
        self.assertFalse(resumed.add(observation(),POST,'second'))
        self.assertEqual(len(resumed.rows),1)
        self.assertTrue(resumed.add(observation('101'),POST,'second'))
        resumed.finish_post(POST,'success','visible_dom_exhausted')
        resumed.finish()
        with self.assertRaisesRegex(ValueError,'immutable'):
            Store(self.root/'crawl_runs',resume=s.run_id)

    def test_torn_write_preserved_and_resume_succeeds(self):
        s=self.store
        s.add(observation(),POST,'page')
        with (s.path/'raw_comments.jsonl').open('ab') as f: f.write(b'{"incomplete')
        resumed=Store(self.root/'crawl_runs',resume=s.run_id)
        self.assertEqual(len(resumed.rows),1)
        self.assertEqual(next(s.path.glob('*.tail_*')).read_bytes(),b'{"incomplete')

    def test_counter_resume_and_checkpoint_lag_do_not_lose_rows(self):
        s=self.store
        s.add(observation('1'),POST,'page')
        s.add(observation('2'),POST,'page')
        self.assertFalse(s.add(observation('2'),POST,'page_again'))
        self.assertEqual(s.post_counts[POST['post_url']],2)
        self.assertEqual(json.loads((s.path/'checkpoint.json').read_text())['rows'],0)
        # Simulate stop without calling checkpoint: fsynced raw is authoritative.
        resumed=Store(self.root/'crawl_runs',resume=s.run_id)
        self.assertEqual(resumed.post_counts[POST['post_url']],2)
        self.assertEqual(len(resumed.rows),2)

    def test_partial_failed_and_blocked_runs_resume_until_success(self):
        for status in ('partial','failed','blocked'):
            with self.subTest(status=status):
                s=Store(self.root/status,CONFIG)
                s.add(observation(),POST,'page')
                s.finish_post(POST,status,'fixture_stop'); s.finish()
                self.assertEqual(json.loads((s.path/'checkpoint.json').read_text())['status'],'interrupted')
                resumed=Store(self.root/status,resume=s.run_id)
                def success(page,store,post):
                    self.assertFalse(store.add(observation(),post,'resumed'))
                    return 'success','visible_dom_exhausted',[]
                run_posts(resumed,None,success)
                self.assertEqual(len(resumed.rows),1)
                self.assertEqual(json.loads((s.path/'checkpoint.json').read_text())['status'],'complete')

    def test_retry_is_bounded_and_batch_continues(self):
        self.store.config['posts']=[POST,dict(POST,post_url=POST['post_url'].replace('123','456'))]
        attempts=[]
        def fake(page,store,post):
            attempts.append(post['post_url'])
            if post==POST: raise TimeoutError('secret must not be logged')
            return 'blocked','access_barrier',[]
        run_posts(self.store,None,collector=fake)
        self.assertEqual(len(attempts),3)
        self.assertEqual([p['status'] for p in self.store.posts],['failed','blocked'])
        self.assertNotIn('secret',(self.store.path/'errors.jsonl').read_text())

    def test_keyboard_interrupt_then_resume(self):
        def interrupted(page,s,p):
            s.add(observation(),p,'one')
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): run_posts(self.store,None,interrupted)
        self.assertEqual(json.loads((self.store.path/'checkpoint.json').read_text())['status'],'interrupted')
        resumed=Store(self.root/'crawl_runs',resume=self.store.run_id)
        def complete(page,s,p):
            s.add(observation(),p,'two')
            s.add(observation('101'),p,'two')
            return 'success','visible_dom_exhausted',[]
        run_posts(resumed,None,complete)
        self.assertEqual(len(resumed.rows),2)

    def test_export_raw_unchanged_import_grouped_split(self):
        s=self.store
        s.add(observation('1','Một phim hay!'),POST,'page')
        s.add(observation('2','Tôi chê kịch bản.'),POST,'page')
        s.add(observation('3','Bị cắt…',extraction_status='truncated'),POST,'page')
        before=(s.path/'raw_comments.jsonl').read_bytes()
        dest=export_run(s.path,self.root/'import')
        self.assertEqual((s.path/'raw_comments.jsonl').read_bytes(),before)
        with (dest/'comments.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['text_raw'],'Một phim hay!')
        report,processed,splits=prepare_data(dest/'import_config.json',self.root/'phase_b')
        manifest=json.loads((splits/'manifest.json').read_text())
        self.assertEqual(len({e['split'] for e in manifest['entries']}),1)
        records=load_lines(processed/'records.jsonl')
        self.assertTrue(all(r['post_namespace']=='facebook' for r in records))
        self.assertTrue(all(not r['annotations']['human'] and not r['annotations']['machine'] for r in records))
        self.assertEqual(report['counts']['raw_comment_rows'],2)
        with self.assertRaises(FileExistsError): export_run(s.path,dest)

    def test_cli_validate_export(self):
        self.store.add(observation(),POST,'page')
        for args in (['validate'],['export','--format','csv']):
            result=subprocess.run([sys.executable,'-m','src.crawler',*args,'--run',self.store.run_id,
                       '--data-root',str(self.root)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([sys.executable,'scripts/build_master_dataset.py','--config',
            str(self.root/'imports'/self.store.run_id/'import_config.json'), '--output-root',str(self.root/'processed')],
            capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)

    def test_validation_rejects_corrupted_metadata(self):
        self.store.add(observation(),POST,'page')
        path=self.store.path/'raw_comments.jsonl'
        rows=load_lines(path)
        rows[0]['post_id']='999'
        path.write_text(json.dumps(rows[0])+'\n',encoding='utf-8')
        self.assertEqual(validate(self.store.path)['parse_errors'],1)
        with self.assertRaises(ValueError): export_run(self.store.path,self.root/'bad_export')
        with self.assertRaises(ValueError): export_run(self.store.path,self.root/'bad_partial_export',allow_partial=True)

    def test_partial_export_requires_opt_in_and_keeps_dom_failures_visible(self):
        s=self.store
        s.add(observation(),POST,'page')
        s.append('errors.jsonl',{'code':'parse_error','count':3,'post_url':POST['post_url']})
        s.finish_post(POST,'partial','time_limit')
        before=(s.path/'raw_comments.jsonl').read_bytes()
        report=validate(s.path)
        self.assertEqual(report['raw_validation_errors'],0)
        self.assertEqual(report['dom_parse_observations'],3)
        self.assertEqual(report['parse_errors'],3)
        with self.assertRaisesRegex(ValueError,'allow-partial'):
            export_run(s.path,self.root/'strict_export')
        dest=export_run(s.path,self.root/'partial_export',allow_partial=True)
        manifest=json.loads((dest/'export_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['exported'],1)
        self.assertEqual(manifest['dom_parse_observations'],3)
        self.assertEqual(manifest['post_status_counts']['partial'],1)
        self.assertFalse(manifest['coverage_verified'])
        self.assertEqual((s.path/'raw_comments.jsonl').read_bytes(),before)
        command=[sys.executable,'-m','src.crawler','export','--run',s.run_id,'--data-root',str(self.root)]
        strict=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(strict.returncode,2)
        self.assertIn('--allow-partial',strict.stdout)
        explicit=subprocess.run(command+['--allow-partial'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(explicit.returncode,0,explicit.stdout+explicit.stderr)

    def test_mention_metadata_export_and_validation_leave_legacy_raw_unchanged(self):
        s=self.store
        old=observation('1');s.add(old,POST,'page')
        before=(s.path/'raw_comments.jsonl').read_bytes()
        fresh=observation('2','Bạn A Phim hay!',text_without_mentions='Phim hay!',mention_count=1,
            non_text_media_count=0,text_extraction_version='dom_text_v2')
        s.add(fresh,POST,'page')
        self.assertTrue((s.path/'raw_comments.jsonl').read_bytes().startswith(before))
        self.assertEqual(validate(s.path)['raw_validation_errors'],0)
        out=export_run(s.path,self.root/'mention_export')
        with (out/'comments.csv').open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
        self.assertEqual(rows[0]['text_without_mentions'],'')
        self.assertEqual(rows[1]['text_raw'],'Bạn A Phim hay!')
        self.assertEqual(rows[1]['text_without_mentions'],'Phim hay!')
        bad=observation('3',text_without_mentions='x',mention_count=-1,non_text_media_count=0,text_extraction_version='dom_text_v2')
        s.add(bad,POST,'page')
        self.assertEqual(validate(s.path)['raw_validation_errors'],1)

    def test_missing_post_id_import_warns_and_keeps_null(self):
        post=dict(POST,post_url='https://www.facebook.com/share/p/unknown')
        s=Store(self.root/'other_runs',dict(CONFIG,posts=[post]))
        row=observation(comment_id=None,comment_permalink=None,post_id=None)
        s.add(row,post,'page')
        dest=export_run(s.path,self.root/'missing_import')
        report,processed,_=prepare_data(dest/'import_config.json',self.root/'missing_phase_b')
        self.assertIsNone(load_lines(processed/'records.jsonl')[0]['post_id'])
        # Phase B can still group the known post_url, but this is not proof
        # that share URLs from different runs identify independent posts.
        self.assertEqual(validate(s.path)['metadata_completeness_rate']['post_id'],0)

    def test_clean_export_resume_preserve_legacy_and_new_raw(self):
        s=self.store;s.add(observation('1'),POST,'old')
        before=(s.path/'raw_comments.jsonl').read_bytes()
        s.add(observation('2','An Không dở :)) https://example.org',
            text_without_mentions='Không dở :)) https://example.org',mention_count=1,
            non_text_media_count=0,text_extraction_version='dom_text_v3',
            text_clean='Không dở :))',clean_status='KEEP',url_count=1,clean_review_reasons=[],
            clean_evidence=[{'kind':'mention','rule':'identity_link','raw_start':0,'raw_end':2},
                            {'kind':'url','rule':'explicit_url_text','raw_start':16,'raw_end':35}]),POST,'new')
        raw=(s.path/'raw_comments.jsonl').read_bytes();self.assertTrue(raw.startswith(before))
        resumed=Store(self.root/'crawl_runs',resume=s.run_id)
        self.assertEqual(resumed.rows[-1]['text_clean'],'Không dở :))')
        self.assertEqual(validate(s.path)['raw_validation_errors'],0)
        out=export_run(s.path,self.root/'clean_export')
        with (out/'comments.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]['text_clean'],'') # No invented view for historical raw.
        self.assertEqual(rows[1]['text_raw'],'An Không dở :)) https://example.org')
        self.assertEqual(rows[1]['text_clean'],'Không dở :))')
        self.assertEqual(json.loads(rows[1]['clean_review_reasons']),[])
        self.assertEqual(json.loads(rows[1]['clean_evidence']),resumed.rows[-1]['clean_evidence'])
        self.assertEqual((s.path/'raw_comments.jsonl').read_bytes(),raw)


@unittest.skipUnless(importlib.util.find_spec('selenium'),'Install requirements/crawler.txt and a Chrome/Brave browser for DOM tests')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        options=webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        if os.environ.get('CRAWLER_TEST_BROWSER'):
            options.binary_location=os.environ['CRAWLER_TEST_BROWSER']
        os.environ.setdefault('SE_CACHE_PATH',str(Path('data/selenium_cache').resolve()))
        cls.driver=webdriver.Chrome(options=options,service=Service(os.environ.get('CRAWLER_TEST_DRIVER')))

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        from unittest.mock import patch
        from urllib.parse import quote
        self.page=self.driver
        self.fixture=Path('tests/fixtures/facebook_comments.html').read_text(encoding='utf-8')
        original_get=self.driver.get
        def fixture_get(url):
            original_get('data:text/html;charset=utf-8,'+quote('<base href="https://www.facebook.com/">'+self.fixture))
        patcher=patch.object(self.driver,'get',side_effect=fixture_get)
        patcher.start(); self.addCleanup(patcher.stop)

    def test_dom_bodies_replies_expansion_and_post_exclusion(self):
        self.page.get(POST['post_url'])
        candidates=self.page.execute_script('return ('+EXTRACT+')(arguments[0]);',POST['post_url'])
        rows,errors=observations(candidates,POST['post_url'])
        self.assertEqual(len(rows),8)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Hay 😍! ko dở.\nĐáng xem!')
        self.assertEqual(rows[1]['parent_comment_id'],'101')
        self.assertEqual(rows[1]['record_type'],'reply')
        self.assertFalse(any('NỘI DUNG' in r['text_raw'] or 'Tên không' in r['text_raw'] for r in rows))
        self.page.find_element('css selector','#long button').click()
        rows,_=observations(self.page.execute_script('return ('+EXTRACT+')(arguments[0]);',POST['post_url']),POST['post_url'])
        self.assertEqual(next(r for r in rows if r['comment_id']=='105')['text_raw'],'Đầy đủ 😍! Không tệ.\nDòng thứ hai.')
        self.assertEqual(next(r for r in rows if r['comment_id']=='106')['extraction_status'],'truncated')

    def test_collection_limits_truncation_and_no_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp,CONFIG)
            status,reason,trace=collect(self.page,s,POST)
            self.assertEqual(status,'partial')
            self.assertIn('EXPAND',trace)
            self.assertEqual(len(s.rows),8)
            self.assertEqual(sum(r['extraction_status']=='truncated' for r in s.rows),1)
        self.fixture='<div role="article"><div data-comment-body>Post only</div></div>'
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp,CONFIG)
            self.assertEqual(collect(self.page,s,POST)[0],'partial')
            self.assertEqual(s.rows,[])

    def test_access_barrier(self):
        self.fixture='<h2>This content isn\'t available</h2>'
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect(self.page,Store(tmp,CONFIG),POST)[:2],('blocked','access_barrier'))

    def test_comment_limit_is_partial_and_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp,dict(CONFIG,max_comments=2))
            self.assertEqual(collect(self.page,s,POST)[:2],('partial','comment_limit'))
            self.assertEqual(len(s.rows),2)


if __name__=='__main__':
    unittest.main()
