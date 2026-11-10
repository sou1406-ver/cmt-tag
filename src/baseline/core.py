import csv
import json
from pathlib import Path
import platform
import time

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.annotation.core import load_release, now, save
from src.data.importers import digest
from src.data.schema import gold_label

LABELS=['POS','NEG','NEU']


def metrics(y,pred):
    report=classification_report(y,pred,labels=LABELS,output_dict=True,zero_division=0)
    return {'accuracy':float(accuracy_score(y,pred)),
            'macro_precision':report['macro avg']['precision'],'macro_recall':report['macro avg']['recall'],
            'macro_f1':report['macro avg']['f1-score'],
            'per_class':{k:report[k] for k in LABELS},'labels':LABELS,
            'confusion_matrix':confusion_matrix(y,pred,labels=LABELS).tolist()}


def dataset(release_path,mode='mixed'):
    records,manifest,meta=load_release(release_path)
    from src.dataset.blind import assert_allowed
    assert_allowed(records, 'train')
    if meta['status']!='ready' or not manifest['locked_gold']: raise ValueError('Independent gold holdout not ready')
    by_id={r['id']:r for r in records}; pools={s:[] for s in ('train','dev','test')}
    for e in manifest['entries']:
        if not e['eligible_for_annotation']: continue
        r=by_id[e['id']]; split=e['split']; h=r['annotations']['human']
        label=gold_label(r,evaluation=split in ('dev','test')); origin='gold' if label else None
        if split in ('dev','test'):
            if not label:
                if h and h[-1]['confirmed'] and h[-1]['evidence_mode']=='blind' and h[-1]['status']=='EXCLUDE': continue
                raise ValueError('Dev/test require independent confirmed blind human gold')
        else:
            if h and (h[-1]['status']!='LABELED' or not h[-1]['confirmed']): continue
            if not label and r['annotations']['machine']:
                d=r['annotations']['machine'][-1]
                if d['status']=='LABELED' and not d['is_pseudo'] and not r['quality']['label_conflict']:
                    label=d['label']; origin='silver'
            if mode=='gold-only' and origin!='gold' or mode=='silver-only' and origin!='silver': continue
        if label: pools[split].append({'id':r['id'],'text':r['text'],'label':label,'origin':origin,'group_id':e['group_id']})
    if any(not rows for rows in pools.values()): raise ValueError('Train/dev/test need labeled examples')
    if len({r['label'] for r in pools['train']})<2: raise ValueError('Training needs at least two classes')
    return pools,meta


def test_key(pools):
    return digest('\n'.join(sorted(r['id'] for r in pools['test'])))


def model(feature,kind,ngram,weight,seed):
    vec=(CountVectorizer if feature=='bow' else TfidfVectorizer)(ngram_range=(1,ngram),token_pattern=r'(?u)\b\w+\b')
    if kind=='nb': estimator=MultinomialNB(alpha=1.0)
    elif kind=='lr': estimator=LogisticRegression(C=1.0,class_weight=weight,random_state=seed,max_iter=2000)
    else: estimator=LinearSVC(C=1.0,class_weight=weight,random_state=seed,max_iter=10000)
    return Pipeline([('vectorizer',vec),('model',estimator)])


def train(release_path,output,usage_root,seed=42,mode='mixed'):
    pools,meta=dataset(release_path,mode)
    key=test_key(pools)
    if (Path(usage_root)/(key+'.json')).exists(): raise ValueError('Test already opened; no further tuning on this release')
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    x=[r['text'] for r in pools['train']]; y=[r['label'] for r in pools['train']]
    xd=[r['text'] for r in pools['dev']]; yd=[r['label'] for r in pools['dev']]
    table=[]; selected=[]
    for feature in ('bow','tfidf'):
        for kind in ('nb','lr','svm'):
            candidates=[]
            for ngram in (1,2):
                for weight in ([None] if kind=='nb' else [None,'balanced']):
                    pipeline=model(feature,kind,ngram,weight,seed)
                    start=time.perf_counter(); pipeline.fit(x,y); fit_time=time.perf_counter()-start
                    start=time.perf_counter(); pred=pipeline.predict(xd); predict_time=time.perf_counter()-start
                    score=metrics(yd,pred)
                    row={'cell':feature+'_'+kind,'ngram':ngram,'class_weight':weight,'dev':score,
                         'fit_seconds':fit_time,'dev_predict_seconds':predict_time}
                    table.append(row); candidates.append((row,pipeline))
            # Stable ties prefer unigram, then no weighting; no test access.
            row,pipeline=max(candidates,key=lambda pair:pair[0]['dev']['macro_f1'])
            filename=row['cell']+'.joblib'; joblib.dump(pipeline,output/filename)
            selected.append(dict(row,artifact=filename))
    dummy=DummyClassifier(strategy='most_frequent',random_state=seed)
    start=time.perf_counter(); dummy.fit(np.zeros((len(y),1)),y); elapsed=time.perf_counter()-start
    pred=dummy.predict(np.zeros((len(yd),1)))
    joblib.dump(dummy,output/'majority.joblib')
    selected.append({'cell':'majority','ngram':None,'class_weight':None,'dev':metrics(yd,pred),
                     'fit_seconds':elapsed,'artifact':'majority.joblib'})
    winner=max(selected,key=lambda r:r['dev']['macro_f1'])['cell']
    save(output/'dev_comparison.json',table)
    config={'release_path':str(Path(release_path).resolve()),
            'release_sha256':digest((Path(release_path)/'release.json').read_bytes()),
            'dataset_version':meta['dataset_version'],'synthetic':meta['synthetic'],'mode':mode,'seed':seed,
            'versions':{'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__},
            'code_sha256':digest(Path(__file__).read_bytes()),'selected':selected,'dev_winner':winner,
            'used_train_ids':[r['id'] for r in pools['train']],'used_tune_ids':[r['id'] for r in pools['dev']],
            'test_key':key,'usage_root':str(Path(usage_root).resolve()),
            'checksums':{p.name:digest(p.read_bytes()) for p in output.iterdir()},
            'note':'Only train used for fit; dev for selection; test not predicted. Artifact timings are nondeterministic.'}
    save(output/'selection.json',config)
    save(output/'used_ids.json',config['used_train_ids']+config['used_tune_ids'])
    return config


def evaluate(run,output):
    run=Path(run); cfg=json.loads((run/'selection.json').read_text(encoding='utf-8'))
    release_path=Path(cfg['release_path'])
    if digest((release_path/'release.json').read_bytes())!=cfg['release_sha256']: raise ValueError('Release changed since selection')
    for name,sha in cfg['checksums'].items():
        if Path(name).name!=name or digest((run/name).read_bytes())!=sha: raise ValueError('Model/run checksum mismatch')
    pools,meta=dataset(release_path,cfg['mode'])
    if test_key(pools)!=cfg['test_key']: raise ValueError('Test changed')
    output=Path(output)
    if output.exists(): raise FileExistsError('Final output already exists')
    ledger=Path(cfg['usage_root']); ledger.mkdir(parents=True,exist_ok=True)
    # Reserve before looking at predictions. A crashed evaluation remains used.
    save(ledger/(cfg['test_key']+'.json'),{'opened_at':now(),'selection_sha256':digest((run/'selection.json').read_bytes()),
         'run':str(run.resolve()),'output':str(output.resolve()),'test_ids':[r['id'] for r in pools['test']],
         'note':'Final test exposed. Do not reuse for tuning; an interrupted evaluation is still exposure.'})
    output.mkdir(parents=True,exist_ok=False)
    x=[r['text'] for r in pools['test']]; y=[r['label'] for r in pools['test']]
    table=[]; predictions=[]; errors=[]
    for cell in cfg['selected']:
        estimator=joblib.load(run/cell['artifact'])
        start=time.perf_counter()
        pred=estimator.predict(np.zeros((len(x),1)) if cell['cell']=='majority' else x)
        elapsed=time.perf_counter()-start
        score=metrics(y,pred)
        table.append({'cell':cell['cell'],'ngram':cell['ngram'],'class_weight':cell['class_weight'],
                      **score,'fit_seconds':cell['fit_seconds'],'predict_seconds':elapsed})
        for r,p in zip(pools['test'],pred):
            item={'id':r['id'],'cell':cell['cell'],'gold':r['label'],'prediction':str(p)}
            predictions.append(item)
            if p!=r['label']:
                text=r['text']; tags=[]
                if any(t in text.casefold() for t in ('không','chẳng','chưa')): tags.append('negation_candidate')
                if 'nhưng' in text.casefold(): tags.append('contrast_candidate')
                if ':)' in text or ':(' in text: tags.append('sarcasm_review_candidate')
                errors.append(dict(item,text=text,review_tags=tags or ['manual_review']))
    save(output/'metrics.json',{'synthetic':meta['synthetic'],'sampling':'Original Phase B grouped reservation; no predicted-label sampling.',
         'dev_selected_winner':cfg['dev_winner'],'models':table,
         'support':{k:y.count(k) for k in LABELS},
         'warnings':['Fixture metrics are not research results.' if meta['synthetic'] else 'Gold test requires verified independent blind human decisions.',
                     'Report rare-class uncertainty; per-class n < 50 is weak evidence. Dev/test targets 200/300.',
                     'Challenge accuracy must be reported separately; no challenge is included here.'],
         'train_origin_counts':{k:sum(r['origin']==k for r in pools['train']) for k in ('gold','silver')},
         'train_size':len(pools['train']),'dev_size':len(pools['dev']),'test_size':len(y),
         'test_opened_once':True,'selected_config_sha256':digest((run/'selection.json').read_bytes())})
    for name,rows in [('predictions.jsonl',predictions),('error_analysis.jsonl',errors)]:
        with (output/name).open('x',encoding='utf-8') as f:
            for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with (output/'comparison.csv').open('x',encoding='utf-8-sig',newline='') as f:
        fields=['cell','ngram','class_weight','accuracy','macro_precision','macro_recall','macro_f1','fit_seconds','predict_seconds']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(table)
    save(output/'artifact_checksums.json',{p.name:digest(p.read_bytes()) for p in output.iterdir()})
    return table
