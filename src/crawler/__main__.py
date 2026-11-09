"""Run python -m src.crawler --help."""
import argparse
import csv
import json
import os
from contextlib import contextmanager, ExitStack
from pathlib import Path
from urllib.parse import urlsplit

from .parser import facebook_url
from .store import Store, export_run, validate
from .locking import RunLock, RunBusyError, LegacyRunLockError


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError('Must be positive')
    return value


def single_post(url=None, movie_id=None, ask=None):
    ask = ask or input
    if url is None:
        while True:
            try:
                url = facebook_url(ask('Link bai Facebook: ').strip())
                break
            except ValueError:
                print('Link khong hop le. Hay dan link https://www.facebook.com/...')
    else:
        url = facebook_url(url)
    if movie_id is None:
        while not movie_id:
            movie_id = ask('Ma phim (vi du: mua_do): ').strip()
    if not movie_id.strip():
        raise ValueError('Every post needs a movie_id')
    return {'post_url':url, 'movie_id':movie_id.strip()}


def browser_options(channel, browser_path=None):
    if browser_path is not None:
        if not browser_path.is_file():
            raise ValueError('Browser executable not found; check --browser-path')
        return {'executable_path':str(browser_path.resolve())}
    if channel == 'brave':
        for variable in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            base = os.environ.get(variable)
            if base:
                path = Path(base)/'BraveSoftware/Brave-Browser/Application/brave.exe'
                if path.is_file():
                    return {'executable_path':str(path.resolve())}
        raise ValueError('Brave not found. Use --channel brave --browser-path "PATH_TO_brave.exe"')
    return {'channel':'chrome'} if channel == 'chrome' else {}


def cdp_endpoint(value):
    parts=urlsplit(value)
    if (parts.scheme!='http' or parts.hostname not in ('127.0.0.1','localhost','::1') or
            parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment):
        raise argparse.ArgumentTypeError('CDP must be a local HTTP endpoint, e.g. http://127.0.0.1:9222')
    try:
        if not parts.port: raise ValueError()
    except ValueError as exc:
        raise argparse.ArgumentTypeError('CDP needs a valid local port') from exc
    return value


def debugger_version(endpoint):
    import re
    from urllib.request import urlopen
    with urlopen(cdp_endpoint(endpoint).rstrip('/')+'/json/version',timeout=5) as response:
        browser=json.load(response).get('Browser','')
    match=re.search(r'(?:Chrome|Chromium)/(\d+\.\d+\.\d+\.\d+)',browser)
    if not match: raise ValueError('Cannot determine attached Chromium version; use --driver-path')
    return match[1]


def attached_driver_path(version):
    from selenium.webdriver.common.selenium_manager import SeleniumManager
    # Brave's patch version need not exist as a Chrome-for-Testing binary.
    # Only resolve a matching-major driver; the browser is already running.
    result=SeleniumManager().binary_paths(['--browser','chrome','--browser-version',version.split('.')[0],
                                          '--avoid-browser-download'])
    return Path(result['driver_path'])


@contextmanager
def browser_page(profile,launch_options,cdp_url=None,driver_path=None):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    if driver_path and not driver_path.is_file():
        raise ValueError('ChromeDriver not found; check --driver-path')
    options=webdriver.ChromeOptions()
    options.page_load_strategy='eager'
    if launch_options.get('executable_path'):
        options.binary_location=launch_options['executable_path']
    if cdp_url:
        endpoint=urlsplit(cdp_url)
        options.debugger_address=endpoint.netloc
        if driver_path is None:
            options.browser_version=debugger_version(cdp_url)
        # Do not add launch-only options to a debuggerAddress connection.
    else:
        options.add_argument('--user-data-dir='+str(profile.resolve()))
    os.environ.setdefault('SE_CACHE_PATH',str(Path('data/selenium_cache').resolve()))
    if cdp_url and driver_path is None:
        driver_path=attached_driver_path(options.browser_version)
    service=Service(executable_path=str(driver_path.resolve()) if driver_path else None)
    driver=webdriver.Chrome(service=service,options=options)
    try:
        driver.set_page_load_timeout(30)
        if cdp_url:
            found=False
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                if urlsplit(driver.current_url).hostname in ('facebook.com','www.facebook.com','m.facebook.com','web.facebook.com'):
                    found=True; break
            if not found:
                driver.switch_to.new_window('tab')
                driver.get('https://www.facebook.com/')
        else:
            driver.get('https://www.facebook.com/')
        yield driver
    finally:
        if cdp_url:
            # Do not send WebDriver quit/close to an attached user browser.
            try:
                driver.command_executor.close()
            finally:
                service.stop()
        else:
            driver.quit()


def main():
    import sys
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Collect accessible Facebook movie comments; no labels or training.')
    sub = ap.add_subparsers(dest='command',required=True)
    login=sub.add_parser('login',help='Open normal browser for manual login; close it before crawling with the same profile')
    login.add_argument('--channel',choices=['chrome','chromium','brave'],default='brave')
    login.add_argument('--profile',type=Path)
    login.add_argument('--browser-path',type=Path)
    for cmd in ('crawl-post','crawl-batch','interactive'):
        p = sub.add_parser(cmd)
        if cmd=='crawl-post':
            p.add_argument('--url',help='HTTPS Facebook post URL; prompt if omitted for a new run')
            p.add_argument('--movie-id',help='Movie code; prompt if omitted for a new run')
        elif cmd=='crawl-batch':
            p.add_argument('--input',type=Path,help='UTF-8 CSV with movie_id,post_url; required for a new run')
        else:
            p.add_argument('--movie-id',help='Initial movie code; prompted once if omitted')
        p.add_argument('--resume',help='Resume an interrupted run; saved inputs/settings are authoritative')
        p.add_argument('--data-root',type=Path,default=Path('data'),help='Local data directory')
        p.add_argument('--source-dataset',help='Batch provenance identifier; defaults to run ID')
        p.add_argument('--profile',type=Path,help='Dedicated profile; default data/browser_profile (Brave: data/browser_profile_brave)')
        p.add_argument('--channel',choices=['chrome','chromium','brave'],default='chromium',help='Selenium browser: Brave or Chrome auto-discovery (chromium is a compatibility alias)')
        p.add_argument('--browser-path',type=Path,help='Optional browser executable path; overrides channel auto-detection')
        p.add_argument('--cdp-url',type=cdp_endpoint,help='Attach to a manually opened local browser, e.g. http://127.0.0.1:9222; do not close it on exit')
        p.add_argument('--driver-path',type=Path,help='Optional matching chromedriver.exe; otherwise use Selenium Manager')
        for flag,default,help_text in [
            ('max-posts',100,'Maximum posts in this run'),('max-comments',5000,'Maximum stored observations per post'),
            ('post-timeout',300,'Seconds per post attempt'),('max-rounds',100,'Expansion/scroll rounds per post'),
            ('max-actions',20,'Button clicks per round'),('wait-ms',10000,'Navigation/action timeout in milliseconds'),
            ('settle-ms',1500,'DOM polling timeout per scroll'),('idle-rounds',3,'Idle rounds before stopping')]:
            p.add_argument('--'+flag,type=positive,default=default,help=help_text)
        p.add_argument('--retries',type=int,choices=range(0,6),default=2,help='Retries for transient browser exceptions (0..5)')
    p = sub.add_parser('validate',help='Validate raw rows and show collection quality')
    p.add_argument('--run',required=True)
    p.add_argument('--data-root',type=Path,default=Path('data'))
    p = sub.add_parser('export',help='Create immutable CSV + Phase B import config; truncated raw stays out of import')
    p.add_argument('--run',required=True)
    p.add_argument('--format',choices=['csv'],default='csv')
    p.add_argument('--data-root',type=Path,default=Path('data'))
    p.add_argument('--output',type=Path,help='New directory; default data/imports/<run_id>')
    p.add_argument('--allow-partial',action='store_true',help='Export validated complete rows despite skipped DOM observations; record coverage warnings')
    args = ap.parse_args()
    try:
        if args.command=='login':
            from .login import open_login
            profile=args.profile or Path('data/browser_profile_brave' if args.channel=='brave' else 'data/browser_profile')
            profile=open_login(profile,args.channel,args.browser_path)
            print('Đã mở trình duyệt thường với profile: '+str(profile))
            print('Tự đăng nhập và hoàn tất xác thực. Đăng nhập xong ĐÓNG cửa sổ này trước khi chạy interactive với cùng --channel/--profile.')
            return 0
        if args.command in ('validate','export'):
            import re
            if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run):
                raise ValueError('Invalid run ID')
            path=args.data_root/'crawl_runs'/args.run
            if args.command=='validate':
                report=validate(path)
                print(json.dumps(report,ensure_ascii=False,indent=2))
                return 2 if report['parse_errors'] or report['duplicate_source_ids_in_raw'] else 0
            output=export_run(path,args.output or args.data_root/'imports'/args.run,allow_partial=args.allow_partial)
            print(json.dumps({'export':str(output)},ensure_ascii=False))
            return 0
        config = None
        if not args.resume:
            if args.command=='interactive':
                posts=[]
            elif args.command=='crawl-post':
                posts=[single_post(args.url,args.movie_id)]
            else:
                if not args.input:
                    raise ValueError('--input is required for a new batch')
                with args.input.open(encoding='utf-8-sig',newline='') as f:
                    posts=[{'post_url':facebook_url(r['post_url']),'movie_id':r['movie_id']} for r in csv.DictReader(f)]
            if args.command!='interactive' and (not posts or any(not p['movie_id'].strip() for p in posts)):
                raise ValueError('Every post needs a movie_id')
            if len({p['post_url'] for p in posts}) != len(posts):
                raise ValueError('Duplicate post URLs; provide each post once')
            config={k:getattr(args,k) for k in ('max_posts','max_comments','post_timeout','max_rounds','max_actions','wait_ms','settle_ms','idle_rounds','retries')}
            config.update(posts=posts,source_dataset=args.source_dataset)
            if args.command=='interactive': config['interactive']=True
        from .browser import run_posts
        if args.cdp_url and (args.profile or args.browser_path):
            raise ValueError('--cdp-url uses the open browser; omit --profile and --browser-path')
        launch_options = {} if args.cdp_url else browser_options(args.channel,args.browser_path)
        profile = args.profile or Path('data/browser_profile_brave' if args.channel=='brave' else 'data/browser_profile')
        import re
        if args.resume and not re.fullmatch(r'[A-Za-z0-9_-]+',args.resume):
            raise ValueError('Invalid run ID')
        lock = args.data_root/'crawl_runs'/args.resume/'.browser.lock' if args.resume else None
        with ExitStack() as locks:
            if lock: locks.enter_context(RunLock(lock))
            store=Store(args.data_root/'crawl_runs',config,resume=args.resume,interactive=args.command=='interactive')
            if args.command=='interactive' and not store.config.get('interactive'):
                raise ValueError('Use an interactive run ID with interactive --resume')
            print('Run: '+store.run_id,flush=True)
            print(f"Giới hạn mỗi bài: {store.config['max_comments']} comment, "
                  f"{store.config['max_rounds']} vòng tải, {store.config['post_timeout']} giây."
                  + (' Resume dùng cấu hình đã lưu; muốn tăng giới hạn hãy tạo run mới.' if args.resume else ''),flush=True)
            if lock is None:
                lock=store.path/'.browser.lock'
                locks.enter_context(RunLock(lock))
            with browser_page(profile,launch_options,args.cdp_url,args.driver_path) as page:
                input('Log in manually in the browser, then press Enter here. Ctrl+C pauses the run. ')
                if args.command=='interactive':
                    from .interactive import session
                    return session(store,page,movie_id=args.movie_id,data_root=args.data_root)
                else:
                    report=run_posts(store,page)
                    print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    except (KeyboardInterrupt, EOFError):
        if 'store' in locals(): store.checkpoint('interrupted')
        print('Interrupted; raw data retained. Resume with the printed run ID.')
        return 130
    except (RunBusyError,LegacyRunLockError) as exc:
        print(json.dumps({'error_type':type(exc).__name__,'hint':str(exc)}))
        return 2
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        # Safe local validation errors have no browser/page contents.
        print(json.dumps({'error_type':type(exc).__name__,
                         'hint':str(exc) if str(exc).startswith(('Brave not found','Browser executable not found',
                             'Unparsed DOM observations','Validation failed','No complete records')) else
                         'Invalid input or run path, completed run, existing export, or active/stale .browser.lock. See docs/CRAWLER.md.'}))
        return 2
    except Exception as exc:
        # Never print browser exceptions, credential-bearing URLs or page dumps.
        print(json.dumps({'error_type':type(exc).__name__,
                         'hint':'Check inputs, dependencies, run status and dedicated profile. See docs/CRAWLER.md.'}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
