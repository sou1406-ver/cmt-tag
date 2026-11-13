"""Small, local pilot coordinator; development calibration is never silver."""
from collections import Counter, defaultdict
import csv
import json
import random
from pathlib import Path

from src.dataset.common import ROOT, digest, load, normal, read_jsonl, save, seal, sha, verify, write_jsonl, write_csv, staged
from src.dataset.blind import assert_allowed, ReservedDataError
from src.preprocessing import preprocess
from src.preprocessing.quality import strip_urls, SEPARATORS
from .guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline
from .gold import workbook, _labels
from .core import now

SEED=20261113
CATEGORIES=['POS','NEG','NEU','REVIEW','EXCLUDE']
SENTIMENT=CATEGORIES[:3]
DEFAULT=ROOT/'outputs/ai_labeling/pilot_20261113'


def fingerprints(text):
    tokens=__import__('re').findall(r'\w+|[^\w\s]',normal(text))
    return {digest('\n'.join(tokens[i:i+3])) for i in range(len(tokens)-2)} if len(normal(text))>=40 else set()


def protection(rows,source,root):
    """Only test/reserved/holdout protection; development posts are permitted.

    Protected journals are used ONLY locally to make duplicate fingerprints,
    never labels or provider inputs. No semantic inspection or gold tuning.
    """
    checks={};texts=[];posts=set();comments=set();ids=set()
    mapping=root/'outputs/canonical/versions/rebuild_20261112/quality_holdout_mapping.local.json'
    if mapping.exists():
        m=load(mapping);checks[str(mapping)]=sha(mapping)
        ids.update(m['retained_ids']);ids.update(m['excluded_ids'])
        canonical=mapping.parent/'normalized_annotation_view.local.jsonl'
        checks[str(canonical)]=sha(canonical)
        for r in read_jsonl(canonical):
            if r['record_id'] in ids:
                if r.get('post_id'): posts.add(str(r['post_id']))
                texts.extend([r['text_raw'],r.get('text_normalized','')])
    for path in sorted((root/'data/test_reservations').glob('*.json')):
        entry=load(path);checks[str(path)]=sha(path)
        if entry.get('collection_root'):
            q=Path(entry['collection_root'])/'post_quarantine.json';checks[str(q)]=sha(q);quarantine=load(q)
            posts.update(quarantine['post_ids']);comments.update(quarantine['comment_ids']);ids.update(quarantine['ids'])
        # New gold's source receipt pins raw observations; do NOT open locked labels/workbooks/results.
        receipt=Path(entry['plan_root'])/'sample_receipt.json'
        if receipt.exists():
            checks[str(receipt)]=sha(receipt)
            for name,h in load(receipt)['source_sha256'].items():
                p=Path(name)
                if p.name!='raw_comments.jsonl':continue
                if sha(p)!=h:raise ValueError('Reserved journal checksum mismatch')
                checks[str(p)]=h
                from .gold import display_text
                for r in read_jsonl(p):
                    raw=r.get('text_raw','');texts.append(raw)
                    if r.get('text_extraction_version')=='dom_text_v2':
                        texts.append(display_text(raw,r.get('text_without_mentions'),r.get('mention_count',0)))
    # Preserve older sealed reservations through the existing production guard.
    if (root/'outputs/phase_g/blind_test').exists():
        m=verify(root/'outputs/phase_g/blind_test')
        if m.get('status')!='PARTIAL':
            q=root/'outputs/phase_g/blind_test/reservation.json';checks[str(q)]=sha(q);r=load(q)
            posts.update(r['post_ids']);comments.update(r['comment_ids']);ids.update(r['ids'])
    for r in rows:
        if r.get('post_id') in posts or r['record_id'] in ids:
            texts.extend([r['text_raw'],r['text_minimal'],r['text_annotation_view']])
    protected_hashes={digest(normal(v)) for t in texts for v in (t,strip_urls(t)) if v}
    protected_shingles=[fingerprints(v) for t in texts for v in (t,strip_urls(t)) if v]
    protected_shingles=[s for s in protected_shingles if s]
    return dict(posts=posts,comments=comments,ids=ids,text_hashes=protected_hashes,shingles=reference_index(protected_shingles),checksums=checks)


def reference_index(values):
    sets=list({frozenset(s) for s in values if s});postings=defaultdict(set)
    for i,s in enumerate(sets):
        for key in s:postings[key].add(i)
    return dict(sets=sets,postings=postings)


def near_any(text,reference):
    value=fingerprints(text)
    if isinstance(reference,dict):
        if not value:return False
        overlap=Counter(i for key in value for i in reference['postings'].get(key,()))
        return any(n/(len(value)+len(reference['sets'][i])-n)>=.9 for i,n in overlap.items())
    return bool(value) and any(len(value&other)/len(value|other)>=.9 for other in reference if other)


def guard_reason(r,guard):
    if r['record_id'] in guard['ids'] or str(r.get('post_id') or '') in guard['posts'] or str(r.get('comment_id') or '') in guard['comments']:
        return 'TEST_RESERVED_HOLDOUT_IDENTITY'
    variants=[r['text_raw'],r['text_minimal'],r['text_annotation_view']]
    if any(digest(normal(t)) in guard['text_hashes'] for t in variants):return 'EXACT_RESERVED_TEXT'
    if any(near_any(t,guard['shingles']) for t in variants):return 'NEAR_RESERVED_TEXT'
    return None


def stratified(rows,count,key,rng):
    """Proportional largest-remainder quotas; random within each stratum."""
    bins=defaultdict(list)
    for r in rows:bins[key(r)].append(r)
    count=min(count,len(rows));allocation={k:int(count*len(v)/len(rows)) for k,v in bins.items()} if rows else {}
    remain=count-sum(allocation.values())
    for k in sorted(bins,key=lambda k:(-(count*len(bins[k])/len(rows)-allocation[k]),str(k)))[:remain]:allocation[k]+=1
    selected=[]
    for k in sorted(bins,key=str):selected+=rng.sample(sorted(bins[k],key=lambda r:r['record_id']),allocation[k])
    return selected


def sample_unlabeled(rows,count=450):
    """Random movie/post round robin, Facebook first; legacy has no movie."""
    rng=random.Random(SEED);fb=defaultdict(lambda:defaultdict(list));legacy=[]
    for r in sorted(rows,key=lambda r:r['record_id']):
        if r.get('human_decisions') or r.get('human_label') or r.get('quality_decision','KEEP')!='KEEP':continue
        if r['source_dataset']=='facebook':fb[r.get('movie_id') or 'UNKNOWN_MOVIE'][r['post_id']].append(r)
        else:legacy.append(r)
    selected=[];pc=Counter();mc=Counter();seen=set();shingles=[]
    movies=sorted(fb);rng.shuffle(movies)
    post_order={m:sorted(fb[m]) for m in movies}
    for m in movies:
        rng.shuffle(post_order[m])
        for p in post_order[m]:rng.shuffle(fb[m][p])
    progress=True
    while progress and len(selected)<count:
        progress=False
        for movie in movies:
            for post in post_order[movie]:
                if pc[post]>=12 or mc[movie]>=36:continue
                while fb[movie][post]:
                    r=fb[movie][post].pop();key=normal(r['text_annotation_view'])
                    if key in seen or near_any(r['text_annotation_view'],shingles):continue
                    selected.append(r);seen.add(key);shingles.append(fingerprints(r['text_annotation_view']))
                    pc[post]+=1;mc[movie]+=1;progress=True;break
                if len(selected)>=count:break
            if len(selected)>=count:break
    rng.shuffle(legacy)
    for r in legacy:
        if len(selected)>=count:break
        key=normal(r['text_annotation_view'])
        if key in seen or near_any(r['text_annotation_view'],shingles):continue
        selected.append(r);seen.add(key);shingles.append(fingerprints(r['text_annotation_view']))
    return selected


def prepare(directory=DEFAULT,source=ROOT/'outputs/canonical/versions/filtered_20261113_quality_v1',root=ROOT):
    directory,source,root=map(lambda p:Path(p).resolve(),(directory,source,root))
    if not directory.is_relative_to(root/'outputs/ai_labeling'):raise ValueError('Pilot must remain local in outputs/ai_labeling')
    if directory.exists():raise FileExistsError('Pilot selection already exists; no resampling after inspection')
    verify(source);validate_guideline(GUIDELINE_VERSION,sha(GUIDELINE))
    from src.models.preprocessing_cv import snapshot
    before=snapshot(root,source);rows=read_jsonl(source/'candidate.local.jsonl')
    guard=protection(rows,source,root);rejections=[];eligible=[];dev=[]
    # Technical review of the exact 20 already-exported tag-only examples; no new rule.
    example_path=root/'outputs/quality_filter_review/examples.local.jsonl';example_checks={}
    if example_path.exists():
        examples=[e for e in read_jsonl(example_path) if e['example_rule']=='EXCLUDE_TAG_ONLY'][:20]
        example_checks=dict(n=len(examples),all_rule_match=all(e['view_method']=='DOM_RULE_MATCH' for e in examples),
            no_remaining_signal=all(bool(SEPARATORS.fullmatch(e['text_after_urls'])) for e in examples),
            human_records=sum(e['human_decision_present'] for e in examples),semantic_human_review=False)
        if len(examples)<20 or not example_checks['all_rule_match'] or not example_checks['no_remaining_signal'] or example_checks['human_records']:
            raise ValueError('Tag-only example gate failed; stop pool use')
    for r in rows:
        reason=None
        if r['quality_decision']!='KEEP':reason='QUALITY_'+r['quality_decision']
        elif r.get('proposed_decision') in ('REVIEW','EXCLUDE'):reason='QUALITY_HUMAN_FLAG_ONLY'
        else:reason=guard_reason(r,guard)
        if reason:rejections.append(dict(record_id=r['record_id'],source=r['source_dataset'],reason=reason));continue
        if r['human_decisions']:
            if r['human_label'] in SENTIMENT:dev.append(r)
            continue
        # Explicitly reopen dev-post records, but keep unverified Facebook identity out.
        if r['source_dataset']=='facebook':
            from src.data.quality import verified_post
            if not verified_post(r):rejections.append(dict(record_id=r['record_id'],source=r['source_dataset'],reason='UNVERIFIED_FACEBOOK_IDENTITY'));continue
        elif r['annotation_eligibility']!='ELIGIBLE_PROPOSED':
            rejections.append(dict(record_id=r['record_id'],source=r['source_dataset'],reason='LEGACY_OLD_ELIGIBILITY'));continue
        eligible.append(r)
    # Local duplicate guard against ALL development labels, without discarding dev posts.
    dev_all=[r for r in rows if r['human_label'] in SENTIMENT]
    dev_exact={normal(r['text_annotation_view']) for r in dev_all};dev_near=reference_index([fingerprints(r['text_annotation_view']) for r in dev_all])
    safe=[]
    for r in eligible:
        if normal(r['text_annotation_view']) in dev_exact or near_any(r['text_annotation_view'],dev_near):
            rejections.append(dict(record_id=r['record_id'],source=r['source_dataset'],reason='EXACT_NEAR_DEVELOPMENT'));continue
        safe.append(r)
    unlabeled=sample_unlabeled(safe);calibration=stratified(dev,150,lambda r:r['human_label'],random.Random(SEED+1))
    if len(unlabeled)!=450 or len(calibration)!=150:
        raise ValueError(f'Insufficient safe records: unlabeled={len(unlabeled)}, calibration={len(calibration)}; no quota relaxed')
    selected=unlabeled+calibration
    # Existing reservation guard remains authoritative; fail closed on corruption.
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text_annotation_view']) for r in selected], 'pseudo_labeling',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    calibration_ids={r['record_id'] for r in calibration};random.Random(SEED+2).shuffle(selected)
    inputs=[dict(record_id=r['record_id'],text=r['text_annotation_view']) for r in selected]
    meta=[dict(record_id=r['record_id'],source=r['source_dataset'],post_id=r['post_id'] if r['source_dataset']=='facebook' else None,
        movie_id=r.get('movie_id') if r['source_dataset']=='facebook' else None,text_sha256=digest(r['text_annotation_view'])) for r in selected]
    summary=dict(status='PREPARED_NO_EXTERNAL_CALLS',selected=600,unlabeled=450,calibration=150,
        unlabeled_sources=dict(Counter(r['source_dataset'] for r in unlabeled)),
        calibration_labels=dict(Counter(r['human_label'] for r in calibration)),calibration_safe_pool=len(dev),
        source_counts_before=dict(Counter(r['source_dataset'] for r in rows if r['annotation_eligibility']=='ELIGIBLE_PROPOSED' and not r['human_decisions'] and r['quality_decision']=='KEEP')),
        source_counts_after=dict(Counter(r['source_dataset'] for r in safe)),
        facebook_posts_before=len({r['post_id'] for r in rows if r['source_dataset']=='facebook' and r['annotation_eligibility']=='ELIGIBLE_PROPOSED' and not r['human_decisions']}),
        facebook_posts_after=len({r['post_id'] for r in safe if r['source_dataset']=='facebook'}),
        selected_post_counts=dict(Counter(r['post_id'] for r in unlabeled if r['source_dataset']=='facebook')),
        selected_movie_counts=dict(Counter(r['movie_id'] for r in unlabeled if r['source_dataset']=='facebook')),
        rejections=dict(Counter(r['reason'] for r in rejections)),quality_example_check=example_checks,
        silver_approved=False,external_approved=False,legacy_provenance='Unknown original source/overall labels; no movie/post inference or external-sharing authorization assumed')
    with staged(directory) as out:
        write_jsonl(out/'pilot_input.local.jsonl',inputs)
        save(out/'coordinator.local.json',dict(rows=meta,calibration_labels={r['record_id']:r['human_label'] for r in calibration},
            unlabeled_ids=[r['record_id'] for r in unlabeled],summary=summary))
        write_jsonl(out/'pool_rejections.local.jsonl',rejections)
        save(out/'pool_report.json',summary)
        save(out/'protection_fingerprints.local.json',dict(post_ids=sorted(guard['posts']),record_ids=sorted(guard['ids']),
            text_hashes=sorted(guard['text_hashes']),reference_fingerprint_count=len(guard['shingles']['sets']),source_sha256=guard['checksums']))
        save(out/'selection_manifest.json',dict(repository_root=str(root),seed=SEED,post_cap=12,movie_cap=36,rows=meta,
            dataset_manifest_sha256=sha(source/'manifest.json'),dataset_path=str(source),input_sha256=sha(out/'pilot_input.local.jsonl'),
            coordinator_sha256=sha(out/'coordinator.local.json'),guideline_version=GUIDELINE_VERSION,guideline_sha256=sha(GUIDELINE),
            calibration_never_silver=True,source_sha256=guard['checksums']))
        if snapshot(root,source)!=before:raise ValueError('Immutable input changed during preparation')
        save(out/'immutability.json',dict(verified=True,files=before))
        seal(out,dict(status='PILOT_PREPARED_MANUAL_WEB_HANDOFF'))
    return summary


def task(directory):
    directory=Path(directory);verify(directory);m=load(directory/'selection_manifest.json')
    if sha(directory/'pilot_input.local.jsonl')!=m['input_sha256'] or sha(directory/'coordinator.local.json')!=m['coordinator_sha256']:
        raise ValueError('Pilot IDs/text/private coordinator changed')
    if sha(GUIDELINE)!=m['guideline_sha256']:raise ValueError('Guideline changed')
    if any(sha(p)!=h for p,h in m['source_sha256'].items()):raise ValueError('Protected source fingerprint input changed')
    if m.get('dataset_path'):
        if sha(Path(m['dataset_path'])/'manifest.json')!=m['dataset_manifest_sha256']:raise ValueError('Source dataset changed')
        verify(Path(m['dataset_path']))
    items=read_jsonl(directory/'pilot_input.local.jsonl');c=load(directory/'coordinator.local.json')
    # Recheck the CURRENT registry so a later reservation also blocks sending.
    root=Path(m.get('repository_root',ROOT));texts={r['record_id']:r['text'] for r in items}
    assert_allowed([dict(r,id=r['record_id'],text_view=texts[r['record_id']]) for r in c['rows']], 'pseudo_labeling',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    return m,items,c


def classification(truth,pred):
    from sklearn.metrics import classification_report,accuracy_score,confusion_matrix
    labels=CATEGORIES+['ERROR','ABSTAIN']
    if not truth:
        return dict(n=0,accuracy=None,macro_f1=None,per_class={k:dict(precision=None,recall=None,**{'f1-score':None},support=0) for k in SENTIMENT},
                    truth_labels=SENTIMENT,prediction_labels=labels,confusion_matrix=[[0]*len(labels) for _ in SENTIMENT])
    r=classification_report(truth,pred,labels=SENTIMENT,output_dict=True,zero_division=0)
    return dict(n=len(truth),accuracy=float(accuracy_score(truth,pred)) if truth else None,
        macro_f1=r['macro avg']['f1-score'],per_class={k:r[k] for k in SENTIMENT},
        truth_labels=SENTIMENT,prediction_labels=labels,
        confusion_matrix=[[sum(a==t and b==p for a,b in zip(truth,pred)) for p in labels] for t in SENTIMENT])


def summarize(directory):
    directory=Path(directory);m,inputs,c=task(directory)
    from .web_labels import successes,provider_config,usage_summary
    cfg=provider_config()
    predictions=successes(directory,cfg);models=[p['model'] for p in cfg['providers']]
    lookup={r['record_id']:r for r in c['rows']};groups=Counter();cohorts=defaultdict(Counter);unanimous={};needs=[];silver=[]
    for r in inputs:
        rid=r['record_id'];values=[predictions.get((rid,model),{}).get('predicted_label') for model in models]
        if None in values:category='IMPORT_OR_SCHEMA_INCOMPLETE'
        else:category={1:'3_OF_3',2:'2_OF_3',3:'ALL_DIFFERENT'}[len(set(values))]
        groups[category]+=1
        cohorts['calibration' if rid in c['calibration_labels'] else 'unlabeled'][category]+=1
        if category=='3_OF_3':unanimous[rid]=values[0]
        if rid in c['calibration_labels']:continue
        entry=dict(record_id=rid,text_sha256=digest(r['text']),predictions=dict(zip(models,values)),source=lookup[rid]['source'],
                   movie_id=lookup[rid]['movie_id'],agreement=category,status='SILVER_CANDIDATE' if category=='3_OF_3' and values[0] in SENTIMENT else 'NEEDS_REVIEW',approved=False)
        (silver if entry['status']=='SILVER_CANDIDATE' else needs).append(entry)
    complete=sum(groups[k] for k in ['3_OF_3','2_OF_3','ALL_DIFFERENT'])
    pairwise={}
    from sklearn.metrics import cohen_kappa_score
    for i,a in enumerate(models):
        for b in models[i+1:]:
            pairs=[(predictions[(r['record_id'],a)]['predicted_label'],predictions[(r['record_id'],b)]['predicted_label']) for r in inputs if (r['record_id'],a) in predictions and (r['record_id'],b) in predictions]
            x,y=zip(*pairs) if pairs else ([],[])
            from sklearn.metrics import confusion_matrix
            k=float(cohen_kappa_score(x,y,labels=CATEGORIES)) if pairs and len(set(x)|set(y))>1 else None
            pairwise[a+' / '+b]=dict(n=len(pairs),agreement=sum(u==v for u,v in pairs)/len(pairs) if pairs else None,kappa=k,
                labels=CATEGORIES,confusion_matrix=confusion_matrix(x,y,labels=CATEGORIES).tolist() if pairs else [])
    fully=[[predictions[(r['record_id'],model)]['predicted_label'] for model in models] for r in inputs if all((r['record_id'],model) in predictions for model in models)]
    totals=Counter(v for row in fully for v in row);pe=sum((totals[k]/(3*len(fully)))**2 for k in CATEGORIES) if fully else 1
    pa=sum(sum(n*(n-1) for n in Counter(row).values())/6 for row in fully)/len(fully) if fully else None
    calibration={};ids=list(c['calibration_labels']);truth=[c['calibration_labels'][rid] for rid in ids]
    for model in models:calibration[model]=classification(truth,[predictions.get((rid,model),{}).get('predicted_label','ERROR') for rid in ids])
    agreed_ids=[rid for rid in ids if rid in unanimous]
    calibration['consensus_3_of_3']=dict(coverage=len(agreed_ids)/len(ids),unanimous_count=len(agreed_ids),
        all_150_with_abstentions=classification(truth,[unanimous.get(rid,'ABSTAIN') for rid in ids]),
        conditional=classification([c['calibration_labels'][rid] for rid in agreed_ids],[unanimous[rid] for rid in agreed_ids]))
    breakdown={}
    for field in ['source','movie_id']:
        values={r[field] for r in c['rows'] if r[field] is not None}
        breakdown[field]={str(v):dict(n=sum(r[field]==v for r in c['rows']),unanimous=sum(r[field]==v and r['record_id'] in unanimous for r in c['rows'])) for v in values}
    report=dict(records=len(inputs),complete_three=complete,counts=dict(groups),cohort_counts={k:dict(v) for k,v in cohorts.items()},rates_complete={k:groups[k]/complete if complete else None for k in ['3_OF_3','2_OF_3','ALL_DIFFERENT']},
        label_counts={model:dict(Counter(v['predicted_label'] for (rid,mo),v in predictions.items() if mo==model)) for model in models},
        pairwise=pairwise,fleiss_kappa=(pa-pe)/(1-pe) if pa is not None and pe<1 else None,
        calibration=calibration,breakdown=breakdown,usage=usage_summary(directory,cfg),silver_candidates=len(silver),needs_review=len(needs),approved=False,
        note='Five workflow categories for agreement; 3 sentiment classes for F1. Calibration is development, not gold. Consensus is not truth. Missing imports count as ERROR/ABSTAIN in all-150 metrics.')
    if not predictions:raise ValueError('No imported web predictions; no agreement/silver artifacts generated')
    write_jsonl(directory/'silver_candidates.local.jsonl',silver);write_jsonl(directory/'needs_review.local.jsonl',needs)
    write_jsonl(directory/'two_of_three.local.jsonl',[r for r in needs if r['agreement']=='2_OF_3'])
    calibration_table=[];confusion_table=[]
    for model in models:
        score=calibration[model]
        for label in SENTIMENT:calibration_table.append(dict(model=model,label=label,**score['per_class'][label],macro_f1=score['macro_f1'],accuracy=score['accuracy'],n=score['n']))
        for i,t in enumerate(SENTIMENT):
            for j,p in enumerate(score['prediction_labels']):confusion_table.append(dict(model=model,true_label=t,predicted_label=p,n=score['confusion_matrix'][i][j]))
    consensus=calibration['consensus_3_of_3']['all_150_with_abstentions']
    for label in SENTIMENT:calibration_table.append(dict(model='consensus_3_of_3_all150',label=label,**consensus['per_class'][label],macro_f1=consensus['macro_f1'],accuracy=consensus['accuracy'],n=consensus['n']))
    for i,t in enumerate(SENTIMENT):
        for j,p in enumerate(consensus['prediction_labels']):confusion_table.append(dict(model='consensus_3_of_3_all150',true_label=t,predicted_label=p,n=consensus['confusion_matrix'][i][j]))
    write_csv(directory/'calibration_metrics.csv',calibration_table,list(calibration_table[0]))
    write_csv(directory/'calibration_confusion.csv',confusion_table,['model','true_label','predicted_label','n'])
    same=[r for r in inputs if r['record_id'] in c['unlabeled_ids'] and r['record_id'] in unanimous]
    chosen=stratified(same,50,lambda r:(unanimous[r['record_id']],lookup[r['record_id']]['source']),random.Random(SEED+3))
    disagree=[r for r in inputs if r['record_id'] in c['unlabeled_ids'] and r['record_id'] not in unanimous and all((r['record_id'],mo) in predictions for mo in models)]
    random.Random(SEED+4).shuffle(disagree)
    def priority(r):
        values={predictions.get((r['record_id'],mo),{}).get('predicted_label') for mo in models}
        return 0 if {'POS','NEG'}<=values else 1 if values&set(SENTIMENT) and values&{'REVIEW','EXCLUDE'} else 2
    disagree.sort(key=priority);chosen+=disagree[:50];random.Random(SEED+5).shuffle(chosen)
    audit=[dict(id=r['record_id'],text=r['text'],text_sha256=digest(r['text'])) for r in chosen]
    report['audit_sampling_actual']=dict(unanimous=min(50,len(same)),disagreement=min(50,len(disagree)),selected=len(audit),
        missing_imports_not_treated_as_disagreement=True)
    save(directory/'agreement_report.json',report)
    if audit:
        save(directory/'audit_coordinator.local.json',dict(rows=audit,agreement_sha256=sha(directory/'agreement_report.json')))
        workbook(directory/'review_blind.xlsx',[dict(id=r['id'],text=r['text'],label='',note='') for r in audit])
    return report


def import_audit(directory):
    directory=Path(directory);_,_,c=task(directory);coord=load(directory/'audit_coordinator.local.json')
    if coord['agreement_sha256']!=sha(directory/'agreement_report.json'):raise ValueError('Audit source changed')
    decisions=_labels(directory/'review_blind.xlsx',coord['rows'])
    from .web_labels import successes,provider_config
    cfg=provider_config();predictions=successes(directory,cfg);result={}
    for p in cfg['providers']:
        ids=[rid for rid,r in decisions.items() if r['label'] in SENTIMENT]
        result[p['model']]=classification([decisions[rid]['label'] for rid in ids],[predictions.get((rid,p['model']),{}).get('predicted_label','ERROR') for rid in ids])
    report=load(directory/'agreement_report.json');models=[p['model'] for p in cfg['providers']]
    agreement=[]
    for rid,r in decisions.items():
        labels=[predictions.get((rid,mo),{}).get('predicted_label') for mo in models]
        if len(set(labels))==1 and labels[0] is not None:agreement.append(labels[0]==r['label'])
    write_jsonl(directory/'human_audit.local.jsonl',list(decisions.values()))
    save(directory/'human_audit_report.json',dict(models=result,n=len(decisions),unanimous_audited=len(agreement),
        unanimous_matches_human=sum(agreement)/len(agreement) if agreement else None,
        sampling='stratified 50 unanimous + prioritized up to 50 disagreements, not population estimate',
        limitation='Per-class support may be small or absent; descriptive metrics, not approval evidence by themselves',approved=False))
    return dict(audited=len(decisions),silver_approved=False)
