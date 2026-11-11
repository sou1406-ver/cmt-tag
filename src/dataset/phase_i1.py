"""Offline Phase I.1 proposals; no annotation release before human quality review."""
from collections import Counter,defaultdict
from pathlib import Path
import random
import re
from .common import ROOT,load,save,sha,verify,read_jsonl,write_jsonl,write_csv,staged,seal
from .unified import protection,check_protection
from .phase_i import duplicate_groups,percentile
from .blind import assert_allowed
from .repetition import repetition_signals
from .semantic_quality import assess
from src.preprocessing.emoji_aliases import normalize_aliases,VERSION


def balanced_audit(rows,count,seed):
    rng=random.Random(seed); buckets=defaultdict(list)
    for r in sorted(rows,key=lambda x:x['record_id']):
        key=(r['source_dataset'],r['quality_status'],r['repetition_status'],
             len(r['text_clean'])>1000,bool(r['alias_changes']) or r['bare_alias_signal'],r['domain_status'])
        buckets[key].append(r)
    keys=sorted(buckets);rng.shuffle(keys)
    for b in buckets.values():rng.shuffle(b)
    out=[]
    while len(out)<count:
        changed=False
        for k in keys:
            if buckets[k]:out.append(buckets[k].pop());changed=True
            if len(out)==count:break
        if not changed:break
    return out


def build(config,output):
    cfg=load(config);source=ROOT/cfg['source'];verify(source)
    snapshot=protection(cfg['protect_paths'])
    rows=read_jsonl(source/'unified_corpus.local.jsonl')
    master={r['id']:r for r in read_jsonl(ROOT/'outputs/phase_g/master/master.jsonl')}
    before_human={r['record_id']:r['human_decisions'] for r in rows}
    changes=[]; example_matches=Counter()
    for r in rows:
        if r['text_raw']!=master[r['record_id']]['text_raw']:raise ValueError('Raw source mismatch')
        old=r['text_clean'];text,events=normalize_aliases(old)
        r['phase_i_quality_status']=r['quality_status'];r['phase_i_pool_status']=r['annotation_pool_status']
        rep=repetition_signals(text);r.update(rep);r.update(assess(r,text,rep))
        r['text_clean']=text;r['text_annotation']=text;r['alias_changes']=events
        r['preprocessing_version']=cfg['version'];r['annotation_eligibility']=bool(
            r['annotation_eligibility'] and r['phase_i_pool_status']=='ELIGIBLE' and not r['human_decisions'] and not r['test_reserved'])
        if events:changes.append(dict(id=r['record_id'],text_raw=r['text_raw'],text_before=old,text_clean=text,events=events))
        if ':rolling_on_the_floor_laughing:' in old:example_matches['laughing_alias_rows']+=1
        if 'saqar' in old.casefold():
            example_matches['user_example_term_rows']+=1
            example_matches['user_example_term_repetition_detected']+=int(rep['repetition_risk'])
    groups,exact,near=duplicate_groups(rows,**cfg['near_duplicate'])
    human_groups={groups[r['record_id']] for r in rows if r['human_decisions']}
    human_ids={r['record_id'] for r in rows if r['human_decisions']}
    pool=[]
    for r in rows:
        rid=r['record_id'];r['duplicate_group_id']=groups[rid]
        if rid in exact or groups[rid] in human_groups or near['neighbors'].get(rid,set()) & human_ids:r['annotation_eligibility']=False
        if r['annotation_eligibility']:pool.append(r)
    rng=random.Random(cfg['seed']);ordered=sorted(pool,key=lambda r:r['record_id']);rng.shuffle(ordered)
    selected=[];ids=set()
    for r in ordered:
        if near['neighbors'].get(r['record_id'],set()) & ids:continue
        selected.append(r);ids.add(r['record_id'])
        if len(selected)==cfg['pilot_count']:break
    # Preserve existing fail-closed guards, including whole-master test components.
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in selected],'pseudo_labeling')
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in pool],'pseudo_labeling')
    audit=balanced_audit(rows,cfg['audit_count'],cfg['seed']+1)
    audit_rows=[dict(id=r['record_id'],text_raw=r['text_raw'],text_clean=r['text_clean'],
        proposed_quality_status=r['quality_status'],proposed_reason=';'.join(r['quality_reason_code']),human_quality_decision='') for r in audit]
    summary={}
    for source_name in sorted({r['source_dataset'] for r in rows}):
        subset=[r for r in rows if r['source_dataset']==source_name];lengths=sorted(len(r['text_clean']) for r in subset)
        summary[source_name]=dict(rows=len(subset),quality=dict(Counter(r['quality_status'] for r in subset)),
            domain=dict(Counter(r['domain_status'] for r in subset)),
            repetition_risk=sum(r['repetition_risk'] for r in subset),exclude_candidates=sum(r['repetition_status']=='EXCLUDE_CANDIDATE' for r in subset),
            technically_valid=sum(bool(r['text_clean']) and '\ufffd' not in r['text_clean'] for r in subset),
            mixed_script_signal=sum(r['multiple_script_signal'] for r in subset),
            alias_rows=sum(bool(r['alias_changes']) for r in subset),alias_replacements=sum(len(r['alias_changes']) for r in subset),
            teencode_preserved=sum(r['teencode_preserved'] for r in subset),
            lengths=dict(median=percentile(lengths,.5),p90=percentile(lengths,.9),p95=percentile(lengths,.95),p99=percentile(lengths,.99),
                **{f'over_{n}':sum(x>n for x in lengths) for n in (256,512,1000,2000)}))
    totals=dict(rows=len(rows),quality=dict(Counter(r['quality_status'] for r in rows)),
        domain=dict(Counter(r['domain_status'] for r in rows)),repetition_risk=sum(r['repetition_risk'] for r in rows),
        exclude_candidates=sum(r['repetition_status']=='EXCLUDE_CANDIDATE' for r in rows),
        alias_rows=len(changes),alias_replacements=sum(len(r['alias_changes']) for r in rows),
        bare_alias_rows=sum(r['bare_alias_signal'] for r in rows),
        teencode_replacements=0,teencode_preserved=sum(r['teencode_preserved'] for r in rows),
        long_review=sum(len(r['text_clean'])>1000 and r['quality_status']=='REVIEW' for r in rows),
        pool=len(pool),pilot=len(selected),audit=len(audit),by_source=summary,example_diagnostics=dict(example_matches),
        duplicates=near['summary'],status='PENDING_HUMAN_QUALITY_APPROVAL',
        verified_domain_labels=0,filter_precision_recall=None,
        audit_strata=dict(Counter(r['source_dataset']+'|'+r['quality_status']+'|'+r['repetition_status'] for r in audit)),
        pilot_sources=dict(Counter(r['source_dataset'] for r in selected)))
    if any(r['human_decisions']!=before_human[r['record_id']] for r in rows):raise AssertionError('Human decisions changed')
    with staged(output) as work:
        write_jsonl(work/'corpus.local.jsonl',rows)
        write_csv(work/'quality_review_200.csv',audit_rows,['id','text_raw','text_clean','proposed_quality_status','proposed_reason','human_quality_decision'])
        write_csv(work/'pilot_500_candidate.csv',[dict(id=r['record_id'],text_annotation=r['text_annotation']) for r in selected],['id','text_annotation'])
        write_jsonl(work/'annotation_pool.local.jsonl',pool)
        write_jsonl(work/'quality_review_coordinator.local.jsonl',audit)
        write_jsonl(work/'alias_before_after.local.jsonl',changes)
        write_jsonl(work/'quality_evidence.local.jsonl',[{k:r[k] for k in ('record_id','quality_status','quality_reason_code','domain_status','domain_evidence',
            'repetition_ratio','longest_repeated_span_tokens','repeated_block_count','repetition_status','compression_ratio','unique_token_ratio','script_counts','underscore_signals')} for r in rows])
        save(work/'summary.json',totals);save(work/'protected_inputs.local.json',snapshot)
        save(work/'selection_manifest.local.json',dict(seed=cfg['seed'],status=totals['status'],selected_ids=sorted(ids),
            audit_ids=[r['record_id'] for r in audit],method='seeded shuffle of eligible pool; no fixed source quotas',
            pilot_ready=False,source_sha256=sha(source/'manifest.json'),config_sha256=sha(config),
            alias_version=VERSION,implementation_sha256={p:sha(ROOT/p) for p in cfg['implementation_paths']}))
        check_protection(snapshot)
        seal(work,dict(phase='I.1',status=totals['status'],rows=len(rows),pilot=len(selected),audit=len(audit)))
    return totals
