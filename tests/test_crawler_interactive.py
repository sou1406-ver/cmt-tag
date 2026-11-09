import json
from pathlib import Path
import tempfile
import unittest

from src.crawler.interactive import session
from src.crawler.store import Store, validate, export_run
from src.crawler.parser import post_id
from tests.test_crawler import CONFIG, observation

URL='https://www.facebook.com/x/posts/123'
OTHER='https://www.facebook.com/x/posts/456'


class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=Store(self.root,dict(CONFIG,posts=[],interactive=True))
        self.calls=[]; self.messages=[]

    def read(self,lines):
        iterator=iter(lines)
        def reader(prompt):
            value=next(iterator)
            if isinstance(value,BaseException): raise value
            return value
        return reader

    def collector(self,page,store,post):
        self.calls.append(dict(post))
        row=observation(str(100+len(self.calls)))
        row['post_id']=post_id(post['post_url'])
        row['comment_permalink']=post['post_url']+('&' if '?' in post['post_url'] else '?')+'comment_id='+row['comment_id']
        store.add(row,post,'fixture_page')
        return 'success','visible_dom_exhausted',[]

    def run_session(self,lines,collector=None,store=None):
        return session(store or self.store,None,read_line=self.read(lines),collector=collector or self.collector,
                       emit=self.messages.append,data_root=self.root)

    def test_invalid_quoted_url_duplicate_movie_change_and_export(self):
        code=self.run_session(['mua_do','bad url',' "'+URL+'?fbclid=tracking" ',URL,'movie phim_b',OTHER,''])
        self.assertEqual(code,0); self.assertEqual(len(self.calls),2)
        self.assertEqual([p['movie_id'] for p in self.calls],['mua_do','phim_b'])
        self.assertTrue(any('Link không hợp lệ' in m for m in self.messages))
        self.assertTrue(any('bỏ qua' in m for m in self.messages))
        self.assertTrue(any('comment mới=1' in m for m in self.messages))
        self.assertTrue(any('validate --run '+self.store.run_id in m for m in self.messages))
        self.assertTrue(any('export  --run '+self.store.run_id in m for m in self.messages))
        report=validate(self.store.path)
        self.assertEqual(report['total_records'],2); self.assertEqual(report['requested_posts'],2)
        self.assertEqual(report['parse_errors'],0)
        export_run(self.store.path,self.root/'export')

    def test_empty_session_and_resume_same_run(self):
        self.run_session(['mua_do',''])
        self.assertEqual(len(self.calls),0)
        resumed=Store(self.root,resume=self.store.run_id)
        self.run_session(['',URL,''],store=resumed)
        self.assertEqual(resumed.run_id,self.store.run_id)
        self.assertEqual(len(resumed.rows),1)

    def test_query_string_is_read_as_one_line(self):
        url='https://www.facebook.com/story.php?story_fbid=123&id=42'
        self.run_session(['mua_do',"'"+url+"'",''])
        self.assertEqual(self.calls[0]['post_url'],url)
        self.assertEqual(validate(self.store.path)['total_records'],1)

    def test_resume_preserves_success_and_movie(self):
        self.run_session(['mua_do',URL,''])
        resumed=Store(self.root,resume=self.store.run_id)
        self.run_session(['',URL,OTHER,''],store=resumed)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[-1]['movie_id'],'mua_do')
        self.assertEqual(len(resumed.rows),2)
        self.assertEqual(validate(resumed.path)['requested_posts'],2)

    def test_interrupt_inside_collector_then_resume(self):
        def stop(page,store,post):
            store.add(observation(),post,'first')
            raise KeyboardInterrupt()
        self.assertEqual(self.run_session(['mua_do',URL],stop),130)
        self.assertEqual(json.loads((self.store.path/'checkpoint.json').read_text())['status'],'interrupted')
        resumed=Store(self.root,resume=self.store.run_id)
        self.assertEqual(len(resumed.rows),1)
        self.run_session(['',URL,''],store=resumed)
        self.assertEqual(len(resumed.rows),2)

    def test_interrupt_at_prompt(self):
        self.assertEqual(self.run_session(['mua_do',KeyboardInterrupt()]),130)
        self.assertEqual(json.loads((self.store.path/'checkpoint.json').read_text())['status'],'interrupted')

    def test_convert_existing_run_without_editing_original_config(self):
        old=Store(self.root/'legacy',dict(CONFIG,posts=[]))
        before=(old.path/'config.json').read_bytes()
        old.finish()
        resumed=Store(self.root/'legacy',resume=old.run_id,interactive=True)
        self.run_session(['mua_do',URL,''],store=resumed)
        self.assertEqual((old.path/'config.json').read_bytes(),before)
        self.assertEqual(validate(old.path)['total_records'],1)

    def test_link_pasted_at_movie_prompt_is_not_saved_as_movie(self):
        self.run_session([URL,'mua_do',''])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0],{'post_url':URL,'movie_id':'mua_do'})
        self.assertEqual(json.loads((self.store.path/'interactive_state.json').read_text())['movie_id'],'mua_do')

    def test_invalid_saved_movie_is_not_offered_as_default(self):
        (self.store.path/'interactive_state.json').write_text(json.dumps({'movie_id':URL}))
        prompts=[]; answers=iter(['mua_do',''])
        def read(prompt): prompts.append(prompt); return next(answers)
        session(self.store,None,read_line=read,collector=self.collector,emit=self.messages.append)
        self.assertNotIn(URL,prompts[0])
        self.assertEqual(json.loads((self.store.path/'interactive_state.json').read_text())['movie_id'],'mua_do')

    def test_movie_command_cannot_replace_movie_with_url(self):
        self.run_session(['mua_do','movie '+URL,OTHER,''])
        self.assertEqual(self.calls[0]['movie_id'],'mua_do')
        self.assertEqual(json.loads((self.store.path/'interactive_state.json').read_text())['movie_id'],'mua_do')


if __name__=='__main__': unittest.main()
