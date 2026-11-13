import argparse
from pathlib import Path
from .core import evaluate, train


def main():
    p=argparse.ArgumentParser(description='BoW/TF-IDF × NB/LR/LinearSVC. Select with dev; open final gold test once.')
    s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('train'); a.add_argument('--release',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True); a.add_argument('--seed',type=int,default=42)
    a.add_argument('--usage-root',type=Path,default=Path('data/evaluation_usage'))
    a.add_argument('--train-mode',choices=['mixed','silver-only','gold-only'],default='mixed')
    a=s.add_parser('evaluate'); a.add_argument('--run',type=Path,required=True); a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('preprocessing-cv',help='Development-only fixed preprocessing comparisons; never evaluates gold')
    a.add_argument('--output',type=Path,default=Path('outputs/preprocessing_experiments'))
    a=s.add_parser('plan-expansion',help='Prepare fixed paired development folds, without training')
    a.add_argument('--config',type=Path,default=Path('configs/development_human_expansion.json'))
    a.add_argument('--output',type=Path,default=Path('outputs/ai_labeling/pilot_20261113/development_plan'))
    args=p.parse_args()
    try:
        if args.cmd=='plan-expansion':
            import json
            from .human_expansion import prepare
            print(json.dumps(prepare(args.config,args.output),ensure_ascii=True))
        elif args.cmd=='preprocessing-cv':
            import json
            from .preprocessing_cv import run
            print(json.dumps(run(args.output),ensure_ascii=True))
        elif args.cmd=='train':
            result=train(args.release,args.output,args.usage_root,args.seed,args.train_mode)
            print('Selection saved; test untouched. Dev winner: '+result['dev_winner'])
        else:
            evaluate(args.run,args.output); print('Final metrics and predictions saved.')
        return 0
    except (ValueError,OSError) as exc: p.exit(2,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': raise SystemExit(main())
