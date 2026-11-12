"""Build the immutable filtered candidate from verified canonical raw lineage."""
from collections import Counter, defaultdict
import json
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from .common import ROOT, csv_rows, digest, load, save, seal, sha, staged, write_csv, write_jsonl, normal
from src.crawler.parser import facebook_url
from src.preprocessing import minimal_filter_text

TEXT_KEYS = ('text_raw', 'text', 'comment', 'body')

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
    from .common import check_protection
    from src.data.split import protection_set,duplicate_groups
    from src.data.quality import layers,verified_post,UI
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
