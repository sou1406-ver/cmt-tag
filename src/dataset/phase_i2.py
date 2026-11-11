"""Immutable raw-derived plain-text corpus and pending quality workbook inputs."""
from collections import Counter,defaultdict
import random
from .common import ROOT,load,read_jsonl,write_jsonl,write_csv,save,staged,seal,verify,sha,csv_rows
from .unified import protection,check_protection
from .phase_i import duplicate_groups
from .phase_i1 import balanced_audit
from .semantic_quality import assess
from .repetition import repetition_signals
from .blind import assert_allowed
from src.preprocessing.plain_text import preprocess


def build(config,output):
    cfg=load(config);source=ROOT/cfg['source'];verify(source)
    protected=protection(cfg['protect_paths'])
    rows=read_jsonl(source/'unified_corpus.local.jsonl')
    old_raw={r['record_id']:r['text_raw'] for r in rows}
    old_human={r['record_id']:r['human_decisions'] for r in rows}
    old_groups={r['record_id']:r['duplicate_group_id'] for r in rows}
    counts=Counter();examples=[]
    for r in rows:
        r['previous_pool_eligible']=r['annotation_pool_status']=='ELIGIBLE'
        result=preprocess(r['text_raw']);r.update(result)
        r['alias_changes']=[e for e in result['transform_events'] if e['rule']=='VERIFIED_EMOJI_ALIAS']
        counts.update(result['underscore_audit'])
        rep=repetition_signals(r['text_clean']);r.update(rep);r.update(assess(r,r['text_clean'],rep))
        if r['unresolved_tokens']:
            r['quality_status']='REVIEW';r['quality_reason_code'].append('UNRESOLVED_TOKEN_FORMAT')
        r['annotation_eligibility']=bool(r['quality_status']=='KEEP' and r['previous_pool_eligible'] and not r['human_decisions'] and not r['test_reserved'])
        if r['transform_events']:examples.append({k:r[k] for k in ('record_id','text_raw','text_clean','transform_events')})
    groups,exact,near=duplicate_groups(rows,**cfg['near_duplicate'])
    old_near_rows,_=csv_rows((source/'direct_near_duplicates.local.csv').read_bytes())
    old_near={tuple(sorted((r['left'],r['right']))) for r in old_near_rows}
    new_near=[e for e in near['edges'] if tuple(sorted((e['left'],e['right']))) not in old_near]
    human_ids={r['record_id'] for r in rows if r['human_decisions']};human_groups={groups[i] for i in human_ids}
    reserved_ids={r['record_id'] for r in rows if r['test_reserved'] or 'TEST_SOURCE_POST_PROTECTED' in r.get('annotation_pool_reasons',[])}
    protected_groups=human_groups|{groups[i] for i in reserved_ids}
    protected_ids={r['record_id'] for r in rows if groups[r['record_id']] in protected_groups}
    pool=[];new_pairs=0;old_by_new=defaultdict(set)
    for r in rows:old_by_new[groups[r['record_id']]].add(old_groups[r['record_id']])
    new_exact_groups=sum(len(g)>1 for g in old_by_new.values())
    for r in rows:
        rid=r['record_id'];r['duplicate_group_id']=groups[rid]
        if rid in exact or groups[rid] in protected_groups or near['neighbors'].get(rid,set()) & protected_ids:r['annotation_eligibility']=False
        if r['annotation_eligibility']:pool.append(r)
    rng=random.Random(cfg['seed']);shuffled=sorted(pool,key=lambda r:r['record_id']);rng.shuffle(shuffled)
    chosen=[];ids=set()
    for r in shuffled:
        if near['neighbors'].get(r['record_id'],set()) & ids:continue
        chosen.append(r);ids.add(r['record_id'])
        if len(chosen)==cfg['pilot_count']:break
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in pool],'pseudo_labeling')
    # All-format strata extend I.1 review sampling without using sentiment labels.
    buckets=defaultdict(list)
    for r in rows:
        key=(r['source_dataset'],bool(r['underscore_audit']),bool(r['alias_changes']),bool(r['transform_events']),
             len(r['text_clean'])>1000,r['repetition_risk'],r['domain_status'],r['flags']['negation_present'])
        buckets[key].append(r)
    keys=list(sorted(buckets));rng.shuffle(keys)
    for b in buckets.values():rng.shuffle(b)
    audit=[]
    while len(audit)<cfg['audit_count']:
        added=False
        for k in keys:
            if buckets[k]:audit.append(buckets[k].pop());added=True
            if len(audit)==cfg['audit_count']:break
        if not added:break
    if len(audit)!=200:raise ValueError('Expected 200 quality audit rows')
    if any(r['text_raw']!=old_raw[r['record_id']] or r['human_decisions']!=old_human[r['record_id']] for r in rows):raise AssertionError('Protected data changed')
    summary=dict(rows=len(rows),quality=dict(Counter(r['quality_status'] for r in rows)),domain=dict(Counter(r['domain_status'] for r in rows)),
        token_categories=dict(counts),changed_rows=len(examples),alias_replacements=sum(len(r['alias_changes']) for r in rows),
        compound_replacements=sum(e['rule']=='REVIEWED_COMPOUND_RESTORATION' for r in rows for e in r['transform_events']),
        unresolved_rows=sum(bool(r['unresolved_tokens']) for r in rows),unresolved_occurrences=sum(len(r['unresolved_tokens']) for r in rows),
        repetition_risk=sum(r['repetition_risk'] for r in rows),duplicates=near['summary'],new_exact_merge_groups=new_exact_groups,new_direct_near_pair_ids=len(new_near),
        pool=len(pool),pilot=len(chosen),audit=len(audit),pilot_sources=dict(Counter(r['source_dataset'] for r in chosen)),
        status='PENDING_HUMAN_QUALITY_APPROVAL',raw_unchanged=True,human_decisions_unchanged=True,
        audit_strata=dict(Counter(r['source_dataset']+'|'+r['quality_status'] for r in audit)))
    with staged(output) as work:
        write_jsonl(work/'corpus.local.jsonl',rows);write_jsonl(work/'annotation_pool.local.jsonl',pool)
        write_jsonl(work/'transforms.local.jsonl',examples);write_jsonl(work/'review_coordinator.local.jsonl',audit)
        write_csv(work/'direct_near_duplicates.local.csv',near['edges'],['left','right','method'])
        write_csv(work/'new_direct_near_pairs.local.csv',new_near,['left','right','method'])
        save(work/'workbook_input.local.json',audit)
        write_csv(work/'pilot_500_candidate.csv',[dict(id=r['record_id'],text_annotation=r['text_annotation']) for r in chosen],['id','text_annotation'])
        save(work/'summary.json',summary);save(work/'protected_inputs.local.json',protected)
        save(work/'selection_manifest.local.json',dict(status=summary['status'],seed=cfg['seed'],selected_ids=sorted(ids),audit_ids=[r['record_id'] for r in audit],
            pilot_ready=False,config_sha256=sha(config),implementation_sha256={p:sha(ROOT/p) for p in cfg['implementation_paths']}))
        check_protection(protected);seal(work,dict(phase='I.2',status=summary['status'],rows=len(rows),pilot=len(chosen),audit=len(audit)))
    return summary


def release_inputs(pilot_path,approval_path,output):
    """Future release requires explicit approval tied to exact candidate bytes."""
    from .common import csv_rows
    approval=load(approval_path)
    if approval.get('approved') is not True or not approval.get('reviewer') or approval.get('pilot_sha256')!=sha(pilot_path):
        raise ValueError('Explicit human quality approval of this exact pilot is required')
    rows,fields=csv_rows(pilot_path.read_bytes())
    if fields!=['id','text_annotation'] or len({r['id'] for r in rows})!=len(rows):raise ValueError('Invalid blind pilot')
    with staged(output) as work:
        for provider in ('codex','claude','gemini'):write_csv(work/f'{provider}_input.csv',rows,fields)
        seal(work,dict(status='HUMAN_APPROVED_INPUT_EXPORT',guideline_sha256=sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md'),approval_sha256=sha(approval_path)))
