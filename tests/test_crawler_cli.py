import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import argparse

from src.crawler.__main__ import browser_options, single_post, cdp_endpoint, browser_page


class CrawlerCliTests(unittest.TestCase):
    def test_prompt_url_and_movie_with_invalid_retry(self):
        answers=iter(['not a link','https://www.facebook.com/example/posts/123','', 'mua_do'])
        with patch('builtins.print'):
            post=single_post(ask=lambda prompt:next(answers))
        self.assertEqual(post,{'post_url':'https://www.facebook.com/example/posts/123','movie_id':'mua_do'})

    def test_flags_skip_prompts_and_keep_url_validation(self):
        ask=lambda prompt:self.fail('Flags must not prompt')
        self.assertEqual(single_post('https://www.facebook.com/x/posts/123','film',ask)['movie_id'],'film')
        with self.assertRaises(ValueError): single_post('bad-url','film',ask)

    def test_movie_flag_leaves_only_link_prompt(self):
        prompts=[]
        def ask(prompt):
            prompts.append(prompt)
            return 'https://www.facebook.com/x/posts/123'
        self.assertEqual(single_post(movie_id='mua_do',ask=ask)['movie_id'],'mua_do')
        self.assertEqual(len(prompts),1)

    def test_brave_detection_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable=Path(tmp)/'BraveSoftware/Brave-Browser/Application/brave.exe'
            executable.parent.mkdir(parents=True); executable.touch()
            with patch.dict(os.environ,{'PROGRAMFILES':tmp},clear=True):
                self.assertEqual(browser_options('brave'),{'executable_path':str(executable.resolve())})
            self.assertEqual(browser_options('brave',executable),{'executable_path':str(executable.resolve())})
            with self.assertRaises(ValueError): browser_options('brave',Path(tmp)/'missing.exe')
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'Brave not found'): browser_options('brave')
        self.assertEqual(browser_options('chrome'),{'channel':'chrome'})
        self.assertEqual(browser_options('chromium'),{})

    def test_cdp_only_local_without_tokens(self):
        self.assertEqual(cdp_endpoint('http://127.0.0.1:9222'),'http://127.0.0.1:9222')
        for bad in ('https://example.com:9222','http://0.0.0.0:9222',
                    'http://user:secret@localhost:9222','http://localhost:9222/?token=secret','http://localhost'):
            with self.subTest(bad=bad),self.assertRaises(argparse.ArgumentTypeError): cdp_endpoint(bad)

    def test_attached_facebook_tab_kept_open_without_navigation(self):
        pw=MagicMock(); context=pw.chromium.connect_over_cdp.return_value.contexts[0]
        other=MagicMock(); other.url='https://example.com'
        facebook=MagicMock(); facebook.url='https://www.facebook.com/groups/example'
        context.pages=[other,facebook]
        with browser_page(pw,Path('unused'),{},'http://127.0.0.1:9222') as page:
            self.assertIs(page,facebook)
        facebook.goto.assert_not_called()
        facebook.close.assert_not_called()
        context.close.assert_not_called()
        pw.chromium.connect_over_cdp.return_value.close.assert_not_called()
        pw.chromium.launch_persistent_context.assert_not_called()

    def test_attached_browser_stays_open_after_interrupt(self):
        pw=MagicMock(); browser=pw.chromium.connect_over_cdp.return_value
        context=MagicMock(); browser.contexts=[context]; context.pages=[]
        with self.assertRaises(KeyboardInterrupt):
            with browser_page(pw,Path('unused'),{},'http://127.0.0.1:9222'):
                raise KeyboardInterrupt()
        context.new_page.return_value.goto.assert_called_once()
        context.close.assert_not_called(); browser.close.assert_not_called()


if __name__=='__main__': unittest.main()
