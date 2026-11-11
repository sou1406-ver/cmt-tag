"""Source evidence audit, independent format status and protected source sampling."""
from collections import Counter,defaultdict
import random
import re
from importlib.metadata import version
from pathlib import Path
from .common import ROOT,load,read_jsonl,write_jsonl,write_csv,save,staged,seal,verify,sha,csv_rows
from .unified import protection,check_protection
from .phase_i import duplicate_groups,percentile
from .semantic_quality import assess
from .repetition import repetition_signals
from .blind import assert_allowed
from src.preprocessing.plain_text_v3 import preprocess,shape


def held(row):
    return row['test_reserved'] or 'TEST_SOURCE_POST_PROTECTED' in row.get('annotation_pool_reasons',[])


def source_sample(pool,neighbors,target,seed,facebook_target):
    rng=random.Random(seed);by_post=defaultdict(list);legacy=[]
    for row in sorted(pool,key=lambda r:r['record_id']):
        if row['source_dataset']=='facebook':by_post[row.get('post_id') or 'unknown'].append(row)
        else:legacy.append(row)
    posts=sorted(by_post);rng.shuffle(posts)
    for values in by_post.values():rng.shuffle(values)
    rng.shuffle(legacy);selected=[];ids=set()
    def add(r):
        if neighbors.get(r['record_id'],set()) & ids:return False
        selected.append(r);ids.add(r['record_id']);return True
    while len(selected)<min(target,facebook_target):
        changed=False
        for post in posts:
            if by_post[post]:changed=add(by_post[post].pop()) or changed
            if len(selected)>=min(target,facebook_target):break
        if not any(by_post.values()):break
    for row in legacy:
        if len(selected)>=target:break
        add(row)
    # If legacy cannot fill target, use remaining valid Facebook without relaxing guards.
    for post in posts:
        for row in by_post[post]:
            if len(selected)>=target:break
            add(row)
    return selected


def funnel(rows):
    flags=['human','same_development_post','test_protection','exact_duplicate','direct_near_duplicate','quality_review','format_unresolved','unverified_facebook_identity','other_guard']
    independent={k:sum(k in r['eligibility_reasons'] for r in rows) for k in flags}
    remaining=list(rows);steps=[]
    for flag in flags:
        before=len(remaining);remaining=[r for r in remaining if flag not in r['eligibility_reasons']]
        steps.append(dict(rule=flag,newly_removed=before-len(remaining),remaining=len(remaining)))
    return dict(total=len(rows),nonexclusive=independent,sequential=steps,eligible=len(remaining),
        pairwise_overlap={a:{b:sum(a in r['eligibility_reasons'] and b in r['eligibility_reasons'] for r in rows) for b in flags} for a in flags})


def build(config,output):
    cfg=load(config);parent=ROOT/cfg['source'];verify(parent);protected=protection(cfg['protect_paths'])
    rows=read_jsonl(parent/'corpus.local.jsonl');counts=Counter(t for r in rows for t in r['unresolved_tokens'])
    if sum(counts.values())!=38833:raise ValueError('I.2 unresolved audit contract changed')
    safe_tokens={t for r in rows if not held(r) for t in r['unresolved_tokens']}
    if version('underthesea')!=cfg['model_version']:raise ValueError('Pinned offline segmenter required')
    import underthesea
    from underthesea import word_tokenize
    accepted=set();roundtrip={}
    for token in sorted(safe_tokens):
        if shape(token)=='ROUNDTRIP_CANDIDATE':
            predicted=word_tokenize(token.replace('_',' '),format='text')
            roundtrip[token]=predicted==token
            if predicted==token:accepted.add(token)
    model_root=Path(underthesea.__file__).parent/'pipeline/word_tokenize/models'
    model_hashes={str(p.relative_to(model_root)):sha(p) for p in sorted(model_root.rglob('*')) if p.is_file()}
    if not model_hashes:raise ValueError('Packaged offline segmentation model missing')
    original={r['record_id']:dict(raw=r['text_raw'],human=r['human_decisions'],clean=r['text_clean'],quality=r['quality_status'],
        reasons=list(r['quality_reason_code']),unresolved=list(r['unresolved_tokens']),group=r['duplicate_group_id']) for r in rows}
    format_counts=Counter();resolved_old=0;format_cleared=0;format_only_to_keep=0
    comparisons=[]
    for row in rows:
        old=original[row['record_id']];source_sha=next((o.get('input_sha256','') for o in row.get('metadata_provenance',[]) if o.get('source_file')==row['source_file']),'')
        result=preprocess(row['text_raw'],accepted,row['source_file'],source_sha,cfg['verified_sources']);row.update(result)
        row['text_clean_i2']=old['clean'];row['text_clean_i3']=row['text_clean']
        rep=repetition_signals(row['text_clean']);row.update(rep);row.update(assess(row,row['text_clean'],rep))
        row['technical_quality_status']='EXCLUDE' if not row['text_clean'] else 'REVIEW' if '\ufffd' in row['text_clean'] else 'KEEP'
        row['format_reason_code']=['UNRESOLVED_TOKEN_FORMAT'] if row['unresolved_tokens'] else []
        row['alias_changes']=[e for e in row['transform_events'] if e['rule'] in ('VERIFIED_EMOJI_ALIAS','CLDR_ALIAS_V3')]
        format_counts.update(e['confidence_category'] for e in row['format_evidence'])
        restored={e['source_token'] for e in row['format_evidence'] if e['confidence_category'].startswith('RESTORED_')}
        resolved_old+=sum(t in restored for t in old['unresolved'])
        format_cleared+=bool(old['unresolved']) and not row['unresolved_tokens']
        format_only_to_keep+=old['reasons']==['UNRESOLVED_TOKEN_FORMAT'] and row['quality_status']=='KEEP' and not row['unresolved_tokens']
        comparisons.append(dict(id=row['record_id'],text_raw=row['text_raw'],text_clean_i2=old['clean'],text_clean_i3=row['text_clean'],transform_events=row['transform_events']))
    groups,exact,near=duplicate_groups(rows,**cfg['near_duplicate'])
    protect_ids={r['record_id'] for r in rows if r['human_decisions'] or held(r)};protect_groups={groups[i] for i in protect_ids}
    protect_ids|={r['record_id'] for r in rows if groups[r['record_id']] in protect_groups}
    for r in rows:
        rid=r['record_id'];prior=set(r.get('annotation_pool_reasons',[]));reason=[]
        if r['human_decisions']:reason.append('human')
        if 'DEVELOPMENT_POST_HELD_OUT' in prior:reason.append('same_development_post')
        if held(r):reason.append('test_protection')
        if rid in exact or 'EXACT_DUPLICATE' in prior:reason.append('exact_duplicate')
        if near['neighbors'].get(rid,set()) & protect_ids or 'DIRECT_NEAR_DUPLICATE_OF_HUMAN_ROW' in prior:reason.append('direct_near_duplicate')
        if r['quality_status']!='KEEP':reason.append('quality_review')
        if r['format_status']=='NEEDS_REVIEW':reason.append('format_unresolved')
        if r['source_dataset']=='facebook' and not all(r.get(k) for k in ('comment_id','post_id','post_url')):reason.append('unverified_facebook_identity')
        if ('MASTER_IDENTITY_REVIEW_FLAG' in prior or (groups[rid] in protect_groups and rid not in protect_ids)):reason.append('other_guard')
        # Protected exact matches cannot enter even when the representative differs.
        if groups[rid] in protect_groups and not (r['human_decisions'] or held(r)):reason.append('other_guard')
        r['eligibility_reasons']=sorted(set(reason));r['annotation_eligibility']=not reason;r['duplicate_group_id']=groups[rid]
    pool=[r for r in rows if r['annotation_eligibility']]
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in pool],'pseudo_labeling')
    selected=source_sample(pool,near['neighbors'],cfg['pilot_count'],cfg['seed'],cfg['facebook_target'])
    fb=funnel([r for r in rows if r['source_dataset']=='facebook']);fb['selected_i2']=17;fb['selected_i3']=sum(r['source_dataset']=='facebook' for r in selected)
    # Stratified format validation, intentionally excluding protected test sources.
    rng=random.Random(cfg['seed']+1);buckets=defaultdict(list)
    for r in rows:
        if held(r):continue
        previous=original[r['record_id']]['unresolved'];freq=max((counts[t] for t in previous),default=0)
        key=(r['source_dataset'],'common' if freq>=20 else 'rare' if previous else 'none',any(t.count('_')>=2 for t in previous),
             r['format_status'],bool(r['alias_changes']),r['text_clean']!=r['text_clean_i2'],len(r['text_clean'])>1000,r['flags']['negation_present'])
        buckets[key].append(r)
    keys=sorted(buckets);rng.shuffle(keys)
    for b in buckets.values():rng.shuffle(b)
    audit=[]
    while len(audit)<200:
        changed=False
        for k in keys:
            if buckets[k]:audit.append(buckets[k].pop());changed=True
            if len(audit)==200:break
        if not changed:break
    def profile(values):
        lengths=sorted(len(r['text_clean']) for r in values)
        return dict(rows=len(values),sources=dict(Counter(r['source_dataset'] for r in values)),median=percentile(lengths,.5),p90=percentile(lengths,.9),
            emoji_rows=sum(r['flags']['emoji_present'] for r in values),teencode_rows=sum(r['flags']['teencode_present'] for r in values),negation_rows=sum(r['flags']['negation_present'] for r in values),
            facebook_posts=len({r['post_id'] for r in values if r['source_dataset']=='facebook' and r['post_id']}),
            facebook_without_post_id=sum(r['source_dataset']=='facebook' and not r['post_id'] for r in values))
    token_audit=[]
    source_counts=defaultdict(Counter)
    for r in rows:
        for t in original[r['record_id']]['unresolved']:source_counts[t][r['source_dataset']]+=1
    for token,n in counts.most_common():token_audit.append(dict(token=token,occurrences=n,characters=len(token),parts=len(token.split('_')),
        source_counts=dict(source_counts[token]),shape=shape(token),local_roundtrip=roundtrip.get(token),accepted=token in accepted))
    old_near,_=csv_rows((parent/'direct_near_duplicates.local.csv').read_bytes());old_edges={tuple(sorted((e['left'],e['right']))) for e in old_near}
    new_edges=[e for e in near['edges'] if tuple(sorted((e['left'],e['right']))) not in old_edges]
    new_groups=defaultdict(set)
    for r in rows:new_groups[groups[r['record_id']]].add(original[r['record_id']]['group'])
    totals=dict(rows=len(rows),unresolved_i2_occurrences=sum(counts.values()),unresolved_i2_unique=len(counts),
        unresolved_by_source=dict(Counter(r['source_dataset'] for r in rows for t in original[r['record_id']]['unresolved'])),
        resolved_i2_occurrences=resolved_old,remaining_i2_occurrences=sum(counts.values())-resolved_old,
        unresolved_i3_occurrences=sum(len(r['unresolved_tokens']) for r in rows),unresolved_i3_rows=sum(bool(r['unresolved_tokens']) for r in rows),
        format_cleared_rows=format_cleared,format_only_review_to_keep=format_only_to_keep,
        i2_format_only_review=sum(v['reasons']==['UNRESOLVED_TOKEN_FORMAT'] for v in original.values()),
        changed_vs_i2=sum(r['text_clean']!=r['text_clean_i2'] for r in rows),confidence_categories=dict(format_counts),
        quality=dict(Counter(r['quality_status'] for r in rows)),format=dict(Counter(r['format_status'] for r in rows)),
        source_segmentation_verified=False,accepted_resource_tokens=len(accepted),pool=profile(pool),pilot=profile(selected),
        duplicate_summary=near['summary'],new_exact_merge_groups=sum(len(v)>1 for v in new_groups.values()),new_near_pair_ids=len(new_edges),
        validation_rows=len(audit),status='PENDING_HUMAN_FORMAT_APPROVAL',human_accuracy=None)
    with staged(output) as work:
        write_jsonl(work/'corpus.local.jsonl',rows);write_jsonl(work/'comparisons.local.jsonl',comparisons)
        write_csv(work/'token_frequency.local.csv',token_audit,['token','occurrences','characters','parts','source_counts','shape','local_roundtrip','accepted'])
        write_jsonl(work/'top_200_tokens.local.jsonl',token_audit[:200]);save(work/'accepted_tokens.local.json',sorted(accepted))
        save(work/'source_preprocessing_provenance.json',dict(verified_sources=cfg['verified_sources'],conclusion='UNKNOWN_ORIGINAL_SEGMENTER; mixed underscore format observed, no source attestation',
            evidence_documents=['docs/PHASE_G2_LEGACY_AUDIT.md','configs/data_legacy.json'],underthesea_version=version('underthesea'),model_sha256=model_hashes,
            resource_built_from_non_test_records_only=True))
        save(work/'facebook_funnel.json',fb);save(work/'summary.json',totals)
        write_csv(work/'direct_near_duplicates.local.csv',near['edges'],['left','right','method']);write_csv(work/'new_direct_near_pairs.local.csv',new_edges,['left','right','method'])
        write_csv(work/'pilot_500_candidate.csv',[dict(id=r['record_id'],text_annotation=r['text_clean']) for r in selected],['id','text_annotation'])
        save(work/'workbook_input.local.json',audit);write_jsonl(work/'annotation_pool.local.jsonl',pool)
        save(work/'selection_manifest.local.json',dict(seed=cfg['seed'],facebook_target=cfg['facebook_target'],selected_ids=[r['record_id'] for r in selected],
            audit_ids=[r['record_id'] for r in audit],status=totals['status'],config_sha256=sha(config),pilot_ready=False,
            code_sha256={p:sha(ROOT/p) for p in ['src/dataset/phase_i3.py','src/preprocessing/plain_text_v3.py','src/preprocessing/plain_text.py']}))
        save(work/'protected_inputs.local.json',protected)
        if any(r['text_raw']!=original[r['record_id']]['raw'] or r['human_decisions']!=original[r['record_id']]['human'] for r in rows):raise AssertionError('Raw/human changed')
        check_protection(protected);seal(work,dict(phase='I.3',status=totals['status'],rows=len(rows),pilot=len(selected),audit=len(audit)))
    return totals
