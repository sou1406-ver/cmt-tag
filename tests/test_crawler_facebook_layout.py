import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from src.crawler.parser import post_id, comment_identity, observations
from src.crawler.browser import EXTRACT, collect, dom
from src.crawler.login import open_login
from src.crawler.store import Store
from tests import test_crawler as crawler_tests

CONFIG=crawler_tests.CONFIG

GROUP='https://www.facebook.com/groups/example/permalink/1909400102999925'


class GroupAndLoginTests(unittest.TestCase):
    def test_group_permalink_and_posts_alias(self):
        self.assertEqual(post_id(GROUP),'1909400102999925')
        cid,parent,_=comment_identity(GROUP.replace('/permalink/','/posts/')+'?comment_id=123&reply_comment_id=456',GROUP)
        self.assertEqual((cid,parent),('456','123'))

    def test_login_is_normal_browser_and_same_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'brave.exe'; binary.touch()
            profile=Path(tmp)/'crawler_profile'
            with patch('subprocess.Popen') as launch:
                self.assertEqual(open_login(profile,'brave',binary),profile.resolve())
            args=launch.call_args.args[0]
            self.assertIn('--user-data-dir='+str(profile.resolve()),args)
            self.assertFalse(any('automation' in a or 'remote-debugging' in a or 'incognito' in a for a in args))

    def test_legacy_missing_group_post_id_remains_valid_without_raw_edit(self):
        from src.crawler.store import validate
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post]))
            store.add({'text_raw':'Phim hay!','comment_id':None,'post_id':None,'parent_comment_id':None,
                'comment_created_at':None,'record_type':'comment','extraction_status':'complete',
                'dom_observation_id':'1','comment_permalink':None},post,'legacy')
            raw=store.path/'raw_comments.jsonl'; before=raw.read_bytes()
            self.assertEqual(validate(store.path)['parse_errors'],0)
            self.assertEqual(raw.read_bytes(),before)


@unittest.skipUnless(importlib.util.find_spec('selenium'),'Selenium optional')
class FacebookLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        crawler_tests.BrowserTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls): cls.driver.quit()

    def load(self,html):
        self.driver.get('data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+html))

    def fixture(self):
        return f'''<div role="article"><a href="/x/posts/999">other post</a>
          <div aria-label="Comment by Outside"><div dir="auto">DO NOT COLLECT</div><a href="/x/posts/999?comment_id=9">time</a></div></div>
          <div role="dialog"><article role="article"><a href="{GROUP}">post permalink</a>
            <div data-ad-comet-preview="message">POST CONTENT NOT COMMENT</div>
            <button id="sort" onclick="document.getElementById('menu').hidden=false;this.setAttribute('aria-expanded','true')">Phù hợp nhất</button>
            <div aria-label="Bình luận của A"><a href="/profile.php?id=42"><span dir="auto">AUTHOR NOT BODY</span></a>
              <div dir="auto">Phim hay 😍!<br>ko dở.</div><a href="{GROUP}?comment_id=101">time</a>
              <div aria-label="Reply"><div dir="auto">Đúng vậy 👍</div><a href="{GROUP}?comment_id=101&amp;reply_comment_id=102">time</a></div>
            </div>
            <div aria-label="Comment from B"><div dir="auto">Chưa đủ…</div><button onclick="this.previousElementSibling.textContent='Đầy đủ!';this.remove()">Xem thêm</button><a href="{GROUP}?comment_id=103">time</a></div>
            <button id="replies" onclick="this.textContent='done'">Xem thêm 5 câu trả lời</button>
          </article></div>
          <div role="menu" id="menu" hidden><button role="menuitem" onclick="document.getElementById('sort').textContent='Tất cả bình luận';document.getElementById('sort').setAttribute('aria-expanded','false');this.parentElement.hidden=true">Tất cả bình luận</button></div>'''

    def test_scoped_roleless_body_reply_author_and_group_id(self):
        self.load(self.fixture())
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0); self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['text_raw'],'Phim hay 😍!\nko dở.')
        self.assertEqual(rows[0]['record_type'],'comment')
        self.assertEqual(rows[1]['parent_comment_id'],'101')
        self.assertTrue(all(r['post_id']=='1909400102999925' for r in rows))
        self.assertFalse(any('AUTHOR' in r['text_raw'] or 'DO NOT' in r['text_raw'] for r in rows))
        buttons=dom(self.driver,GROUP,'buttons')
        self.assertTrue(any('5 câu trả lời' in b.text for b in buttons))

    def test_sort_requires_real_confirmation(self):
        self.load(self.fixture())
        step=dom(self.driver,GROUP,'sort'); self.assertEqual(step['status'],'opening'); step['element'].click()
        step=dom(self.driver,GROUP,'sort'); self.assertEqual(step['status'],'selecting'); step['element'].click()
        self.assertEqual(dom(self.driver,GROUP,'sort')['status'],'confirmed')

    def test_collect_group_layout_end_to_end(self):
        original=self.driver.get
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post],max_rounds=7))
            # load needs the original get while collect alone is redirected.
            html='data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+self.fixture())
            with patch.object(self.driver,'get',side_effect=lambda url:original(html)):
                status,reason,trace=collect(self.driver,store,post)
            self.assertEqual(status,'success',(reason,trace))
            self.assertEqual(len(store.rows),3)
            self.assertTrue(all(r['extraction_status']=='complete' for r in store.rows))
            self.assertIn('SORT_CONFIRMED',trace)

    def test_wrong_post_never_falls_back_to_whole_page(self):
        self.load(self.fixture())
        self.assertEqual(dom(self.driver,GROUP.replace('1909400102999925','777'),'inspect')['status'],'missing_scope')
        self.assertEqual(dom(self.driver,GROUP.replace('1909400102999925','777')),[])

    def test_photo_fbid_does_not_poison_post_identity(self):
        html=self.fixture().replace('post permalink</a>','post permalink</a><a href="https://www.facebook.com/photo/?fbid=555">Attached photo</a>')
        self.load(html)
        self.assertEqual(dom(self.driver,GROUP,'inspect')['status'],'ready')
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0); self.assertEqual(len(rows),3)
        self.assertTrue(all(r['post_id']=='1909400102999925' for r in rows))

    def test_message_paragraphs_share_one_verified_wrapper(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.','<span dir="auto"><div><div dir="auto">Phim hay 😍!</div></div><div><div dir="auto">ko dở.</div></div></span>')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Phim hay 😍!\nko dở.')

    def test_sort_steps_do_not_consume_loading_budget(self):
        original=self.driver.get
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post],max_rounds=1))
            html='data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+self.fixture())
            with patch.object(self.driver,'get',side_effect=lambda url:original(html)):
                status,reason,trace=collect(self.driver,store,post)
            self.assertEqual(reason,'round_limit')
            self.assertEqual(trace.count('EXPAND'),1)
            self.assertEqual(len(store.rows),3)

    def test_message_paragraphs_with_embedded_link(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<span dir="auto"><div dir="auto">Phim <a href="/film">này</a> hay 😍!</div>'
            '<div dir="auto">ko dở.</div></span>')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Phim này hay 😍!\nko dở.')
        self.assertFalse(any('AUTHOR' in r['text_raw'] for r in rows))

    def test_tag_only_message_keeps_emoji_but_excludes_author(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<span dir="auto"><div dir="auto"><a href="/tagged">Bạn được tag</a>'
            '<img alt="😍"><img alt="👍"></div></span>')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Bạn được tag😍👍')
        self.assertFalse(any('AUTHOR' in r['text_raw'] for r in rows))

    def test_separate_body_candidates_remain_ambiguous(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<span dir="auto"><div dir="auto">Phim hay!</div></span>'
            '<span dir="auto"><div dir="auto">Nội dung khác.</div></span>')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,1)
        self.assertFalse(any(r['comment_id']=='101' for r in rows))

    def test_collect_loads_multiple_comment_pages(self):
        button=f'''<button data-page="0" onclick="
            const page=Number(this.dataset.page);
            for(let i=0;i&lt;10;i++){{
                const id=500+page*10+i;
                const row=document.createElement('div');
                row.setAttribute('aria-label','Comment by Fixture');
                row.innerHTML='&lt;div dir=auto&gt;Fixture '+id+'&lt;/div&gt;&lt;a href={GROUP}?comment_id='+id+'&gt;time&lt;/a&gt;';
                this.before(row);
            }}
            this.dataset.page=page+1;
            if(page===2)this.remove();">Xem thêm bình luận</button>'''
        html=self.fixture().replace('</article></div>',button+'</article></div>')
        original=self.driver.get
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post],max_rounds=6,post_timeout=10))
            fixture='data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+html)
            with patch.object(self.driver,'get',side_effect=lambda url:original(fixture)):
                status,reason,trace=collect(self.driver,store,post)
            self.assertEqual((status,reason),('success','visible_dom_exhausted'))
            self.assertEqual(len(store.rows),33)
            self.assertEqual(len({r['comment_id'] for r in store.rows}),33)

    def test_scroll_reaches_loaded_tail_without_jumping_virtual_spacer(self):
        comments=''.join(f'<div aria-label="Comment by Fixture" style="height:50px">'
            f'<div dir="auto">Fixture {i}</div><a href="{GROUP}?comment_id={500+i}">time</a></div>'
            for i in range(30))
        self.load(f'<div style="height:3000px">Background feed</div>'
            f'<div role="dialog" id="viewport" style="position:fixed;top:0;height:200px;overflow-y:auto">'
            f'<a href="{GROUP}">source</a>{comments}<div style="height:10000px"></div></div>')
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual((len(rows),errors),(30,0))
        before=self.driver.execute_script('return document.scrollingElement.scrollTop')
        self.assertTrue(dom(self.driver,GROUP,'scroll')['moved'])
        position=self.driver.execute_script('return document.getElementById("viewport").scrollTop')
        self.assertGreater(position,1000)
        self.assertLess(position,1600)
        self.assertEqual(self.driver.execute_script('return document.scrollingElement.scrollTop'),before)


if __name__=='__main__': unittest.main()
