"""Collection limits and platform isolation, entirely on synthetic fixtures."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.crawler.__main__ import comment_limit
from src.crawler.browser import collect
from src.crawler.store import Store,validate
from src.dataset.master import reconcile
from src.dataset.blind import deny_reserved,eligible,quarantine_posts
from test_crawler import CONFIG,POST,observation
from test_master_dataset import observation as master_observation,NEAR
from test_blind_test import candidates,attest


class G1Tests(unittest.TestCase):
    def test_all_is_no_count_cap_not_a_large_magic_number(self):
        self.assertIsNone(comment_limit('all'));self.assertEqual(comment_limit('100'),100)
        with self.assertRaises(Exception):comment_limit('0')

    def collect_fixture(self,cap):
        with tempfile.TemporaryDirectory() as temp:
            cfg=dict(CONFIG,max_comments=cap,max_rounds=2,idle_rounds=1)
            store=Store(Path(temp)/'runs',cfg);items=[observation(str(i),'fixture '+str(i)) for i in range(150)]
            class Page:
                current_url=POST['post_url']
                def get(self,url):pass
                def set_page_load_timeout(self,t):pass
            class Wait:
                def __init__(self,*a,**k):pass
                def until(self,fn):
                    result=fn(Page())
                    if not result:raise TimeoutError()
                    return result
            def dom(page,url,action='read'):
                return {'inspect':dict(status='ready',comment_containers=150),'sort':dict(status='confirmed'),
                        'buttons':[],'scroll':dict(moved=False)}.get(action,items)
            with patch('src.crawler.browser.dom',side_effect=dom),patch('src.crawler.browser.access_barrier',return_value=False),patch('selenium.webdriver.support.ui.WebDriverWait',Wait),patch('src.crawler.browser.observations',return_value=(items,0)):
                status,reason,_=collect(Page(),store,POST)
            store.finish_post(POST,status,reason);report=validate(store.path)
            return len(store.rows),status,reason,report

    def test_collector_keeps_more_than_100_and_never_claims_total_coverage(self):
        n,status,reason,report=self.collect_fixture(None)
        self.assertEqual(n,150);self.assertEqual((status,reason),('success','visible_dom_exhausted'))
        self.assertFalse(report['coverage_verified']);self.assertIsNone(report['record_count_cap'])

    def test_old_explicit_cap_still_works(self):
        n,status,reason,_=self.collect_fixture(100)
        self.assertEqual((n,status,reason),(100,'partial','comment_limit'))

    def test_same_source_id_on_facebook_and_momo_never_merges_identity(self):
        fb=master_observation(text='Facebook distinct text');momo=master_observation(text='MoMo different text')
        momo.update(source_platform='momo',post_url='https://www.momo.vn/cinema/fixture-10')
        rows,_,_,_,_=reconcile([fb,momo],[],NEAR)
        self.assertEqual(len(rows),2);self.assertEqual({r['platform'] for r in rows},{'facebook','momo'})
        self.assertEqual(len({r['group_id'] for r in rows}),2)

    def test_momo_never_enters_facebook_independent_test(self):
        rows=candidates(2,1);rows[0].update(source_platform='momo',platform='momo',source='momo')
        usable,_=eligible(rows,[],attest(rows))
        self.assertNotIn(rows[0]['id'],{r['id'] for r in usable})

    def test_all_post_members_and_cross_platform_duplicate_aliases_quarantined(self):
        rows=candidates(2,15)
        for r in rows:r['source_platform']='facebook'
        momo=dict(rows[0],id='momo_alias',source_platform='momo',post_id='momo_page',comment_id='momo_review',text_view='duplicate')
        rows.append(momo)
        contract=quarantine_posts(rows,{'0'})
        self.assertEqual(contract['member_records'],16)
        with self.assertRaises(ValueError):deny_reserved([dict(comment_id=rows[14]['comment_id'])],'train',contract)
        with self.assertRaises(ValueError):deny_reserved([dict(source_platform='momo',comment_id='momo_review')],'train',contract)
        # A numeric source ID collision alone is not a cross-platform duplicate.
        deny_reserved([dict(source_platform='momo',comment_id=rows[14]['comment_id'])],'train',contract)


if __name__=='__main__':unittest.main()
