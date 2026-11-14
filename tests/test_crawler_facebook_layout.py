import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from src.crawler.parser import post_id, comment_identity, observations
from src.crawler.browser import EXTRACT, collect, dom, access_barrier
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
        # collect() changes this shared driver's deadline; isolate fixture setup
        # from a previous test's deliberately tiny crawl timeout.
        self.driver.set_page_load_timeout(5)
        self.driver.get('data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+html))

    def test_access_barrier_survives_replaced_heading(self):
        self.load('<h2>Loading</h2>')
        stale = self.driver.find_element('css selector', 'h2')
        self.driver.execute_script("document.querySelector('h2').outerHTML='<h2>Temporarily blocked</h2>'")
        # Emulate the heading replacement observed between WebDriver lookup
        # and text retrieval; the current visible warning must still block.
        with patch.object(self.driver, 'find_elements', return_value=[stale]):
            self.assertTrue(access_barrier(self.driver))
        self.driver.execute_script("document.querySelector('h2').outerHTML='<h2>Comments</h2>'")
        with patch.object(self.driver, 'find_elements', return_value=[stale]):
            self.assertFalse(access_barrier(self.driver))

    def test_access_barrier_hidden_alert_and_visible_warning(self):
        self.load('<h1>Comments</h1><h2 hidden>captcha</h2><div role="alert" style="display:none">Temporarily blocked</div>')
        self.assertFalse(access_barrier(self.driver))
        self.driver.execute_script("document.querySelector('[role=alert]').style.display='block'")
        self.assertTrue(access_barrier(self.driver))

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

    def test_mention_free_text_keeps_original_and_plain_film_names(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<a role="link" href="/fixture.a">Bạn A</a> '
            '<a role="link" href="/profile.php?id=987">Bạn B</a>: '
            'Phim Mưa Đỏ hay! ❤️<br>Không dở.')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        row=rows[0]
        self.assertEqual(row['text_raw'],'Bạn A Bạn B: Phim Mưa Đỏ hay! ❤️\nKhông dở.')
        self.assertEqual(row['text_without_mentions'],'Phim Mưa Đỏ hay! ❤️\nKhông dở.')
        self.assertEqual(row['mention_count'],2)
        self.assertEqual(row['text_extraction_version'],'dom_text_v3')

    def test_inline_mentions_removed_but_external_links_and_plain_names_kept(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            'Diễn viên X diễn hay, <a href="/people/fixture-b/987">Bạn B</a> xem '
            '<a href="https://example.org/review">review</a> chưa?')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_without_mentions'],'Diễn viên X diễn hay, xem review chưa?')
        self.assertEqual(rows[0]['mention_count'],1)

    def test_group_user_mention_in_reply_removed_without_author_lookup(self):
        html=self.fixture().replace('Đúng vậy 👍',
            '<a href="/groups/123456/user/987654/">Bạn được tag</a>: '
            'Mong đạo diễn giữ tên phim Mưa Đỏ, phim hay 👍')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        reply=next(row for row in rows if row['comment_id']=='102')
        self.assertEqual(reply['text_raw'],'Bạn được tag: Mong đạo diễn giữ tên phim Mưa Đỏ, phim hay 👍')
        self.assertEqual(reply['text_without_mentions'],'Mong đạo diễn giữ tên phim Mưa Đỏ, phim hay 👍')
        self.assertEqual(reply['mention_count'],1)
        self.assertEqual(reply['parent_comment_id'],'101')

    def test_group_non_identity_links_and_plain_names_preserved(self):
        for href in ('https://example.org/groups/123/user/456/',
                     '/groups/123/posts/456/', '/groups/123/',
                     '/groups/123/user/456/posts/789/',
                     '/groups/123/user/not-a-numeric-id/',
                     '/groups/123/user/456/?comment_id=789'):
            with self.subTest(href=href):
                html=self.fixture().replace('Đúng vậy 👍',
                    f'Mong đạo diễn đọc <a href="{href}">đối chiếu</a>; Thanh Phương nói phim hay 👍')
                self.load(html)
                rows,errors=observations(dom(self.driver,GROUP),GROUP)
                self.assertEqual(errors,0)
                reply=next(row for row in rows if row['comment_id']=='102')
                self.assertEqual(reply['text_without_mentions'],reply['text_raw'])
                self.assertEqual(reply['mention_count'],0)

    def test_emoji_alt_is_unicode_not_generated_image_caption(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            'Phim hay <img alt="😂"><img alt="❤️"><img alt="👍🏽"><img alt="1️⃣">'
            '<img alt="Có thể là hình ảnh của một người">!')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Phim hay 😂❤️👍🏽1️⃣!')
        self.assertEqual(rows[0]['text_without_mentions'],rows[0]['text_raw'])
        self.assertEqual(rows[0]['non_text_media_count'],1)

    def test_tag_only_text_has_no_invented_sentiment(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<span dir="auto"><div dir="auto"><a href="/fixture.a">Bạn A</a></div></span>')
        self.load(html)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        self.assertEqual(rows[0]['text_raw'],'Bạn A')
        self.assertEqual(rows[0]['text_without_mentions'],'')
        self.assertEqual(rows[0]['mention_count'],1)

    def test_unchanged_reply_button_does_not_keep_run_alive(self):
        html=self.fixture().replace("this.textContent='done'","void(0)")
        original=self.driver.get
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post],max_rounds=20,post_timeout=10))
            fixture='data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+html)
            with patch.object(self.driver,'get',side_effect=lambda url:original(fixture)):
                status,reason,trace=collect(self.driver,store,post)
            self.assertEqual((status,reason),('success','visible_dom_exhausted'))
            self.assertLess(trace.count('EXPAND'),20)
            self.assertEqual(len(store.rows),3)

    def test_async_loaded_rows_are_read_before_idle_stop(self):
        action=f'''this.dataset.clicks=Number(this.dataset.clicks||0)+1;
            if(this.dataset.clicks==='2')setTimeout(()=>{{
              const row=document.createElement('div');row.setAttribute('aria-label','Comment by Fixture');
              row.innerHTML='&lt;div dir=auto&gt;Loaded later&lt;/div&gt;&lt;a href={GROUP}?comment_id=9999&gt;time&lt;/a&gt;';
              this.before(row);
            }},250)'''
        html=self.fixture().replace("this.textContent='done'",action)
        original=self.driver.get
        with tempfile.TemporaryDirectory() as tmp:
            post={'post_url':GROUP,'movie_id':'mua_do'}
            store=Store(tmp,dict(CONFIG,posts=[post],max_rounds=10,post_timeout=10,idle_rounds=1,settle_ms=500))
            fixture='data:text/html;charset=utf-8,'+quote('<meta charset="utf-8"><base href="https://www.facebook.com/">'+html)
            with patch.object(self.driver,'get',side_effect=lambda url:original(fixture)):
                status,reason,trace=collect(self.driver,store,post)
            self.assertEqual((status,reason),('success','visible_dom_exhausted'))
            self.assertTrue(any(row['comment_id']=='9999' for row in store.rows))

    def test_comment_citing_another_post_does_not_invalidate_source_dialog(self):
        html=self.fixture().replace('Phim hay 😍!<br>ko dở.',
            'Phim hay! <a href="/reference/posts/777">Xem đối chiếu</a>')
        self.load(html)
        self.assertEqual(dom(self.driver,GROUP,'inspect')['status'],'ready')
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual((len(rows),errors),(3,0))
        self.assertEqual(rows[0]['comment_id'],'101')
        self.assertEqual(rows[0]['text_without_mentions'],'Phim hay! Xem đối chiếu')

    def test_two_unseparated_post_headers_still_refused(self):
        self.load(f'<div role="dialog"><a href="{GROUP}">source</a>'
            '<a href="/other/posts/777">other source</a>'
            f'<div aria-label="Comment by Fixture"><div dir="auto">Keep private to source</div>'
            f'<a href="{GROUP}?comment_id=101">time</a></div></div>')
        self.assertEqual(dom(self.driver,GROUP,'inspect')['status'],'missing_scope')
        self.assertEqual(dom(self.driver,GROUP),[])

    def test_clean_view_mentions_urls_and_sentiment_signals(self):
        cases=[
            ('<a href="/fixture.a">An Bình</a>: ko dở :))', 'ko dở :))',1,0,'KEEP'),
            ('<a href="/fixture.a">An</a> <a href="/profile.php?id=42">Bình</a> hayyy 😂', 'hayyy 😂',2,0,'KEEP'),
            ('Không <a href="/groups/movie.group/user/42/">An Bình</a> chán!', 'Không chán!',1,0,'KEEP'),
            ('<a href="/fixture.a">An Bình</a>', '',1,0,'EXCLUDE'),
            ('Chưa dở https://example.org/review. :))', 'Chưa dở . :))',0,1,'KEEP'),
            ('ko https://example.org/?a=1&amp;b=2 hay www.example.org 😭', 'ko hay 😭',0,2,'KEEP'),
            ('Chẳng tệ <a href="https://example.org/review">https://example.org/review</a> đâu!', 'Chẳng tệ đâu!',0,1,'KEEP'),
            ('<span>giữ chữ <a href="/other/posts/777"><img alt="Preview image">bài chia sẻ</a> không tệ</span>', 'giữ chữ không tệ',0,1,'KEEP'),
            ('<a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.org"><img alt="Preview image">Preview</a>', '',0,1,'EXCLUDE'),
            ('😂 😭 ❤️', '😂 😭 ❤️',0,0,'KEEP'),
            ('<img alt="😂"><img alt="❤️">', '😂❤️',0,0,'KEEP'),
            ('ko đc cx mn :)) =)) :v :( :):) :-) -_- - hayyy!!!', 'ko đc cx mn :)) =)) :v :( :):) :-) -_- - hayyy!!!',0,0,'KEEP'),
            ('Trấn Thành và nhân vật Sen diễn hay', 'Trấn Thành và nhân vật Sen diễn hay',0,0,'KEEP'),
            ('<a role="link">An Bình</a> phim hay', 'An Bình phim hay',0,0,'REVIEW'),
            ('<a href="/groups/x/user/not-id/">An Bình</a> phim hay', 'An Bình phim hay',0,0,'REVIEW'),
            ('<a href="/hashtag/phim">#phim</a> không dở', '#phim không dở',0,0,'KEEP'),
            ('<a href="/fixture.a">An</a> :):) -_- - không dở', ':):) -_- - không dở',1,0,'KEEP'),
            ('<a href="/fixture.a">An</a> :-)', ':-)',1,0,'KEEP'),
            ('https://example.org/:))', ':))',0,1,'KEEP'),
            ('www.example.org=))', '=))',0,1,'KEEP'),
            ('<img alt="A photo of someone">', '',0,0,'EXCLUDE'),
            ('<a href="/fixture.a">An</a> https://example.org', '',1,1,'EXCLUDE'),
        ]
        for fragment,cleaned,mentions,urls,status in cases:
            with self.subTest(fragment=fragment):
                self.load(self.fixture().replace('Phim hay 😍!<br>ko dở.',
                    '<span data-comment-body>'+fragment+'</span>'))
                rows,errors=observations(dom(self.driver,GROUP),GROUP)
                self.assertEqual(errors,0)
                row=next(r for r in rows if r['comment_id']=='101')
                self.assertEqual(row['text_clean'],cleaned)
                self.assertEqual((row['mention_count'],row['url_count'],row['clean_status']),(mentions,urls,status))
                if status=='REVIEW': self.assertTrue(row['clean_review_reasons'])
                if not mentions and not urls: self.assertEqual(row['text_raw'],cleaned)

    def test_clean_view_nested_reply_never_inherits_parent_author_or_ui(self):
        self.load(self.fixture().replace('Đúng vậy 👍',
            '<a href="/profile.php?id=99">Tên được tag</a> Không dở 👍 '
            '<a href="https://example.org">https://example.org</a><button>Reply</button><time>3 giờ</time>'))
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        parent=next(r for r in rows if r['comment_id']=='101')
        reply=next(r for r in rows if r['comment_id']=='102')
        self.assertEqual(parent['text_clean'],'Phim hay 😍!\nko dở.')
        self.assertEqual(reply['text_clean'],'Không dở 👍')
        self.assertEqual(reply['parent_comment_id'],'101')
        self.assertNotIn('AUTHOR',reply['text_raw'])
        self.assertNotIn('3 giờ',reply['text_raw'])

    def test_punctuation_review_but_emoji_emoticons_kept(self):
        for fragment,status in [('<a href="/fixture.a">Chee</a> ?','REVIEW'),
                                ('?! ...','REVIEW'),(':))','KEEP'),(':):)','KEEP'),
                                ('-_-','KEEP'),('❤️','KEEP'),('😂','KEEP')]:
            with self.subTest(fragment=fragment):
                self.load(self.fixture().replace('Phim hay 😍!<br>ko dở.',
                    '<span data-comment-body>'+fragment+'</span>'))
                rows,errors=observations(dom(self.driver,GROUP),GROUP)
                self.assertEqual(errors,0)
                row=next(r for r in rows if r['comment_id']=='101')
                self.assertEqual(row['clean_status'],status)
                if status=='REVIEW':self.assertIn('punctuation_only',row['clean_review_reasons'])

    def test_clean_evidence_utf16_spans_without_account_ids(self):
        fragment='😂 <a href="/groups/example/user/42/">Chee</a> hay '
        fragment+='https://example.org :)) <a href="https://example.net"><img alt="Preview">preview</a>'
        self.load(self.fixture().replace('Phim hay 😍!<br>ko dở.',
            '<span data-comment-body>'+fragment+'</span>'))
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual(errors,0)
        row=next(r for r in rows if r['comment_id']=='101')
        self.assertEqual(row['text_clean'],'😂 hay :))')
        events=row['clean_evidence'];self.assertEqual(len(events),3)
        raw=row['text_raw'].encode('utf-16-le')
        removed=[raw[e['raw_start']*2:e['raw_end']*2].decode('utf-16-le') for e in events]
        self.assertEqual(removed,['Chee','https://example.org','preview'])
        self.assertEqual([e['rule'] for e in events],['group_user_link','explicit_url_text','shared_link'])
        self.assertTrue(all(set(e)=={'kind','rule','raw_start','raw_end'} for e in events))

    def test_media_presence_does_not_decide_text_sentiment_or_context(self):
        cases=[('Phim rất hay 😂<img alt="A photo">','Phim rất hay 😂','KEEP',1),
               ('<img alt="A photo">','','EXCLUDE',1),
               ('<video><span>Generated caption</span></video>','','EXCLUDE',1),
               ('Không dở <img alt="GIF animation">','Không dở','KEEP',1),
               ('😂<img alt="A photo">','😂','KEEP',1),
               (':))<img alt="A photo">',':))','KEEP',1),
               ('<img alt="😂">','😂','KEEP',0)]
        for fragment,expected,status,media_count in cases:
            with self.subTest(fragment=fragment):
                self.load(self.fixture().replace('Phim hay 😍!<br>ko dở.',
                    '<span data-comment-body>'+fragment+'</span>'))
                candidates=dom(self.driver,GROUP);raw=next(c for c in candidates if c.get('permalink','').endswith('comment_id=101'))['text_raw']
                rows,errors=observations(candidates,GROUP);self.assertEqual(errors,0)
                row=next(r for r in rows if r['comment_id']=='101')
                self.assertEqual((row['text_clean'],row['clean_status'],row['non_text_media_count']),(expected,status,media_count))
                self.assertEqual(row['text_raw'],raw)
                self.assertNotIn('non_text_media',row['clean_review_reasons'])
        # No keyword heuristic: a human may explicitly request REVIEW instead.
        self.load(self.fixture().replace('Đúng vậy 👍','Như ảnh <img alt="A photo">'))
        candidates=dom(self.driver,GROUP)
        candidate=next(c for c in candidates if c.get('is_reply'))
        original_raw=candidate['text_raw']
        candidate.update(clean_status='REVIEW',clean_review_reasons=['media_context_required'])
        rows,errors=observations([candidate],GROUP)
        self.assertEqual(errors,0);self.assertEqual(rows[0]['clean_status'],'REVIEW')
        self.assertEqual(rows[0]['text_raw'],original_raw)

    def test_url_positions_fragments_and_ambiguous_anchor_prose(self):
        cases=[('Phim này hay 😂 https://example.com','Phim này hay 😂',1,'KEEP'),
               ('https://example.com phim dở thật','phim dở thật',1,'KEEP'),
               ('Xem ở www.example.com nhé','Xem ở nhé',1,'KEEP'),
               ('https://example.com http://example.net www.example.org','',3,'EXCLUDE'),
               ('<a href="/fixture.a">Minh</a> https://example.com 😂','😂',1,'KEEP'),
               ('Diễn xuất của Trấn Thành hay','Diễn xuất của Trấn Thành hay',0,'KEEP'),
               ('https://exa<span>mple.com</span> phim hay','phim hay',1,'KEEP'),
               ('<a href="https://example.com">Trấn Thành diễn hay</a> 😂','Trấn Thành diễn hay 😂',0,'REVIEW'),
               ('<a href="/other/posts/777">Mưa Đỏ rất hay</a>','Mưa Đỏ rất hay',0,'REVIEW'),
               ('<a href="https://example.org/hashtag/phim">đánh giá phim</a>','đánh giá phim',0,'REVIEW')]
        for fragment,expected,urls,status in cases:
            with self.subTest(fragment=fragment):
                self.load(self.fixture().replace('Phim hay 😍!<br>ko dở.',
                    '<span data-comment-body>'+fragment+'</span>'))
                rows,errors=observations(dom(self.driver,GROUP),GROUP);self.assertEqual(errors,0)
                row=next(r for r in rows if r['comment_id']=='101')
                self.assertEqual((row['text_clean'],row['url_count'],row['clean_status']),(expected,urls,status))
                self.assertNotRegex(row['text_clean'],r'https?://|www\.')

    def test_reply_with_mention_and_media_keeps_only_its_own_text(self):
        self.load(self.fixture().replace('Đúng vậy 👍',
            '<a href="/profile.php?id=99">Minh</a> Không chán :))<img alt="A photo">'))
        rows,errors=observations(dom(self.driver,GROUP),GROUP);self.assertEqual(errors,0)
        reply=next(r for r in rows if r['comment_id']=='102')
        self.assertEqual((reply['text_clean'],reply['clean_status'],reply['mention_count'],reply['non_text_media_count']),
                         ('Không chán :))','KEEP',1,1))
        self.assertEqual(reply['parent_comment_id'],'101')
        self.assertNotIn('AUTHOR',reply['text_raw']);self.assertNotIn('Phim hay',reply['text_raw'])

    def test_innermost_source_dialog_excludes_outer_dialog_comments(self):
        start=self.fixture().index('<div role="dialog">')
        inner=self.fixture()[start:]
        self.load(f'<div role="dialog"><a href="{GROUP}">source</a>'
            f'<div aria-label="Comment by Outside"><div dir="auto">OUTER NOT TARGET</div>'
            f'<a href="{GROUP}?comment_id=888">time</a></div>{inner}</div>')
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual((len(rows),errors),(3,0))
        self.assertFalse(any(row['comment_id']=='888' for row in rows))

    def test_foreign_comment_permalink_is_not_collected(self):
        extra='<div aria-label="Comment by Other"><div dir="auto">FOREIGN COMMENT</div><a href="/other/posts/777?comment_id=999">time</a></div>'
        self.load(self.fixture().replace('</article></div>',extra+'</article></div>'))
        self.assertEqual(dom(self.driver,GROUP,'inspect')['comment_containers'],3)
        rows,errors=observations(dom(self.driver,GROUP),GROUP)
        self.assertEqual((len(rows),errors),(3,0))
        self.assertFalse(any(row['comment_id']=='999' for row in rows))


if __name__=='__main__': unittest.main()
