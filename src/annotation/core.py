import csv
import json
import random
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from src.data.importers import canonical_json, digest
from src.data.schema import append_decision, gold_label, validate_decision
from src.data.quality import mark_exact_duplicates
from src.data.split import validate_manifest
from src.data.validation import read_jsonl, verify_prepared
from .guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, obj):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def journal(path, obj):
    import os
    with Path(path).open('a', encoding='utf-8', newline='\n') as f:
        f.write(canonical_json(obj)+'\n')
        f.flush()
        os.fsync(f.fileno())


def prepared(root, version):
    root=Path(root)
    verify_prepared(root,version)
    p=root/'processed'/version
    return (read_jsonl(p/'records.jsonl'), read_jsonl(p/'near_duplicates.jsonl'),
            json.loads((root/'splits'/version/'manifest.json').read_text(encoding='utf-8')))


def export_tasks(root, version, output, seed=42, random_count=150, hard_ids=(), split=None, count=None):
    validate_guideline(GUIDELINE_VERSION, digest(GUIDELINE.read_bytes()))
    records,_,manifest=prepared(root,version)
    eligible={e['id']:e for e in manifest['entries'] if e['eligible_for_annotation']}
    lookup={r['id']:r for r in records}
    pool=sorted(rid for rid,e in eligible.items() if split is None or e['split']==split)
    hard_ids=list(hard_ids)
    if len(hard_ids)!=len(set(hard_ids)) or not set(hard_ids).issubset(pool):
        raise ValueError('Hard IDs must be unique eligible IDs in the chosen pool')
    if hard_ids and (split not in (None,'train') or any(eligible[rid]['split']!='train' for rid in hard_ids)):
        raise ValueError('Purposeful hard pilot selection is train-only; representative holdouts must be blind random')
    rng=random.Random(seed)
    random_ids=rng.sample([rid for rid in pool if rid not in hard_ids],min(count or random_count,len(pool)-len(hard_ids)))
    selected=[(rid,'random') for rid in random_ids]+[(rid,'hard') for rid in hard_ids]
    from src.dataset.blind import assert_allowed
    assert_allowed([lookup[rid] for rid,_ in selected],'active_learning')
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    rows=[{'id':rid,'text_raw':lookup[rid]['text_raw'],'split':eligible[rid]['split'],
           'cohort':cohort,'status':'','label':'','review_reason':'','reason':''} for rid,cohort in selected]
    if not rows:
        raise ValueError('No eligible records')
    with (output/'blind.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    save(output/'task.json',{'dataset_version':version,'guideline_version':GUIDELINE_VERSION,
         'guideline_sha256':digest(GUIDELINE.read_bytes()),'seed':seed,'split':split,
         'requested':count or random_count,'selected':len(random_ids),'hard_selected':len(hard_ids),
         'rows':[{k:r[k] for k in ('id','text_raw','split','cohort')} for r in rows],
         'note':'Independent blind human annotation; no machine labels, predictions or explanations.'})
    return output


def import_human(task_path, csv_path, output, annotator, blind, adjudication=False):
    if not annotator.strip(): raise ValueError('Annotator ID required')
    task=json.loads(Path(task_path).read_text(encoding='utf-8'))
    validate_guideline(task['guideline_version'], task['guideline_sha256'])
    expected={r['id']:r for r in task['rows']}
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):
        raise ValueError('CSV must contain exactly the task IDs once; join is by ID')
    events=[]
    for row in rows:
        ref=expected[row['id']]
        if row['text_raw']!=ref['text_raw']:
            raise ValueError('Comment text edited')
        if ref['split'] in ('dev','test') and not blind:
            raise ValueError('Holdout decisions must be blind')
        decision={'label_source':'human','status':row['status'],'label':row['label'] or None,
            'review_reason':row.get('review_reason') or None,'confirmed':True,'is_pseudo':False,
            'needs_review':row['status']=='REVIEW','annotator_id':annotator,
            'evidence_mode':'blind' if blind else 'assisted','decided_at':now(),
            'guideline_version':task['guideline_version'],'reason':row.get('reason',''),
            'adjudication':adjudication}
        validate_decision(decision)
        events.append({'id':row['id'],'dataset_version':task['dataset_version'],
            'guideline_sha256':task['guideline_sha256'],'cohort':ref['cohort'],'decision':decision})
    with Path(output).open('x',encoding='utf-8',newline='\n') as f:
        for e in events: f.write(canonical_json(e)+'\n')
    return len(events)


def pair_metrics(x,y):
    """Shared categorical agreement; workflow states remain separate from sentiment."""
    if not x or len(x)!=len(y): raise ValueError('Equal nonempty decision pairs required')
    def metrics(left,right,categories):
        n=len(left);cx,cy=Counter(left),Counter(right)
        po=sum(u==v for u,v in zip(left,right))/n
        pe=sum(cx[k]*cy[k] for k in set(cx)|set(cy))/(n*n)
        return dict(n=n,agreement=po,kappa=(po-pe)/(1-pe) if pe<1 else None,categories=categories,
            confusion_matrix=[[sum(u==c and v==d for u,v in zip(left,right)) for d in categories] for c in categories])
    result=metrics(x,y,['POS','NEG','NEU','REVIEW','EXCLUDE'])
    pairs=[(u,v) for u,v in zip(x,y) if u in ('POS','NEG','NEU') and v in ('POS','NEG','NEU')]
    result['sentiment_pair_count']=len(pairs)
    result['sentiment_only']=metrics([u for u,v in pairs],[v for u,v in pairs],['POS','NEG','NEU']) if pairs else None
    result['note']='REVIEW/EXCLUDE are workflow decisions. Null Kappa means degenerate marginals.'
    return result


def agreement(left_path,right_path,output):
    left,right=read_jsonl(left_path),read_jsonl(right_path)
    def index(rows):
        d={r['id']:r for r in rows}
        if len(d)!=len(rows): raise ValueError('Duplicate IDs')
        for r in rows:
            validate_decision(r['decision'])
            if r['decision']['label_source']!='human' or r['decision']['evidence_mode']!='blind':
                raise ValueError('Agreement requires independent blind human decisions')
        return d
    a,b=index(left),index(right)
    if not a or set(a)!=set(b): raise ValueError('Annotators must cover identical IDs')
    if {r['decision']['annotator_id'] for r in left}&{r['decision']['annotator_id'] for r in right}:
        raise ValueError('Annotators must differ')
    sig=lambda r:r['decision']['label'] or r['decision']['status']
    reports={}; disagreements=[]
    for rid in a:
        if any(a[rid][k]!=b[rid][k] for k in ('dataset_version','guideline_sha256','cohort')):
            raise ValueError('Task provenance mismatch')
        if sig(a[rid])!=sig(b[rid]): disagreements.append({'id':rid,'left':a[rid],'right':b[rid]})
    for cohort in sorted({r['cohort'] for r in left}):
        ids=[rid for rid in a if a[rid]['cohort']==cohort]
        reports[cohort]=pair_metrics([sig(a[rid]) for rid in ids],[sig(b[rid]) for rid in ids])
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    save(output/'agreement.json',reports)
    with (output/'disagreements.jsonl').open('x',encoding='utf-8') as f:
        for r in disagreements: f.write(canonical_json(r)+'\n')
    return reports


def release(root, version, event_paths, output, used_ids=(), synthetic=False):
    original,pairs,manifest=prepared(root,version)
    records=deepcopy(original); lookup={r['id']:r for r in records}
    history=[]
    guide_contract=None
    for path in event_paths:
        for event in read_jsonl(path):
            if event['dataset_version']!=version or event['id'] not in lookup:
                raise ValueError('Event dataset/ID mismatch')
            r=lookup[event['id']]; d=event['decision']
            contract=validate_guideline(d['guideline_version'], event['guideline_sha256'])
            if guide_contract is not None and guide_contract != contract:
                raise ValueError('Mixed guidelines require explicit human migration')
            guide_contract=contract
            if d.get('fixture_only') and not synthetic: raise ValueError('Replay events are fixture-only')
            if d['label_source']=='human' and r['annotations']['human']:
                previous=r['annotations']['human'][-1]
                if (previous['status'],previous['label'])!=(d['status'],d['label']) and not d.get('adjudication'):
                    raise ValueError('Human disagreement requires explicit adjudication')
            append_decision(r,d); history.append(event)
    mark_exact_duplicates(records)
    validate_manifest(records,pairs,manifest,used_ids=used_ids)
    entries={e['id']:e for e in manifest['entries']}
    unknown=set(used_ids)-set(lookup)
    holdout_groups={e['group_id'] for e in entries.values() if e['split'] in ('dev','test')}
    if unknown or any(entries[rid]['group_id'] in holdout_groups for rid in used_ids):
        raise ValueError('Usage intersects holdout or unknown IDs')
    unresolved=[]
    for rid,e in entries.items():
        if e['eligible_for_annotation'] and e['split'] in ('dev','test'):
            h=lookup[rid]['annotations']['human']
            d=h[-1] if h else {}
            if not (d.get('confirmed') and d.get('evidence_mode')=='blind' and
                    d.get('status') in ('LABELED','EXCLUDE') and not lookup[rid]['quality']['label_conflict']):
                unresolved.append(rid)
    manifest=deepcopy(manifest); manifest['locked_gold']=not unresolved
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    for name,rows in [('records.jsonl',records),('near_duplicates.jsonl',pairs),('events.jsonl',history)]:
        with (output/name).open('x',encoding='utf-8',newline='\n') as f:
            for r in rows: f.write(canonical_json(r)+'\n')
    save(output/'manifest.json',manifest)
    guide_version,guide_sha=guide_contract or validate_guideline(GUIDELINE_VERSION,digest(GUIDELINE.read_bytes()))
    save(output/'release.json',{'dataset_version':version,'guideline_version':guide_version,
        'guideline_sha256':guide_sha,'created_at':now(),'synthetic':synthetic,
        'status':'ready' if not unresolved else 'draft','unresolved_holdout_ids':unresolved,
        'used_train_tune_ids':sorted(used_ids),'parent_report_sha256':digest((Path(root)/'processed'/version/'report.json').read_bytes()),
        'checksums':{p.name:digest(p.read_bytes()) for p in output.iterdir()}})
    return output


def load_release(path):
    path=Path(path); meta=json.loads((path/'release.json').read_text(encoding='utf-8'))
    for name,sha in meta['checksums'].items():
        if Path(name).name!=name or digest((path/name).read_bytes())!=sha: raise ValueError('Release checksum mismatch')
    records=read_jsonl(path/'records.jsonl'); pairs=read_jsonl(path/'near_duplicates.jsonl')
    manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if manifest['data_version']!=meta['dataset_version']: raise ValueError('Release version mismatch')
    validate_manifest(records,pairs,manifest,used_ids=meta['used_train_tune_ids'])
    holdout={e['group_id'] for e in manifest['entries'] if e['split'] in ('dev','test')}
    entries={e['id']:e for e in manifest['entries']}
    if any(rid not in entries or entries[rid]['group_id'] in holdout for rid in meta['used_train_tune_ids']):
        raise ValueError('Holdout used for training/tuning')
    return records,manifest,meta
