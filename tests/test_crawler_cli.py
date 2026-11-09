import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import argparse
import importlib.util

from src.crawler.__main__ import browser_options, single_post, cdp_endpoint, browser_page, debugger_version, attached_driver_path


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

    def test_two_factor_page_is_an_access_barrier(self):
        from src.crawler.browser import access_barrier
        driver=MagicMock(); driver.current_url='https://www.facebook.com/two_step_verification/authentication/'
        self.assertTrue(access_barrier(driver))
        driver.find_elements.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('selenium'),'Selenium optional')
    @patch('src.crawler.__main__.debugger_version',return_value='157.0.8103.39')
    @patch('src.crawler.__main__.attached_driver_path',return_value=Path('chromedriver.exe'))
    def test_attached_facebook_tab_kept_open_without_navigation(self,driver_path,version):
        with patch('selenium.webdriver.Chrome') as chrome, patch('selenium.webdriver.chrome.service.Service') as service:
            driver=chrome.return_value
            driver.window_handles=['other','fb']
            def switch(handle):
                driver.current_url='https://www.facebook.com/groups/example' if handle=='fb' else 'https://example.com'
            driver.switch_to.window.side_effect=switch
            with browser_page(Path('unused'),{},'http://127.0.0.1:9222') as page:
                self.assertIs(page,driver)
            driver.get.assert_not_called(); driver.close.assert_not_called(); driver.quit.assert_not_called()
            driver.command_executor.close.assert_called_once(); service.return_value.stop.assert_called_once()
            self.assertEqual(chrome.call_args.kwargs['options'].debugger_address,'127.0.0.1:9222')
            self.assertEqual(chrome.call_args.kwargs['options'].browser_version,'157.0.8103.39')
            self.assertNotIn('detach',chrome.call_args.kwargs['options'].to_capabilities()['goog:chromeOptions'])

    @unittest.skipUnless(importlib.util.find_spec('selenium'),'Selenium optional')
    @patch('src.crawler.__main__.debugger_version',return_value='157.0.8103.39')
    @patch('src.crawler.__main__.attached_driver_path',return_value=Path('chromedriver.exe'))
    def test_attached_browser_stays_open_after_interrupt(self,driver_path,version):
        with patch('selenium.webdriver.Chrome') as chrome, patch('selenium.webdriver.chrome.service.Service') as service:
            driver=chrome.return_value; driver.window_handles=[]
            with self.assertRaises(KeyboardInterrupt):
                with browser_page(Path('unused'),{},'http://127.0.0.1:9222'):
                    raise KeyboardInterrupt()
            driver.switch_to.new_window.assert_called_once_with('tab')
            driver.get.assert_called_once(); driver.quit.assert_not_called()
            service.return_value.stop.assert_called_once()

    @unittest.skipUnless(importlib.util.find_spec('selenium'),'Selenium optional')
    def test_launched_driver_owns_cleanup(self):
        with patch('selenium.webdriver.Chrome') as chrome, patch('selenium.webdriver.chrome.service.Service'):
            with browser_page(Path('data/test_profile'),{'executable_path':'brave.exe'}):
                pass
            chrome.return_value.quit.assert_called_once()
            options=chrome.call_args.kwargs['options']
            self.assertEqual(options.binary_location,'brave.exe')
            self.assertTrue(any(a.startswith('--user-data-dir=') for a in options.arguments))

    def test_matching_driver_uses_attached_version(self):
        import io
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"Browser":"Chrome/157.0.8103.39"}')):
            self.assertEqual(debugger_version('http://127.0.0.1:9222'),'157.0.8103.39')
        if importlib.util.find_spec('selenium'):
            with patch('selenium.webdriver.common.selenium_manager.SeleniumManager.binary_paths',return_value={'driver_path':'driver.exe'}) as manager:
                self.assertEqual(attached_driver_path('157.0.8103.39'),Path('driver.exe'))
                manager.assert_called_once_with(['--browser','chrome','--browser-version','157','--avoid-browser-download'])


if __name__=='__main__': unittest.main()
