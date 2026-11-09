"""Run python -m src.crawler --help."""
import argparse
import csv
import json
from pathlib import Path

from .parser import facebook_url
from .store import Store, export_run, validate


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError('Must be positive')
    return value


def main():
    import sys
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Collect accessible Facebook movie comments; no labels or training.')
    sub = ap.add_subparsers(dest='command',required=True)
    for cmd in ('crawl-post','crawl-batch'):
        p = sub.add_parser(cmd)
        if cmd=='crawl-post':
            p.add_argument('--url',required=True,help='HTTPS Facebook post URL')
            p.add_argument('--movie-id',required=True,help='Movie code supplied by you')
        else:
            p.add_argument('--input',type=Path,help='UTF-8 CSV with movie_id,post_url; required for a new run')
        p.add_argument('--resume',help='Resume an interrupted run; saved inputs/settings are authoritative')
        p.add_argument('--data-root',type=Path,default=Path('data'),help='Local data directory')
        p.add_argument('--source-dataset',help='Batch provenance identifier; defaults to run ID')
        p.add_argument('--profile',type=Path,default=Path('data/browser_profile'),help='Dedicated private browser profile; never your everyday Chrome profile')
        p.add_argument('--channel',choices=['chrome','chromium'],default='chromium',help='Use installed Chrome or Playwright Chromium')
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
    args = ap.parse_args()
    try:
        if args.command in ('validate','export'):
            import re
            if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run):
                raise ValueError('Invalid run ID')
            path=args.data_root/'crawl_runs'/args.run
            if args.command=='validate':
                report=validate(path)
                print(json.dumps(report,ensure_ascii=False,indent=2))
                return 2 if report['parse_errors'] or report['duplicate_source_ids_in_raw'] else 0
            output=export_run(path,args.output or args.data_root/'imports'/args.run)
            print(json.dumps({'export':str(output)},ensure_ascii=False))
            return 0
        config = None
        if not args.resume:
            if args.command=='crawl-post':
                posts=[{'post_url':facebook_url(args.url),'movie_id':args.movie_id}]
            else:
                if not args.input:
                    raise ValueError('--input is required for a new batch')
                with args.input.open(encoding='utf-8-sig',newline='') as f:
                    posts=[{'post_url':facebook_url(r['post_url']),'movie_id':r['movie_id']} for r in csv.DictReader(f)]
            if not posts or any(not p['movie_id'].strip() for p in posts):
                raise ValueError('Every post needs a movie_id')
            if len({p['post_url'] for p in posts}) != len(posts):
                raise ValueError('Duplicate post URLs; provide each post once')
            config={k:getattr(args,k) for k in ('max_posts','max_comments','post_timeout','max_rounds','max_actions','wait_ms','settle_ms','idle_rounds','retries')}
            config.update(posts=posts,source_dataset=args.source_dataset)
        from .browser import run_posts
        from playwright.sync_api import sync_playwright
        import re
        if args.resume and not re.fullmatch(r'[A-Za-z0-9_-]+',args.resume):
            raise ValueError('Invalid run ID')
        lock = args.data_root/'crawl_runs'/args.resume/'.browser.lock' if args.resume else None
        if lock:
            with lock.open('x'):
                pass
        try:
            store=Store(args.data_root/'crawl_runs',config,resume=args.resume)
            print('Run: '+store.run_id,flush=True)
            if lock is None:
                lock=store.path/'.browser.lock'
                with lock.open('x'):
                    pass
            with sync_playwright() as pw:
                with pw.chromium.launch_persistent_context(str(args.profile.resolve()),headless=False,
                        channel='chrome' if args.channel=='chrome' else None) as context:
                    page=context.new_page()
                    page.goto('https://www.facebook.com/',wait_until='domcontentloaded')
                    input('Log in manually in the browser, then press Enter here. Ctrl+C pauses the run. ')
                    report=run_posts(store,page)
                    print(json.dumps(report,ensure_ascii=False,indent=2))
        finally:
            if lock:
                lock.unlink(missing_ok=True)
        return 0
    except KeyboardInterrupt:
        print('Interrupted; raw data retained. Resume with the printed run ID.')
        return 130
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        # Safe local validation errors have no browser/page contents.
        print(json.dumps({'error_type':type(exc).__name__,
                         'hint':'Invalid input or run path, completed run, existing export, or active/stale .browser.lock. See docs/CRAWLER.md.'}))
        return 2
    except Exception as exc:
        # Never print browser exceptions, credential-bearing URLs or page dumps.
        print(json.dumps({'error_type':type(exc).__name__,
                         'hint':'Check inputs, dependencies, run status and dedicated profile. See docs/CRAWLER.md.'}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
