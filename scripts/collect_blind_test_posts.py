"""Validate a post-only selection list, reuse crawl-batch, then lock a blind test."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.test_posts import preflight,crawl,reserve


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    v=sub.add_parser('preflight',help='Metadata/exposure checks only; never opens a browser')
    v.add_argument('--input',type=Path,default=Path('test_posts.csv'))
    v.add_argument('--master',type=Path,default=Path('outputs/phase_g/master'))
    v.add_argument('--output',type=Path,required=True)
    c=sub.add_parser('crawl',help='Run existing crawler only after a READY preflight')
    c.add_argument('--plan',type=Path,required=True)
    c.add_argument('--data-root',type=Path,default=Path('data'))
    c.add_argument('--channel',choices=['brave','chrome','chromium'],default='brave')
    c.add_argument('--profile',type=Path);c.add_argument('--resume')
    r=sub.add_parser('reserve',help='Rebuild duplicate graph in a new master, apply fixed quotas, lock before labeling')
    r.add_argument('--plan',type=Path,required=True);r.add_argument('--run',required=True)
    r.add_argument('--data-root',type=Path,default=Path('data'));r.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.command=='preflight':
            result=preflight(a.input,a.master,a.output)
            print({k:result[k] for k in ('status','rows','ready_rows','blocked_rows','comments_inspected_for_selection')})
            return 0 if result['status']=='READY_FOR_CRAWL' else 2
        if a.command=='crawl':return crawl(a.plan,a.data_root,a.channel,a.profile,a.resume)
        result=reserve(a.plan,a.data_root,a.run,a.output)
        print({k:result[k] for k in ('status','target','selected','attainable_under_quota')})
        return 2 if result['status']=='PARTIAL' else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(2,type(exc).__name__+': '+str(exc)+'\n')


if __name__=='__main__':raise SystemExit(main())
