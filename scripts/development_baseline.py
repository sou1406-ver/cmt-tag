"""Preflight or explicitly run exploratory grouped CV; never an independent test."""
import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_development import grouped_records, load, read_csv, save, sha, write_csv
from src.baseline.core import LABELS, metrics, model
from sklearn.model_selection import StratifiedGroupKFold
import sklearn


def mask_text(text, aliases, movie_id):
    """Literal, curated aliases only; longest match wins in a single substitution."""
    text = unicodedata.normalize('NFC', text)
    candidates = [a for a in aliases if not a.get('movies') or movie_id in a['movies']]
    patterns = []
    for a in sorted(candidates, key=lambda a: -len(a['text'])):
        pattern = r'(?<!\w)'+re.escape(unicodedata.normalize('NFC',a['text']))+r'(?!\w)'
        if not a.get('case_sensitive', False):
            pattern = '(?i:'+pattern+')'
        patterns.append((pattern,a['token']))
    if not patterns:
        return text
    compiled = re.compile('|'.join('(?P<a'+str(i)+'>'+p+')' for i,(p,_) in enumerate(patterns)))
    return compiled.sub(lambda m: patterns[int(m.lastgroup[1:])][1], text)


def plan(rows, cfg):
    ids = [r['id'] for r in rows]
    if len(ids)!=len(set(ids)) or any(not r['post_id'] or not r['post_url'] or not r['comment_id'] for r in rows):
        raise ValueError('Unique IDs and post/source provenance required')
    _,pairs,groups = grouped_records(rows)
    eligible = [r for r in rows if r['status']=='LABELED' and r['label'] in LABELS
                and not r['validation_issues'] and not r['audit_pending']]
    if len({groups[r['id']] for r in eligible}) < cfg['folds']:
        raise ValueError('Not enough independent post/duplicate components for CV')
    # Remove exact duplicate observations from scoring, retain all source rows and group bridges.
    seen, usable, duplicate_ids = {}, [], []
    for r in sorted(eligible, key=lambda r:r['id']):
        key = ' '.join(unicodedata.normalize('NFC',r['text_raw']).split()).casefold()
        source_key = 'id:'+r['comment_id']
        if key in seen or source_key in seen:
            previous = seen.get(key,seen.get(source_key))
            if previous['label'] != r['label']:
                raise ValueError('Duplicate human label conflict requires explicit review')
            duplicate_ids.append(r['id'])
            continue
        seen[key] = seen[source_key] = r
        usable.append(r)
    splitter = StratifiedGroupKFold(n_splits=cfg['folds'],shuffle=True,random_state=cfg['seed'])
    folds = []
    for index,(train_idx,valid_idx) in enumerate(splitter.split(usable,[r['label'] for r in usable],[groups[r['id']] for r in usable])):
        train_rows,valid_rows = [usable[i] for i in train_idx],[usable[i] for i in valid_idx]
        if {groups[r['id']] for r in train_rows} & {groups[r['id']] for r in valid_rows}:
            raise AssertionError('Post/duplicate group leakage')
        folds.append(dict(fold=index,train_ids=[r['id'] for r in train_rows],validation_ids=[r['id'] for r in valid_rows],
                          train_counts=dict(Counter(r['label'] for r in train_rows)),
                          validation_counts=dict(Counter(r['label'] for r in valid_rows))))
    return dict(method='StratifiedGroupKFold on post + exact/near duplicate connected components',
                seed=cfg['seed'], folds=folds, group_by_id=groups,
                candidates=len(usable), omitted_duplicate_ids=duplicate_ids, near_duplicate_pairs=pairs,
                independent_test=False, movie_holdout=False,
                note='Development CV on exposed/purposefully sampled data. Shared folds for both variants. No estimate of natural-distribution performance.')


def execute(rows, cfg, split_plan, aliases):
    """Reuse Phase D estimators and metric definitions, fit vectorizers inside each fold."""
    by_id={r['id']:r for r in rows}
    results, predictions, coefficients = [], [], []
    for variant in cfg['variants']:
        def text(rid):
            row=by_id[rid]
            return mask_text(row['text_raw'],aliases,row['movie_id']) if variant=='masked' else row['text_raw']
        for kind in cfg['models']:
            truth,guess = [], []
            per_fold = []
            for fold in split_plan['folds']:
                train_ids,valid_ids = fold['train_ids'],fold['validation_ids']
                train_y=[by_id[rid]['label'] for rid in train_ids]
                if set(train_y) != set(LABELS):
                    raise ValueError('Every development training fold must contain all three classes')
                estimator=model('tfidf',kind,cfg['ngram_max'],None if kind=='nb' else cfg['class_weight'],cfg['seed'])
                started=time.perf_counter()
                estimator.fit([text(rid) for rid in train_ids],train_y)
                pred=estimator.predict([text(rid) for rid in valid_ids]).tolist()
                expected=[by_id[rid]['label'] for rid in valid_ids]
                truth.extend(expected);guess.extend(pred)
                per_fold.append(dict(fold=fold['fold'],seconds=time.perf_counter()-started,metrics=metrics(expected,pred)))
                for rid,actual,predicted in zip(valid_ids,expected,pred):
                    predictions.append(dict(id=rid,variant=variant,model=kind,fold=fold['fold'],
                                            movie_id=by_id[rid]['movie_id'],post_id=by_id[rid]['post_id'],
                                            human_label=actual,predicted_label=predicted,text_raw=by_id[rid]['text_raw']))
                if kind=='svm':
                    names=estimator['vectorizer'].get_feature_names_out()
                    for label,weights in zip(estimator['model'].classes_,estimator['model'].coef_):
                        for j in weights.argsort()[-cfg['top_features']:][::-1]:
                            coefficients.append(dict(variant=variant,fold=fold['fold'],label=label,
                                                     feature=names[j],coefficient=float(weights[j])))
            results.append(dict(variant=variant,model=kind,oof=metrics(truth,guess),folds=per_fold))
    return results,predictions,coefficients


def prepare_or_run(config_path, output, run=False):
    cfg=load(config_path)
    if cfg['models'] != ['nb','lr','svm'] or cfg['variants'] != ['original','masked']:
        raise ValueError('Expected fixed NB/LR/LinearSVC and original/masked development comparison')
    source=ROOT/cfg['dataset']
    manifest=load(source/'manifest.json')
    for name,checksum in manifest['output_sha256'].items():
        if Path(name).name!=name or sha(source/name)!=checksum:
            raise ValueError('Prepared data checksum mismatch')
    if manifest['purpose']!='exploratory_development_only' or manifest['independent_test']:
        raise ValueError('This entry point accepts exposed development data only')
    rows=read_csv(source/'annotations.csv')
    aliases=load(ROOT/cfg['mask_lexicon'])['aliases']
    split_plan=plan(rows,cfg)
    ready=manifest['all_human_review_resolved'] and not manifest['pending_review_ids'] and not any(r['audit_pending'] or r['validation_issues'] for r in rows)
    if run and not ready:
        raise ValueError('Human review is pending; no estimator was fitted')
    if run and any(not set(LABELS).issubset(f['train_counts']) for f in split_plan['folds']):
        raise ValueError('Every development training fold must contain all three classes')
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    split_plan.update(provisional=not ready,models_trained=False,
                      dataset_manifest_sha256=sha(source/'manifest.json'),
                      config_sha256=sha(config_path),mask_lexicon_sha256=sha(ROOT/cfg['mask_lexicon']),
                      sklearn_version=sklearn.__version__,pending_human_count=len(manifest['pending_review_ids']),
                      ready_to_run=bool(ready))
    save(output/'plan.json',split_plan)
    if run:
        results,predictions,coefficients=execute(rows,cfg,split_plan,aliases)
        save(output/'metrics.json',dict(independent_test=False,results=results))
        write_csv(output/'predictions.csv',predictions,list(predictions[0]))
        write_csv(output/'svm_features.csv',coefficients,list(coefficients[0]))
        split_plan['models_trained']=True
        save(output/'plan.json',split_plan)
    return split_plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'configs/baseline_development.json')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/development/baseline_plan')
    p.add_argument('--run',action='store_true',help='Explicit fitting, only after human review has been resolved')
    args=p.parse_args()
    try:
        result=prepare_or_run(args.config,args.output,args.run)
    except (ValueError,OSError,KeyError) as exc:
        p.exit(2,f'{type(exc).__name__}: {exc}\n')
    print(json.dumps({k:result[k] for k in ('candidates','provisional','pending_human_count','ready_to_run','models_trained')}))


if __name__=='__main__':
    main()
