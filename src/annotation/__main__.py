import argparse
import json
from pathlib import Path
from .core import agreement, export_tasks, import_human, release
from .silver import annotate


def main():
    p=argparse.ArgumentParser(description='Blind annotation tasks, agreement, silver and immutable releases')
    s=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('export','release','silver'):
        a=s.add_parser(cmd); a.add_argument('--data-root',type=Path,required=True)
        a.add_argument('--version',required=True); a.add_argument('--output',type=Path,required=True)
        if cmd=='export':
            a.add_argument('--split',choices=['train','dev','test'],required=True)
            a.add_argument('--count',type=int,default=150); a.add_argument('--seed',type=int,default=42)
            a.add_argument('--hard-ids',type=Path,help='Train-only JSON array of IDs; separate purposeful cohort')
        elif cmd=='release':
            a.add_argument('--events',type=Path,nargs='+',required=True)
            a.add_argument('--used-ids',type=Path,help='JSON array of IDs previously used to train/tune')
        else:
            a.add_argument('--provider-config',type=Path,required=True)
            a.add_argument('--allow-external',action='store_true'); a.add_argument('--retries',type=int,default=2)
    a=s.add_parser('import-human'); a.add_argument('--task',type=Path,required=True)
    a.add_argument('--csv',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    a.add_argument('--annotator',required=True); a.add_argument('--blind',action='store_true')
    a.add_argument('--adjudication',action='store_true',help='Explicit resolution event after independent review')
    a=s.add_parser('agreement'); a.add_argument('--left',type=Path,required=True)
    a.add_argument('--right',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.cmd=='export':
            if args.count<=0: raise ValueError('Count must be positive')
            result=str(export_tasks(args.data_root,args.version,args.output,seed=args.seed,split=args.split,count=args.count,
                 hard_ids=json.loads(args.hard_ids.read_text()) if args.hard_ids else ()))
        elif args.cmd=='import-human':
            result=import_human(args.task,args.csv,args.output,args.annotator,args.blind,args.adjudication)
        elif args.cmd=='agreement': result=agreement(args.left,args.right,args.output)
        elif args.cmd=='silver': result=annotate(args.data_root,args.version,args.provider_config,args.output,args.allow_external,args.retries)
        else: result=str(release(args.data_root,args.version,args.events,args.output,
                  used_ids=json.loads(args.used_ids.read_text()) if args.used_ids else ()))
        print(json.dumps(result,ensure_ascii=True)); return 0
    except (ValueError,KeyError,OSError) as exc:
        p.exit(2,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': raise SystemExit(main())
