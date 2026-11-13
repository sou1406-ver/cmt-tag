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
    a=s.add_parser('build-demo',help='Fit and save a fixed demo on existing 425 human dev labels; no gold evaluation')
    a.add_argument('--output',type=Path,default=Path('outputs/demo_baselines_425'))
    a=s.add_parser('silver-cv',help='Explicit provisional human-only vs human+silver paired development CV; no gold')
    a.add_argument('--config',type=Path,default=Path('configs/development_silver_cv.json'))
    a.add_argument('--output',type=Path,default=Path('outputs/development_silver_cv_20261113_partial'))
    a=s.add_parser('predict',help='Predict a typed movie comment using the local demo model')
    a.add_argument('--model-dir',type=Path,default=Path('outputs/demo_baselines_425'))
    a.add_argument('--model',choices=['bow_multinomial_nb','bow_complement_nb','tfidf_word_svm','tfidf_char_svm','phobert','visobert'])
    inputs=a.add_mutually_exclusive_group()
    inputs.add_argument('--text');inputs.add_argument('--interactive',action='store_true')
    a=s.add_parser('build-transformer-demo',help='Train fixed PhoBERT/ViSoBERT demos on 425 development labels only')
    a.add_argument('--model',choices=['phobert','visobert'],required=True)
    a.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        if args.cmd=='silver-cv':
            import json
            from .human_expansion import run_silver_cv
            print(json.dumps(run_silver_cv(args.config,args.output),ensure_ascii=True))
        elif args.cmd=='build-transformer-demo':
            from .transformer_demo import train as train_transformer
            print(train_transformer(args.model,args.output))
        elif args.cmd=='build-demo':
            import json
            from .demo import build
            print(json.dumps(build(args.output),ensure_ascii=True))
        elif args.cmd=='predict':
            import json
            from .demo import load_model,predict,interactive,menu
            if not (args.model_dir/'model_info.json').is_file():raise ValueError('Run python -m src.models build-demo first')
            if args.text is not None or args.model:
                name=args.model or 'tfidf_char_svm'
                if name in ('phobert','visobert'):
                    from .transformer_demo import TransformerPredictor
                    model=TransformerPredictor(args.model_dir.parent/'demo_transformers_425'/name)
                else:model=load_model(args.model_dir,name)
                if args.text is not None:print(json.dumps({'model':name,'label':predict(model,args.text)},ensure_ascii=True))
                else:interactive(model)
            else:menu(args.model_dir)
        elif args.cmd=='plan-expansion':
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
