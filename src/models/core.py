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

GOLD_CONFIG={
    'bow_complement_nb':{'feature':'bow','model':'complement_nb','alpha':1.0,'ngram_range':[1,1]},
    'bow_multinomial_nb':{'feature':'bow','model':'multinomial_nb','alpha':1.0,'ngram_range':[1,1]},
    'tfidf_word_svm':{'feature':'word','model':'svm','ngram_range':[1,2],'class_weight':'balanced','C':1.0},
    'tfidf_char_svm':{'feature':'char_wb','model':'svm','ngram_range':[3,5],'class_weight':'balanced','C':1.0},
}


def gold_model(name):
    """Predeclared models; NB deliberately never receives class_weight."""
    from sklearn.naive_bayes import ComplementNB
    cfg=GOLD_CONFIG[name]
    if cfg['feature']=='bow':
        vec=CountVectorizer(ngram_range=(1,1),token_pattern=r'(?u)\b\w+\b')
        estimator=(ComplementNB if cfg['model']=='complement_nb' else MultinomialNB)(alpha=1.0)
    else:
        vec=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5)) if cfg['feature']=='char_wb' else TfidfVectorizer(ngram_range=(1,2),token_pattern=r'(?u)\b\w+\b')
        estimator=LinearSVC(C=1.0,class_weight='balanced',random_state=20261113,max_iter=20000)
    return Pipeline([('vectorizer',vec),('model',estimator)])


def confusion_png(path,matrix):
    """Readable 3-class PNG with a tiny bitmap font, no plotting dependency."""
    import struct,zlib
    glyphs={
      '0':'01110/10001/10011/10101/11001/10001/01110','1':'00100/01100/00100/00100/00100/00100/01110',
      '2':'01110/10001/00001/00010/00100/01000/11111','3':'11110/00001/00001/01110/00001/00001/11110',
      '4':'00010/00110/01010/10010/11111/00010/00010','5':'11111/10000/10000/11110/00001/00001/11110',
      '6':'01110/10000/10000/11110/10001/10001/01110','7':'11111/00001/00010/00100/01000/01000/01000',
      '8':'01110/10001/10001/01110/10001/10001/01110','9':'01110/10001/10001/01111/00001/00001/01110',
      'P':'11110/10001/10001/11110/10000/10000/10000','O':'01110/10001/10001/10001/10001/10001/01110',
      'S':'01111/10000/10000/01110/00001/00001/11110','N':'10001/11001/11001/10101/10011/10011/10001',
      'E':'11111/10000/10000/11110/10000/10000/11111','G':'01110/10001/10000/10111/10001/10001/01110',
      'T':'11111/00100/00100/00100/00100/00100/00100','R':'11110/10001/10001/11110/10100/10010/10001',
      'U':'10001/10001/10001/10001/10001/10001/01110','D':'11110/10001/10001/10001/10001/10001/11110',
      'I':'11111/00100/00100/00100/00100/00100/11111','C':'01111/10000/10000/10000/10000/10000/01111'}
    width,height=430,390;pixels=bytearray([255])*(width*height*3)
    def rectangle(x,y,w,h,color):
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                if 0<=xx<width and 0<=yy<height:pixels[(yy*width+xx)*3:(yy*width+xx)*3+3]=bytes(color)
    def text(x,y,value,scale=2,color=(20,30,40)):
        for i,char in enumerate(value):
            for yy,line in enumerate(glyphs[char].split('/')):
                for xx,bit in enumerate(line):
                    if bit=='1':rectangle(x+i*6*scale+xx*scale,y+yy*scale,scale,scale,color)
    text(170,8,'PREDICTED');text(8,8,'TRUE')
    maximum=max(1,max(max(row) for row in matrix))
    for i,label in enumerate(LABELS):text(126+i*100,43,label);text(45,112+i*100,label)
    for y,row in enumerate(matrix):
        for x,count in enumerate(row):
            ratio=count/maximum;color=(int(245-185*ratio),int(250-145*ratio),int(255-80*ratio))
            rectangle(99+x*100,69+y*100,100,100,(210,220,230));rectangle(100+x*100,70+y*100,98,98,color)
            value=str(count);text(100+x*100+(100-len(value)*24)//2,105+y*100,value,4,(255,255,255) if ratio>.65 else (15,25,35))
    def chunk(tag,body):return struct.pack('!I',len(body))+tag+body+struct.pack('!I',zlib.crc32(tag+body)&0xffffffff)
    raw=b''.join(b'\x00'+bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def gold_train_rows(gold_rows,train_path,root):
    """Keep gold; remove train identity/exact/near leakage before existing guards."""
    from src.dataset.common import verify,read_jsonl as read_lines
    from src.data.split import duplicate_groups
    from src.dataset.blind import assert_allowed,ReservedDataError
    from src.preprocessing import preprocess
    verify(Path(train_path).parent)
    candidates=[r for r in read_lines(train_path) if r.get('human_label') in LABELS and
        any(d.get('status')=='LABELED' and d.get('label')==r['human_label'] for d in r.get('human_decisions',[]))]
    combined=[dict(record_id='g_'+r['id'],text_clean=preprocess(r['text'])) for r in gold_rows]
    combined += [dict(record_id='t_'+r['record_id'],text_clean=preprocess(r.get('text_minimal') or r['text_raw'])) for r in candidates]
    groups,_,near=duplicate_groups(combined,threshold=.9,min_chars=40,max_posting=max(256,len(combined)+1))
    near['summary']['near_duplicate_limit']='No posting truncation for gold/train leakage check; minimum 40 characters, token-3gram Jaccard >= 0.9'
    if near['summary']['high_document_frequency_shingles_skipped']:
        raise ValueError('Gold/train leakage check must not truncate common-shingle postings')
    test_ids={r['record_id'] for r in combined if r['record_id'].startswith('g_')}
    test_groups={groups[rid] for rid in test_ids};test_posts={r['post_id'] for r in gold_rows}
    test_comments={r.get('comment_id') for r in gold_rows if r.get('comment_id')};used=[];excluded=[]
    for row in candidates:
        rid='t_'+row['record_id'];reason=None
        if row.get('post_id') and row['post_id'] in test_posts or row.get('comment_id') and row['comment_id'] in test_comments:reason='SOURCE_IDENTITY_LEAKAGE'
        elif groups[rid] in test_groups:reason='EXACT_OR_NORMALIZED_TEXT_LEAKAGE'
        elif near['neighbors'].get(rid,set())&test_ids:reason='NEAR_TEXT_LEAKAGE'
        if reason is None:
            adapted=dict(row,id=row['record_id'],text=row.get('text_minimal') or row['text_raw'])
            try:
                assert_allowed([adapted],'train',reservation_root=Path(root)/'outputs/phase_g/blind_test',
                               registry=Path(root)/'data/test_reservations')
            except ReservedDataError:reason='RESERVED_POOL_LEAKAGE'
        if reason:excluded.append(dict(id=row['record_id'],reason=reason))
        else:used.append(dict(id=row['record_id'],text=preprocess(row.get('text_minimal') or row['text_raw']),label=row['human_label']))
    return used,excluded,dict(candidates=len(candidates),used=len(used),excluded=len(excluded),near_detector=near['summary'])


def evaluate_gold(directory,train_path,root):
    """One-shot, fixed configurations. Called on real gold ONLY by the user."""
    from src.dataset.common import load,sha,save as store,read_jsonl,write_csv
    from src.annotation.gold import _task,_directory
    directory=_directory(directory,root);lock_path=directory/'locked_gold.json'
    if not lock_path.is_file():raise ValueError('Gold must be locked after recheck/final decisions before evaluation')
    contract=_task(directory);locked=load(lock_path)
    if locked['status']!='LOCKED_SINGLE_ANNOTATOR_TEST' or locked['records_sha256']!=sha(directory/'locked_gold.local.jsonl') or locked['coordinator_sha256']!=sha(directory/'coordinator.json'):
        raise ValueError('Locked gold checksum/status mismatch')
    if not locked['agreement'].get('within_one_day'):raise ValueError('This fixed protocol requires the intra-annotator recheck within less than one day')
    results=directory/'results';ledger=Path(root)/'data/evaluation_usage';key=sha(directory/'coordinator.json')
    if (results/'receipt.json').exists() or (ledger/('gold_'+key+'.json')).exists():raise FileExistsError('Gold evaluation already claimed; exactly one execution is allowed')
    all_gold=read_jsonl(directory/'locked_gold.local.jsonl')
    expected={r['id']:r for r in contract['rows']}
    if len(all_gold)!=len(expected) or {r['id'] for r in all_gold}!=set(expected) or any(r['text_sha256']!=digest(r['text']) or r['text']!=expected[r['id']]['text'] for r in all_gold):raise ValueError('Locked gold IDs/text differ')
    test=[r for r in all_gold if r['status']=='LABELED' and r['label'] in LABELS]
    if not test:raise ValueError('Gold has no POS/NEG/NEU examples')
    train,excluded,train_summary=gold_train_rows(all_gold,train_path,root)
    if len({r['label'] for r in train})<2:raise ValueError(f'Only {len(train)} leakage-safe training records remain after {len(excluded)} exclusions; at least two classes required, no guard relaxed')
    ledger.mkdir(parents=True,exist_ok=True);results.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='CLAIMED_ONCE',gold_sha256=sha(lock_path),gold_records_sha256=sha(directory/'locked_gold.local.jsonl'),
        train_source_sha256=sha(train_path),used_train_sha256=digest(json.dumps(train,sort_keys=True,ensure_ascii=False)),
        configuration=GOLD_CONFIG,seed=20261113,claimed_at=now(),train_counts=train_summary,
        implementation_sha256=digest(Path(__file__).read_bytes()),runtime=dict(python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__),
        annotation_protocol='one annotator; intra-annotator recheck <1 day; first up to 60 Facebook-ordered records/post')
    store(ledger/('gold_'+key+'.json'),receipt)  # Exclusive claim BEFORE fitting/predicting; crashes remain consumed.
    store(results/'receipt.json',receipt)
    write_csv(results/'train_exclusions.csv',excluded,['id','reason'])
    table={};predictions=[];group_table=[];x=[r['text'] for r in train];y=[r['label'] for r in train]
    for name in GOLD_CONFIG:
        estimator=gold_model(name);started=time.perf_counter();estimator.fit(x,y)
        pred=estimator.predict([r['text'] for r in test]);summary=metrics([r['label'] for r in test],pred)
        summary['seconds']=time.perf_counter()-started;table[name]=summary
        confusion_png(results/(name+'_confusion.png'),summary['confusion_matrix'])
        predictions.extend(dict(model=name,id=r['id'],label=r['label'],prediction=str(p)) for r,p in zip(test,pred))
        for field in ('movie_id','group'):
            for value in sorted({r[field] for r in test}):
                positions=[i for i,r in enumerate(test) if r[field]==value]
                item=metrics([test[i]['label'] for i in positions],[pred[i] for i in positions])
                group_table.append(dict(model=name,field=field,value=value,n=len(positions),accuracy=item['accuracy'],macro_f1=item['macro_f1'],per_class=item['per_class']))
    store(results/'metrics.json',dict(models=table,train=train_summary,gold_sentiment=len(test),gold_workflow_excluded=len(all_gold)-len(test),
        interpretation='Single-annotator test, convenience first-60 source order; no gold tuning or inter-annotator claim'))
    write_csv(results/'comparison.csv',[dict(model=k,accuracy=v['accuracy'],macro_f1=v['macro_f1'],seconds=v['seconds']) for k,v in table.items()],['model','accuracy','macro_f1','seconds'])
    write_csv(results/'predictions.local.csv',predictions,['model','id','label','prediction'])
    write_csv(results/'by_movie_and_group.csv',group_table,['model','field','value','n','accuracy','macro_f1','per_class'])
    return dict(models=list(table),train=train_summary,gold_sentiment=len(test),output=str(results))


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
