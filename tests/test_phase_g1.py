"""Collection limits and platform isolation, entirely on synthetic fixtures."""
from pathlib import Path
import tempfile
import unittest
import importlib.util
from unittest.mock import patch

from src.crawler.__main__ import comment_limit
from src.crawler.browser import collect
from src.crawler.store import Store,validate
from test_crawler import CONFIG,POST,observation


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

    @unittest.skipUnless(importlib.util.find_spec("selenium"), "Optional Selenium dependency")
    def test_collector_keeps_more_than_100_and_never_claims_total_coverage(self):
        n,status,reason,report=self.collect_fixture(None)
        self.assertEqual(n,150);self.assertEqual((status,reason),('success','visible_dom_exhausted'))
        self.assertFalse(report['coverage_verified']);self.assertIsNone(report['record_count_cap'])

    @unittest.skipUnless(importlib.util.find_spec("selenium"), "Optional Selenium dependency")
    def test_old_explicit_cap_still_works(self):
        n,status,reason,_=self.collect_fixture(100)
        self.assertEqual((n,status,reason),(100,'partial','comment_limit'))





if __name__=='__main__':unittest.main()
