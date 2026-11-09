import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.crawler.__main__ import browser_options, single_post


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


if __name__=='__main__': unittest.main()
