"""Offline legacy audit and blinded train-annotation sampling, never gold creation."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import re
import unicodedata

from .common import ROOT,csv_rows,digest,load,read_jsonl,save,seal,sha,staged,verify,write_csv
from .master import normal
from .blind import BLIND_FIELDS,assert_allowed
from src.data.quality import near_duplicate_candidates
from src.data.split import UnionFind
from src.annotation.guidelines import GUIDELINE,GUIDELINE_VERSION,validate_guideline

TRUST=('VERIFIED_HUMAN_GOLD','LEGACY_LABELED_UNVERIFIED','UNLABELED_USABLE','NEEDS_REVIEW','EXCLUDE')
POS=re.compile(r'\b(hay|đỉnh|xuất sắc|tuyệt vời|ấn tượng|thích|cảm động|xúc động|đáng xem|tuyệt phẩm)\b')
NEUTRAL=re.compile(r'\?|\b(bao giờ|khi nào|ai biết|cho hỏi|ra rạp|công chiếu|lịch chiếu|dài bao lâu|nội dung|đạo diễn là)\b')
HARD=re.compile(r'\b(nhưng|mỉa mai|không phải|chẳng|chưa|đâu có)\b|:\)+|=\)+|:v')
FILM=re.compile(r'\b(phim|diễn viên|diễn xuất|kịch bản|đạo diễn|nhân vật|cảnh quay|âm nhạc|rạp|cinema|movie|film)\b')
VI_MARKS=re.compile('[ăâđêôơưĂÂĐÊÔƠƯàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]')


def verified_tail_block(rows,rule):
    """Exact file-position AND original-ID evidence; never a numeric-ID cutoff."""
    count=rule['last_records'];first=rule['first_original_id'];last=rule['last_original_id']
    if count<=0 or len(rows)<count or last-first+1!=count:raise ValueError('Invalid source block contract')
    ids=[r['id'] for r in rows]
    if any(not rid for rid in ids) or len(set(ids))!=len(ids):raise ValueError('Missing/repeated original source ID')
    tail=rows[-count:]
    if [r['id'] for r in tail]!=[str(i) for i in range(first,last+1)]:raise ValueError('Tail row/ID sequence mismatch; refuse exclusion')
    return set(range(len(rows)-count+1,len(rows)+1))


def region_audit(rows,window=1000):
    """Contiguous measured windows, not presumed natural/synthetic boundaries."""
    result=[]
    for start in range(0,len(rows),window):
        part=rows[start:start+window];texts=[r['comment'] for r in part];lengths=sorted(map(len,texts))
        result.append(dict(first_source_row=start+1,last_source_row=start+len(part),first_original_id=part[0]['id'],last_original_id=part[-1]['id'],rows=len(part),
            underscore_rows=sum('_' in t for t in texts),split_entity_rows=sum(bool(re.search(r'&\s+(?:quot|amp|lt|gt|apos)\s*;',t)) for t in texts),
            punctuation_spacing_rows=sum(bool(re.search(r'\s+[,.!?;:]',t)) for t in texts),
            abbreviation_rows=sum(bool(re.search(r'(?<!\w)(?:ko|khum|hok|đc|cx|mn|bt|k)(?!\w)',t)) for t in texts),
            short_under_10=sum(len(t)<10 for t in texts),encoding_failure_rows=sum('\ufffd' in t for t in texts),
            film_cue_rows=sum(bool(FILM.search(t)) for t in texts),domain_uncertain_without_cue=sum(not bool(FILM.search(t)) for t in texts),
            length_min=lengths[0],length_median=lengths[len(lengths)//2],length_max=lengths[-1],
            legacy_overall_audit_only=dict(Counter(r['overall'] for r in part)),
            raw_exact_duplicate_extra_rows=len(texts)-len(set(map(normal,texts)))))
    return result


def template_overlap_audit(rows,tail_rows,width=12,min_chars=50,min_records=8):
    """Descriptive long-phrase overlap with excluded block, never AI-origin inference."""
    tokenize=lambda text:re.findall(r'[^\W_]+',unicodedata.normalize('NFC',text).casefold())
    def phrases(text):
        tokens=tokenize(text)
        return {tuple(tokens[i:i+width]) for i in range(len(tokens)-width+1) if len(' '.join(tokens[i:i+width]))>=min_chars}
    counts=Counter()
    for n in sorted(tail_rows):counts.update(phrases(rows[n-1]['comment']))
    frequent={p:n for p,n in counts.items() if n>=min_records};matches={};coverage=0
    for n,row in enumerate(rows,1):
        hits=phrases(row['comment'])&frequent.keys()
        if n in tail_rows:coverage+=bool(hits)
        elif hits:matches[n]=sorted(digest(' '.join(t)) for t in hits)
    pattern_rows=[dict(phrase=' '.join(p),phrase_sha256=digest(' '.join(p)),source_records=n) for p,n in sorted(frequent.items(),key=lambda x:(-x[1],x[0]))]
    return matches,pattern_rows,dict(method='exact NFC/casefold 12-word phrases >=50 characters present in >=8 excluded records; configurable',
        phrase_width=width,min_chars=min_chars,min_tail_records=min_records,frequent_phrase_types=len(frequent),tail_records_with_phrase=coverage,
        outside_phrase_review_records=len(matches),ai_generated_claim=False,limitation='literal long-phrase matches only; paraphrases/short templates and unknown entity substitutions may be missed')


def quality(text,old_label):
    view=normal(text).replace('_',' ');flags=[]
    technical=[]
    if not view:technical.append('EMPTY')
    if re.fullmatch(r'https?://\S+',view):technical.append('URL_ONLY')
    if view in {'viết bình luận','xem bản dịch','đăng nhập để bình luận'}:technical.append('EXACT_UI_STRING')
    if '\ufffd' in text or any(unicodedata.category(c)=='Cc' and c not in '\n\r\t' for c in text):flags.append('TEXT_CORRUPTION_REVIEW')
    if view and not any(c.isalnum() for c in text):flags.append('EMOJI_OR_PUNCTUATION_CONTEXT_REVIEW')
    if sum(bool(re.search(p,view)) for p in (r'\b(mua ngay|đặt hàng|inbox|zalo|sale|giảm giá)\b',r'\b0\d{8,10}\b',r'https?://'))>=2:
        flags.append('ADVERTISING_SIGNALS_REVIEW_NOT_CONFIRMED_SPAM')
    status='EXCLUDE' if technical else 'NEEDS_REVIEW' if flags else 'LEGACY_LABELED_UNVERIFIED' if old_label else 'UNLABELED_USABLE'
    language='vietnamese_diacritic_signal' if VI_MARKS.search(text) else 'latin_without_vi_diacritic_signal' if re.search('[a-zA-Z]',text) else 'other_or_no_latin_signal'
    return dict(trust_status=status,quality_flags=technical+flags,language_signal=language,
        film_cue=bool(FILM.search(view)),positive_cues=len(POS.findall(view)),neutral_cues=len(NEUTRAL.findall(view)),
        hard_cues=len(HARD.findall(view)),underscore_tokens=bool(re.search(r'\w_\w',text)),
        emoji_alias_signal=bool(re.search(r':[a-z_]{3,}:|\b(?:face_with|crying_face|red_heart|smiling_face)\b',text)),
        nfc_changed=unicodedata.normalize('NFC',text)!=text,characters=len(text),tokens=len(text.split()))


def near_groups(rows,config):
    """One component across old master groups, exact text and Phase G near matches."""
    uf=UnionFind([r['id'] for r in rows]);seen={};unique={};owners=defaultdict(list)
    for row in rows:
        for key in [('master_group',row['group_id']),('text',normal(row['text_view']))]:
            if key in seen:uf.union(row['id'],seen[key])
            else:seen[key]=row['id']
        h=digest(normal(row['text_view']));owners[h].append(row['id'])
        unique[h]=dict(id=h,text=normal(row['text_view']),quality=dict(status='KEEP',duplicate_of=None))
    pairs=near_duplicate_candidates(list(unique.values()),config)
    for pair in pairs:uf.union(owners[pair['left']][0],owners[pair['right']][0])
    for row in rows:row['annotation_group']='lg_'+uf.find(row['id'])
    return pairs


def select(rows,count,seed):
    rng=random.Random(seed);groups=defaultdict(list)
    for row in sorted(rows,key=lambda r:r['id']):
        if row['train_candidate']:groups[row['annotation_group']].append(row)
    pool=[rng.choice(groups[g]) for g in sorted(groups)]
    rng.shuffle(pool);chosen=[];used=set()
    def take(values,n,method):
        if n<=0:return
        taken=0
        for row in values:
            if row['annotation_group'] in used:continue
            chosen.append(dict(row,sampling_method=method));used.add(row['annotation_group']);taken+=1
            if taken>=n:break
    take(pool,count//2,'seeded_random_component_representative')
    for key,n in [('positive_cues',count//4),('neutral_cues',count//6),('hard_cues',count-count//2-count//4-count//6)]:
        eligible=[r for r in pool if r[key]>0];rng.shuffle(eligible)
        eligible.sort(key=lambda r:-r[key]);take(eligible,n,'targeted_train_'+key+'_not_a_label')
    if len(chosen)<count:take(pool,count-len(chosen),'random_fill_for_sparse_rule_buckets')
    chosen=chosen[:count];rng.shuffle(chosen)
    if len({r['annotation_group'] for r in chosen})!=len(chosen):raise AssertionError('Duplicate component in annotation task')
    return chosen


def reservation_contracts():
    contracts=[];default=ROOT/'outputs/phase_g/blind_test'
    if default.exists():
        m=verify(default)
        if m['status']!='PARTIAL':contracts.append(load(default/'reservation.json'))
    from .test_posts import REGISTRY
    for path in REGISTRY.glob('*.json'):
        entry=load(path);plan=Path(entry['plan_root']);verify(plan)
        if sha(plan/'manifest.json')!=entry['plan_manifest_sha256']:raise ValueError('Intake registry changed')
        posts=load(plan/'candidate_quarantine.json')
        contracts.append(dict(ids=[],groups=[],text_hashes=[],comment_ids=[],post_ids=posts['post_ids'],post_urls=posts['post_urls']))
        if entry.get('collection_root'):
            directory=Path(entry['collection_root']);m=load(directory/'manifest.json')
            if (sha(directory/'manifest.json')!=entry['collection_manifest_sha256'] or
                sha(directory/'post_quarantine.json')!=m['output_sha256']['post_quarantine.json']):raise ValueError('Collection quarantine changed')
            contracts.append(load(directory/'post_quarantine.json'))
        if entry.get('reservation_root'):
            directory=Path(entry['reservation_root']);m=verify(directory)
            if sha(directory/'manifest.json')!=entry['reservation_manifest_sha256']:raise ValueError('Test reservation changed')
            if m['status']!='PARTIAL':contracts.append(load(directory/'reservation.json'))
    return [{key:set(c.get(key,[])) for key in ('ids','groups','text_hashes')} for c in contracts]


def quantiles(values):
    values=sorted(values)
    def percentile(p):
        at=(len(values)-1)*p;lo=int(at);return values[lo]+(values[min(lo+1,len(values)-1)]-values[lo])*(at-lo)
    return {name:percentile(p) for name,p in [('min',0),('median',.5),('p95',.95),('max',1)]} if values else {}


def audit(config_path,output):
    cfg=load(config_path);source=(ROOT/cfg['input']).resolve();master=ROOT/cfg['master_root'];manifest=verify(master)
    if sha(master/'manifest.json')!=cfg['master_manifest_sha256']:raise ValueError('Frozen master changed')
    source_sha=sha(source)
    if source_sha!=cfg['input_sha256']:raise ValueError('Legacy file differs from audited source contract')
    raw,fields=csv_rows(source.read_bytes())
    if fields!=['id','comment','overall']:raise ValueError('Legacy schema changed; explicit mapping required')
    all_master=read_jsonl(master/'master.jsonl');mapping={};master_groups=defaultdict(list)
    exposed={r['group_id'] for r in all_master if r['exposure_status']=='exposed_development_component'}
    for row in all_master:
        master_groups[row['group_id']].append(row)
        for obs in row['observations']:
            if obs['input_sha256']==source_sha and obs['source_file']==cfg['master_source_file']:
                if obs['source_row'] in mapping:raise ValueError('Legacy row mapped twice')
                mapping[obs['source_row']]=(row,obs)
    if len(raw)!=cfg['expected_rows'] or set(mapping)!=set(range(1,len(raw)+1)):raise ValueError('Missing legacy/master provenance rows')
    development,_=csv_rows((ROOT/cfg['development_csv']).read_bytes());devtexts={normal(r['text_raw']) for r in development}
    contracts=reservation_contracts();rows=[]
    for number,original in enumerate(raw,1):
        linked,obs=mapping[number]
        if obs['text_raw']!=original['comment'] or str(obs['original_label'])!=original['overall']:raise ValueError('Master source text/label mismatch')
        q=quality(original['comment'],original['overall']);text_hash=digest(normal(original['comment']))
        quarantined=any(linked['id'] in c['ids'] or linked['group_id'] in c['groups'] or text_hash in c['text_hashes'] for c in contracts)
        direct=normal(original['comment']) in devtexts;connected=linked['group_id'] in exposed
        severe='TEXT_CORRUPTION_REVIEW' in q['quality_flags']
        rows.append(dict(id=linked['id'],text_view=original['comment'],text_raw=original['comment'],source_id=original['id'],
            source_row=number,source_file=str(source),source_sha256=source_sha,legacy_label=original['overall'],
            group_id=linked['group_id'],**q,exposure_status='confirmed_exposed' if direct else 'unknown_exposure',
            exposure_evidence='exact content overlap with development, NOT verified same comment identity' if direct else '',
            connected_to_exposed_component=connected,test_quarantined=quarantined,
            train_candidate=not (q['trust_status']=='EXCLUDE' or severe or quarantined or connected or direct),
            movie_id='',post_id='',comment_id='',platform='unknown',label_source='legacy_unverified'))
    pairs=near_groups(rows,cfg['near_duplicate']);chosen=select(rows,cfg['annotation_count'],cfg['seed'])
    # Mandatory fresh guard check before publishing any training annotation task.
    assert_allowed(chosen,'train')
    same_text=Counter(normal(r['text_view']) for r in rows);exact_raw=Counter(r['text_view'] for r in rows)
    source_ids=Counter(r['source_id'] for r in rows);labels=Counter(r['legacy_label'] for r in rows)
    report=dict(rows=len(rows),columns=fields,source_sha256=source_sha,
        missing_by_column={k:sum(not r[k].strip() for r in raw) for k in fields},
        duplicated_source_ids=sum(n-1 for n in source_ids.values() if n>1),
        unique_raw_texts=len(exact_raw),unique_normalized_texts=len(same_text),
        raw_duplicate_excess=sum(n-1 for n in exact_raw.values()),normalized_duplicate_excess=sum(n-1 for n in same_text.values()),
        unique_texts_not_verified_unique_facebook_comments=True,near_duplicate_pairs=len(pairs),
        annotation_components=len({r['annotation_group'] for r in rows}),
        legacy_overall_distribution=dict(labels),overall_semantics_and_labeling_method='UNVERIFIED; strings retained without target-label mapping',
        trust_groups={k:sum(r['trust_status']==k for r in rows) for k in TRUST},
        quality_flags=dict(Counter(f for r in rows for f in r['quality_flags'])),
        language_signals=dict(Counter(r['language_signal'] for r in rows)),language_detection_validated=False,
        char_lengths=quantiles([r['characters'] for r in rows]),token_lengths=quantiles([r['tokens'] for r in rows]),
        underscore_token_rows=sum(r['underscore_tokens'] for r in rows),emoji_alias_signal_rows=sum(r['emoji_alias_signal'] for r in rows),
        unicode_nfc_changed_rows=sum(r['nfc_changed'] for r in rows),film_cue_rows=sum(r['film_cue'] for r in rows),
        no_film_cue_does_not_mean_unrelated=True,verified_in_scope_sentiment_rows=None,
        train_candidates=sum(r['train_candidate'] for r in rows),eligible_candidate_components=len({r['annotation_group'] for r in rows if r['train_candidate']}),
        annotation_candidates_selected=len(chosen),selection_methods=dict(Counter(r['sampling_method'] for r in chosen)),
        exact_content_overlap_development=sum(normal(r['text_view']) in devtexts for r in rows),
        connected_to_exposed_master_component=sum(r['connected_to_exposed_component'] for r in rows),
        test_quarantined_rows=sum(r['test_quarantined'] for r in rows),
        exposure=dict(Counter(r['exposure_status'] for r in rows)),confirmed_unused_with_evidence=0,independent_test_candidates=0,
        verified_movies=0,verified_posts=0,verified_comment_ids=0,known_source_files=1,
        metadata_restored=0,identity_verified_agreement_pairs=0,legacy_human_agreement=None,
        film_sampling_claim=False,multiple_source_diversity_claim=False,
        annotation_only_pending_human=True,training_permission_and_source_rights_unverified=True,
        blockers=['No post/movie/platform/comment provenance','No verified semantics or origin of overall',
                  'No affirmative unused/exposure evidence','No verified source license/API rights',
                  'Semantic relevance and usable sentiment count require human review'])
    validate_guideline(GUIDELINE_VERSION,sha(GUIDELINE))
    with staged(output) as work:
        save(work/'legacy_quality_report.json',report);save(work/'near_duplicates.json',pairs)
        write_csv(work/'legacy_audit.csv',rows,[k for k in rows[0] if k!='text_raw'])
        save(work/'coordinator_mapping.json',chosen)
        task=[dict(id=r['id'],text_view=r['text_view'],status='',label='',review_reason='',reason='') for r in chosen]
        enough=len(chosen)==cfg['annotation_count']
        if enough:
            save(work/'workbook_input.json',task);write_csv(work/'legacy_train_candidates.csv',task,BLIND_FIELDS)
        save(work/'selection_manifest.json',dict(seed=cfg['seed'],target=cfg['annotation_count'],selected=len(task),
            selected_ids=[r['id'] for r in chosen],selected_components=[r['annotation_group'] for r in chosen],
            methods=report['selection_methods'],guideline_version=GUIDELINE_VERSION,guideline_sha256=sha(GUIDELINE),
            source_sha256=source_sha,legacy_labels_used_for_selection=False,model_predictions_used=False,
            film_stratification=False,source_stratification=False,purpose='train_annotation_not_independent_test',gold_created=False))
        save(work/'config.json',cfg)
        if sha(source)!=source_sha:raise ValueError('Legacy file changed during audit')
        result=seal(work,dict(status='ANNOTATION_POOL_PREPARED_PENDING_WORKBOOK' if enough else 'PARTIAL',phase='G.2',
            rows=len(rows),selected=len(task),source_sha256=source_sha,master_manifest_sha256=sha(master/'manifest.json'),
            gold_created=False,models_trained=False,external_api_called=False))
    return report,result
