"""Focused normalization audit: new proposal field, unchanged annotation pointer."""
from collections import Counter,defaultdict
import random
import re
from .common import ROOT,load,read_jsonl,write_jsonl,write_csv,save,sha,verify,staged,seal,csv_rows
from .unified import protection,check_protection
from .phase_i import duplicate_groups
from .phase_i3 import held
from .format_workbook import validate as validate_format
from .phase_i4 import validate_domain_workbook
from src.preprocessing.final_normalization import normalize,TECHNICAL
from src.preprocessing.plain_text import TOKEN
from src.preprocessing.plain_text_v3 import shape,ALIASES3

FOCUS_PREFIXES=('HTML_','ABBREVIATION_','PUNCTUATION_','FUNCTION_WORD_','USER_CONFIRMED_')


def categories(row):
    rules={e['rule'] for e in row['normalization_events']};out=[]
    if rules&{'FUNCTION_WORD_SEGMENT_RECOVERY','USER_CONFIRMED_COMPOUND'}:out.append('UNDERSCORE')
    for prefix,label in [('HTML_','HTML'),('ABBREVIATION_','ABBREVIATION'),('PUNCTUATION_','PUNCTUATION')]:
        if any(rule.startswith(prefix) for rule in rules):out.append(label)
    return out


def build(config,output):
    cfg=load(config);root=ROOT/cfg['source'];verify(root);snapshot=protection(cfg['protect_paths'])
    rows=read_jsonl(root/'corpus.local.jsonl');accepted=set(load(ROOT/cfg['accepted_tokens']));abbreviations=load(ROOT/cfg['abbreviation_rules'])
    original={r['record_id']:(r['text_raw'],r['human_decisions'],r['text_annotation'],r['text_clean']) for r in rows}
    by_source=defaultdict(Counter);rule_counts=Counter();changes=[];resolved_old=0
    audit_patterns={
        'split_entity':re.compile(r'&\s+(?:quot|amp|lt|gt|apos|#\s*39)\s*;|&\s*amp\s*;\s*quot\s*;'),
        'valid_entity':re.compile(r'&(?:amp;)*(?:quot|amp|lt|gt|apos|#39);'),
        'common_abbreviation':re.compile(r'(?<!\w)(?:ko|khum|hok|đc|cx)(?!\w)'),
        'space_before_punctuation_surface_signal':re.compile(r'\s+[,.!?;:]')}
    origin={};top_patterns=Counter()
    for label,pattern in audit_patterns.items():
        origin[label]={source:dict(raw_rows=sum(bool(pattern.search(r['text_raw'])) for r in rows if r['source_dataset']==source),
            i3_rows=sum(bool(pattern.search(r['text_clean'])) for r in rows if r['source_dataset']==source)) for source in sorted({r['source_dataset'] for r in rows})}
        top_patterns.update((label,m[0]) for r in rows for m in pattern.finditer(r['text_raw']))
    unresolved_inventory=Counter(t for r in rows for t in r['unresolved_tokens'])
    if sum(unresolved_inventory.values())!=12264:raise ValueError('I.3 unresolved inventory changed')
    for row in rows:
        source=row['source_dataset'];old_unresolved=list(row['unresolved_tokens'])
        result=normalize(row['text_raw'],accepted,source,abbreviations,cfg['max_decode_passes'])
        again=normalize(result['text_normalized'],accepted,source,abbreviations,cfg['max_decode_passes'])
        if again['text_normalized']!=result['text_normalized']:raise ValueError('Unstable normalized text')
        row['text_clean_i3']=row['text_clean'];row.update(result)
        row['annotation_text_version']='plain_text_v3';row['annotation_approval_transferred']=False
        row['changed_vs_i3']=row['text_normalized']!=row['text_clean_i3'];row['change_categories']=categories(row)
        new_rules=[e for e in row['normalization_events'] if e['rule'].startswith(FOCUS_PREFIXES)]
        counts=Counter(e['rule'] for e in new_rules);rule_counts.update(counts);by_source[source].update(counts)
        by_source[source]['records']+=1;by_source[source]['changed_vs_i3']+=row['changed_vs_i3']
        converted=Counter(e['before'] for e in new_rules if e['rule'] in ('FUNCTION_WORD_SEGMENT_RECOVERY','USER_CONFIRMED_COMPOUND'))
        resolved_old+=sum((Counter(old_unresolved)&converted).values())
        row['meaning_risk_proposed']=bool(row['normalization_flags'] or any(e['rule'].startswith(('ABBREVIATION_','FUNCTION_WORD_','USER_CONFIRMED_','HTML_')) for e in new_rules))
        if row['changed_vs_i3']:changes.append({k:row[k] for k in ['record_id','text_raw','text_clean_i3','text_normalized','normalization_events','normalization_flags','change_categories']})
        for span in TECHNICAL.finditer(row['text_raw']):
            if span[0] not in row['text_normalized']:raise AssertionError('Protected span changed')
    views=[dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in rows]
    groups,exact,near=duplicate_groups(views,threshold=.9,min_chars=40,shingle_size=3,max_posting=256)
    old_near,_=csv_rows((root/'direct_near_duplicates.local.csv').read_bytes());old_edges={tuple(sorted((e['left'],e['right']))) for e in old_near}
    new_edges=[e for e in near['edges'] if tuple(sorted((e['left'],e['right']))) not in old_edges]
    old_by_new=defaultdict(set);human_labels=defaultdict(set)
    for r in rows:
        old_by_new[groups[r['record_id']]].add(r['duplicate_group_id'])
        if r['human_label']:human_labels[groups[r['record_id']]].add(r['human_label'])
    holdout_ids=set(load(ROOT/'outputs/phase_i4/v5/quality_holdout_reservation.local.json')['ids'])
    blocked={r['record_id'] for r in rows if held(r)}|holdout_ids
    blocked_groups={groups[i] for i in blocked};blocked_old_groups={r['duplicate_group_id'] for r in rows if r['record_id'] in blocked}
    blocked|={r['record_id'] for r in rows if groups[r['record_id']] in blocked_groups or r['duplicate_group_id'] in blocked_old_groups}
    initial_blocked=set(blocked)
    for edge in near['edges']+old_near:
        if edge['left'] in initial_blocked:blocked.add(edge['right'])
        elif edge['right'] in initial_blocked:blocked.add(edge['left'])
    rng=random.Random(cfg['seed']);safe=[r for r in sorted(rows,key=lambda r:r['record_id']) if r['record_id'] not in blocked];rng.shuffle(safe)
    changed=[r for r in safe if r['changed_vs_i3']];controls=[r for r in safe if not r['changed_vs_i3']]
    selected=[];ids=set();seen_groups=set()
    predicates=[lambda r,c=c:c in r['change_categories'] for c in ('UNDERSCORE','HTML','ABBREVIATION','PUNCTUATION')]
    predicates += [lambda r:r['source_dataset']=='facebook',lambda r:r['source_dataset']=='legacy_29k_unverified',lambda r:r['flags']['negation_present'],lambda r:len(r['text_normalized'])>1000,lambda r:len(r['change_categories'])>1]
    def add(row):
        rid=row['record_id'];group=groups[rid]
        if rid in ids or group in seen_groups or near['neighbors'].get(rid,set())&ids:return False
        selected.append(row);ids.add(rid);seen_groups.add(group);return True
    for predicate in predicates:
        for candidate in changed:
            if predicate(candidate) and add(candidate):break
    for r in controls:
        if sum(not x['changed_vs_i3'] for x in selected)>=10:break
        add(r)
    buckets=defaultdict(list)
    for r in changed:buckets[(r['source_dataset'],tuple(r['change_categories']))].append(r)
    while len(selected)<cfg['review_count']:
        progress=False
        for key in sorted(buckets):
            while buckets[key]:
                if add(buckets[key].pop()):progress=True;break
            if len(selected)==cfg['review_count']:break
        if not progress:break
    if len(selected)!=150:raise ValueError('Insufficient safe review rows')
    fmt=validate_format(ROOT/'outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx',ROOT/'outputs/phase_i3/validation_v1/workbook_input.local.json')
    dom,_=validate_domain_workbook(ROOT/'outputs/phase_i4/workbook_v2/semantic_quality_review_200.xlsx',ROOT/'outputs/phase_i4/v5/workbook_input.local.json')
    status=dict(normalization='PENDING_HUMAN_NORMALIZATION_APPROVAL',format='PENDING_HUMAN_FORMAT_APPROVAL',domain='PENDING_HUMAN_DOMAIN_REVIEW',
        old_format_decisions=dict(Counter(r['format_decision'] or 'BLANK' for r in fmt)),old_domain_decisions=dict(Counter(r['human_domain_decision'] or 'BLANK' for r in dom)),old_approval_transferred=False,annotation_pointer_updated=False)
    summary=dict(rows=len(rows),changed_vs_i3=len(changes),by_source={k:dict(v) for k,v in by_source.items()},rule_counts=dict(rule_counts),
        original_i3_unresolved=12264,additional_i3_underscore_occurrences_restored=resolved_old,
        remaining_unprotected_format_occurrences=sum(len(r['remaining_format_tokens']) for r in rows),
        remaining_unprotected_format_rows=sum(bool(r['remaining_format_tokens']) for r in rows),
        all_underscore_token_occurrences_after=sum(sum('_' in t for t in r['text_normalized'].split()) for r in rows),
        meaning_risk_proposed_rows=sum(r['meaning_risk_proposed'] for r in rows),
        proposed_human_review_rows=sum(bool(r['changed_vs_i3'] or r['normalization_flags'] or r['remaining_format_tokens']) for r in rows),
        new_exact_merge_groups=sum(len(v)>1 for v in old_by_new.values()),new_near_pair_ids=len(new_edges),duplicates=near['summary'],
        normalized_human_conflict_groups=sum(len(v)>1 for v in human_labels.values()),source_pattern_audit=origin,
        review_sources=dict(Counter(r['source_dataset'] for r in selected)),review_controls=sum(not r['changed_vs_i3'] for r in selected),
        status=status,raw_unchanged=True,human_decisions_unchanged=True,annotation_unchanged=True)
    if any((r['text_raw'],r['human_decisions'],r['text_annotation'],r['text_clean'])!=original[r['record_id']] for r in rows):raise AssertionError('Protected source fields changed')
    with staged(output) as out:
        write_jsonl(out/'corpus_proposals.local.jsonl',rows);write_jsonl(out/'before_after.local.jsonl',changes)
        save(out/'summary.json',summary);save(out/'approval_state.json',status);save(out/'workbook_input.local.json',selected)
        write_csv(out/'source_patterns.local.csv',[dict(category=k[0],pattern=k[1],occurrences=v) for k,v in top_patterns.most_common()],['category','pattern','occurrences'])
        write_csv(out/'i3_remaining_token_inventory.local.csv',[dict(token=t,occurrences=n,shape=shape(t),known_emoji_alias=t.strip(':') in ALIASES3) for t,n in unresolved_inventory.most_common()],['token','occurrences','shape','known_emoji_alias'])
        write_csv(out/'direct_near_normalized.local.csv',near['edges'],['left','right','method']);write_csv(out/'new_direct_near_normalized.local.csv',new_edges,['left','right','method'])
        save(out/'protected_inputs.local.json',snapshot);save(out/'config.json',cfg)
        save(out/'normalization_contract.local.json',dict(source_manifest_sha256=sha(root/'manifest.json'),config_sha256=sha(config),
            rule_table_sha256=sha(ROOT/cfg['abbreviation_rules']),implementation_sha256=sha(ROOT/'src/preprocessing/final_normalization.py'),
            build_sha256=sha(ROOT/'src/dataset/final_normalization_audit.py'),review_ids=[r['record_id'] for r in selected],review_seed=cfg['seed'],
            sampling='targeted category anchors + source/category round robin; 10 unchanged controls; not representative accuracy sample'))
        check_protection(snapshot);return seal(out,dict(status='PENDING_HUMAN_NORMALIZATION_APPROVAL',rows=len(rows),review_rows=150,annotation_pointer_updated=False))
