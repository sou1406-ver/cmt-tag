"""Human quality validation tooling; no preprocessing changes or automatic release."""
from collections import Counter,defaultdict
import random
from .common import ROOT,load,save,sha,verify,staged,seal,read_jsonl,write_jsonl,write_csv,csv_rows
from .unified import protection,check_protection
from .phase_i3 import held
from .format_workbook import validate as validate_format
from .quality_workbook import read_sheet

DOMAINS={'IN_DOMAIN','OFF_TOPIC','CONTEXT_REQUIRED','UNSURE'}


def source_description(row):
    if row['source_dataset']!='facebook':return 'legacy: original platform/source unverified'
    if all(row.get(k) for k in ('comment_id','post_id','post_url')):return 'facebook: comment/post metadata present; no independence attestation'
    if row.get('post_id'):return 'facebook: post metadata only; comment/URL identity incomplete'
    return 'facebook archive: post identity unavailable'


def proposal(row):
    old=row['domain_status'];evidence=row.get('domain_evidence',[])
    # Metadata alone cannot establish comment-level relevance.
    domain=({'IN_DOMAIN_LIKELY':'IN_DOMAIN','OFF_TOPIC_LIKELY':'OFF_TOPIC',
             'CONTEXT_NEEDED':'CONTEXT_REQUIRED','UNCERTAIN':'UNCERTAIN'}.get(old,'UNCERTAIN'))
    if evidence==['VERIFIED_FILM_POST_METADATA']:domain='UNCERTAIN'
    return dict(proposed_domain_status=domain,proposal_status='PROPOSED_UNVALIDATED',
        proposed_quality_reason='; '.join(row['quality_reason_code']+evidence),
        format_status=row['format_status'],technical_status=row['technical_quality_status'],
        domain_status='PROPOSED_'+domain,spam_status='PROPOSED_REPETITION_RISK' if row['repetition_risk'] else 'NOT_FLAGGED_UNVALIDATED',
        annotation_eligibility='PENDING_HUMAN_REVIEW')


def sample(rows,seed,keep_count=50,total=200):
    rng=random.Random(seed);groups=defaultdict(list)
    for r in sorted(rows,key=lambda x:x['record_id']):
        if r['quality_status']=='KEEP':key='KEEP_RANDOM'
        else:key='|'.join(map(str,(r['source_dataset'],r['proposed_domain_status'],r['repetition_risk'],
             bool(r.get('movie_id') and r.get('post_id')),len(r['text_clean'])<=32,len(r['text_clean'])>1000,
             r['text_raw']!=r['text_clean'])))
        groups[key].append(r)
    keep=groups.pop('KEEP_RANDOM',[])
    if len(keep)<keep_count:raise ValueError('Insufficient random KEEP frame')
    selected=[];manifest=[]
    def draw(key,values,n):
        picked=rng.sample(values,n);prob=n/len(values)
        for r in picked:selected.append(dict(r,sampling_stratum=key,inclusion_probability=prob))
        manifest.append(dict(stratum=key,frame=len(values),selected=n,inclusion_probability=prob))
    draw('KEEP_RANDOM',keep,keep_count)
    quotas=Counter();keys=sorted(groups);rng.shuffle(keys)
    while sum(quotas.values())<total-keep_count:
        changed=False
        for key in keys:
            if quotas[key]<len(groups[key]):quotas[key]+=1;changed=True
            if sum(quotas.values())==total-keep_count:break
        if not changed:raise ValueError('Insufficient REVIEW frame')
    for key in keys:draw(key,groups[key],quotas[key])
    rng.shuffle(selected)
    return selected,manifest


def domain_metrics(rows):
    if not rows or any(r.get('human_domain_decision') not in DOMAINS for r in rows):
        raise ValueError('Metrics require genuine, complete human domain decisions')
    matrix=defaultdict(Counter);by_source=defaultdict(Counter);tp=fp=fn=0;keep_off_topic=0;false_exclusions=0;spam=Counter()
    for r in rows:
        predicted=r['proposed_domain_status'];human=r['human_domain_decision']
        matrix[predicted][human]+=1;by_source[r['source_dataset']][human]+=1
        if human in ('IN_DOMAIN','OFF_TOPIC'):
            tp+=predicted=='OFF_TOPIC' and human=='OFF_TOPIC'
            fp+=predicted=='OFF_TOPIC' and human=='IN_DOMAIN'
            fn+=predicted!='OFF_TOPIC' and human=='OFF_TOPIC'
        keep_off_topic+=r['quality_status']=='KEEP' and human=='OFF_TOPIC'
        note=r.get('human_note','').strip()
        marker=next((m for m in ('[SPAM]','[NOT_SPAM]','[SPAM_UNSURE]') if note.startswith(m)),None)
        if marker:spam[marker]+=1
        false_exclusions+=r['quality_status']=='EXCLUDE' and human=='IN_DOMAIN' and marker=='[NOT_SPAM]'
    return dict(rows=len(rows),confusion={k:dict(v) for k,v in matrix.items()},human_by_source={k:dict(v) for k,v in by_source.items()},
        off_topic_precision=tp/(tp+fp) if tp+fp else None,off_topic_recall=tp/(tp+fn) if tp+fn else None,
        off_topic_binary_support=sum(r['human_domain_decision'] in ('IN_DOMAIN','OFF_TOPIC') for r in rows),
        context_and_unsure_abstained=sum(r['human_domain_decision'] not in ('IN_DOMAIN','OFF_TOPIC') for r in rows),
        off_topic_in_keep=keep_off_topic,false_exclusions=false_exclusions,human_spam_note_markers=dict(spam),
        interpretation='unweighted reviewed-sample diagnostics; not natural corpus prevalence/accuracy')


def format_summary(workbook,coordinator):
    rows=validate_format(workbook,coordinator);counts=Counter(r['format_decision'] or 'BLANK' for r in rows)
    result=dict(rows=len(rows),counts=dict(counts),status='COMPLETE' if not counts['BLANK'] else 'PENDING_HUMAN_FORMAT_REVIEW',
                accept_rate_in_targeted_sample=None,by_source={},by_rule={},by_confidence_category={},population_accuracy=None)
    if counts['BLANK']:return result
    expected={r['record_id']:r for r in load(coordinator)};source=defaultdict(Counter);rules=defaultdict(Counter);categories=defaultdict(Counter)
    for r in rows:
        e=expected[r['id']];source[e['source_dataset']][r['format_decision']]+=1
        for rule in {x['rule'] for x in e['transform_events']+e['format_evidence']}:rules[rule][r['format_decision']]+=1
        for category in {x['confidence_category'] for x in e['format_evidence']}:categories[category][r['format_decision']]+=1
    result.update(accept_rate_in_targeted_sample=counts['ACCEPT']/len(rows),by_source={k:dict(v) for k,v in source.items()},by_rule={k:dict(v) for k,v in rules.items()},by_confidence_category={k:dict(v) for k,v in categories.items()})
    return result


def validate_domain_workbook(path,coordinator,complete=False):
    verify(coordinator.parent)
    contract=load(coordinator);expected={r['record_id']:r for r in contract['rows']}
    headers,rows,_=read_sheet(path,'Review');_,rawrows,_=read_sheet(path,'Raw & Evidence')
    if headers!=['id','text_annotation','proposed_domain_status','proposed_quality_reason','human_domain_decision','human_note']:raise ValueError('Wrong semantic review schema')
    for values in (rows,rawrows):
        if len(values)!=len(expected) or len({r['id'] for r in values})!=len(expected) or {r['id'] for r in values}!=set(expected):raise ValueError('Wrong IDs')
    literal=lambda s:s[1:] if s.startswith("'=") else s
    for r in rows:
        e=expected[r['id']]
        for key in ('text_annotation','proposed_domain_status','proposed_quality_reason'):
            if literal(r[key])!=e[key]:raise ValueError('Text/proposal edited or truncated')
        if r['human_domain_decision'] not in DOMAINS|{''}:raise ValueError('Sentiment is not a domain decision')
        if complete and not r['human_domain_decision']:raise ValueError('Human domain review incomplete')
    for r in rawrows:
        e=expected[r['id']]
        if any(literal(r[k])!=e[k] for k in ('text_raw','text_clean','source_view')):raise ValueError('Raw/evidence source edited')
        if literal(r['evidence'])!=e['evidence']:raise ValueError('Evidence edited')
    return rows,contract


def import_domain(path,coordinator,output):
    rows,contract=validate_domain_workbook(path,coordinator,complete=True)
    expected={r['record_id']:r for r in contract['rows']}
    enriched=[dict(expected[r['id']],id=r['id'],human_domain_decision=r['human_domain_decision'],human_note=r['human_note']) for r in rows]
    metrics=domain_metrics(enriched)
    with staged(output) as out:
        write_csv(out/'human_domain_decisions.local.csv',enriched,['id','human_domain_decision','human_note'])
        save(out/'metrics.json',metrics)
        seal(out,dict(status='HUMAN_DOMAIN_REVIEW_IMPORTED',rows=len(rows),input_sha256=sha(path),coordinator_sha256=sha(coordinator),
            source_manifest_sha256=contract['source_manifest_sha256'],pilot_ready=False,sentiment_labels_changed=False))
    return metrics


def require_release(format_import,domain_import,holdout_import,approval_path,source_manifest):
    approval=load(approval_path)
    flags=['approved','format_issues_resolved','domain_issues_resolved','independent_quality_holdout_approved']
    if any(approval.get(k) is not True for k in flags) or not approval.get('reviewer') or not approval.get('approved_at'):raise ValueError('Explicit human quality approval and issue resolution required')
    artifacts=[verify(p) for p in (format_import,domain_import,holdout_import)]
    if artifacts[0].get('status')!='HUMAN_FORMAT_REVIEW_IMPORTED' or artifacts[1].get('status')!='HUMAN_DOMAIN_REVIEW_IMPORTED' or artifacts[2].get('status')!='HUMAN_DOMAIN_REVIEW_IMPORTED':raise ValueError('Real human imports required')
    if artifacts[0]['rows']!=200 or artifacts[1]['rows']!=200 or artifacts[2]['rows']<40:raise ValueError('Complete reviews and quality holdout required')
    for name,path in [('format',format_import),('domain',domain_import),('holdout',holdout_import)]:
        if approval.get(name+'_import_manifest_sha256')!=sha(path/'manifest.json'):raise ValueError('Approval/import checksum mismatch')
    if approval.get('source_manifest_sha256')!=sha(source_manifest):raise ValueError('Approval/corpus checksum mismatch')
    if any(m.get('source_manifest_sha256')!=sha(source_manifest) for m in artifacts[1:]):raise ValueError('Domain/holdout corpus mismatch')
    dev,_=csv_rows((domain_import/'human_domain_decisions.local.csv').read_bytes());hold,_=csv_rows((holdout_import/'human_domain_decisions.local.csv').read_bytes())
    if {r['id'] for r in dev}&{r['id'] for r in hold}:raise ValueError('Quality holdout intersects development review')
    return 'HUMAN_APPROVED_FOR_ANNOTATION'


def export_approved_inputs(source,format_import,domain_import,holdout_import,approval_path,candidate_path,output):
    """Future export is fail-closed; never invoked during pending I.4 preparation."""
    state=require_release(format_import,domain_import,holdout_import,approval_path,source/'manifest.json')
    verify(source);approval=load(approval_path)
    if approval.get('candidate_sha256')!=sha(candidate_path):raise ValueError('Candidate approval checksum mismatch')
    candidates,fields=csv_rows(candidate_path.read_bytes())
    if fields!=['id','text_annotation'] or len(candidates)!=500 or len({r['id'] for r in candidates})!=500:raise ValueError('Exact 500-row blind schema required')
    corpus={r['record_id']:r for r in read_jsonl(source/'corpus.local.jsonl')};selected=[]
    for candidate in candidates:
        r=corpus[candidate['id']]
        if candidate['text_annotation']!=r['text_annotation'] or not r['annotation_eligibility'] or r['human_decisions'] or held(r):raise ValueError('Candidate ineligible or changed')
        selected.append(r)
    if len({r['duplicate_group_id'] for r in selected})!=500:raise ValueError('Exact duplicates in release')
    ids={r['record_id'] for r in selected};edges,_=csv_rows((source/'direct_near_duplicates.local.csv').read_bytes())
    if any(e['left'] in ids and e['right'] in ids for e in edges):raise ValueError('Direct-near duplicates in release')
    from .blind import assert_allowed
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in selected],'pseudo_labeling')
    with staged(output) as out:
        for provider in ('codex','claude','gemini'):write_csv(out/f'{provider}_input.csv',candidates,fields)
        if len({sha(out/f'{provider}_input.csv') for provider in ('codex','claude','gemini')})!=1:raise AssertionError('Blind outputs differ')
        return seal(out,dict(status=state,rows=500,approval_sha256=sha(approval_path),source_manifest_sha256=sha(source/'manifest.json'),
                            guideline_sha256=sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md')))


def build(config,output):
    import json
    cfg=load(config);source=ROOT/cfg['source'];verify(source);snapshot=protection(cfg['protect_paths'])
    fmt=format_summary(ROOT/cfg['format_workbook'],ROOT/cfg['format_coordinator'])
    rows=read_jsonl(source/'corpus.local.jsonl');format_ids={r['record_id'] for r in load(ROOT/cfg['format_coordinator'])}
    protected_ids={r['record_id'] for r in rows if held(r)}|format_ids
    protected_groups={r['duplicate_group_id'] for r in rows if r['record_id'] in protected_ids}
    protected_ids|={r['record_id'] for r in rows if r['duplicate_group_id'] in protected_groups}
    edges,_=csv_rows((source/'direct_near_duplicates.local.csv').read_bytes());neighbors=defaultdict(set)
    for e in edges:neighbors[e['left']].add(e['right']);neighbors[e['right']].add(e['left'])
    frame=[];seen=set()
    for row in sorted(rows,key=lambda r:r['record_id']):
        if row['record_id'] in protected_ids or neighbors[row['record_id']]&protected_ids or row['duplicate_group_id'] in seen:continue
        seen.add(row['duplicate_group_id']);r=dict(row);r.update(proposal(row))
        r['source_view']=source_description(row)
        r['evidence']=json.dumps({k:r[k] for k in ['proposal_status','domain_evidence','format_status','technical_status','spam_status','repetition_ratio','repeated_block_count']},ensure_ascii=False,sort_keys=True)
        frame.append(r)
    chosen,design=sample(frame,cfg['seed'],cfg['random_keep_count'],cfg['review_count'])
    review_ids={r['record_id'] for r in chosen};review_groups={r['duplicate_group_id'] for r in chosen}
    review_posts={r['post_id'] for r in chosen if r['source_dataset']=='facebook' and r['post_id']}
    hold_frame=[r for r in frame if r['record_id'] not in review_ids and r['duplicate_group_id'] not in review_groups and not(neighbors[r['record_id']]&review_ids)
        and not(r['source_dataset']=='facebook' and r['post_id'] in review_posts)]
    rng=random.Random(cfg['seed']+1);holdout=rng.sample(hold_frame,min(cfg['holdout_count'],len(hold_frame)))
    readiness=dict(preparation_state='TECHNICALLY_PREPARED',release_state='PENDING_HUMAN_REVIEW',human_approved=False,
        total_records=len(rows),technical_keep=sum(r['technical_quality_status']=='KEEP' for r in rows),
        plain_or_protected=sum(r['format_status']=='PLAIN_OR_PROTECTED' for r in rows),unresolved_format=sum(r['format_status']=='NEEDS_REVIEW' for r in rows),
        heuristic_candidate_pool=sum(r['annotation_eligibility'] for r in rows),human_decisions=sum(len(r['human_decisions']) for r in rows),
        human_sentiment_rows=sum(bool(r['human_label']) for r in rows),format_review=fmt,domain_human_review_rows=0,
        domain_metrics=None,spam_human_verified=False,official_inputs_exported=False,
        blockers=['Human format review incomplete' if fmt['status']!='COMPLETE' else 'Format findings need explicit approval','Human domain/spam audit missing','Independent quality holdout not human-validated','Explicit corpus release approval missing'])
    with staged(output) as out:
        save(out/'format_validation_summary.json',fmt);save(out/'corpus_readiness.json',readiness)
        contract=dict(rows=chosen,source_manifest_sha256=sha(source/'manifest.json'),status='PROPOSED_UNVALIDATED',fields=['id','text_annotation'])
        save(out/'workbook_input.local.json',contract);save(out/'sampling_manifest.local.json',dict(seed=cfg['seed'],frame=len(frame),design=design,
            unit='one exact-duplicate representative; non-test and disjoint from I.3 format-review text/direct-near IDs',method='disjoint random KEEP plus stratified REVIEW; n_h/N_h inclusion probabilities',
            selected_ids=sorted(review_ids),holdout_ids=[r['record_id'] for r in holdout],holdout_rows=len(holdout),holdout_frame=len(hold_frame),
            holdout_purpose='development quality-rule holdout, not independent sentiment gold test; legacy post independence unknown'))
        write_jsonl(out/'semantic_review_coordinator.local.jsonl',chosen)
        save(out/'quality_holdout_reservation.local.json',dict(ids=[r['record_id'] for r in holdout],source_manifest_sha256=sha(source/'manifest.json'),labels_created=False))
        save(out/'protected_inputs.local.json',snapshot);save(out/'config.json',cfg)
        check_protection(snapshot);return seal(out,dict(phase='I.4',status='PENDING_HUMAN_REVIEW',review_rows=len(chosen),holdout_rows=len(holdout),format_status=fmt['status'],source_manifest_sha256=sha(source/'manifest.json'),code_sha256=sha(ROOT/'src/dataset/phase_i4.py')))
