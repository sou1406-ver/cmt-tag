"""Inventory local sources and reconcile observations without inventing identity."""
from collections import Counter, defaultdict
import io
import json
import os
import re
from pathlib import Path
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import zipfile

from .common import ROOT, csv_rows, digest, load, save, seal, sha, staged, write_csv, write_jsonl
from src.crawler.parser import facebook_url, post_id as url_post_id
from src.data.quality import near_duplicate_candidates
from src.data.split import UnionFind

TEXT_KEYS = ('text_raw', 'text', 'comment', 'body')
META = ('comment_id', 'post_id', 'post_url', 'parent_comment_id', 'movie_id', 'collected_at')
SKIP = {'.git', 'node_modules', '__pycache__', 'selenium_cache', '.playwright-browsers', '.agents', '.codex', '.aws'}


def canonical_sources(records,manifest,legacy_path,legacy_sha):
    """Resolve original payloads through pinned observation identity, never clean views."""
    cache={};index=[]
    def source(name):
        if name in cache:return cache[name]
        archive,separator,member=name.partition('!');path=(ROOT/archive).resolve()
        if not path.is_relative_to(ROOT) and path!=legacy_path.resolve():raise ValueError('Unapproved source path outside repository')
        expected=manifest['input_sha256'].get(str(path))
        if not expected or sha(path)!=expected:raise ValueError('Original source/container checksum mismatch')
        if separator:
            with zipfile.ZipFile(path) as z:payload=z.read(member)
            suffix=Path(member).suffix.lower()
        else:payload=path.read_bytes();suffix=path.suffix.lower()
        checksum=digest(payload);rows,fields=read_payload(payload,suffix)
        if not any(k in fields for k in TEXT_KEYS):raise ValueError('Original source has no literal text column')
        cache[name]=(rows,fields,checksum)
        index.append(dict(source_file=name,absolute_path=str(path),archive_member=member,source_sha256=checksum,container_sha256=expected,rows=len(rows),fields=fields,encoding='UTF-8 with optional BOM'))
        return cache[name]
    result=[];mapping=[];observations=0
    for item in records:
        for obs in item['observations']:
            rows,fields,checksum=source(obs['source_file']);n=obs['source_row']
            if checksum!=obs['input_sha256'] or not isinstance(n,int) or not 1<=n<=len(rows):raise ValueError('Observation source identity changed')
            key=next(k for k in TEXT_KEYS if k in fields)
            if rows[n-1][key]!=obs['text_raw']:raise ValueError('Observation raw text mismatch')
            observations+=1
        rows,fields,checksum=source(item['source_file']);n=item['source_row'];actual=rows[n-1]
        key=next(k for k in TEXT_KEYS if k in fields);raw=actual[key]
        if raw!=item['text_raw']:raise ValueError('Selected original raw does not match master identity')
        if not any(o['source_file']==item['source_file'] and o['source_row']==n and o['input_sha256']==checksum for o in item['observations']):raise ValueError('Selected source lacks observation evidence')
        legacy=(ROOT/item['source_file']).resolve()==legacy_path.resolve() if '!' not in item['source_file'] else False
        if legacy and checksum!=legacy_sha:raise ValueError('Legacy source differs from approved original')
        original_id=str(actual.get('id','')) if legacy else str(actual.get('internal_record_id') or actual.get('comment_id') or '')
        r=dict(record_id=item['id'],original_id=original_id,source_dataset='legacy_29k_unverified' if legacy else 'facebook' if item['source_platform']=='facebook' else 'unknown_source',
            source_file=item['source_file'],source_row=n,source_sha256=checksum,text_raw=raw,raw_sha256=digest(raw),
            platform=item['source_platform'],source_platform=item['source_platform'],master_group_id=item['group_id'],
            movie_id=item['movie_id'],post_id=item['post_id'],post_url=item['post_url'],comment_id=item['comment_id'],parent_comment_id=item['parent_comment_id'],
            original_metadata={k:v for k,v in actual.items() if k not in TEXT_KEYS},legacy_overall=actual.get('overall','') if legacy else '',legacy_overall_status='UNVERIFIED' if legacy else '',
            metadata_provenance=[dict({k:v for k,v in o.items() if k not in ('text_raw','text_view')},text_raw_sha256=digest(o['text_raw'])) for o in item['observations']],
            source_text_variants=list(item['text_variants']),development_ids=list(item['development_ids']),master_review_flags=list(item['review_flags']))
        result.append(r);mapping.append({k:r[k] for k in ('record_id','source_dataset','source_file','source_row','source_sha256','original_id','raw_sha256')})
    return result,mapping,sorted(index,key=lambda r:r['source_file']),observations


def normal(text):
    return ' '.join(unicodedata.normalize('NFC', text).split()).casefold()


def rebuild_canonical(config_path,output):
    """Raw-derived curation with exact exclusion evidence; never promotes or approves."""
    import random
    from .common import verify,read_jsonl
    from .legacy_audit import verified_tail_block,region_audit,template_overlap_audit
    from .phase_i import annotation_registry,protection_set,duplicate_groups
    from .unified import protection,check_protection,source_rows as verify_human_lineage
    from .quality_readiness import layers,verified_post
    from .blind import assert_allowed
    from .normalization_workbook import validate as validate_normalization
    from src.preprocessing import preprocess
    cfg=load(config_path);master=ROOT/cfg['master_root'];master_manifest=verify(master)
    if sha(master/'manifest.json')!=cfg['master_manifest_sha256']:raise ValueError('Master ancestry mismatch')
    legacy_path=(ROOT/cfg['legacy_source']).resolve()
    if sha(legacy_path)!=cfg['legacy_source_sha256']:raise ValueError('Legacy source hash mismatch; no source substitution allowed')
    source_bytes=legacy_path.read_bytes();legacy,fields=csv_rows(source_bytes)
    if fields!=cfg['legacy_fields']:raise ValueError('Legacy schema changed')
    tail_rows=verified_tail_block(legacy,cfg['legacy_block'])
    if any(not r['comment'].strip() or '\ufffd' in r['comment'] for r in legacy):raise ValueError('Legacy empty/corrupt content requires source audit')
    manifest_sources=[p for p,h in master_manifest['input_sha256'].items() if Path(p).resolve()==legacy_path and h==cfg['legacy_source_sha256']]
    if len(manifest_sources)!=1:raise ValueError('Original legacy file not uniquely bound to Phase G provenance')
    lineage=load(ROOT/cfg['lineage_config']);original=read_jsonl(master/'master.jsonl')
    protected=protection(load(ROOT/cfg['quality_config'])['protect_paths'])
    # The user's workbook is mutable, so capture its current bytes; do not enforce an old blank checksum.
    protected[str((ROOT/cfg['normalization_workbook']).resolve())]=sha(ROOT/cfg['normalization_workbook'])
    sources,mapping,source_index,observations=canonical_sources(original,master_manifest,legacy_path,cfg['legacy_source_sha256'])
    for entry in source_index:protected[entry['absolute_path']]=entry['container_sha256']
    registry,decisions,human_summary=annotation_registry(lineage,original)
    verified_human,_,_,_=verify_human_lineage(load(ROOT/lineage['human_lineage_config']))
    if len(verified_human)!=human_summary['sentiment_rows']:raise ValueError('Human lineage count mismatch')
    oldroot=ROOT/cfg['old_normalized_reference'];verify(oldroot)
    old={r['record_id']:r for r in read_jsonl(oldroot/'corpus_proposals.local.jsonl')}
    if any(registry.get(r['record_id'],[])!=old[r['record_id']]['human_decisions'] for r in sources):raise ValueError('Human decision history changed')
    excluded={r['record_id'] for r in sources if r['source_dataset']=='legacy_29k_unverified' and r['source_sha256']==cfg['legacy_source_sha256'] and r['source_row'] in tail_rows}
    if len(excluded)!=len(tail_rows):raise ValueError('Verified source block is not one-to-one with canonical identities')
    by_id={r['record_id']:r for r in sources}
    for r in sources:
        if r['source_dataset']=='legacy_29k_unverified':
            actual=legacy[r['source_row']-1]
            if r['original_id']!=actual['id'] or r['text_raw']!=actual['comment']:raise ValueError('Legacy identity/raw mapping mismatch')
            for d in registry.get(r['record_id'],[]):
                if d['source_sha256']!=r['source_sha256'] or int(d['source_row'])!=r['source_row']:raise ValueError('Human legacy source identity mismatch')
    regions=region_audit(legacy,cfg['region_window'])
    phrase_matches,patterns,template_summary=template_overlap_audit(legacy,tail_rows,cfg['template_phrase_words'],cfg['template_min_chars'],cfg['template_min_records'])
    suspect={r['record_id'] for r in sources if r['source_dataset']=='legacy_29k_unverified' and r['source_row'] in phrase_matches}
    accepted=set(load(ROOT/cfg['accepted_tokens']));abbreviations=load(ROOT/cfg['abbreviations']);normalized=[]
    for r in sources:
        result=preprocess(r['text_raw'],version=cfg['normalization_version'],source=r['source_dataset'],accepted_tokens=accepted,abbreviations=abbreviations)['details']
        # A change here is not an authorized normalization patch.
        if result['text_normalized']!=old[r['record_id']]['text_normalized']:raise ValueError('Frozen normalization behavior changed')
        normalized.append(dict(r,**result,human_decisions=registry.get(r['record_id'],[]),human_label=next((d['label'] for d in registry.get(r['record_id'],[]) if d['status']=='LABELED'),'')))
    norm_by={r['record_id']:r for r in normalized}
    full_groups,_,full_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in normalized],**cfg['near_duplicate'])
    raw_groups,_,raw_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_raw']) for r in sources],**cfg['near_duplicate'])
    excluded_groups={full_groups[i] for i in excluded};excluded_raw_groups={raw_groups[i] for i in excluded}
    alias_owners=defaultdict(set)
    for r in sources:
        for text in (r['text_raw'],*r['source_text_variants']):alias_owners[digest(normal(text))].add(r['record_id'])
    excluded_alias_ids=set().union(*(owners for owners in alias_owners.values() if owners&excluded))
    shadow_edges=full_near['edges']+raw_near['edges']
    for e in shadow_edges:
        if e['left'] in excluded and e['right'] not in excluded:suspect.add(e['right'])
        if e['right'] in excluded and e['left'] not in excluded:suspect.add(e['left'])
    suspect|=({r['record_id'] for r in sources if full_groups[r['record_id']] in excluded_groups or raw_groups[r['record_id']] in excluded_raw_groups}|excluded_alias_ids)-excluded
    curated=[r for r in sources if r['record_id'] not in excluded];views=[r for r in normalized if r['record_id'] not in excluded]
    groups,exact,near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in views],**cfg['near_duplicate'])
    raw_new_groups,raw_exact,raw_new_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_raw']) for r in curated],**cfg['near_duplicate'])
    review_rows=validate_normalization(ROOT/cfg['normalization_workbook'],ROOT/cfg['normalization_coordinator'])
    if not cfg.get('review_convention_authorization'):raise ValueError('Real user authorization required for shorthand review convention')
    migrated=[];format_decisions={}
    for item in review_rows:
        rid=item['id'];r=by_id[rid];decision=item['human_decision']
        effective='REJECT' if item['human_note'].strip() or decision=='REJECT' else decision or 'ACCEPT'
        same=r['text_raw']==old[rid]['text_raw'] and norm_by[rid]['text_normalized']==old[rid]['text_normalized'] and old[rid]['normalization_version']==cfg['normalization_version']
        if not same:raise ValueError('Old review identity/text/version cannot be carried')
        migrated.append(dict(record_id=rid,source_sha256=r['source_sha256'],source_row=r['source_row'],raw_sha256=r['raw_sha256'],text_sha256=digest(norm_by[rid]['text_normalized']),
            normalization_version=cfg['normalization_version'],human_decision=effective,original_cell_decision=decision,human_note=item['human_note'],
            decision_basis='EXPLICIT_CELL' if decision==effective else 'USER_AUTHORIZED_NOTE_OR_BLANK_CONVENTION',canonical_membership=rid not in excluded))
        if rid not in excluded:format_decisions[rid]=effective
    reserved_ids,reserved_comments,reserved_posts,test_info=protection_set(lineage,original)
    planned_posts=test_info.pop('candidate_post_ids');holdout=set(load(ROOT/cfg['quality_holdout'])['ids'])
    humans=set(registry);human_posts={r['post_id'] for r in sources if r['record_id'] in humans and r['source_dataset']=='facebook' and r['post_id']}
    hold_posts={by_id[i]['post_id'] for i in holdout if by_id[i]['source_dataset']=='facebook' and by_id[i]['post_id']}
    protected_ids=humans|holdout|excluded|reserved_ids|{r['record_id'] for r in sources if r['comment_id'] and r['comment_id'] in reserved_comments or r['post_id'] and r['post_id'] in reserved_posts|planned_posts|human_posts|hold_posts}
    protected_raw={raw_groups[i] for i in protected_ids if i in raw_groups};protected_norm={full_groups[i] for i in protected_ids if i in full_groups}
    protected_ids|={r['record_id'] for r in sources if raw_groups[r['record_id']] in protected_raw or full_groups[r['record_id']] in protected_norm}
    protected_ids|=set().union(*(owners for owners in alias_owners.values() if owners&protected_ids))
    neighbor=defaultdict(set)
    for e in shadow_edges+near['edges']:neighbor[e['left']].add(e['right']);neighbor[e['right']].add(e['left'])
    raw_snapshots=[];pool=[];quality_counts=Counter();parents=defaultdict(list)
    for r in views:
        if r['comment_id']:parents[(r['source_dataset'],r['post_id'],r['comment_id'])].append(r)
    for r in curated:
        rid=r['record_id'];r['duplicate_group_id']=raw_new_groups[rid];r['human_decisions']=registry.get(rid,[]);raw_snapshots.append(r)
    for r in views:
        rid=r['record_id'];reasons=[];r['duplicate_group_id']=groups[rid];r['old_duplicate_group_id']=old[rid]['duplicate_group_id']
        r['test_reserved']=rid in reserved_ids or bool(r['comment_id'] and r['comment_id'] in reserved_comments) or bool(r['post_id'] and r['post_id'] in reserved_posts)
        r['annotation_pool_reasons']=[];r['source_format_evidence']=['FACEBOOK_LITERAL_SOURCE'] if r['source_dataset']=='facebook' else ['LEGACY_LITERAL_SOURCE',*(['UNDERSCORE_SIGNAL_NOT_SYNTHETIC_PROOF'] if '_' in r['text_raw'] else []),*(['ENTITY_SIGNAL'] if re.search(r'&\s*(?:quot|amp|#)',r['text_raw']) else [])]
        r['contamination_status']='SUSPECTED_CONTAMINATION_REVIEW' if rid in suspect else 'NOT_FLAGGED_UNVALIDATED'
        if rid in holdout:r.update(technical_status='RESERVED_NOT_ASSESSED',domain_status='UNCERTAIN',spam_status='RESERVED_NOT_ASSESSED',final_quality_decision='RESERVED_QUALITY_HOLDOUT');reasons.append('QUALITY_HOLDOUT')
        else:
            linked=parents.get((r['source_dataset'],r['post_id'],r['parent_comment_id']),[])
            r.update(layers(r,linked[0] if len(linked)==1 else None))
            if r['technical_status']!='VALID':reasons.append('TECHNICAL_REVIEW')
            if r['domain_status']!='IN_DOMAIN_CANDIDATE':reasons.append('DOMAIN_UNCONFIRMED')
            if r['spam_status']=='SPAM_CANDIDATE':reasons.append('SPAM_REVIEW')
        if registry.get(rid):reasons.append('HUMAN_DECISION_PRESENT')
        if rid in protected_ids or neighbor[rid]&protected_ids:reasons.append('DEVELOPMENT_TEST_EXCLUDED_OR_HOLDOUT_LINK')
        if rid in exact or rid in raw_exact:reasons.append('EXACT_DUPLICATE')
        if r['master_review_flags'] and set(r['master_review_flags'])-{'TEXT_VARIANTS_RETAINED'}:reasons.append('MASTER_IDENTITY_REVIEW_FLAG')
        if r['source_dataset']=='facebook' and not verified_post(r):reasons.append('UNVERIFIED_FACEBOOK_IDENTITY')
        if rid in suspect:reasons.append('SUSPECTED_CONTAMINATION_REVIEW')
        if format_decisions.get(rid)=='REJECT':reasons.append('HUMAN_NORMALIZATION_REJECT')
        if (r['remaining_format_tokens'] or r['normalization_flags']) and format_decisions.get(rid)!='ACCEPT':reasons.append('FORMAT_REVIEW_PENDING')
        r['format_status']='HUMAN_ACCEPTED_SAME_TEXT' if format_decisions.get(rid)=='ACCEPT' else 'HUMAN_REJECTED' if format_decisions.get(rid)=='REJECT' else 'NEEDS_REVIEW' if r['remaining_format_tokens'] or r['normalization_flags'] else 'PLAIN_OR_PROTECTED_PROPOSAL'
        r['quality_status']='EXCLUDE' if r['technical_status'].startswith('EXCLUDE_') else 'REVIEW' if rid in suspect or r['format_status'] in ('NEEDS_REVIEW','HUMAN_REJECTED') or r['final_quality_decision']!='KEEP_PROPOSED' else 'KEEP_PROPOSED'
        r['eligibility_reasons']=sorted(set(reasons));r['annotation_eligibility']='ELIGIBLE_PROPOSED' if not reasons else 'INELIGIBLE';r['annotation_approval_transferred']=False
        r['text_annotation']=None;r['annotation_text_version']=None;quality_counts[r['quality_status']]+=1
        if not reasons:pool.append(r)
    assert not ({r['record_id'] for r in views}&excluded)
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id'],text_view=r['text_normalized']) for r in pool],'pseudo_labeling')
    # One targeted quality workbook, held/test posts/IDs/aliases/direct neighbors excluded.
    review_block=holdout|reserved_ids|{r['record_id'] for r in sources if r['post_id'] and r['post_id'] in reserved_posts|planned_posts|hold_posts}
    blocked_raw={raw_groups[i] for i in review_block if i in raw_groups}
    review_block|={r['record_id'] for r in sources if raw_groups[r['record_id']] in blocked_raw}
    review_block|=set().union(*(owners for owners in alias_owners.values() if owners&review_block))
    review_groups={full_groups[i] for i in review_block if i in full_groups}|{full_groups[i] for i in excluded}
    safe=[r for r in views if r['record_id'] not in review_block and full_groups[r['record_id']] not in review_groups and not neighbor[r['record_id']]&review_block]
    rng=random.Random(cfg['seed']);safe=sorted(safe,key=lambda r:r['record_id']);rng.shuffle(safe);selected=[];seen=set()
    def add(r):
        if groups[r['record_id']] in seen or any(x['record_id'] in neighbor[r['record_id']] for x in selected):return False
        selected.append(r);seen.add(groups[r['record_id']]);return True
    predicates=[lambda r:r['source_dataset']=='facebook',lambda r:r['source_dataset']=='legacy_29k_unverified' and r['source_row']<=cfg['region_window'],
        lambda r:r['source_dataset']=='legacy_29k_unverified' and cfg['region_window']<r['source_row']<min(tail_rows) and '_' in r['text_raw'],
        lambda r:r['source_dataset']=='legacy_29k_unverified' and r['source_row']>=min(tail_rows)-cfg['region_window'],
        lambda r:r['record_id'] in suspect,lambda r:r['text_raw']==r['text_normalized'],lambda r:r['text_raw']!=r['text_normalized']]
    anchors={}
    for i,predicate in enumerate(predicates):
        for r in safe:
            if predicate(r) and add(r):anchors[str(i)]=r['record_id'];break
    for r in safe:
        if sum(x['source_dataset']=='facebook' for x in selected)>=min(40,cfg['review_count']//4):break
        if r['source_dataset']=='facebook':add(r)
    buckets=defaultdict(list)
    for r in safe:buckets[(r['source_dataset'],r['source_row']//cfg['region_window'] if r['source_dataset']=='legacy_29k_unverified' else 0,r['contamination_status'],r['text_raw']!=r['text_normalized'])].append(r)
    while len(selected)<cfg['review_count']:
        progress=False
        for key in sorted(buckets):
            while buckets[key]:
                if add(buckets[key].pop()):progress=True;break
            if len(selected)>=cfg['review_count']:break
        if not progress:raise ValueError('Insufficient protected quality sample')
    historical_ledger=[dict(human_decision=d,canonical_membership=d['record_id'] not in excluded,exclusion_reason='SUSPECTED_TEMPLATE_BLOCK' if d['record_id'] in excluded else '') for d in decisions]
    usable=[d for d in decisions if d['record_id'] not in excluded and d['status']=='LABELED']
    holdout_removed=sorted(holdout&excluded)
    summary=dict(status='REBUILD_VERIFIED',quality_status='QUALITY_REVIEW_PENDING',canonical_approved=False,active_pointer_updated=False,
        old_records=len(sources),records=len(curated),removed_records=len(excluded),old_sources=dict(Counter(r['source_dataset'] for r in sources)),sources=dict(Counter(r['source_dataset'] for r in curated)),
        original_source_rows=len(legacy),original_source_sha256=cfg['legacy_source_sha256'],human_decisions_historical=len(decisions),human_decisions_retained=sum(d['record_id'] not in excluded for d in decisions),
        historical_sentiment_labels=human_summary['sentiment_rows'],retained_sentiment_labels=len(usable),retained_sentiment_distribution=dict(Counter(d['label'] for d in usable)),excluded_human_sentiment_labels=human_summary['sentiment_rows']-len(usable),
        approved_training_labels=0,retained_human_labels_with_quality_flags=sum(bool(r['human_label']) and r['quality_status']!='KEEP_PROPOSED' for r in views),
        suspected_contamination_review=len(suspect-excluded),template_audit=template_summary,raw_duplicates=raw_new_near['summary'],normalized_duplicates=near['summary'],old_normalized_duplicates=load(oldroot/'summary.json')['duplicates'],
        underscore_rows=sum('_' in r['text_normalized'] for r in views),unresolved_format_rows=sum(bool(r['remaining_format_tokens']) for r in views),unresolved_format_occurrences=sum(len(r['remaining_format_tokens']) for r in views),
        proposed_annotation_pool=len(pool),proposed_pool_sources=dict(Counter(r['source_dataset'] for r in pool)),approved_annotation_pool=0,quality_counts=dict(quality_counts),
        quality_holdout=dict(original=len(holdout),retained=len(holdout-excluded),excluded=len(holdout_removed),status='RESERVATION_REVIEW_REQUIRED' if holdout_removed else 'PENDING_QUALITY_HOLDOUT'),
        migrated_normalization_decisions=dict(Counter(r['human_decision'] for r in migrated)),retained_normalization_decisions=dict(Counter(r['human_decision'] for r in migrated if r['canonical_membership'])),
        source_observations_verified=observations,logical_sources_verified=len(source_index),official_ai_inputs_exported=False,normalization_version=cfg['normalization_version'])
    content_hash=digest(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n' for r in views))
    logical=dict(source_manifest_sha256=sha(master/'manifest.json'),raw_sources=source_index,exclusion_source_rows=sorted(tail_rows),excluded_ids=sorted(excluded),
        normalizer_sha256=sha(ROOT/'src/preprocessing/final_normalization.py'),accepted_tokens_sha256=sha(ROOT/cfg['accepted_tokens']),rules_sha256=sha(ROOT/cfg['abbreviations']),
        normalization_components_sha256={p:sha(ROOT/p) for p in ('src/preprocessing/plain_text.py','src/preprocessing/plain_text_v3.py','src/preprocessing/emoji_aliases.py','configs/plain_text_lexicon_v1.json')},
        normalized_corpus_sha256=content_hash,config_sha256=sha(config_path),human_ledger_sha256=digest(json.dumps(decisions,ensure_ascii=False,sort_keys=True)),
        normalization_review_sha256=sha(ROOT/cfg['normalization_workbook']),quality_holdout_sha256=sha(ROOT/cfg['quality_holdout']),quality_rules_sha256=sha(ROOT/'src/dataset/quality_readiness.py'))
    version='canonical_'+digest(json.dumps(logical,ensure_ascii=False,sort_keys=True))[:20];summary['dataset_version']=version
    with staged(output) as work:
        write_jsonl(work/'curated_raw.local.jsonl',raw_snapshots);write_jsonl(work/'normalized_annotation_view.local.jsonl',views)
        write_jsonl(work/'human_decisions_historical.local.jsonl',historical_ledger)
        write_jsonl(work/'exclusion_ledger.local.jsonl',[dict(by_id[i],status='EXCLUDED_FROM_CANONICAL_DATASET',reason='SUSPECTED_TEMPLATE_BLOCK',human_decisions=registry.get(i,[])) for i in sorted(excluded)])
        write_csv(work/'source_to_canonical.local.csv',[dict(r,canonical_membership=r['record_id'] not in excluded) for r in mapping],list(mapping[0])+['canonical_membership'])
        save(work/'original_sources.local.json',source_index);save(work/'source_region_quality_audit.local.json',regions)
        save(work/'template_summary.json',template_summary);write_csv(work/'template_patterns.local.csv',patterns,['phrase','phrase_sha256','source_records'])
        write_jsonl(work/'suspected_contamination_review.local.jsonl',[dict(record_id=r['record_id'],source_file=r['source_file'],source_row=r['source_row'],original_id=r['original_id'],text_raw=r['text_raw'],status='SUSPECTED_CONTAMINATION_REVIEW',phrase_hashes=phrase_matches.get(r['source_row'],[]) if r['source_dataset']=='legacy_29k_unverified' else []) for r in views if r['record_id'] in suspect])
        write_csv(work/'direct_near_duplicates.local.csv',sorted(near['edges'],key=lambda e:(e['left'],e['right'])),['left','right','method']);write_csv(work/'raw_direct_near_duplicates.local.csv',sorted(raw_new_near['edges'],key=lambda e:(e['left'],e['right'])),['left','right','method'])
        write_csv(work/'normalization_review_carryover.local.csv',migrated,list(migrated[0]))
        save(work/'quality_holdout_mapping.local.json',dict(retained_ids=sorted(holdout-excluded),excluded_ids=holdout_removed,original_reservation_sha256=sha(ROOT/cfg['quality_holdout']),new_reservation_created=False))
        save(work/'summary.json',summary);save(work/'source_contract.local.json',logical);save(work/'config.json',dict(cfg,source=cfg['master_root']))
        content_sha=sha(work/'normalized_annotation_view.local.jsonl')
        if content_sha!=content_hash:raise AssertionError('Canonical content digest mismatch')
        sample=[dict(record_id=r['record_id'],text_view=r['text_normalized'],text_raw=r['text_raw'],text_previous=old[r['record_id']]['text_normalized'],source_dataset=r['source_dataset'],
            source_view=json.dumps({k:r[k] for k in ('source_dataset','source_file','source_row','source_sha256','original_id','source_format_evidence','contamination_status')},ensure_ascii=False),
            text_sha256=digest(r['text_normalized']),human_domain_decision='',human_spam_decision='',human_note='') for r in selected]
        save(work/'workbook_input.local.json',dict(kind='canonical',rows=sample,review_count=len(sample),source_manifest_sha256=sha(master/'manifest.json'),canonical_content_sha256=content_sha,
            normalization_version=cfg['normalization_version'],dataset_version=version,status='QUALITY_REVIEW_PENDING'))
        save(work/'selection_manifest.local.json',dict(seed=cfg['seed'],ids=[r['record_id'] for r in selected],anchors=anchors,method='source/region/change round robin with explicit anchors; targeted quality sample, no sentiment selection',source_counts=dict(Counter(r['source_dataset'] for r in selected))))
        impact=dict(old_source_manifest_sha256=sha(oldroot/'manifest.json'),new_canonical_content_sha256=content_sha,active_pointer_updated=False,
            stale_for_new_corpus=['I/J quality proposals and eligibility','review coordinator corpus bindings (same-text decisions carried separately)','quality holdout: 3 excluded; no resampling','pilot selection and freeze/release approval','future experiment input manifests'],
            preserved_historical=['master and 650 human decisions','old splits and test reservation/quarantine','E/E.1/E.2/G/H results/checkpoints'],normalization_review_reused_only_if_identity_raw_text_version_equal=True)
        save(work/'dependency_impact.json',impact);save(work/'protected_inputs.local.json',protected)
        check_protection(protected);seal(work,dict(status='REBUILD_VERIFIED',quality_status='QUALITY_REVIEW_PENDING',dataset_version=version,records=len(curated),canonical_content_sha256=content_sha,
            active_pointer_updated=False,implementation_sha256=sha(Path(__file__)),config_sha256=sha(config_path)))
    return summary


def promote_canonical(directory,approval_path,pointer):
    """Source-switch approval is separate from quality/freeze approval."""
    from .common import verify
    manifest=verify(directory);approval=load(approval_path)
    if manifest.get('status')!='REBUILD_VERIFIED' or approval.get('source_switch_approved') is not True or not approval.get('reviewer') or not approval.get('approved_at'):raise ValueError('Explicit verified source-switch approval required')
    if approval.get('manifest_sha256')!=sha(directory/'manifest.json') or approval.get('canonical_content_sha256')!=manifest['canonical_content_sha256']:raise ValueError('Source-switch approval checksum mismatch')
    if approval.get('quality_approved'):raise ValueError('Source promotion cannot approve corpus quality')
    if pointer.exists():raise FileExistsError('Existing active pointer requires a separately reviewed migration; no overwrite')
    pointer.parent.mkdir(parents=True,exist_ok=True)
    save(pointer,dict(status='QUALITY_REVIEW_PENDING',source_switch_approved=True,canonical_approved=False,dataset_version=manifest['dataset_version'],
        corpus_root=str(directory.resolve()),manifest_sha256=sha(directory/'manifest.json'),approval_sha256=sha(approval_path)))
    return 'QUALITY_REVIEW_PENDING'


def cleaning_protection(rows,seeds,edges=(),fields=('text_raw','text_normalized')):
    """Conservative alias/exact/direct-near closure, without deleting any record."""
    aliases=defaultdict(set);neighbors=defaultdict(set)
    for r in rows:
        for text in [*(r.get(k,'') for k in fields),*r.get('source_text_variants',[])]:
            if text:aliases[digest(normal(text))].add(r['record_id'])
        if r.get('comment_id') and r.get('post_id'):
            aliases['identity:'+r['source_dataset']+':'+r['post_id']+':'+r['comment_id']].add(r['record_id'])
    for values in aliases.values():
        for rid in values:neighbors[rid].update(values-{rid})
    for e in edges:
        neighbors[e['left']].add(e['right']);neighbors[e['right']].add(e['left'])
    blocked=set(seeds);front=list(blocked)
    while front:
        rid=front.pop()
        for other in neighbors[rid]-blocked:blocked.add(other);front.append(other)
    return blocked,neighbors


def cleaning_sample(rows,blocked,groups,neighbors,previous_rejects,seed=20261120):
    """Deterministic review; no sentiment access and no protected diagnostic pairs."""
    import random,difflib
    rng=random.Random(seed);safe=sorted([r for r in rows if r['record_id'] not in blocked],key=lambda r:r['record_id'])
    changed=[r for r in safe if r['text_normalized']!=r['text_normalized_v3_1']];rng.shuffle(changed)
    controls=[r for r in safe if r['text_normalized']==r['text_normalized_v3_1']];rng.shuffle(controls)
    largest=sorted(changed,key=lambda r:(difflib.SequenceMatcher(None,r['text_normalized_v3_1'],r['text_normalized'],autojunk=False).ratio(),r['record_id']))
    risky=[r for r in safe if r['record_id'] in previous_rejects or r['text_preprocessing_source']=='VERIFIED_DOM_VIEW' and r['text_preprocessing_input']!=r['text_raw']
        or any(e['rule'] in ('TECHNICAL_AT_MENTION','FB_DISTINCT_TOKEN_EVIDENCE') for e in r['transform_events']) or any('UNDERSCORE' in f for f in r['normalization_flags'])]
    rng.shuffle(risky);selected=[];chosen=set();used_groups=set();counts=Counter()
    def add(r,kind):
        rid=r['record_id']
        if rid in chosen or groups[rid] in used_groups or neighbors[rid]&chosen:return False
        selected.append(r);chosen.add(rid);used_groups.add(groups[rid]);counts[kind]+=1;return True
    for kind,values,quota in [('random_changed',changed,35),('largest_changed',largest,25),('risk',risky,30),('unchanged_control',controls,10)]:
        for r in values:
            if counts[kind]>=quota:break
            add(r,kind)
    for r in [*changed,*controls]:
        if len(selected)>=100:break
        add(r,'reallocated')
    return selected,dict(seed=seed,target_counts=dict(random_changed=35,largest_changed=25,risk=30,unchanged_control=10),
        actual_counts=dict(counts),rows=len(selected),method='sequential disjoint groups; shortage reallocated, no sentiment selection; exact/direct-near isolation',
        ids=[r['record_id'] for r in selected])


def rebuild_cleaning(source,output):
    """Verify full local ancestry, derive a v3.2 candidate; never publish or promote."""
    import difflib
    from .common import verify,read_jsonl
    from .unified import check_protection
    from .phase_i import protection_set,duplicate_groups
    from .normalization_workbook import validate as validate_old_review
    from .quality_readiness import layers,verified_post as quality_post
    from .blind import assert_allowed
    from src.preprocessing.evidence_cleaning import normalize as clean,select_dom,token_evidence,aliases_resource,COMPOUND,segments,ALIAS
    if output.exists():raise FileExistsError('Immutable cleaning output exists')
    baseline_manifest=verify(source);cfg=load(source/'config.json');contract=load(source/'source_contract.local.json')
    if baseline_manifest.get('status')!='REBUILD_VERIFIED' or baseline_manifest.get('dataset_version')!='canonical_37cf670237e3398b5c96':raise ValueError('Expected verified canonical ancestry')
    protected=load(source/'protected_inputs.local.json');check_protection(protected)
    for file in source.rglob('*'):
        if file.is_file():protected[str(file.resolve())]=sha(file)
    public=ROOT/'data/canonical/canonical_37cf670237e3398b5c96';verify(public)
    for file in public.iterdir():
        if file.is_file():protected[str(file.resolve())]=sha(file)
    frozen={**contract['normalization_components_sha256'],'src/preprocessing/final_normalization.py':contract['normalizer_sha256'],cfg['accepted_tokens']:contract['accepted_tokens_sha256'],cfg['abbreviations']:contract['rules_sha256']}
    for p,h in frozen.items():
        if sha(ROOT/p)!=h:raise ValueError('Frozen v3.1 resource changed: '+p)
        protected[str((ROOT/p).resolve())]=h
    pointer=ROOT/cfg['active_pointer'];pointer_before=sha(pointer) if pointer.exists() else None
    original=read_jsonl(ROOT/cfg['master_root']/'master.jsonl');master_manifest=verify(ROOT/cfg['master_root'])
    verified,_,index,observation_count=canonical_sources(original,master_manifest,(ROOT/cfg['legacy_source']).resolve(),cfg['legacy_source_sha256'])
    rows=read_jsonl(source/'normalized_annotation_view.local.jsonl');by={r['record_id']:r for r in rows};original_by={r['record_id']:r for r in verified}
    if any(r['text_raw']!=original_by[r['record_id']]['text_raw'] for r in rows):raise ValueError('Canonical/raw mapping mismatch')
    excluded=read_jsonl(source/'exclusion_ledger.local.jsonl');all_rows=[*rows,*excluded]
    lineage=load(ROOT/cfg['lineage_config'])
    reservation=ROOT/lineage['test_reservation'];availability=ROOT/lineage['test_source_candidates']
    test_manifest=verify(reservation.parent)
    if not availability.is_file():raise FileNotFoundError('Required test/exposure availability evidence missing')
    if test_manifest.get('status')!='PARTIAL' and not reservation.is_file():raise FileNotFoundError('Required test reservation missing')
    quarantine=ROOT/lineage['test_quarantine_root']
    if not quarantine.is_dir():raise FileNotFoundError('Required quarantine root missing')
    protection_paths=[reservation.parent/'manifest.json',availability,*sorted(quarantine.rglob('post_quarantine.json'))]
    if reservation.is_file():protection_paths.append(reservation)
    for p in protection_paths:protected[str(p.resolve())]=sha(p)
    rid,cid,pid,info=protection_set(lineage,original)
    planned=info['candidate_post_ids'];hold=load(ROOT/cfg['quality_holdout'])['ids'];hold=set(hold)
    history=read_jsonl(source/'human_decisions_historical.local.jsonl');human={r['human_decision']['record_id'] for r in history}
    heldposts={r['post_id'] for r in all_rows if r['record_id'] in hold|human and r.get('post_id')}
    seeds=rid|hold|human|{r['record_id'] for r in excluded}|{r['record_id'] for r in rows if 'DEVELOPMENT_TEST_EXCLUDED_OR_HOLDOUT_LINK' in r['eligibility_reasons']}
    seeds|={r['record_id'] for r in all_rows if r.get('comment_id') in cid or r.get('post_id') in pid|planned|heldposts}
    policy=cfg['near_duplicate']
    raw_groups,raw_exact,raw_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_raw']) for r in all_rows],**policy)
    old_groups,old_exact,old_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r.get('text_normalized',r['text_raw'])) for r in all_rows],**policy)
    evidence_block,_=cleaning_protection(all_rows,seeds,[*raw_near['edges'],*old_near['edges']])
    evidence=token_evidence(rows,evidence_block)
    evidence.update(source_dataset_version=baseline_manifest['dataset_version'],source_content_sha256=baseline_manifest['canonical_content_sha256'],
        protection_policy='All human decisions/development posts, test/reserved/planned/holdout whole posts, old guards, raw aliases/exact/direct-near closure; no legacy evidence',
        protected_ids_sha256=digest('|'.join(sorted(evidence_block))))
    resource=aliases_resource();accepted=set(load(ROOT/cfg['accepted_tokens']));abbr=load(ROOT/cfg['abbreviations'])
    # Every DOM candidate comes from a checksum-bound observation in the original master.
    cache={};candidate_by=defaultdict(list)
    for s in index:
        path=Path(s['absolute_path']);payload=path.read_bytes()
        if sha(path)!=s['container_sha256']:raise ValueError('DOM source checksum mismatch')
        if s['archive_member']:
            with zipfile.ZipFile(io.BytesIO(payload)) as z:payload=z.read(s['archive_member'])
        if digest(payload)!=s['source_sha256']:raise ValueError('DOM member checksum mismatch')
        cache[s['source_file']]=(read_payload(payload,Path(s['archive_member'] or path.name).suffix)[0],s)
    for r in rows:
        if r['source_dataset']!='facebook':continue
        for obs in r['metadata_provenance']:
            payloads,s=cache[obs['source_file']];n=obs['source_row'];item=payloads[n-1]
            if item.get('text_extraction_version')!='dom_text_v2' or 'text_without_mentions' not in item:continue
            key=next(k for k in TEXT_KEYS if k in item)
            if digest(item[key])!=obs['text_raw_sha256']:raise ValueError('DOM observation raw hash mismatch')
            candidate_by[r['record_id']].append(dict(item,text_raw=item[key],comment_id=str(item.get('comment_id') or ''),post_id=str(item.get('post_id') or ''),
                source_file=s['source_file'],source_sha256=s['source_sha256'],source_row=n,checksum_verified=True))
    views=[];dom_ledger=[];unresolved=[];events=[];dom_summary=Counter();dom_sources=defaultdict(Counter);rejections=Counter();changed_rules=defaultdict(set)
    for r in rows:
        text,dom_flags,audit=select_dom(r,candidate_by[r['record_id']]);valid=[a for a in audit if a['status']=='VALID'];conflict='DOM_CONFLICT' in dom_flags
        used=bool(valid) and not conflict;input_source='VERIFIED_DOM_VIEW' if used else 'RAW'
        if r['source_dataset']=='facebook':
            dom_summary['facebook_records']+=1;dom_summary['with_candidate']+=bool(audit);dom_summary['full_checks_passed']+=bool(valid)
            dom_summary['selected']+=used;dom_summary['selected_changed']+=used and text!=r['text_raw'];dom_summary['conflicts']+=conflict
        for a in audit:
            dom_sources[a['source_file']][a['status']]+=1
            if a['status']!='VALID':rejections[a['status']]+=1
        d=dict(record_id=r['record_id'],text_preprocessing_source=input_source,evidence=audit,flags=dom_flags)
        dom_ledger.append(d)
        if dom_flags and r['source_dataset']=='facebook':unresolved.append(d)
        result=clean(text,source=r['source_dataset'],accepted_tokens=accepted,evidence_tokens=evidence['vocabulary'],abbreviations=abbr,aliases=resource['aliases'])
        # Explicit independent idempotence and raw determinism checks for every retained record.
        again=clean(result['text_normalized'],source=r['source_dataset'],accepted_tokens=accepted,evidence_tokens=evidence['vocabulary'],abbreviations=abbr,aliases=resource['aliases'])
        if result['text_normalized']!=again['text_normalized']:raise ValueError('v3.2 text idempotence failed')
        new=dict(r,**result,text_normalized_v3_1=r['text_normalized'],text_preprocessing_source=input_source,text_preprocessing_input=text,
            preprocessing_source_evidence=audit,dom_flags=dom_flags,text_annotation=None,annotation_text_version=None,normalization_version='plain_text_v3_2',
            normalization_events_v3_1=r['normalization_events'],normalization_events=result['transform_events'],
            needs_human_recheck=bool(r['human_label']) and result['text_normalized']!=r['text_normalized'],normalization_human_decision='')
        for e in result['transform_events']:
            events.append(dict(record_id=r['record_id'],**e));changed_rules[e['rule']].add(r['record_id'])
        views.append(new)
    # Excluded content remains outside the corpus; derive shadows for protection only.
    shadows=[]
    for r in excluded:
        text=clean(r['text_raw'],source=r['source_dataset'],accepted_tokens=accepted,evidence_tokens=evidence['vocabulary'],abbreviations=abbr,aliases=resource['aliases'])['text_normalized']
        shadows.append(dict(r,text_normalized=text))
    all_new=[*views,*shadows]
    new_groups,new_exact,new_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in all_new],**policy)
    candidate_groups,candidate_exact,candidate_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in views],**policy)
    # Raw+old+new aliases and all direct edges are protected together; no old guard is relaxed.
    joint=[dict(r,text_normalized_v3_1=by.get(r['record_id'],{}).get('text_normalized',r['text_raw'])) for r in all_new]
    blocked,neighbors=cleaning_protection(joint,evidence_block,[*raw_near['edges'],*old_near['edges'],*new_near['edges']],('text_raw','text_normalized_v3_1','text_normalized'))
    pool=[];eligibility_diff=[];parents=defaultdict(list)
    for r in views:
        if r['comment_id'] and r['post_id']:parents[(r['source_dataset'],r['post_id'],r['comment_id'])].append(r)
    for r in views:
        rid=r['record_id'];previous=by[rid];linked=parents.get((r['source_dataset'],r['post_id'],r['parent_comment_id']),[])
        r.update(layers(r,linked[0] if len(linked)==1 else None))
        if 'NON_TEXT_REVIEW' in r['normalization_flags']:
            r.update(technical_status='REVIEW_NON_TEXT',final_quality_decision='REVIEW_PROPOSED')
        reasons=[]
        if r['technical_status']!='VALID':reasons.append('TECHNICAL_REVIEW')
        if r['domain_status']!='IN_DOMAIN_CANDIDATE':reasons.append('DOMAIN_UNCONFIRMED')
        if r['spam_status']=='SPAM_CANDIDATE':reasons.append('SPAM_REVIEW')
        if r['human_decisions']:reasons.append('HUMAN_DECISION_PRESENT')
        if rid in blocked:reasons.append('DEVELOPMENT_TEST_EXCLUDED_OR_HOLDOUT_LINK')
        if rid in candidate_exact or rid in raw_exact:reasons.append('EXACT_DUPLICATE')
        if r['master_review_flags'] and set(r['master_review_flags'])-{'TEXT_VARIANTS_RETAINED'}:reasons.append('MASTER_IDENTITY_REVIEW_FLAG')
        if r['source_dataset']=='facebook' and not quality_post(r):reasons.append('UNVERIFIED_FACEBOOK_IDENTITY')
        if r['contamination_status'] not in ('NOT_FLAGGED','NOT_FLAGGED_BY_DECLARED_RULES'):reasons.extend(x for x in previous['eligibility_reasons'] if 'CONTAMINATION' in x)
        unresolved_tokens=[m[0] for protected,s,_ in segments(r['text_normalized']) if not protected for m in COMPOUND.finditer(s)]
        r['remaining_format_tokens']=unresolved_tokens;r['format_status']='NEEDS_REVIEW' if unresolved_tokens else 'PLAIN_OR_PROTECTED_PROPOSAL'
        if unresolved_tokens or any(f in ('BARE_ALIAS_AMBIGUOUS','UNMATCHED_ALIAS_REVIEW') or f.startswith(('UNBALANCED_','AMBIGUOUS_ABBREVIATION')) for f in r['normalization_flags']):reasons.append('FORMAT_REVIEW_PENDING')
        if 'DOM_CONFLICT' in r['dom_flags']:reasons.append('DOM_CONFLICT_REVIEW')
        r['quality_status']='REVIEW' if r['final_quality_decision']!='KEEP_PROPOSED' or 'FORMAT_REVIEW_PENDING' in reasons or 'DOM_CONFLICT_REVIEW' in reasons else 'KEEP_PROPOSED'
        r['eligibility_reasons']=sorted(set(reasons));r['annotation_eligibility']='INELIGIBLE' if reasons else 'ELIGIBLE_PROPOSED';r['duplicate_group_id']=candidate_groups[rid]
        r['annotation_pool_reasons_v3_1']=previous['annotation_pool_reasons'];r['annotation_pool_reasons']=list(r['eligibility_reasons'])
        if not reasons:pool.append(r)
        if r['annotation_eligibility']!=previous['annotation_eligibility'] or set(reasons)!=set(previous['eligibility_reasons']):eligibility_diff.append(dict(record_id=rid,before=previous['annotation_eligibility'],after=r['annotation_eligibility'],old_reasons=previous['eligibility_reasons'],new_reasons=r['eligibility_reasons']))
        if r['human_decisions']!=previous['human_decisions'] or r['human_label']!=previous['human_label'] or r['text_raw']!=previous['text_raw']:raise AssertionError('Raw/human mutation')
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id'],text_view=r['text_normalized']) for r in pool],'pseudo_labeling')
    review=validate_old_review(ROOT/cfg['normalization_workbook'],ROOT/cfg['normalization_coordinator'])
    if not cfg.get('review_convention_authorization'):raise ValueError('Missing real review-convention authorization')
    effective={r['id']:('REJECT' if r['human_note'].strip() or r['human_decision']=='REJECT' else r['human_decision'] or 'ACCEPT') for r in review}
    rejected={i for i,d in effective.items() if d=='REJECT'};root_causes=[];new_by={r['record_id']:r for r in views}
    for old_review in review:
        rid=old_review['id']
        if rid not in rejected:continue
        previous=by[rid];r=new_by[rid];note=old_review['human_note'];causes=[]
        if previous['remaining_format_tokens']:causes.append('INCOMPLETE_UNDERSCORE_RECOVERY')
        if any('EMOJI' in e['rule'] for e in r['transform_events']) or 'face_' in note or '❤️' in note:causes.append('EMOJI_SERIALIZATION')
        if 'TT' in note or 'Akira' in note:causes.append('AMBIGUOUS_NAME_OR_ABBREVIATION')
        if 'emote' in note:causes.append('DOMAIN_NON_TEXT_DECISION_NOT_NORMALIZATION_ONLY')
        if not note.strip():causes.append('NO_HUMAN_REASON_CAUSAL_ATTRIBUTION_UNCONFIRMED')
        if not causes:causes.append('INSUFFICIENT_EVIDENCE_FOR_SPECIFIC_RULE')
        applicable=[e for e in r['transform_events'] if e['stage']!='preserved v3.1 components']
        status='FIX_PROPOSED' if applicable and r['text_normalized']!=previous['text_normalized'] else 'NO_SAFE_FIX' if 'AMBIGUOUS_NAME_OR_ABBREVIATION' in causes else 'NEEDS_REVIEW'
        root_causes.append(dict(record_id=rid,text_raw=previous['text_raw'],text_v3_1=previous['text_normalized'],text_v3_2=r['text_normalized'],human_note=note,
            old_events=previous['normalization_events'],old_flags=previous['normalization_flags'],old_decision='REJECT',old_version='plain_text_v3_1',
            causes=causes,causal_attribution='NOTE/SPAN_EVIDENCE' if note.strip() else 'OBSERVED_RESIDUAL_NOT_PROVEN_BAD_TRANSFORMATION',status=status,
            new_decision='',remaining_format=r['remaining_format_tokens'],targeted_events=applicable))
    selected,sampling=cleaning_sample(views,blocked,candidate_groups,neighbors,rejected)
    remaining=Counter(t for r in views for t in r['remaining_format_tokens']);reason_counts=Counter(e['reason'] for r in views for e in r['unresolved_underscore'])
    changed_ids={r['record_id'] for r in views if r['text_normalized']!=r['text_normalized_v3_1']}
    group_members=defaultdict(list)
    for r in views:group_members[candidate_groups[r['record_id']]].append(r['record_id'])
    newly_merged_groups=[sorted(ids) for ids in group_members.values() if len({old_groups[i] for i in ids})>1]
    posts_evidence_missing={r['post_id'] for r in views if r['source_dataset']=='facebook' and r['post_id'] and not any(a['status']=='VALID' for a in r['preprocessing_source_evidence'])}
    # Compare actual sealed edge ledgers on exactly the same retained population.
    old_edge_rows=csv_rows((source/'direct_near_duplicates.local.csv').read_bytes())[0];old_edge_set={(e['left'],e['right']) for e in old_edge_rows}
    new_edge_set={(e['left'],e['right']) for e in candidate_near['edges']}
    original_summary=load(source/'summary.json')
    baseline=dict(records=len(rows),sources=dict(Counter(r['source_dataset'] for r in rows)),human_decisions=sum(len(r['human_decisions']) for r in rows),sentiment=sum(bool(r['human_label']) for r in rows),
        underscore_records=sum('_' in r['text_normalized'] for r in rows),underscore_tokens=sum(len(COMPOUND.findall(r['text_normalized'])) for r in rows),
        exact_groups=original_summary['normalized_duplicates']['exact_groups'],
        alias_records=sum(any((m[1] or m[2]) in resource['aliases'] for m in ALIAS.finditer(r['text_normalized'])) for r in rows),
        technical_at_mention_records=sum(bool(re.search(r'(?<!\w)@[A-Za-z][A-Za-z0-9_.]*',r['text_normalized'])) for r in rows),
        exact_duplicate_excess=original_summary['normalized_duplicates']['exact_duplicate_rows'],near_edges=len(old_edge_set),
        protected_records=sum('DEVELOPMENT_TEST_EXCLUDED_OR_HOLDOUT_LINK' in r['eligibility_reasons'] for r in rows),
        computed_protected_records=sum(r['record_id'] in evidence_block for r in rows),unresolved_format=sum(bool(r['remaining_format_tokens']) for r in rows),
        format_status=dict(Counter(r['format_status'] for r in rows)),quality_status=dict(Counter(r['quality_status'] for r in rows)),proposed_annotation_pool=original_summary['proposed_annotation_pool'],approved=0)
    metrics=dict(status='CANDIDATE_REBUILT_QUALITY_REVIEW_PENDING',preprocessing_version='plain_text_v3_2',baseline=baseline,records=len(views),sources=dict(Counter(r['source_dataset'] for r in views)),
        human_decisions_retained=sum(len(r['human_decisions']) for r in views),human_decisions_historical=len(history),sentiment_retained=sum(bool(r['human_label']) for r in views),
        changed_records=sum(r['text_normalized']!=r['text_normalized_v3_1'] for r in views),dom=dict(dom_summary),dom_candidate_rejections=dict(rejections),dom_by_source={k:dict(v) for k,v in dom_sources.items()},
        records_with_rejected_dom_candidates=sum(any(a['status']!='VALID' for a in r['preprocessing_source_evidence']) for r in views),
        records_with_candidates_but_none_selected=sum(bool(r['preprocessing_source_evidence']) and r['text_preprocessing_source']=='RAW' for r in views),
        posts_missing_dom_evidence=len(posts_evidence_missing),
        contribution_rule_records={k:len(v) for k,v in sorted(changed_rules.items())},
        changed_records_involving_rule={k:len(v&changed_ids) for k,v in sorted(changed_rules.items())},
        alias_recovery_events=sum(e['rule']=='PINNED_EMOJI_ALIAS' for e in events),unmatched_alias_review_records=sum('UNMATCHED_ALIAS_REVIEW' in r['normalization_flags'] for r in views),
        ambiguous_alias_review_records=sum('BARE_ALIAS_AMBIGUOUS' in r['normalization_flags'] for r in views),
        evidence_split_events=sum(e['rule']=='FB_DISTINCT_TOKEN_EVIDENCE' for e in events),
        evidence_distinct_comments=evidence['distinct_comments'],evidence_vocabulary=len(evidence['vocabulary']),
        underscore_records=sum('_' in r['text_normalized'] for r in views),remaining_underscore_tokens=sum(remaining.values()),remaining_underscore_types=len(remaining),underscore_reason_counts=dict(reason_counts),
        reject_decisions=dict(Counter(effective.values())),reject_fix_status=dict(Counter(r['status'] for r in root_causes)),reject_causes=dict(Counter(c for r in root_causes for c in r['causes'])),
        non_text_review=sum('NON_TEXT_REVIEW' in r['normalization_flags'] for r in views),human_needs_recheck=sum(r['needs_human_recheck'] for r in views),
        duplicates=candidate_near['summary'],new_exact_groups=len(newly_merged_groups),new_near_edges=len(new_edge_set-old_edge_set),removed_near_edges=len(old_edge_set-new_edge_set),
        protected_records=sum(r['record_id'] in blocked for r in views),newly_protected_records=sum(r['record_id'] in blocked-evidence_block for r in views),
        unresolved_format=sum(bool(r['remaining_format_tokens']) for r in views),normalization_review_records=sum(r['format_status']=='NEEDS_REVIEW' for r in views),
        quality_status=dict(Counter(r['quality_status'] for r in views)),proposed_annotation_pool=len(pool),approved_annotation_pool=0,approved_training_labels=0,
        eligibility_changes=len(eligibility_diff),sampling=sampling,source_observations_verified=observation_count,logical_sources_verified=len(index),
        active_pointer_updated=False,canonical_approved=False,ai_inputs_exported=False,normalization_decisions_transferred=0)
    with staged(output) as out:
        write_jsonl(out/'candidate_corpus.local.jsonl',views);write_jsonl(out/'transform_events.local.jsonl',events)
        write_jsonl(out/'dom_provenance.local.jsonl',dom_ledger);write_jsonl(out/'unresolved_dom.local.jsonl',unresolved)
        save(out/'token_evidence.local.json',evidence);save(out/'emoji_resource.json',{k:v for k,v in resource.items() if k!='aliases'})
        write_jsonl(out/'normalization_reject_root_causes.local.jsonl',root_causes)
        write_csv(out/'remaining_underscore.local.csv',[dict(token=t,count=n) for t,n in sorted(remaining.items(),key=lambda x:(-x[1],x[0]))],['token','count'])
        save(out/'summary.json',metrics);save(out/'protected_inputs.local.json',protected)
        write_csv(out/'direct_near_duplicates.local.csv',sorted(candidate_near['edges'],key=lambda e:(e['left'],e['right'])),['left','right','method'])
        save(out/'duplicate_leakage_diff.local.json',dict(old_near_edges=sorted(old_edge_set),new_near_edges=sorted(new_edge_set),new_exact_groups=newly_merged_groups,new_protected_ids=sorted(blocked-evidence_block),old_protected_ids=sorted(evidence_block),new_all_protected_ids=sorted(blocked),
            policy='Raw/old/new exact alias + direct-near conservative transitive protection, includes excluded shadows; no frozen splits changed'))
        write_jsonl(out/'eligibility_diff.local.jsonl',eligibility_diff)
        write_csv(out/'annotation_pool.local.csv',[dict(record_id=r['record_id'],text_view=r['text_normalized']) for r in pool],['record_id','text_view'])
        save(out/'workbook_input.local.json',dict(kind='cleaning_v3_2',rows=[dict(id=r['record_id'],text_truoc=r['text_normalized_v3_1'],text_sau=r['text_normalized'],decision='',note='') for r in selected],
            source_manifest_sha256=sha(source/'manifest.json'),candidate_content_sha256=sha(out/'candidate_corpus.local.jsonl'),preprocessing_version='plain_text_v3_2',sampling=sampling))
        save(out/'config.json',dict(source=str(source.resolve()),source_manifest_sha256=sha(source/'manifest.json'),near_duplicate=policy,seed=sampling['seed']))
        save(out/'verification.json',dict(raw_and_human_unchanged=True,frozen_v31_resources_unchanged=True,idempotence_records=len(views),historical_decisions=len(history),review_protected_overlap=0,
            source_manifest_sha256=sha(source/'manifest.json'),public_snapshot_manifest_sha256=sha(public/'manifest.json'),v31_resource_sha256=frozen,
            engine_sha256=sha(ROOT/'src/preprocessing/evidence_cleaning.py'),owner_sha256=sha(Path(__file__)),facade_sha256=sha(ROOT/'src/preprocessing/__init__.py'),emoji_mapping_sha256=resource['mapping_sha256']))
        check_protection(protected)
        if (sha(pointer) if pointer.exists() else None)!=pointer_before:raise ValueError('Active pointer changed')
        seal(out,dict(status=metrics['status'],preprocessing_version='plain_text_v3_2',source_manifest_sha256=sha(source/'manifest.json'),records=len(views),
            canonical_approved=False,annotation_approved=False,active_pointer_updated=False,candidate_content_sha256=sha(out/'candidate_corpus.local.jsonl')))
    return metrics


def minimal_filter_text(text):
    """Small data view: NFC, exact valid HTML, CRLF/NBSP and outer whitespace.

    Internal spacing/newlines and punctuation stay literal; no segmentation,
    alias conversion, teencode, case changes or mention/name guessing.
    """
    import html,html.entities
    entity=re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);')
    technical=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
    def decode(m):
        name=m[0][1:-1]
        if name.startswith('#'):
            try:code=int(name[2:],16) if name[1:2].lower()=='x' else int(name[1:])
            except ValueError:return m[0]
            if not 32<=code<=0x10ffff or 0xd800<=code<=0xdfff:return m[0]
        elif name+';' not in html.entities.html5:return m[0]
        return html.unescape(m[0])
    current=text
    while True:
        parts=[];cursor=0
        def clean(s):return entity.sub(decode,unicodedata.normalize('NFC',s)).replace('\r\n','\n').replace('\r','\n').replace('\u00a0',' ')
        for m in technical.finditer(current):parts.extend([clean(current[cursor:m.start()]),m[0]]);cursor=m.end()
        parts.append(clean(current[cursor:]));value=''.join(parts).strip()
        if value==current:return value
        current=value


def filter_row_reasons(row,legacy_max_characters=1000,facebook_max_characters=None):
    """Only explicit format/length policy, unusable text and real human EXCLUDE."""
    text=row['text_raw'];reasons=[]
    if row['source_dataset']=='legacy_29k_unverified' and '_' in text:reasons.append('LEGACY_RAW_UNDERSCORE')
    limit=legacy_max_characters if row['source_dataset']=='legacy_29k_unverified' else facebook_max_characters
    if limit is not None and len(text)>limit:reasons.append('EXC_TOO_LONG')
    if not text.strip():reasons.append('EMPTY_TEXT')
    if '\ufffd' in text or any(0xd800<=ord(c)<=0xdfff or ord(c)<32 and c not in '\t\r\n' for c in text):reasons.append('INVALID_ENCODING_OR_CONTROL')
    statuses={d['status'] for d in row.get('human_decisions',[])}
    if statuses=={'EXCLUDE'}:reasons.append('HUMAN_EXCLUDE')
    return reasons


def strict_filter_dedup(rows):
    """Exact minimal-view equality only; preserve original labeled identity first."""
    buckets=defaultdict(list)
    for row in rows:buckets[row['text_normalized']].append(row)
    kept=[];removed=[];membership={};conflicts=set()
    for text,values in sorted(buckets.items()):
        ordered=sorted(values,key=lambda r:(not bool(r.get('human_label')),not bool(r.get('human_decisions')),r['source_dataset']!='facebook',r['record_id']))
        chosen=ordered[0];group='fx_'+digest(text)
        if len({r['human_label'] for r in values if r.get('human_label')})>1:conflicts.add(group)
        kept.append(chosen)
        for r in values:membership[r['record_id']]=group
        for r in ordered[1:]:removed.append((r,chosen['record_id']))
    return sorted(kept,key=lambda r:r['record_id']),removed,membership,conflicts


def facebook_length_review(row):
    return row['source_dataset']=='facebook' and len(row['text_raw'])>1000


def filter_canonical(source,output,legacy_max_characters=1000,facebook_max_characters=None):
    """One reproducible simple filter; no old normalizer or annotation approval."""
    from .common import verify,read_jsonl
    from .unified import check_protection
    from .phase_i import protection_set,duplicate_groups
    from .quality_readiness import layers,verified_post,UI
    from .blind import assert_allowed
    if any(x is not None and (type(x) is not int or x<1) for x in (legacy_max_characters,facebook_max_characters)):raise ValueError('Positive length limits required')
    if output.exists():raise FileExistsError('Immutable filtered output exists')
    manifest=verify(source);cfg=load(source/'config.json')
    if manifest.get('status')!='REBUILD_VERIFIED' or manifest.get('dataset_version')!='canonical_37cf670237e3398b5c96':raise ValueError('Verified canonical raw source required')
    protected=load(source/'protected_inputs.local.json');check_protection(protected)
    for p in source.iterdir():
        if p.is_file():protected[str(p.resolve())]=sha(p)
    master=ROOT/cfg['master_root'];mm=verify(master);original=read_jsonl(master/'master.jsonl')
    originals,_,_,observations=canonical_sources(original,mm,(ROOT/cfg['legacy_source']).resolve(),cfg['legacy_source_sha256'])
    raw_by={r['record_id']:r for r in originals};rows=read_jsonl(source/'normalized_annotation_view.local.jsonl');old_by={r['record_id']:r for r in rows}
    if len(rows)!=38642 or any(r['text_raw']!=raw_by[r['record_id']]['text_raw'] for r in rows):raise ValueError('Canonical raw lineage changed')
    prior_excluded=read_jsonl(source/'exclusion_ledger.local.jsonl');history=read_jsonl(source/'human_decisions_historical.local.jsonl')
    lineage=load(ROOT/cfg['lineage_config']);reservation=ROOT/lineage['test_reservation'];test_manifest=verify(reservation.parent)
    availability=ROOT/lineage['test_source_candidates']
    if not availability.is_file() or test_manifest.get('status')!='PARTIAL' and not reservation.is_file():raise FileNotFoundError('Required reservation/exposure evidence missing')
    for p in [reservation.parent/'manifest.json',availability,*sorted((ROOT/lineage['test_quarantine_root']).rglob('post_quarantine.json'))]:protected[str(p.resolve())]=sha(p)
    if reservation.is_file():protected[str(reservation.resolve())]=sha(reservation)
    held_ids,held_comments,held_posts,info=protection_set(lineage,original);holdout=set(load(ROOT/cfg['quality_holdout'])['ids'])
    humans={x['human_decision']['record_id'] for x in history};excluded_ids={r['record_id'] for r in prior_excluded}
    human_posts={r['post_id'] for r in rows if r['record_id'] in humans|holdout and r['post_id']}
    seed=humans|holdout|held_ids|excluded_ids|{r['record_id'] for r in rows if 'DEVELOPMENT_TEST_EXCLUDED_OR_HOLDOUT_LINK' in r['eligibility_reasons']}
    seed|={r['record_id'] for r in originals if r['comment_id'] in held_comments or r['post_id'] and r['post_id'] in held_posts|info['candidate_post_ids']|human_posts}
    exclusions=[];usable=[];views=[]
    source_fields=('record_id','source_dataset','source_file','source_row','source_sha256','original_id','movie_id','post_id','post_url','comment_id','parent_comment_id','raw_sha256','master_group_id','master_review_flags','human_decisions','human_label')
    def exclusion(r,reasons,prior=False,target=''):
        return dict({k:r.get(k,'') for k in ('record_id','source_dataset','source_file','source_row','source_sha256','original_id','raw_sha256')},
            primary_reason=reasons[0],reasons=reasons,preexisting=prior,duplicate_representative_id=target,human_label=r.get('human_label',''))
    for r in prior_excluded:exclusions.append(exclusion(r,['SUSPECTED_TEMPLATE_BLOCK'],True))
    for r in rows:
        reasons=filter_row_reasons(r,legacy_max_characters,facebook_max_characters)
        text=minimal_filter_text(r['text_raw'])
        if not text and 'EMPTY_TEXT' not in reasons:reasons.append('EMPTY_AFTER_MINIMAL_VIEW')
        v=dict({k:r[k] for k in source_fields},text_raw=r['text_raw'],raw_characters=len(r['text_raw']),facebook_length_review=facebook_length_review(r),text_normalized=text,text_minimal=text,
            normalization_policy='NFC_EXACT_HTML_CRLF_NBSP_OUTER_TRIM',text_annotation=None,baseline_text=r['text_normalized'],source_text_variants=r['source_text_variants'])
        views.append(v)
        if reasons:exclusions.append(exclusion(r,reasons))
        else:usable.append(v)
    kept,duplicates,exact_groups,conflicts=strict_filter_dedup(usable)
    for r,target in duplicates:exclusions.append(exclusion(r,['EXACT_DUPLICATE'],target=target))
    # Preserve both raw aliases and historical guards; excluded template shadows
    # never enter the usable corpus. New exact/near groups are computed afresh.
    shadows=[dict(r,text_normalized=minimal_filter_text(r['text_raw']),baseline_text=r['text_raw']) for r in prior_excluded]
    combined=[*views,*shadows];policy=cfg['near_duplicate']
    _,_,raw_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_raw']) for r in combined],**policy)
    full_alias,_,full_near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in combined],**policy)
    old_edges=csv_rows((source/'direct_near_duplicates.local.csv').read_bytes())[0]
    blocked,_=cleaning_protection(combined,seed,[*raw_near['edges'],*full_near['edges'],*old_edges],('text_raw','baseline_text','text_normalized'))
    alias,alias_excess,near=duplicate_groups([dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in kept],**policy)
    alias_sizes=Counter(alias.values());pool=[];parents=defaultdict(list)
    for r in kept:
        if r['post_id'] and r['comment_id']:parents[(r['source_dataset'],r['post_id'],r['comment_id'])].append(r)
    for r in kept:
        rid=r['record_id'];parent=parents.get((r['source_dataset'],r['post_id'],r['parent_comment_id']),[]);r.update(layers(r,parent[0] if len(parent)==1 else None))
        # A dictionary match alone does not establish UI extraction evidence.
        if r['technical_status']=='EXCLUDE_EXACT_UI':r.update(technical_status='REVIEW_UI_UNCONFIRMED',final_quality_decision='REVIEW_PROPOSED')
        r.update(exact_group_id=exact_groups[rid],alias_group_id=alias[rid],near_duplicate_review=rid in near['neighbors'],
            normalized_alias_review=alias_sizes[alias[rid]]>1,is_protected=rid in blocked,
            needs_human_recheck=bool(r['human_label']) and (r['text_normalized']!=old_by[rid]['text_normalized'] or exact_groups[rid] in conflicts))
        reasons=[]
        if r['technical_status']!='VALID':reasons.append('TECHNICAL_REVIEW')
        if r['facebook_length_review']:reasons.append('FACEBOOK_LONG_REVIEW')
        if r['domain_status']!='IN_DOMAIN_CANDIDATE':reasons.append('DOMAIN_UNCONFIRMED')
        if r['spam_status']=='SPAM_CANDIDATE':reasons.append('SPAM_REVIEW_UNCONFIRMED')
        if r['human_decisions']:reasons.append('HUMAN_DECISION_PRESENT')
        if rid in blocked:reasons.append('DEVELOPMENT_TEST_OR_HOLDOUT_LINK')
        if r['near_duplicate_review']:reasons.append('NEAR_DUPLICATE_REVIEW')
        if r['normalized_alias_review']:reasons.append('CASE_OR_WHITESPACE_ALIAS_REVIEW')
        if exact_groups[rid] in conflicts:reasons.append('HUMAN_LABEL_CONFLICT_IN_EXACT_GROUP')
        if r['source_dataset']=='facebook' and not verified_post(r):reasons.append('FACEBOOK_IDENTITY_UNVERIFIED')
        if set(r['master_review_flags'])-{'TEXT_VARIANTS_RETAINED'}:reasons.append('SOURCE_IDENTITY_REVIEW')
        r['eligibility_reasons']=reasons;r['annotation_eligibility']='INELIGIBLE' if reasons else 'ELIGIBLE_PROPOSED'
        r['quality_status']='KEEP_PROPOSED' if r['final_quality_decision']=='KEEP_PROPOSED' and not any(x.endswith('_REVIEW') or x=='SPAM_REVIEW_UNCONFIRMED' for x in reasons) else 'REVIEW'
        r['provenance_status']='FACEBOOK_SOURCE_BOUND' if r['source_dataset']=='facebook' else 'LEGACY_UNVERIFIED_NOT_INDEPENDENT_TEST'
        del r['baseline_text'];del r['source_text_variants']
        if not reasons:pool.append(r)
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id'],text_view=r['text_normalized']) for r in pool],'pseudo_labeling')
    keep_ids={r['record_id'] for r in kept};new_exclusions=[e for e in exclusions if not e['preexisting']]
    if keep_ids&{e['record_id'] for e in exclusions} or len(kept)+len(new_exclusions)!=len(rows):raise AssertionError('Filter partition invalid')
    if any(r['text_raw']!=old_by[r['record_id']]['text_raw'] or r['human_decisions']!=old_by[r['record_id']]['human_decisions'] or r['human_label']!=old_by[r['record_id']]['human_label'] for r in kept):raise AssertionError('Raw or label mutation')
    summary=dict(status='FILTERED_CANDIDATE_QUALITY_REVIEW_PENDING',input_records=len(rows),records=len(kept),sources_before=dict(Counter(r['source_dataset'] for r in rows)),sources_after=dict(Counter(r['source_dataset'] for r in kept)),
        removed_from_canonical=len(new_exclusions),preexisting_exclusions=len(prior_excluded),exclusions_total=len(exclusions),primary_reasons=dict(Counter(r['primary_reason'] for r in new_exclusions)),
        all_reason_counts=dict(Counter(reason for r in new_exclusions for reason in r['reasons'])),legacy_max_characters=legacy_max_characters,facebook_max_characters=facebook_max_characters,
        facebook_length_counts={str(n):sum(r['source_dataset']=='facebook' and len(r['text_raw'])>n for r in rows) for n in (300,500,600,800,1000,1500)},
        facebook_review_characters=1000,facebook_long_review_records=sum(r['facebook_length_review'] for r in kept),
        historical_human_decisions=len(history),human_decisions_retained=sum(len(r['human_decisions']) for r in kept),human_sentiment_before=sum(bool(r['human_label']) for r in rows),
        human_sentiment_retained=sum(bool(r['human_label']) for r in kept),human_sentiment_distribution=dict(Counter(r['human_label'] for r in kept if r['human_label'])),human_labeled_needs_recheck=sum(r['needs_human_recheck'] for r in kept),
        proposed_annotation_pool=len(pool),pool_sources=dict(Counter(r['source_dataset'] for r in pool)),approved_annotation_pool=0,approved_training_labels=0,canonical_approved=False,active_pointer_updated=False,
        protected_records=sum(r['is_protected'] for r in kept),exact_duplicates_removed=len(duplicates),strict_exact_duplicates_remaining=0,normalized_alias_excess=len(alias_excess),near_duplicate_edges=near['summary']['direct_near_duplicate_edges'],near_duplicate_records=len(near['neighbors']),near_duplicates_removed=0,
        quality_counts=dict(Counter(r['quality_status'] for r in kept)),holdout=dict(original=len(holdout),retained=len(holdout&keep_ids),removed=len(holdout-keep_ids),resampled=False),
        changed_by_minimal_view=sum(r['text_raw']!=r['text_normalized'] for r in kept),logical_source_observations_verified=observations)
    pointer=ROOT/cfg['active_pointer'];pointer_before=sha(pointer) if pointer.exists() else None
    with staged(output) as out:
        write_jsonl(out/'candidate.local.jsonl',kept)
        csv_fields=['record_id','source_dataset','movie_id','post_id','post_url','comment_id','parent_comment_id','text_raw','text_minimal','raw_characters','facebook_length_review','human_label','quality_status','annotation_eligibility','is_protected','exact_group_id','source_file','source_row','source_sha256','original_id']
        write_csv(out/'comments.csv',kept,csv_fields)
        write_csv(out/'exclusions.csv',exclusions,['record_id','source_dataset','source_file','source_row','source_sha256','original_id','raw_sha256','primary_reason','reasons','preexisting','duplicate_representative_id','human_label'])
        write_jsonl(out/'human_history.local.jsonl',[dict(original_decision=x['human_decision'],retained_in_filtered=x['human_decision']['record_id'] in keep_ids) for x in history])
        write_csv(out/'annotation_candidates.local.csv',[dict(record_id=r['record_id'],text_view=r['text_normalized']) for r in pool],['record_id','text_view'])
        write_csv(out/'direct_near_duplicates.local.csv',sorted(near['edges'],key=lambda e:(e['left'],e['right'])),['left','right','method'])
        save(out/'protection.local.json',dict(protected_ids=sorted(blocked),retained_protected_ids=sorted(keep_ids&blocked),holdout_retained_ids=sorted(holdout&keep_ids),holdout_removed_ids=sorted(holdout-keep_ids),near_policy=near['summary']))
        sample=sorted([r for r in kept if r['record_id'] not in blocked],key=lambda r:(r['text_raw']==r['text_normalized'],r['record_id']))[:12]
        write_jsonl(out/'before_after_examples.local.jsonl',[dict(record_id=r['record_id'],text_raw=r['text_raw'],text_minimal=r['text_normalized']) for r in sample])
        save(out/'summary.json',summary);save(out/'protected_inputs.local.json',protected)
        save(out/'config.json',dict(source=str(source.resolve()),source_manifest_sha256=sha(source/'manifest.json'),legacy_max_characters=legacy_max_characters,facebook_max_characters=facebook_max_characters,facebook_review_characters=1000,
            strict_exact='case-sensitive minimal text equality; existing labeled identity first, then human decisions, Facebook, stable ID; no label transfer',
            normalization='NFC and exact valid HTML outside URL/email/code; CRLF/NBSP and outer trim only; internal spacing, emoji/emoticon/dash unchanged',near_policy=policy))
        check_protection(protected)
        if (sha(pointer) if pointer.exists() else None)!=pointer_before:raise AssertionError('Active pointer changed')
        seal(out,dict(status=summary['status'],source_manifest_sha256=sha(source/'manifest.json'),records=len(kept),implementation_sha256=sha(Path(__file__)),canonical_approved=False,active_pointer_updated=False))
    return summary


def post_url(value):
    """Strip tracking and comment anchors; retain only post identity parameters."""
    if not value: return ''
    try:
        canonical = facebook_url(value)
        parts = urlsplit(canonical); query = parse_qs(parts.query)
        query = {key: query[key][0] for key in ('story_fbid', 'id', 'fbid', 'v') if key in query}
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    except ValueError: return ''


def source_platform(row, role):
    """Explicit platform first; never identify a comment's platform from a movie name."""
    explicit=str(row.get('platform') or row.get('source_platform') or row.get('source') or '').strip().casefold()
    if explicit in {'facebook','momo','unknown'}:return explicit
    host=urlsplit(row.get('post_url') or row.get('url') or '').hostname
    if host in {'momo.vn','www.momo.vn'}:return 'momo'
    if host in {'facebook.com','www.facebook.com','m.facebook.com','web.facebook.com'}:return 'facebook'
    return 'unknown' if role in {'legacy_unverified','platform_export'} else 'facebook'


def platform_url(value, platform):
    if platform=='facebook':return post_url(value)
    if platform=='momo' and value:
        parts=urlsplit(value)
        if parts.scheme=='https' and parts.hostname in {'momo.vn','www.momo.vn'} and not parts.username and not parts.password:
            return urlunsplit(('https','www.momo.vn',parts.path.rstrip('/'),'', ''))
    return ''


def safe_files(roots, excluded=()):
    """Never descend into browser profiles, credentials, environments or symlinks."""
    excluded = [Path(p).resolve() for p in excluded]
    seen = set()
    for root in roots:
        root = Path(root).resolve()
        for base, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.lower().startswith(
                ('.venv', 'browser', 'chrome_profile', 'credentials', '.cache'))
                and not (Path(base)/d).is_symlink()
                and not any((Path(base)/d).resolve().is_relative_to(p) for p in excluded))
            for name in sorted(names):
                p = Path(base)/name
                sensitive = name.lower()
                if sensitive.startswith('.env') or any(term in sensitive for term in
                    ('credential','cookie','secret','api_key','access_token','refresh_token')): continue
                if p.is_symlink() or p.resolve() in seen: continue
                if p.suffix.lower() in {'.csv', '.json', '.jsonl', '.xlsx', '.zip'}:
                    seen.add(p.resolve()); yield p


def source_role(path, root, archive=False):
    name = path.name; rel = path.as_posix()
    if archive: return 'archive_export'
    if name == 'raw_comments.jsonl' and '/data/crawl_runs/' in rel: return 'raw_journal'
    if name == 'comments.csv' and ('/data/imports/' in rel or '/data/crawl_runs/' in rel): return 'export'
    if '/data/imports/' in rel and name in {'reviews.csv','reviews.json','reviews.jsonl','comments.json','comments.jsonl'}:
        return 'platform_export'
    if name == 'data_module1.csv' or (path.parent == root/'crawl' and path.suffix == '.csv'):
        return 'legacy_unverified'
    return 'derived_or_support_not_new_source'


def read_payload(payload, suffix):
    if suffix == '.csv': return csv_rows(payload)
    if suffix == '.jsonl':
        # An incomplete journal tail is inventoried, not silently truncated or merged.
        if payload and not payload.endswith(b'\n'): raise ValueError('Uncommitted JSONL tail')
        rows = [json.loads(line) for line in payload.decode('utf-8-sig').splitlines() if line.strip()]
    else:
        obj = json.loads(payload.decode('utf-8-sig'))
        rows = obj if isinstance(obj, list) else []
    if not all(isinstance(r, dict) for r in rows): return [], []
    return rows, sorted({k for r in rows for k in r})


def inventory(roots, root, excluded):
    entries, observations, inputs = [], [], {}

    def inspect(path, payload, suffix, role, container_sha=None):
        entry = dict(path=path, format=suffix[1:], sha256=digest(payload), bytes=len(payload), role=role,
                     rows=None, movies=None, posts=None, metadata=[], status='indexed')
        if container_sha: entry['archive_sha256'] = container_sha
        entries.append(entry)
        if suffix not in {'.csv', '.json', '.jsonl'}: return
        try:
            rows, fields = read_payload(payload, suffix)
            entry.update(rows=len(rows), metadata=[f for f in META if f in fields],
                         movies=len({r.get('movie_id') for r in rows if r.get('movie_id')}),
                         posts=len({r.get('post_id') for r in rows if r.get('post_id')}))
            key = next((k for k in TEXT_KEYS if k in fields), None)
            if not key: return
            entry['text_column'] = key
            if role == 'derived_or_support_not_new_source': return
            for number, row in enumerate(rows, 1):
                if not isinstance(row.get(key), str): raise ValueError('Nonliteral comment text')
                clean = row.get('text_without_mentions')
                mention = isinstance(clean, str) and row.get('text_extraction_version') == 'dom_text_v2'
                platform=source_platform(row,role)
                pid = str(row.get('post_id') or '')
                url = platform_url(row.get('post_url') or row.get('url') or '',platform)
                parsed = url_post_id(url) if url and platform=='facebook' else None
                identity_error = bool(pid and parsed and pid != parsed)
                source = str(row.get('source_dataset') or row.get('crawl_run_id') or path)
                observations.append(dict(text_raw=row[key], text_view=clean if mention else row[key],
                    mention_policy='existing_dom_text_v2' if mention else 'unchanged_no_name_guess',
                    source_dataset=source, source_file=path, source_row=number,
                    input_sha256=entry['sha256'], role=role,
                    **{k: str(row.get(k) or '') for k in META if k not in {'post_id', 'post_url','comment_id'}},
                    comment_id=str(row.get('comment_id') or (row.get('review_id') if platform=='momo' else '') or ''),
                    post_id=pid or (parsed or ''), post_url=url, metadata_identity_error=identity_error,
                    original_internal_id=str(row.get('internal_record_id') or ''),
                    original_label=row.get('overall', row.get('nhan_may', '')),
                    original_label_source='unverified_external' if 'overall' in row else ('legacy_machine' if row.get('nhan_may') else ''),
                    extraction_version=row.get('text_extraction_version', ''),
                    extraction_status=row.get('extraction_status', ''),
                    source_platform=platform,platform=platform,source=platform))
        except (ValueError, UnicodeError, csv_error()) as exc:
            entry['status'] = type(exc).__name__; entry['reason'] = 'Invalid or incomplete data; not silently repaired'
            # A malformed source must not contribute a partially read prefix.
            observations[:] = [r for r in observations if r['source_file'] != path]

    for path in safe_files(roots, excluded):
        relative = os.path.relpath(path, root).replace('\\', '/')
        try:
            checksum = sha(path); inputs[str(path.resolve())] = checksum
            if path.suffix.lower() == '.xlsx':
                # Workbook XML dimensions only; source CSV and reviewed canonical snapshot govern labels.
                with zipfile.ZipFile(path) as book:
                    import xml.etree.ElementTree as ET
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    sheets = []
                    for member in book.namelist():
                        if member.startswith('xl/worksheets/sheet') and member.endswith('.xml'):
                            xml = ET.fromstring(book.read(member))
                            sheets.append(dict(member=member, stored_rows=len(xml.findall('s:sheetData/s:row', ns))))
                entries.append(dict(path=relative, format='xlsx', sha256=checksum, bytes=path.stat().st_size,
                    role='workbook_copy_not_new_source', status='indexed_xml_dimensions_only', sheets=sheets,
                    rows=None, metadata=[], movies=None, posts=None))
            elif path.suffix.lower() == '.zip':
                entries.append(dict(path=relative, format='zip', sha256=checksum, bytes=path.stat().st_size,
                    role='archive_container', status='indexed', rows=None, metadata=[], movies=None, posts=None))
                with zipfile.ZipFile(path) as archive:
                    for item in archive.infolist():
                        # Inspect in memory only, without extracting potentially unsafe member paths.
                        if item.filename.endswith('.csv'):
                            inspect(relative+'!'+item.filename, archive.read(item), '.csv', 'archive_export', checksum)
            else: inspect(relative, path.read_bytes(), path.suffix.lower(), source_role(path, root))
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            entries.append(dict(path=relative, status='unreadable_'+type(exc).__name__, role='unprocessed',
                                rows=None, metadata=[], movies=None, posts=None))
    return entries, observations, inputs


def csv_error():
    import csv
    return csv.Error


def reconcile(observations, development, near_config):
    """Merge only corroborated source identity. Same text alone never merges rows."""
    buckets = defaultdict(list)
    for i, row in enumerate(observations):
        platform = row.get('source_platform', 'facebook')
        pid = row.get('post_id') or row.get('post_url', '')
        if row.get('metadata_identity_error'):
            key = ('identity_error', row['source_file'], row['source_row'])
        elif platform in {'facebook','momo'} and row.get('comment_id') and pid:
            key = (platform, 'cid_post', row['comment_id'], pid)
        elif platform in {'facebook','momo'} and row.get('original_internal_id') and pid:
            key = (platform, 'internal_post', row['original_internal_id'], pid)
        else: key = (platform, 'observation', row['source_file'], row['source_row'])
        buckets[key].append(row)
    records, conflicts = [], []
    for key, rows in sorted(buckets.items(), key=lambda pair: str(pair[0])):
        def priority(r):
            # Verified identity and explicit DOM mention extraction outrank completeness.
            # Timestamp/length never decides which observation is correct.
            return (-bool(r.get('post_url') and r.get('post_id') and not r.get('metadata_identity_error')),
                    -(r.get('extraction_version') == 'dom_text_v2'),
                    -(r.get('extraction_status') == 'complete'),
                    -sum(bool(r.get(k)) for k in META), r['source_file'], r['source_row'])
        chosen = min(rows, key=priority)
        variants = sorted({r['text_raw'] for r in rows})
        rid = 'm_'+digest(json.dumps(key, ensure_ascii=False, separators=(',', ':')))
        record = {k: chosen.get(k, '') for k in (*META, 'text_raw', 'source_dataset', 'source_file', 'source_row', 'source_platform')}
        record.update(platform=chosen['source_platform'],source=chosen['source_platform'])
        record.update(id=rid, text_view=chosen['text_view'], mention_policy=chosen.get('mention_policy', ''),
            annotation_status='UNLABELED', label='', label_source='', human_decisions=[], development_ids=[],
            development_groups=[], development=False, observations=rows, text_variants=variants,
            metadata_conflicts={}, metadata_alternatives={}, review_flags=[], original_labels=[dict(value=r['original_label'],
                source=r['original_label_source'], source_file=r['source_file'], source_row=r['source_row'])
                for r in rows if r.get('original_label') not in (None, '')])
        for field in META:
            values = sorted({r.get(field, '') for r in rows if r.get(field)})
            if not record[field] and len(values) == 1: record[field] = values[0]
            if len(values) > 1:
                record['metadata_alternatives'][field] = values
                # Multiple observation timestamps and URL aliases are expected across crawls.
                if field in {'post_id','movie_id','parent_comment_id'}: record['metadata_conflicts'][field] = values
        if len({normal(s) for s in variants}) > 1: record['review_flags'].append('TEXT_VARIANTS_RETAINED')
        if record['metadata_conflicts']: record['review_flags'].append('METADATA_CONFLICT')
        if any(r.get('metadata_identity_error') for r in rows): record['review_flags'].append('URL_POST_ID_CONFLICT')
        records.append(record)
    # Conflicting uses of a source ID are not silently collapsed across posts.
    by_cid = defaultdict(list)
    for row in records:
        if row['source_platform'] == 'facebook' and row['comment_id']: by_cid[row['comment_id']].append(row)
    for cid, rows in by_cid.items():
        if len(rows) > 1:
            for row in rows: row['review_flags'].append('COMMENT_ID_IDENTITY_UNRESOLVED')
            conflicts.append(dict(kind='COMMENT_ID_IDENTITY_UNRESOLVED', comment_id=cid, ids=[r['id'] for r in rows]))
    mapping = []
    for decision in development:
        matches = [r for r in by_cid.get(decision['comment_id'], []) if r['post_id'] == decision['post_id']
                   and not r['metadata_conflicts'].get('post_id') and 'URL_POST_ID_CONFLICT' not in r['review_flags']]
        if len(matches) != 1:
            raise ValueError('Development decision cannot be linked uniquely without identity guessing: '+decision['id'])
        row = matches[0]
        row['human_decisions'].append(dict(decision))  # Full original text/decision/review event retained.
        row['development_ids'].append(decision['id']); row['development_groups'].append(decision['group_id'])
        row['development'] = True
        mapping.append(dict(development_id=decision['id'], master_id=row['id'], original_group_id=decision['group_id']))
    for row in records:
        decisions = row['human_decisions']
        signatures = {(d['status'], d['label']) for d in decisions}
        if len(signatures) > 1:
            row['review_flags'].append('HUMAN_IDENTITY_LABEL_CONFLICT')
            conflicts.append(dict(kind='HUMAN_IDENTITY_LABEL_CONFLICT', ids=[row['id']]))
        elif decisions:
            row['annotation_status'], row['label'] = next(iter(signatures))
            row['label_source'] = 'human_single_annotator_development'
        elif row['original_labels']:
            row['label_source'] = 'unverified_or_machine_not_human'
    # Group every observed text variant, not just the selected rendering; bridges are transitive.
    uf = UnionFind([r['id'] for r in records]); seen = {}; variants = {}; text_owners = defaultdict(set)
    for row in records:
        keys = []
        for field in ('post_id', 'post_url', 'comment_id'):
            if row.get(field): keys.append((row['source_platform'], field, row[field]))
        for old in row['development_groups']: keys.append(('old_development_component', old))
        for text in [*row['text_variants'], row['text_view'], *(d['text_raw'] for d in row['human_decisions'])]:
            normalized = normal(text)
            if not normalized: continue
            key = digest(normalized); variants[key] = normalized; text_owners[key].add(row['id'])
            keys.append(('exact_text', key))
        for key in keys:
            if key in seen: uf.union(row['id'], seen[key])
            else: seen[key] = row['id']
    near_records = [dict(id=h, text=t, quality=dict(status='KEEP', duplicate_of=None)) for h, t in sorted(variants.items())]
    pairs = near_duplicate_candidates(near_records, near_config)
    for pair in pairs:
        left = min(text_owners[pair['left']]); right = min(text_owners[pair['right']])
        uf.union(left, right)
        pair.update(left_master_id=left, right_master_id=right)
    components = defaultdict(list)
    for row in records: components[uf.find(row['id'])].append(row['id'])
    group_ids = {key: 'mg_'+digest('\n'.join(sorted(ids))) for key, ids in components.items()}
    for row in records: row['group_id'] = group_ids[uf.find(row['id'])]
    # Same text with incompatible human labels needs review even across different source IDs.
    human_text = defaultdict(list)
    for row in records:
        for decision in row['human_decisions']: human_text[normal(decision['text_raw'])].append((row, decision))
    for key, items in human_text.items():
        if key and len({(d['status'], d['label']) for _, d in items}) > 1:
            ids = sorted({r['id'] for r, _ in items})
            conflicts.append(dict(kind='EXACT_TEXT_HUMAN_LABEL_CONFLICT', ids=ids))
            for row, _ in items: row['review_flags'].append('EXACT_TEXT_HUMAN_LABEL_CONFLICT')
    stats = dict(observations=len(observations), records=len(records),
        reconciled_identity_observations=len(observations)-len(records),
        exact_text_groups=sum(len(owners) > 1 for owners in text_owners.values()), near_duplicate_pairs=len(pairs),
        connected_groups=len(components), human_decisions=sum(len(r['human_decisions']) for r in records),
        human_labeled_records=sum(r['annotation_status'] == 'LABELED' for r in records),
        unverified_or_machine_records=sum(bool(r['original_labels']) for r in records),
        unlabeled_records=sum(r['annotation_status'] == 'UNLABELED' for r in records),
        metadata_present={k: sum(bool(r[k]) for r in records) for k in META},
        missing_required_metadata=sum(not all(r[k] for k in ('comment_id','post_id','post_url','movie_id')) for r in records),
        identity_unlinked_records=sum(not (r['source_platform']=='facebook' and r['comment_id'] and r['post_id']) for r in records),
        movies=len({r['movie_id'] for r in records if r['movie_id']}),
        posts=len({(r['source_platform'], r['post_id']) for r in records if r['post_id']}),
        source_datasets=len({o['source_dataset'] for r in records for o in r['observations']}),
        by_platform=dict(Counter(r['source_platform'] for r in records)),
        provenance_observations=sum(len(r['observations']) for r in records),
        label_counts=dict(Counter(r['label'] if r['annotation_status']=='LABELED' else r['annotation_status'] for r in records)))
    return records, mapping, pairs, conflicts, stats


def build(config_path, output):
    cfg = load(config_path); root = Path(cfg.get('repository_root', ROOT)).resolve()
    roots = [Path(p).resolve() for p in cfg['inventory_roots']]
    protected = {}
    for relative in cfg.get('protect_paths', []):
        target = root/relative
        if not target.exists(): raise ValueError('Required protected input missing: '+relative)
        paths = [target] if target.is_file() else sorted(p for p in target.rglob('*') if p.is_file())
        protected.update({str(p.resolve()): sha(p) for p in paths})
    reviewed = root/cfg['reviewed_root']
    from scripts.import_development_review import verify_files, verify_reviewed_dataset
    reviewed_manifest = load(reviewed/'manifest.json')
    if sha(reviewed/'manifest.json') != cfg['reviewed_manifest_sha256']: raise ValueError('Reviewed manifest changed')
    verify_files(reviewed, reviewed_manifest)
    development, _ = csv_rows((reviewed/'annotations.csv').read_bytes())
    verify_reviewed_dataset(reviewed, development, reviewed_manifest)
    if len(development) != cfg['expected_development_rows']: raise ValueError('Development row count changed')
    entries, observations, inputs = inventory(roots, root, [Path(output), root/'outputs/phase_g',
        root/'outputs/phase_g_support', root/'configs'])
    inputs.update(protected)
    missing = []
    for relative in cfg['expected_optional_sources']:
        if not (root/relative).exists(): missing.append(relative)
    records, mapping, pairs, conflicts, stats = reconcile(observations, development, cfg['near_duplicate'])
    # Record checksum-protected exposure evidence. Unknown posts are NOT attested unused.
    exposure = load(root/cfg['exposure_ledger'])
    exposure['evidence_source_checksums'] = {}
    evidence_posts = set(exposure.get('known_exposed_post_ids', []))
    def collect_ids(value):
        if isinstance(value, dict):
            if value.get('post_id'): evidence_posts.add(str(value['post_id']))
            for child in value.values(): collect_ids(child)
        elif isinstance(value, list):
            for child in value: collect_ids(child)
    for relative in exposure.get('previous_selection_pool_sources', []):
        path = root/relative
        if not path.is_file(): raise ValueError('Exposure evidence source missing: '+relative)
        exposure['evidence_source_checksums'][relative] = sha(path)
        collect_ids(load(path))
    exposure['known_exposed_post_ids'] = sorted(evidence_posts)
    exposed_posts = {str(p) for p in exposure.get('known_exposed_post_ids', [])}
    development_posts = {r['post_id'] for r in development}
    exposed_groups = {r['group_id'] for r in records if r['development'] or r['post_id'] in exposed_posts}
    for row in records:
        row['exposure_status'] = 'exposed_development_component' if row['group_id'] in exposed_groups else 'unknown_not_attested_unused'
    with staged(output) as work:
        write_jsonl(work/'master.jsonl', records)
        fields = ['id','text_raw','platform','source','source_platform','source_dataset','source_file','source_row',*META,'annotation_status','label','label_source','group_id',
                  'text_view','mention_policy','development_ids','exposure_status','review_flags']
        write_csv(work/'master.csv', records, list(dict.fromkeys(fields)))
        write_csv(work/'inventory.csv', entries, ['path','format','sha256','bytes','role','status','rows','movies','posts','metadata'])
        save(work/'inventory.json', entries); save(work/'quality_report.json', stats)
        save(work/'development_mapping.json', mapping); save(work/'near_duplicates.json', pairs)
        save(work/'conflicts.json', conflicts); save(work/'exposure_ledger.json', exposure)
        save(work/'human_review_history.json', load(reviewed/'review_history.json'))
        save(work/'config.json', cfg)
        changed = [path for path, checksum in inputs.items() if sha(path) != checksum]
        if changed: raise ValueError('Inventory input changed during build')
        manifest = seal(work, dict(schema_version='1.0', dataset_version=cfg['dataset_version'],
            phase='G', purpose='master_reconciliation_not_gold', status='MASTER_CREATED',
            inventory_roots=[str(p) for p in roots], sensitive_directories_not_read=True,
            inventory_exclusions=['browser profiles/credentials/environments', 'configs (not datasets)', 'Phase G own outputs/support'],
            protected_input_sha256=protected,
            input_sha256=inputs, config_sha256=sha(config_path), development_manifest_sha256=cfg['reviewed_manifest_sha256'],
            expected_optional_missing=missing, inaccessible=[e['path'] for e in entries if e['status'].startswith('unreadable')],
            original_development_post_ids=sorted(development_posts), source_scope='Accessible configured workspace only; other computers and sensitive directories not searched',
            **stats))
    return manifest
