import argparse
import json
from pathlib import Path
from .core import agreement, export_tasks, import_human, release


def main():
    p=argparse.ArgumentParser(description='Blind human annotation, agreement and immutable releases')
    s=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('export','release'):
        a=s.add_parser(cmd); a.add_argument('--data-root',type=Path,required=True)
        a.add_argument('--version',required=True); a.add_argument('--output',type=Path,required=True)
        if cmd=='export':
            a.add_argument('--split',choices=['train','dev','test'],required=True)
            a.add_argument('--count',type=int,default=150); a.add_argument('--seed',type=int,default=42)
            a.add_argument('--hard-ids',type=Path,help='Train-only JSON array of IDs; separate purposeful cohort')
        elif cmd=='release':
            a.add_argument('--events',type=Path,nargs='+',required=True)
            a.add_argument('--used-ids',type=Path,help='JSON array of IDs previously used to train/tune')
    a=s.add_parser('import-human'); a.add_argument('--task',type=Path,required=True)
    a.add_argument('--csv',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    a.add_argument('--annotator',required=True); a.add_argument('--blind',action='store_true')
    a.add_argument('--adjudication',action='store_true',help='Explicit resolution event after independent review')
    a=s.add_parser('agreement'); a.add_argument('--left',type=Path,required=True)
    a.add_argument('--right',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    pilot=s.add_parser('pilot',help='One 600-record blinded file for manual GPT/Claude/Gemini web labeling')
    ps=pilot.add_subparsers(dest='pilot_command',required=True)
    for command in ('prepare','prepare-expansion','export-web','import-web','analyze','audit-import','audit-errors','friend-import'):
        q=ps.add_parser(command);q.add_argument('--directory',type=Path,default=Path('outputs/ai_labeling/pilot_20261113'))
        if command=='prepare':q.add_argument('--source',type=Path,default=Path('outputs/canonical/versions/filtered_20261113_quality_v1'))
        if command=='prepare-expansion':
            q.set_defaults(directory=Path('outputs/ai_labeling/expansion_web_20261113'))
            q.add_argument('--previous',type=Path,default=Path('outputs/ai_labeling/pilot_20261113'))
        if command=='import-web':
            q.add_argument('--provider',choices=['GPT','Claude','Gemini'],required=True)
            q.add_argument('--response',type=Path,required=True);q.add_argument('--model',default='UNKNOWN_WEB_MODEL')
            q.add_argument('--allow-partial',action='store_true')
        if command=='audit-errors':q.add_argument('--output',type=Path,help='New diagnostics directory under pilot; default error_analysis')
        if command=='analyze':
            q.add_argument('--providers',nargs=2,choices=['GPT','Claude','Gemini'],help='Compare exactly two actual AI responses; omit for original 3-AI analysis')
            q.add_argument('--output',type=Path,help='New two-AI analysis directory under the batch')
        if command=='friend-import':
            q.add_argument('--annotator',required=True)
            q.add_argument('--origin',choices=['human','human_reviewed_ai','ai'],required=True)
            q.add_argument('--workbook',type=Path);q.add_argument('--output',type=Path)
    g=s.add_parser('gold',help='One-annotator new-Facebook gold: sample, recheck, agreement, evaluate')
    gs=g.add_subparsers(dest='gold_command',required=True)
    for command in ('sample','recheck','agreement','evaluate'):
        q=gs.add_parser(command)
        q.add_argument('--directory',type=Path,default=Path('outputs/gold'))
        if command=='sample':
            source=q.add_mutually_exclusive_group(required=True)
            source.add_argument('--export',type=Path,help='Existing crawler export directory')
            source.add_argument('--run',help='New crawl run ID; reuse existing exporter locally, without crawling')
            q.add_argument('--posts',type=Path,help='Defaults to DIRECTORY/posts.csv')
        elif command=='recheck':q.add_argument('--annotator',default='user')
        elif command=='agreement':q.add_argument('--final',action='store_true',help='Import filled label_final from gold_disagreements.xlsx and lock')
    args=p.parse_args()
    try:
        if args.cmd=='pilot':
            from . import pilot
            from . import web_labels
            if args.pilot_command=='prepare':result=pilot.prepare(args.directory,args.source)
            elif args.pilot_command=='prepare-expansion':result=pilot.prepare_expansion(args.directory,previous=args.previous)
            elif args.pilot_command=='export-web':result=web_labels.export_web(args.directory)
            elif args.pilot_command=='import-web':result=web_labels.import_web(args.directory,args.provider,args.response,args.model,args.allow_partial)
            elif args.pilot_command=='analyze':
                result=pilot.summarize_pair(args.directory,args.providers,args.output) if args.providers else pilot.summarize(args.directory)
            elif args.pilot_command=='audit-errors':
                from .audit import analyze_errors
                result=analyze_errors(args.directory,args.output or args.directory/'error_analysis')
            elif args.pilot_command=='friend-import':
                from .audit import import_friend
                result=import_friend(args.directory,args.annotator,args.origin,args.workbook,args.output)
            else:result=pilot.import_audit(args.directory)
        elif args.cmd=='gold':
            from . import gold
            if args.gold_command=='sample':result=gold.sample(args.export,args.posts,args.directory,run_id=args.run)
            elif args.gold_command=='recheck':result=gold.recheck(args.directory,args.annotator)
            elif args.gold_command=='agreement':result=gold.agreement(args.directory,args.final)
            else:
                from src.models.core import evaluate_gold
                from src.dataset.common import ROOT
                result=evaluate_gold(args.directory,ROOT/'outputs/canonical/versions/filtered_20261112_final/candidate.local.jsonl',ROOT)
        elif args.cmd=='export':
            if args.count<=0: raise ValueError('Count must be positive')
            result=str(export_tasks(args.data_root,args.version,args.output,seed=args.seed,split=args.split,count=args.count,
                 hard_ids=json.loads(args.hard_ids.read_text()) if args.hard_ids else ()))
        elif args.cmd=='import-human':
            result=import_human(args.task,args.csv,args.output,args.annotator,args.blind,args.adjudication)
        elif args.cmd=='agreement': result=agreement(args.left,args.right,args.output)
        else: result=str(release(args.data_root,args.version,args.events,args.output,
                  used_ids=json.loads(args.used_ids.read_text()) if args.used_ids else ()))
        print(json.dumps(result,ensure_ascii=True)); return 0
    except (ValueError,KeyError,OSError) as exc:
        p.exit(2,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': raise SystemExit(main())
