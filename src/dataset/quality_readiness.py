"""Phase J: local quality proposals and review handoff; never infer corpus approval."""
from collections import Counter,defaultdict
import json
import re
from pathlib import Path
from .common import ROOT,load,save,sha,digest,verify,staged,seal,read_jsonl,write_jsonl,write_csv,csv_rows
from .unified import protection,check_protection
from .phase_i import duplicate_groups
from .phase_i3 import held
from .phase_i4 import validate_domain_workbook,DOMAINS
from .format_workbook import validate as validate_format
from .normalization_workbook import validate as validate_normalization
from .repetition import repetition_signals
from .semantic_quality import FILM,AD
from src.crawler.parser import post_id as parsed_post_id

SPAM={'SPAM','NOT_SPAM','SPAM_UNSURE'}
UI={s.casefold() for s in load(ROOT/'configs/phase_i.json')['exact_ui_strings']}


def spam_marker(note):
    match=re.match(r'^\[(SPAM|NOT_SPAM|SPAM_UNSURE)\](?:\s|$)',note.strip())
    return match[1] if match else ''


def verified_post(row):
    # Available metadata is an identity link, not an unused-source attestation.
    if row.get('source_dataset')!='facebook' or not all(row.get(k) for k in ('post_id','post_url','comment_id')):return ''
    try:return str(row['post_id']) if parsed_post_id(row['post_url'])==str(row['post_id']) else ''
    except ValueError:return ''


def layers(row,parent=None):
    text=row['text_normalized'];technical='VALID';reasons=[]
    if not text.strip():technical='EXCLUDE_EMPTY';reasons.append('EMPTY_TEXT')
    elif text.strip().casefold() in UI:technical='EXCLUDE_EXACT_UI';reasons.append('EXACT_KNOWN_UI')
    elif '\ufffd' in text:technical='REVIEW_ENCODING';reasons.append('REPLACEMENT_CHARACTER')
    elif any('TRUNCAT' in x or 'CORRUPT' in x for x in row.get('quality_reasons',[]) if isinstance(x,str)):
        technical='REVIEW_CORRUPTION';reasons.append('SOURCE_CORRUPTION_FLAG')
    elif not re.search(r'\w',text):technical='REVIEW_NON_TEXT';reasons.append('NON_TEXT_CONTEXT_REQUIRED')
    rep=repetition_signals(text)
    advertising=len(AD.findall(text))>=2
    spam='SPAM_CANDIDATE' if rep['repetition_risk'] or advertising else 'NOT_FLAGGED_UNVALIDATED'
    evidence=[]
    if FILM.search(text):domain='IN_DOMAIN_CANDIDATE';evidence.append('FILM_CONTENT_CUE')
    elif row.get('parent_comment_id') and len(text)<=80:
        domain='CONTEXT_REQUIRED';evidence.append('SHORT_REPLY')
        if parent is not None and FILM.search(parent['text_normalized']):evidence.append('LINKED_PARENT_FILM_CUE_NOT_CHILD_CONFIRMATION')
    elif advertising:domain='OFF_TOPIC_CANDIDATE';evidence.append('MULTIPLE_AD_CUES_UNVALIDATED')
    else:domain='UNCERTAIN';evidence.append('INSUFFICIENT_COMMENT_EVIDENCE')
    if verified_post(row):evidence.append('POST_IDENTITY_PRESENT_NOT_DOMAIN_PROOF')
    return dict(technical_status=technical,domain_status=domain,domain_evidence=evidence,spam_status=spam,
        technical_reasons=reasons,structural_spam_reasons=(['REPETITION_SIGNAL'] if rep['repetition_risk'] else [])+(['ADVERTISING_CUES'] if advertising else []),
        repetition_diagnostics=rep,final_quality_decision='EXCLUDE_TECHNICAL' if technical.startswith('EXCLUDE_') else 'KEEP_PROPOSED' if technical=='VALID' and domain=='IN_DOMAIN_CANDIDATE' and spam=='NOT_FLAGGED_UNVALIDATED' else 'REVIEW_PROPOSED')


def quality_metrics(rows):
    """Unweighted sample diagnostics, abstention-aware, domain separate from spam."""
    if not rows or any(r.get('human_domain_decision') not in DOMAINS or r.get('human_spam_decision') not in SPAM for r in rows):
        raise ValueError('Complete real human domain AND spam decisions required')
    def measure(values):
        domain=defaultdict(Counter);spam=defaultdict(Counter);tp=fp=fn=stp=sfp=sfn=fkeep=fexclude=0
        for r in values:
            p=r['domain_status'];h=r['human_domain_decision'];s=r['human_spam_decision'];sp=r['spam_status']=='SPAM_CANDIDATE'
            domain[p][h]+=1;spam[r['spam_status']][s]+=1
            if h in ('IN_DOMAIN','OFF_TOPIC'):
                tp+=p=='OFF_TOPIC_CANDIDATE' and h=='OFF_TOPIC';fp+=p=='OFF_TOPIC_CANDIDATE' and h=='IN_DOMAIN';fn+=p!='OFF_TOPIC_CANDIDATE' and h=='OFF_TOPIC'
            if s in ('SPAM','NOT_SPAM'):
                stp+=sp and s=='SPAM';sfp+=sp and s=='NOT_SPAM';sfn+=not sp and s=='SPAM'
            fkeep+=r['final_quality_decision']=='KEEP_PROPOSED' and h=='OFF_TOPIC'
            fexclude+=r['final_quality_decision']=='EXCLUDE_TECHNICAL' and h=='IN_DOMAIN' and s=='NOT_SPAM'
        ratio=lambda a,b:a/b if b else None
        return dict(rows=len(values),domain_confusion={k:dict(v) for k,v in domain.items()},spam_confusion={k:dict(v) for k,v in spam.items()},
            off_topic_precision=ratio(tp,tp+fp),off_topic_recall=ratio(tp,tp+fn),spam_precision=ratio(stp,stp+sfp),spam_recall=ratio(stp,stp+sfn),
            domain_binary_support=sum(r['human_domain_decision'] in ('IN_DOMAIN','OFF_TOPIC') for r in values),
            spam_binary_support=sum(r['human_spam_decision'] in ('SPAM','NOT_SPAM') for r in values),false_keep=fkeep,false_exclude=fexclude)
    strata=defaultdict(list)
    for row in rows:
        for key in ('source:'+row['source_dataset'],'length:'+('short' if len(row['text_view'])<=32 else 'long' if len(row['text_view'])>1000 else 'middle'),
                    'domain:'+row['domain_status'],'repetition:'+str(row['repetition_diagnostics']['repetition_risk'])):strata[key].append(row)
    return dict(overall=measure(rows),strata={k:measure(v) for k,v in strata.items()},interpretation='unweighted sample diagnostics; no corpus prevalence claim; do not tune on reserved holdout')


def isolation(rows,review_ids,holdout_ids,edges,groups):
    by={r['record_id']:r for r in rows};review_ids=set(review_ids);holdout_ids=set(holdout_ids)
    pair_overlap=sum((e['left'] in review_ids and e['right'] in holdout_ids) or (e['right'] in review_ids and e['left'] in holdout_ids) for e in edges)
    rp={verified_post(by[i]) for i in review_ids}-{''};hp={verified_post(by[i]) for i in holdout_ids}-{''}
    return dict(record_overlap=len(review_ids&holdout_ids),exact_group_overlap=len({groups[i] for i in review_ids}&{groups[i] for i in holdout_ids}),
        direct_near_overlap=pair_overlap,verified_post_overlap=len(rp&hp),holdout_identity_incomplete=sum(not verified_post(by[i]) for i in holdout_ids))


def review_contract(rows,kind,source,original=None):
    return dict(kind=kind,normalization_version='plain_text_v3_1',source_manifest_sha256=sha(source/'manifest.json'),
        rows=rows,status='PENDING_QUALITY_HOLDOUT' if kind=='holdout' else 'PENDING_HUMAN_DOMAIN_SPAM_REVIEW',
        original_workbook_sha256=sha(original) if original else None)


def build(config,output):
    cfg=load(config);source=ROOT/cfg['source'];verify(source);snapshot=protection(cfg['protect_paths'])
    rows=read_jsonl(source/'corpus_proposals.local.jsonl');original={r['record_id']:(r['text_raw'],r['human_decisions'],r['human_label'],r['text_annotation']) for r in rows}
    if len(rows)!=39842 or sum(len(r['human_decisions']) for r in rows)!=650 or sum(bool(r['human_label']) for r in rows)!=532:raise ValueError('Corpus/human contract changed')
    fmt=validate_format(ROOT/cfg['format_workbook'],ROOT/cfg['format_coordinator'])
    domain,old_contract=validate_domain_workbook(ROOT/cfg['domain_workbook'],ROOT/cfg['domain_coordinator'])
    norm=validate_normalization(ROOT/cfg['normalization_workbook'],ROOT/cfg['normalization_coordinator'])
    format_expected={r['record_id']:r for r in load(ROOT/cfg['format_coordinator'])}
    old_expected={r['record_id']:r for r in old_contract['rows']}
    hold_ids=load(ROOT/cfg['holdout_reservation'])['ids']
    if len(hold_ids)!=40 or len(set(hold_ids))!=40:raise ValueError('Exact original 40 reservation IDs required')
    statuses={name:dict(rows=len(values),decisions=dict(Counter(r[field] or 'BLANK' for r in values)),missing=sum(not r[field] for r in values),workbook_sha256=sha(ROOT/cfg[name+'_workbook']))
        for name,values,field in [('format',fmt,'format_decision'),('domain',domain,'human_domain_decision'),('normalization',norm,'human_decision')]}
    statuses['spam']=dict(rows=200,decisions=dict(Counter(spam_marker(r['human_note']) or 'BLANK' for r in domain)),missing=sum(not spam_marker(r['human_note']) for r in domain))
    by={r['record_id']:r for r in rows};parents=defaultdict(list)
    for r in rows:
        if r.get('comment_id'):parents[(r['source_dataset'],r.get('post_id'),r['comment_id'])].append(r)
    # Holdout text is never sent to the domain/spam proposal function or rule development.
    all_quality_review_ids={r['id'] for r in domain}|{r['id'] for r in fmt}|{r['id'] for r in norm}
    views=[dict(record_id=r['record_id'],text_clean=r['text_normalized']) for r in rows]
    groups,exact,near=duplicate_groups(views,threshold=.9,min_chars=40,shingle_size=3,max_posting=256)
    old_edges,_=csv_rows((ROOT/'outputs/phase_i3/v3/direct_near_duplicates.local.csv').read_bytes())
    checks=isolation(rows,all_quality_review_ids,hold_ids,near['edges']+old_edges,groups)
    isolation_ok=not any(checks[k] for k in ('record_overlap','exact_group_overlap','direct_near_overlap','verified_post_overlap'))
    protected_ids={r['record_id'] for r in rows if r['human_decisions'] or held(r)}|set(hold_ids)
    protected_posts={verified_post(by[i]) for i in protected_ids}-{''}
    # Conservatively quarantine known post IDs even if the source lacks full identity metadata.
    protected_posts|={str(by[i]['post_id']) for i in protected_ids if by[i]['source_dataset']=='facebook' and by[i].get('post_id')}
    protected_groups={groups[i] for i in protected_ids}
    protected_old={by[i]['duplicate_group_id'] for i in protected_ids}
    protected_ids|={r['record_id'] for r in rows if groups[r['record_id']] in protected_groups or r['duplicate_group_id'] in protected_old or (r['source_dataset']=='facebook' and str(r.get('post_id','')) in protected_posts)}
    edges=near['edges']+old_edges;neighbors=defaultdict(set)
    for e in edges:neighbors[e['left']].add(e['right']);neighbors[e['right']].add(e['left'])
    delta=[];migrated=[];holdout=[];pool=[]
    for row in rows:
        rid=row['record_id'];row['quality_status_i3']=row['quality_status'];row['domain_status_i3']=row['domain_status']
        if rid in hold_ids:
            row.update(technical_status='RESERVED_NOT_ASSESSED',domain_status='UNCERTAIN',spam_status='RESERVED_NOT_ASSESSED',
                       final_quality_decision='RESERVED_QUALITY_HOLDOUT',annotation_eligibility='INELIGIBLE',eligibility_reasons=['quality_holdout'])
        else:
            linked=parents.get((row['source_dataset'],row.get('post_id'),row.get('parent_comment_id')),[])
            parent=linked[0] if len(linked)==1 else None
            row.update(layers(row,parent));reason=[]
            # Preserve identity/leakage guards; only re-assess format/quality with the fixed candidate.
            reason.extend(x for x in row['eligibility_reasons'] if x not in ('quality_review','format_unresolved'))
            if row['human_decisions']:reason.append('human')
            if held(row):reason.append('test_protection')
            if row['source_dataset']=='facebook' and not verified_post(row):reason.append('unverified_facebook_identity')
            if rid in protected_ids or neighbors[rid]&protected_ids:reason.append('protected_identity_or_duplicate')
            if rid in exact:reason.append('exact_duplicate')
            if row['technical_status']!='VALID':reason.append('technical_review')
            if row['remaining_format_tokens'] or row['normalization_flags']:reason.append('format_unresolved')
            if row['domain_status']!='IN_DOMAIN_CANDIDATE':reason.append('domain_unconfirmed_candidate')
            if row['spam_status']=='SPAM_CANDIDATE':reason.append('structural_spam_review')
            if rid in all_quality_review_ids:reason.append('quality_review_exposure')
            row['eligibility_reasons']=sorted(set(reason));row['annotation_eligibility']='ELIGIBLE_PROPOSED' if not reason else 'INELIGIBLE'
            if not reason:pool.append(row)
        row['annotation_approval_transferred']=False
    # Same 200 semantic IDs, no resampling. Decisions carry only for byte-identical text.
    for d in domain:
        r=by[d['id']];old=old_expected[d['id']];same=r['text_normalized']==old['text_annotation']
        entry=dict(record_id=r['record_id'],text_view=r['text_normalized'],text_raw=r['text_raw'],text_previous=old['text_annotation'],
            source_view=old['source_view'],text_sha256=digest(r['text_normalized']),source_dataset=r['source_dataset'],
            human_domain_decision=d['human_domain_decision'] if same else '',human_spam_decision=spam_marker(d['human_note']) if same else '',
            human_note=d['human_note'],domain_status=r['domain_status'],spam_status=r['spam_status'],final_quality_decision=r['final_quality_decision'],
            repetition_diagnostics=r['repetition_diagnostics'],migration='UNCHANGED_EXACT_TEXT' if same else 'DELTA_REQUIRES_REVIEW')
        migrated.append(entry)
        if not same:delta.append(dict(id=r['record_id'],review='domain',text_previous=old['text_annotation'],text_normalized=r['text_normalized'],old_decision=d['human_domain_decision'],old_text_sha256=digest(old['text_annotation']),new_text_sha256=entry['text_sha256']))
    for f in fmt:
        r=by[f['id']];old=format_expected[f['id']]['text_clean_i3']
        if r['text_normalized']!=old:delta.append(dict(id=r['record_id'],review='format',text_previous=old,text_normalized=r['text_normalized'],old_decision=f['format_decision'],old_text_sha256=digest(old),new_text_sha256=digest(r['text_normalized'])))
    for rid in hold_ids:
        r=by[rid];holdout.append(dict(record_id=rid,text_view=r['text_normalized'],text_raw=r['text_raw'],text_previous=r['text_clean_i3'],
            source_view='reserved quality holdout; '+r['source_dataset']+'; original post provenance may be incomplete',source_dataset=r['source_dataset'],
            text_sha256=digest(r['text_normalized']),human_domain_decision='',human_spam_decision='',human_note='',
            domain_status='WITHHELD',spam_status='WITHHELD',migration='ORIGINAL_RESERVED_ID'))
    summaries={}
    for src in sorted({r['source_dataset'] for r in rows}):
        source_rows=[r for r in rows if r['source_dataset']==src];p=[r for r in pool if r['source_dataset']==src]
        reasons=Counter(x for r in source_rows for x in r['eligibility_reasons']);remaining=source_rows[:];steps=[]
        for reason in sorted(reasons):
            before=len(remaining);remaining=[r for r in remaining if reason not in r['eligibility_reasons']];steps.append(dict(rule=reason,newly_removed=before-len(remaining),remaining=len(remaining)))
        summaries[src]=dict(rows=len(source_rows),eligible_proposed=len(p),eligible_approved=0,nonexclusive_reasons=dict(reasons),sequential_funnel=steps,
            verified_posts=len({verified_post(r) for r in p}-{''}),movies_with_identity_metadata=len({r['movie_id'] for r in p if verified_post(r) and r.get('movie_id')}),
            provenance='legacy source/original post provenance unverified; local candidate only' if src!='facebook' else 'metadata identity counts, not independently attested source diversity')
    summary=dict(status='DATASET_FREEZE_PENDING',rows=len(rows),human_decisions=650,sentiment_labels=532,review_status=statuses,
        eligible_proposed=len(pool),eligible_approved=0,sources=summaries,quality_holdout_status='PENDING_QUALITY_HOLDOUT',holdout_rows=40,
        isolation=checks,isolation_ok=isolation_ok,new_normalized_exact_merges=load(source/'summary.json')['new_exact_merge_groups'],
        new_normalized_near_pairs=load(source/'summary.json')['new_near_pair_ids'],domain_metrics=None,spam_metrics=None,
        normalization_version=cfg['normalization_version'],annotation_pointer_updated=False,official_inputs_exported=False,
        pilot_status='BLOCKED_HUMAN_QUALITY_AND_FREEZE_APPROVAL',pilot_selected=0,
        blockers=['Format review incomplete or delta unresolved','Normalization review/explicit version approval missing','Domain/spam review incomplete',
                  'Quality holdout incomplete'+(' and isolation conflict' if not isolation_ok else ''),'Legacy quality and provenance unresolved','Explicit checksum-bound corpus freeze approval missing'])
    if any((r['text_raw'],r['human_decisions'],r['human_label'],r['text_annotation'])!=original[r['record_id']] for r in rows):raise AssertionError('Raw/human/pointer changed')
    with staged(output) as out:
        write_jsonl(out/'quality_proposals.local.jsonl',rows);save(out/'readiness.json',summary);save(out/'human_review_status.json',statuses)
        write_csv(out/'review_delta.local.csv',delta,['id','review','text_previous','text_normalized','old_decision','old_text_sha256','new_text_sha256'])
        save(out/'semantic_review_input.local.json',review_contract(migrated,'development',source,ROOT/cfg['domain_workbook']))
        save(out/'holdout_input.local.json',review_contract(holdout,'holdout',source))
        save(out/'pilot_preparation_manifest.local.json',dict(seed=cfg['seed'],target=500,selected_ids=[],status=summary['pilot_status'],source_manifest_sha256=sha(source/'manifest.json'),eligible_proposed=len(pool),eligible_approved=0,legacy_overall_used=False))
        save(out/'protected_inputs.local.json',snapshot);save(out/'config.json',cfg)
        save(out/'contract.json',dict(source_manifest_sha256=sha(source/'manifest.json'),config_sha256=sha(config),normalizer_sha256=sha(ROOT/'src/preprocessing/final_normalization.py'),
            rule_table_sha256=sha(ROOT/'configs/abbreviations_v3_1.json'),guideline_sha256=sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md'),
            implementation_sha256=sha(Path(__file__)),holdout_reservation_sha256=sha(ROOT/cfg['holdout_reservation']),isolation_ok=isolation_ok))
        check_protection(snapshot);return seal(out,dict(status=summary['status'],rows=len(rows),eligible_proposed=len(pool),eligible_approved=0))
