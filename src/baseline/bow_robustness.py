"""Phase E.1: count baselines, fixed-fold evidence, repeated grouped CV and topic transfer."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from importlib.metadata import version
from itertools import permutations
import json
from pathlib import Path
import platform
import shutil
from statistics import mean, stdev
import tempfile
import time
import warnings

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.pipeline import Pipeline

from scripts.prepare_development import ROOT, load, read_csv, save, sha, write_csv
from src.baseline.core import LABELS, metrics
from .preprocessing_experiments import estimator as tfidf_estimator, offline_network, read_locked


def validate_config(cfg):
    if (len(cfg['seeds'])!=5 or len(set(cfg['seeds']))!=5 or any(type(s) is not int for s in cfg['seeds'])
            or cfg['seeds'][0]!=42 or cfg['estimator_seed']!=42 or cfg['folds']!=3 or cfg['std_ddof']!=1):
        raise ValueError('Five distinct fixed seeds, reference 42, three folds, fixed estimator RNG and seed-level sample std required')
    if cfg['input_view']!='unchanged_text_raw' or cfg['nb_alpha']!=1 or cfg['complement_norm'] is not False:
        raise ValueError('Fixed raw-count alpha=1/norm=False comparison required')
    expected=[('bow_mnb_w1','bow','mnb',1),('bow_mnb_w12','bow','mnb',2),
              ('bow_cnb_w1','bow','cnb',1),('bow_cnb_w12','bow','cnb',2),
              ('tfidf_word_lr','word','lr',None),('tfidf_word_svm','word','svm',None),
              ('tfidf_char_svm','char','svm',None)]
    actual=[(s['id'],s['feature'],s['model'],s.get('ngram_max')) for s in cfg['models']]
    if actual!=expected or any(s.get('class_weight')!='balanced' for s in cfg['models'] if s['feature']!='bow'):
        raise ValueError('Keep the seven declared model specifications; no diagnostic-driven model tuning')
    reference_ids={'tfidf_word_lr':'B0_lr_balanced','tfidf_word_svm':'B0_svm_balanced','tfidf_char_svm':'B3_svm_balanced'}
    if any(s.get('phase_e_run_id')!=reference_ids[s['id']] for s in cfg['models'] if s['id'] in reference_ids):
        raise ValueError('Do not disable or redirect reproduction of the three Phase E references')
    transfer=cfg['transfer']
    if (transfer['independent_test'] or transfer['hyperparameter_selection']
            or transfer['cross_boundary_group_policy']!='exclude_entire_spanning_component_from_diagnostic_only'):
        raise ValueError('Transfer is limited development diagnosis with intact groups, not independent test/tuning')
    for key in ('min_train_per_class_to_fit','min_eval_per_class_to_fit','limited_support_below_per_class','limited_support_below_groups_per_class'):
        if type(transfer[key]) is not int or transfer[key]<1:raise ValueError('Positive predeclared transfer support limits required')


def inputs(cfg):
    root=ROOT/cfg['phase_e_root'];manifest=load(root/'manifest.json')
    if sha(root/'manifest.json')!=cfg['phase_e_manifest_sha256']:
        raise ValueError('Phase E manifest changed')
    if (manifest['purpose']!='development_preprocessing_ablation_only' or manifest['independent_test']
            or not manifest['models_trained'] or manifest['candidates']!=cfg['expected_candidates']):
        raise ValueError('Expected the completed, exposed Phase E run')
    for name,checksum in manifest['output_sha256'].items():
        if Path(name).name!=name or sha(root/name)!=checksum:raise ValueError('Locked Phase E artifact changed: '+name)
    if (sha(root/'experiment_config.json')!=cfg['phase_e_config_sha256']
            or sha(root/'metrics.json')!=cfg['phase_e_metrics_sha256']):
        raise ValueError('Phase E config/metrics do not match the E.1 contract')
    old_cfg=load(root/'experiment_config.json')
    rows,locked,_,_=read_locked(old_cfg)
    if cfg['expected_candidates']!=locked['candidates']:raise ValueError('Candidate count changed')
    env=load(root/'environment.json')
    for package in ('scikit-learn','numpy','scipy'):
        if version(package)!=env['packages'][package]:raise ValueError('Reproduce the pinned Phase E numerical environment')
    return rows,locked,load(root/'metrics.json'),old_cfg


def make_model(spec,cfg,old_cfg):
    if spec['feature']=='bow':
        vectorizer=CountVectorizer(ngram_range=(1,spec['ngram_max']),token_pattern=r'(?u)\b\w+\b',
                                   lowercase=True,strip_accents=None,stop_words=None,binary=False)
        nb=(MultinomialNB(alpha=cfg['nb_alpha'],fit_prior=True) if spec['model']=='mnb'
            else ComplementNB(alpha=cfg['nb_alpha'],norm=cfg['complement_norm']))
        return Pipeline([('vectorizer',vectorizer),('model',nb)])
    recipe=dict(feature=spec['feature'],light=False,segment=False,teencode=False)
    return tfidf_estimator(recipe,spec['model'],spec['class_weight'],dict(old_cfg,seed=cfg['estimator_seed']))


def validate_plan(folds,ids,groups,by_id):
    expected=set(ids);observed=[]
    if len(folds)!=3 or {f['fold'] for f in folds}!={0,1,2}:raise ValueError('Expected three numbered folds')
    for fold in folds:
        train,valid=fold['train_ids'],fold['validation_ids']
        if (len(train)!=len(set(train)) or len(valid)!=len(set(valid)) or set(train)&set(valid)
                or set(train)|set(valid)!=expected):raise ValueError('Fold IDs must partition the original candidates')
        if {groups[r] for r in train}&{groups[r] for r in valid}:raise ValueError('Post/source-ID/duplicate component leaks across fold')
        if {by_id[r]['label'] for r in train}!=set(LABELS):raise ValueError('Three-class training unsupported by this seed/fold; do not replace seed')
        for key,values in [('train_counts',train),('validation_counts',valid)]:
            if fold[key]!=dict(Counter(by_id[r]['label'] for r in values)):raise ValueError('Fold label support mismatch')
        observed.extend(valid)
    if len(observed)!=len(set(observed)) or set(observed)!=expected:raise ValueError('Every comment must appear in validation once per seed')


def repeated_plans(rows,locked,cfg):
    ids=sorted({rid for f in locked['folds'] for rid in f['validation_ids']});by_id={r['id']:r for r in rows}
    groups=locked['group_by_id'];plans=[]
    for seed in cfg['seeds']:
        splitter=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=seed);folds=[]
        for index,(train_idx,valid_idx) in enumerate(splitter.split(ids,[by_id[i]['label'] for i in ids],[groups[i] for i in ids])):
            train,valid=[ids[i] for i in train_idx],[ids[i] for i in valid_idx]
            folds.append(dict(fold=index,train_ids=train,validation_ids=valid,
                              train_counts=dict(Counter(by_id[i]['label'] for i in train)),
                              validation_counts=dict(Counter(by_id[i]['label'] for i in valid))))
        validate_plan(folds,ids,groups,by_id)
        if seed==locked['seed'] and folds!=locked['folds']:
            raise ValueError('Seed 42 failed to reproduce the locked folds; keep Phase E unchanged')
        plans.append(dict(seed=seed,folds=folds))
    return plans


def partition_diagnostics(plans,groups,movie_ids,movie):
    assignments=[{rid:f['fold'] for f in p['folds'] for rid in f['validation_ids']} for p in plans]
    reference=assignments[0];rows=[]
    for plan,assignment in zip(plans,assignments):
        canonical=sorted(sorted(f['validation_ids']) for f in plan['folds'])
        signature=hashlib.sha256(json.dumps(canonical).encode()).hexdigest()
        align=min(permutations(range(3)),key=lambda perm:sum(perm[value]!=reference[rid] for rid,value in assignment.items()))
        moved=[rid for rid,value in assignment.items() if align[value]!=reference[rid]]
        rows.append(dict(seed=plan['seed'],partition_sha256=signature,moved_comments_vs_reference=len(moved),
                         moved_groups_vs_reference=len({groups[r] for r in moved}),
                         moved_movie_comments_vs_reference=sum(movie_ids[r]==movie for r in moved)))
    return dict(unique_partitions=len({r['partition_sha256'] for r in rows}),seeds=rows,
                note='Partition identity ignores fold-number permutations. Seeds reuse the same observations; no independent-sample CI.')


def fit_predict(train,valid,by_id,spec,cfg,old_cfg):
    pipeline=make_model(spec,cfg,old_cfg);start=time.perf_counter()
    pipeline.fit([by_id[r]['text_raw'] for r in train],[by_id[r]['label'] for r in train])
    fitted=time.perf_counter();pred=pipeline.predict([by_id[r]['text_raw'] for r in valid]).tolist();end=time.perf_counter()
    return pred,dict(fit_seconds=fitted-start,predict_seconds=end-fitted,total_seconds=end-start)


def score_cv(folds,by_id,spec,cfg,old_cfg):
    truth=[];guesses=[];fold_results=[];predictions=[]
    for fold in folds:
        valid=fold['validation_ids'];pred,timing=fit_predict(fold['train_ids'],valid,by_id,spec,cfg,old_cfg)
        actual=[by_id[r]['label'] for r in valid];m=metrics(actual,pred)
        n_errors=sum(a!=b for a,b in zip(actual,pred))
        fold_results.append(dict(fold=fold['fold'],metrics=m,n=len(valid),errors=n_errors,error_rate=n_errors/len(valid),
                                 train_counts=fold['train_counts'],validation_counts=fold['validation_counts'],**timing))
        truth.extend(actual);guesses.extend(pred)
        predictions.extend(dict(model_id=spec['id'],fold=fold['fold'],id=rid,human_label=a,predicted_label=b)
                           for rid,a,b in zip(valid,actual,pred))
    total_errors=sum(f['errors'] for f in fold_results)
    for f in fold_results:f['share_of_model_errors']=f['errors']/total_errors if total_errors else 0.0
    return dict(model_id=spec['id'],metrics=metrics(truth,guesses),folds=fold_results,
                total_seconds=sum(f['total_seconds'] for f in fold_results)),predictions


def validate_reference(result,predictions,phase_e,reference_predictions,run_id):
    old=next(r for r in phase_e['results'] if r['run_id']==run_id)
    if result['metrics']!=old['oof'] or [r['metrics'] for r in result['folds']]!=[r['metrics'] for r in old['folds']]:
        raise ValueError('E.1 refit did not reproduce Phase E metrics')
    original={(r['id'],int(r['fold'])):(r['human_label'],r['predicted_label']) for r in reference_predictions if r['run_id']==run_id}
    current={(r['id'],r['fold']):(r['human_label'],r['predicted_label']) for r in predictions}
    if original!=current:raise ValueError('Phase E OOF predictions changed')


def distributions(rows,folds,groups,movie):
    by_id={r['id']:r for r in rows};table=[];special=[]
    for fold in folds:
        for partition,key in [('train','train_ids'),('validation','validation_ids')]:
            selected=[by_id[i] for i in fold[key]]
            for field in ('movie_id','post_id'):
                buckets=defaultdict(list)
                for r in selected:buckets[r[field]].append(r)
                for value,items in sorted(buckets.items()):
                    c=Counter(r['label'] for r in items)
                    table.append(dict(fold=fold['fold'],partition=partition,group_by=field,value=value,n=len(items),
                                      **{label:c[label] for label in LABELS},n_components=len({groups[r['id']] for r in items})))
            subset=[r for r in selected if r['movie_id']==movie];c=Counter(r['label'] for r in subset)
            special.append(dict(fold=fold['fold'],partition=partition,n=len(subset),**{label:c[label] for label in LABELS},
                                other_movie_POS=sum(r['label']=='POS' and r['movie_id']!=movie for r in selected)))
    return table,special


def seed_summary(results,model_ids,seeds):
    if Counter((r['model_id'],r['seed']) for r in results)!=Counter({(model_id,seed):1 for model_id in model_ids for seed in seeds}):
        raise ValueError('Exactly one pooled OOF result per model/seed is required; folds are not repetitions')
    output=[]
    for model_id in model_ids:
        subset=[next(r for r in results if r['model_id']==model_id and r['seed']==s) for s in seeds]
        def summarize(values):return dict(mean=mean(values),std=stdev(values),minimum=min(values),maximum=max(values))
        output.append(dict(model_id=model_id,n_seeds=len(seeds),ddof=1,
                           macro_f1=summarize([r['metrics']['macro_f1'] for r in subset]),
                           accuracy=summarize([r['metrics']['accuracy'] for r in subset]),
                           recall={label:summarize([r['metrics']['per_class'][label]['recall'] for r in subset]) for label in LABELS},
                           note='One pooled OOF score per seed; descriptive variability, not 15 independent folds.'))
    return output


def transfer_plans(rows,ids,groups,config):
    movie=config['movie_id'];buckets=defaultdict(set)
    for row in rows:buckets[groups[row['id']]].add(row['movie_id']==movie)
    excluded={g for g,categories in buckets.items() if len(categories)>1}
    by_id={r['id']:r for r in rows};usable=[i for i in ids if groups[i] not in excluded]
    target=sorted(i for i in usable if by_id[i]['movie_id']==movie);other=sorted(set(usable)-set(target))
    output=[]
    for name,train,valid in [('other_to_mua_do',other,target),('mua_do_to_other',target,other)]:
        reasons=[];limits=[];supports={}
        for side,selected in [('train',train),('evaluation',valid)]:
            counts=Counter(by_id[i]['label'] for i in selected)
            group_counts={label:len({groups[i] for i in selected if by_id[i]['label']==label}) for label in LABELS}
            supports[side]=dict(n=len(selected),counts={label:counts[label] for label in LABELS},groups_per_class=group_counts,
                                n_posts=len({by_id[i]['post_id'] for i in selected}))
            threshold=config['min_train_per_class_to_fit'] if side=='train' else config['min_eval_per_class_to_fit']
            for label in LABELS:
                if counts[label]<threshold:reasons.append(f'{side} {label}: {counts[label]} < {threshold}')
                if counts[label]<config['limited_support_below_per_class']:limits.append(f'{side} {label}: only {counts[label]} comments')
                if group_counts[label]<config['limited_support_below_groups_per_class']:limits.append(f'{side} {label}: only {group_counts[label]} components')
        if {groups[i] for i in train}&{groups[i] for i in valid}:raise ValueError('Transfer leaks a connected component')
        output.append(dict(direction=name,train_ids=train,evaluation_ids=valid,support=supports,
                           excluded_spanning_group_ids=sorted(excluded),excluded_candidate_ids=sorted(set(ids)-set(usable)),
                           status='skipped' if reasons else ('limited_diagnostic' if limits else 'development_diagnostic'),
                           skip_reasons=reasons,limitations=limits,independent_test=False,hyperparameter_selection=False,
                           topic_semantics='movie_id is source-post topic; cross-film references can remain in text'))
    return output


def flatten(result):
    m=result['metrics']
    row=dict(model_id=result['model_id'],macro_f1=m['macro_f1'],accuracy=m['accuracy'],total_seconds=result['total_seconds'])
    for label in LABELS:
        for key in ('precision','recall','f1-score','support'):row[label+'_'+key]=m['per_class'][label][key]
    return row


def _run(config_path,output):
    config_sha=sha(config_path);cfg=load(config_path);validate_config(cfg)
    rows,locked,phase_e,old_cfg=inputs(cfg);by_id={r['id']:r for r in rows}
    plans=repeated_plans(rows,locked,cfg);ids=sorted(plans[0]['folds'][0]['train_ids']+plans[0]['folds'][0]['validation_ids'])
    groups=locked['group_by_id'];phase_root=ROOT/cfg['phase_e_root']
    reference_predictions=read_csv(phase_root/'predictions.csv')
    diagnostics=partition_diagnostics(plans,groups,{r['id']:r['movie_id'] for r in rows},cfg['transfer']['movie_id'])
    transfer=transfer_plans(rows,ids,groups,cfg['transfer'])
    output.mkdir();started=time.perf_counter()
    shutil.copyfile(config_path,output/'config.json')
    if sha(output/'config.json')!=config_sha:raise ValueError('E.1 config changed while copying')
    shutil.copyfile(phase_root/'manifest.json',output/'phase_e_manifest.json')
    shutil.copyfile(phase_root/'locked_plan.json',output/'original_locked_plan.json')
    original=[];repeated=[];predictions=[];transfer_results=[];fits=0
    with offline_network(),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        for spec in cfg['models']:
            result,pred=score_cv(locked['folds'],by_id,spec,cfg,old_cfg);fits+=3
            if spec.get('phase_e_run_id'):validate_reference(result,pred,phase_e,reference_predictions,spec['phase_e_run_id'])
            original.append(result);repeated.append(dict(seed=locked['seed'],reuses_reference_fit=True,**deepcopy(result)))
            predictions.extend(dict(stage='original_and_seed_42',seed=locked['seed'],**r) for r in pred)
            print(json.dumps(dict(stage='original',model=spec['id'],macro_f1=result['metrics']['macro_f1'])),flush=True)
        for plan in plans[1:]:
            for spec in cfg['models']:
                result,pred=score_cv(plan['folds'],by_id,spec,cfg,old_cfg);fits+=3
                repeated.append(dict(seed=plan['seed'],reuses_reference_fit=False,**result))
                predictions.extend(dict(stage='repeated',seed=plan['seed'],**r) for r in pred)
            print(json.dumps(dict(stage='repeated',seed=plan['seed'])),flush=True)
        for diagnostic in transfer:
            diagnostic['results']=[]
            if diagnostic['status']=='skipped':continue
            train,valid=diagnostic['train_ids'],diagnostic['evaluation_ids'];actual=[by_id[i]['label'] for i in valid]
            prior=Counter(by_id[i]['label'] for i in train);majority=max(sorted(prior),key=prior.get)
            diagnostic['training_majority_reference']=dict(label=majority,metrics=metrics(actual,[majority]*len(valid)),kind='analytical_constant_prediction')
            for spec in cfg['models']:
                pred,timing=fit_predict(train,valid,by_id,spec,cfg,old_cfg);fits+=1
                r=dict(model_id=spec['id'],metrics=metrics(actual,pred),**timing)
                diagnostic['results'].append(r)
                predictions.extend(dict(stage=diagnostic['direction'],seed='',model_id=spec['id'],fold='',id=i,
                                        human_label=a,predicted_label=p) for i,a,p in zip(valid,actual,pred))
                transfer_results.append(dict(direction=diagnostic['direction'],status=diagnostic['status'],
                                             **flatten(dict(r,total_seconds=timing['total_seconds']))))
        warning_messages=sorted({str(w.message) for w in caught})
    summary=seed_summary(repeated,[s['id'] for s in cfg['models']],cfg['seeds'])
    distribution_rows,special=distributions(rows,locked['folds'],groups,cfg['transfer']['movie_id'])
    overall=[]
    for field in ('movie_id','post_id'):
        buckets=defaultdict(list)
        for rid in ids:buckets[by_id[rid][field]].append(by_id[rid])
        for value,items in sorted(buckets.items()):
            counts=Counter(r['label'] for r in items)
            overall.append(dict(group_by=field,value=value,n=len(items),**{label:counts[label] for label in LABELS},
                                n_components=len({groups[r['id']] for r in items})))
    fold_table=[]
    for r in original:
        for fold in r['folds']:
            fold_table.append(dict(model_id=r['model_id'],fold=fold['fold'],n_validation=fold['n'],errors=fold['errors'],
                error_rate=fold['error_rate'],share_of_model_errors=fold['share_of_model_errors'],macro_f1=fold['metrics']['macro_f1'],
                **{'recall_'+label:fold['metrics']['per_class'][label]['recall'] for label in LABELS},
                **{'train_'+label:fold['train_counts'].get(label,0) for label in LABELS},
                **{'validation_'+label:fold['validation_counts'].get(label,0) for label in LABELS},total_seconds=fold['total_seconds']))
    for name,values in [('original_comparison.csv',[flatten(r) for r in original]),('original_fold_metrics.csv',fold_table),
                        ('original_fold_distribution.csv',distribution_rows),('mua_do_fold_support.csv',special),
                        ('overall_distribution.csv',overall),
                        ('predictions.csv',predictions),
                        ('seed_scores.csv',[dict(seed=r['seed'],**flatten(r)) for r in repeated])]:
        write_csv(output/name,values,list(values[0]))
    write_csv(output/'transfer_comparison.csv',transfer_results,list(transfer_results[0]) if transfer_results else ['direction','status','model_id'])
    save(output/'original_results.json',original);save(output/'repeated_results.json',repeated)
    save(output/'repeated_plans.json',plans);save(output/'partition_diagnostics.json',diagnostics)
    save(output/'seed_summary.json',summary);save(output/'transfer_diagnostics.json',transfer)
    save(output/'warnings.json',warning_messages)
    env=dict(python=platform.python_version(),packages={p:version(p) for p in ('scikit-learn','numpy','scipy','joblib')},network_disabled=True)
    save(output/'environment.json',env)
    (output/'REPORT.md').write_text(report(cfg,original,repeated,summary,diagnostics,special,transfer),encoding='utf-8',newline='\n')
    inputs(cfg)
    if sha(config_path)!=config_sha:raise ValueError('E.1 config changed during execution')
    result=dict(purpose='bow_and_grouped_robustness_development_only',independent_test=False,
                fixture_only=load(phase_root/'manifest.json').get('fixture_only',False),
                config_sha256=config_sha,phase_e_manifest_sha256=cfg['phase_e_manifest_sha256'],
                dataset_manifest_sha256=old_cfg['dataset_manifest_sha256'],original_plan_sha256=sha(output/'original_locked_plan.json'),
                models=[s['id'] for s in cfg['models']],seeds=cfg['seeds'],candidates=len(ids),fits=fits,
                original_phase_e_predictions_reproduced=True,unique_seed_partitions=diagnostics['unique_partitions'],
                seconds=time.perf_counter()-started,output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    save(output/'manifest.json',result)
    return result


def report(cfg,original,repeated,summary,diagnostics,special,transfer):
    old_table='\n'.join(f"| {r['model_id']} | {r['metrics']['macro_f1']:.4f} | {r['metrics']['accuracy']:.4f} | "+
                       ' | '.join(f"{r['metrics']['per_class'][c]['recall']:.4f}" for c in LABELS)+f" | {r['total_seconds']:.3f} |" for r in original)
    mean_table='\n'.join(f"| {r['model_id']} | {r['macro_f1']['mean']:.4f} ± {r['macro_f1']['std']:.4f} | "+
                        ' | '.join(f"{r['recall'][c]['mean']:.4f} ± {r['recall'][c]['std']:.4f}" for c in LABELS)+' |' for r in summary)
    scores='\n'.join('| '+r['model_id']+' | '+' | '.join(f"{next(x for x in repeated if x['model_id']==r['model_id'] and x['seed']==s)['metrics']['macro_f1']:.4f}" for s in cfg['seeds'])+' |' for r in original)
    fold_lines=[]
    for r in original:
        for f in r['folds']:
            fold_lines.append(f"| {r['model_id']} | {f['fold']+1} | {f['n']} | {f['errors']} | {f['error_rate']:.4f} | {f['metrics']['macro_f1']:.4f} | "+
                              ' | '.join(f"{f['metrics']['per_class'][c]['recall']:.4f}" for c in LABELS)+' |')
    special_table='\n'.join(f"| {r['fold']+1} | {r['partition']} | {r['n']} | {r['POS']} | {r['NEG']} | {r['NEU']} | {r['other_movie_POS']} |" for r in special)
    movement='\n'.join(f"| {r['seed']} | {r['moved_comments_vs_reference']} | {r['moved_groups_vs_reference']} | {r['moved_movie_comments_vs_reference']} |" for r in diagnostics['seeds'])
    char=next(r for r in original if r['model_id']=='tfidf_char_svm');folds=char['folds']
    worst_count=max(f['errors'] for f in folds);worst_rate=max(f['error_rate'] for f in folds);lowest=min(f['metrics']['macro_f1'] for f in folds)
    worst_text=f"Char-SVM: nhiều lỗi tuyệt đối nhất ở fold {[f['fold']+1 for f in folds if f['errors']==worst_count]} ({worst_count} lỗi); tỷ lệ lỗi cao nhất ở fold {[f['fold']+1 for f in folds if f['error_rate']==worst_rate]} ({worst_rate:.4f}); Macro-F1 thấp nhất ở fold {[f['fold']+1 for f in folds if f['metrics']['macro_f1']==lowest]} ({lowest:.4f})."
    transfers=[]
    for d in transfer:
        support=json.dumps(d['support'],ensure_ascii=False)
        table='\n'.join(f"| {r['model_id']} | {r['metrics']['macro_f1']:.4f} | {r['metrics']['accuracy']:.4f} | "+
                        ' | '.join(f"{r['metrics']['per_class'][c]['recall']:.4f}" for c in LABELS)+' |' for r in d['results'])
        prior=d.get('training_majority_reference')
        prior_text=(f"Train-majority {prior['label']}: Macro-F1 {prior['metrics']['macro_f1']:.4f}, accuracy {prior['metrics']['accuracy']:.4f}." if prior else '')
        transfers.append(f"### {d['direction']}\n\nStatus: {d['status']}.\n\nSupport: `{support}`.\n\nGiới hạn: {json.dumps(d['limitations'],ensure_ascii=False)}. Bỏ qua nếu: {json.dumps(d['skip_reasons'],ensure_ascii=False)}.\n\n{prior_text}\n\n| Model | Macro-F1 | Accuracy | Recall POS | Recall NEG | Recall NEU |\n|---|---:|---:|---:|---:|---:|\n{table}\n")
    return f'''# Phase E.1 — BoW Baselines & Grouped CV Robustness

Đúng {cfg['expected_candidates']} nhãn người, không thêm data hoặc sửa nhãn.
Phase E được khóa và giữ nguyên. E.1 refit TF-IDF để đo thời gian cùng cách,
nhưng kiểm tất cả OOF/fold metrics và dự đoán trùng Phase E. Không thay mốc
seed 42 bằng seed tốt nhất, không chọn tham số theo transfer.

## BoW và mốc ba fold cũ

CountVectorizer word unigram / unigram+bigram, lowercase, token đơn cũng giữ,
không stopword/strip accents, binary=False, alpha=1. ComplementNB norm=False.
Không thêm char-BoW vào thí nghiệm chính. TF-IDF LR/SVM balanced, C=1; char
TF-IDF dùng đúng char_wb(3,5) và L2 của Phase E. Input là raw như B0/B3.
Vectorizer fit riêng train từng fold; estimator seed luôn 42 để đổi seed chỉ
tác động cách chia nhóm. Fit_seconds gồm vector hóa train, predict_seconds
gồm transform validation; total là tổng hai phần, không so với timing cũ có
diagnostics overhead. Các lần chạy không cache feature từ validation.

| Model | Macro-F1 OOF | Accuracy | Recall POS | Recall NEG | Recall NEU | Giây |
|---|---:|---:|---:|---:|---:|---:|
{old_table}

Precision/Recall/F1/support từng lớp và confusion matrices đầy đủ ở
original_results.json, repeated_results.json, transfer_diagnostics.json;
bảng phẳng original_comparison.csv. Accuracy chỉ mô tả mẫu phát triển đã chọn.

## Bằng chứng theo fold cũ

Macro-F1 OOF tính trên toàn bộ dự đoán ngoài fold, không phải trung bình ba
Macro-F1. Số lỗi có thể cộng, Macro-F1 không phân rã cộng theo fold. Phân biệt
số lỗi tuyệt đối với tỷ lệ lỗi khi validation khác kích thước.

| Model | Fold | N validation | Lỗi | Tỷ lệ lỗi | Macro-F1 | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(fold_lines)}

{worst_text}
Đây là xác định bằng confusion matrices/OOF, không suy đoán nguyên nhân từ điểm.
original_fold_metrics.csv có số lớp train/validation, tỷ trọng lỗi và timing.
original_fold_distribution.csv có phân bố nhãn theo movie_id và post_id cho
cả train/validation từng fold; không lấy tên phim làm bằng chứng nhân quả.

Mưa Đỏ và phần POS còn lại:

| Fold | Phần | N Mưa Đỏ | POS Mưa Đỏ | NEG Mưa Đỏ | NEU Mưa Đỏ | POS phim khác |
|---|---|---:|---:|---:|---:|---:|
{special_table}

## 5-seed grouped CV

Seeds cố định trước khi đo: {cfg['seeds']}. Cùng một plan cho mọi model trong
mỗi seed. Nhóm nối theo bài, source comment ID và exact/near duplicates như
Phase E, kể cả liên kết qua dòng ngoài train. Seed 42 tái tạo nguyên byte ID
của ba fold cũ và tái dùng kết quả refit E.1, không tính là thí nghiệm độc lập.

| Model | {' | '.join(str(s) for s in cfg['seeds'])} |
|---|{'---:|'*len(cfg['seeds'])}
{scores}

Một pooled OOF Macro-F1/seed; mean ± sample std (ddof=1) trên 5 seed scores,
KHÔNG trên 15 fold và KHÔNG gộp 5 lần lặp thành 1.730 mẫu độc lập.

| Model | Macro-F1 mean ± std | Recall POS mean ± std | Recall NEG mean ± std | Recall NEU mean ± std |
|---|---:|---:|---:|---:|
{mean_table}

Chỉ có {diagnostics['unique_partitions']} partition khác nhau khi bỏ qua
hoán vị tên fold. Các seed cùng dữ liệu, các partition giống nhau hoặc chỉ
chuyển ít nhóm không phải bằng chứng độc lập. Std nhỏ chỉ mô tả độ nhạy trong
những cách chia cụ thể này, không chứng minh khái quát tốt. Không báo CI hoặc
kiểm định dựa trên giả định 15 fold độc lập.

| Seed | Số câu đổi fold so với 42 | Số component đổi | Số câu Mưa Đỏ đổi |
|---|---:|---:|---:|
{movement}

## Movie/source-topic transfer diagnostic

movie_id là chủ đề bài nguồn, không luôn là phim thực sự được bình luận.
Hai chiều sau là diagnostic phát triển, không independent gold test hoặc
đánh giá phim chưa thấy sạch về ngữ nghĩa. Nếu component vắt qua hai miền,
loại nguyên component khỏi diagnostic và ghi ID; không phá nhóm hay xóa data.
Ngưỡng fit cố định: train mỗi lớp ≥{cfg['transfer']['min_train_per_class_to_fit']}, eval mỗi lớp ≥{cfg['transfer']['min_eval_per_class_to_fit']}.
Support <{cfg['transfer']['limited_support_below_per_class']} câu/lớp hoặc <{cfg['transfer']['limited_support_below_groups_per_class']} component/lớp được gắn hạn chế,
đây là quy tắc cảnh báo đã khai báo, không bảo đảm suy luận thống kê nếu vượt ngưỡng.

{chr(10).join(transfers)}

## Artifact và tái lập

Chạy scripts/run_bow_robustness.py với venv Phase E và dependencies đã khóa.
Artifact E.1 mới, từ chối ghi đè output; không ghi ngược Phase E. Config,
original_locked_plan.json, phase_e_manifest.json và mọi repeated plan lưu
cùng kết quả. predictions.csv giữ đủ ID/seed/fold/model để tái tính mọi số đo.
Dataset/guideline/split cũ không đổi; không gọi GPT/Claude, silver-labeling
hoặc PhoBERT. Kết quả transfer không dùng chọn hyperparameter/test cuối.

API tham khảo: [CountVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html),
[ComplementNB](https://scikit-learn.org/stable/modules/generated/sklearn.naive_bayes.ComplementNB.html),
[StratifiedGroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html).
'''


def run(config_path,output):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('E.1 output exists; do not overwrite recorded artifacts')
    phase_root=(ROOT/load(config_path)['phase_e_root']).resolve()
    if phase_root in output.parents:
        raise ValueError('Keep E.1 output outside the immutable Phase E directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.phase-e1-',dir=output.parent) as temp:
        staged=Path(temp)/'run';result=_run(config_path,staged);staged.rename(output)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'configs/bow_robustness.json')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/phase_e1')
    args=p.parse_args()
    try:result=run(args.config,args.output)
    except (ValueError,OSError,KeyError,RuntimeError) as exc:p.exit(2,f'{type(exc).__name__}: {exc}\n')
    print(json.dumps({k:result[k] for k in ('candidates','fits','seeds','unique_seed_partitions','independent_test')}))


if __name__=='__main__':main()
