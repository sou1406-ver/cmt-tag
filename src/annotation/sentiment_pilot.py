"""Offline two-person text-only pilot. No canonical writes, models or API calls."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import random
import re

from src.dataset.common import (ROOT, digest, load, normal, read_sheet, literal_text,
    save, sha, staged, write_csv, write_jsonl, seal, verify, read_jsonl)
from src.dataset.blind import assert_allowed
from . import guidelines
from .core import pair_metrics
from .pilot import fingerprints, near_any, protection, guard_reason, reference_index

SEED = 20261115
LABELS = ['POS', 'NEG', 'NEU', 'REVIEW', 'EXCLUDE']
FIELDS = ['comment_id', 'text_clean', 'sentiment_label', 'note', 'annotator_id', 'cleaning_issue']
ADJUDICATION_FIELDS = ['comment_id', 'text_clean', 'label_A', 'label_B', 'note_A', 'note_B', 'final_label', 'adjudication_note']
ADJUDICATION_SOURCE_FIELDS = ADJUDICATION_FIELDS[:6]
DEFAULT = ROOT/'outputs/sentiment_pilot'
SOURCE = ROOT/'data/imports/fb_54e6c18b6c514f9ab822354611ab3316/comments.csv'


def guideline_contract():
    """Snapshot the official file at prepare time; old runs retain their SHA."""
    path = guidelines.GUIDELINE
    if not path.is_file() or not path.read_bytes().strip():
        raise FileNotFoundError('Official guideline is missing or empty')
    return dict(guideline_file=str(path), guideline_sha256=sha(path),
                status='READY', guideline_status='APPROVED_FOR_PILOT')


def snapshot_guideline(work, directory, contract):
    """Copy exact bytes; future validation uses only this batch-local snapshot."""
    payload = Path(contract['guideline_file']).read_bytes()
    if digest(payload) != contract['guideline_sha256']:
        raise ValueError('Official guideline changed during prepare')
    snapshot = 'guideline_snapshot.md'
    (work/snapshot).write_bytes(payload)
    return {**contract, 'guideline_source':contract['guideline_file'],
            'guideline_file':str(directory/snapshot), 'guideline_snapshot':snapshot,
            'guideline_sha256':sha(work/snapshot)}


def batch_guideline(directory, manifest):
    if 'guideline_snapshot' not in manifest:
        return Path(manifest['guideline_file'])  # Historical pinned-path compatibility.
    if manifest['guideline_snapshot'] != 'guideline_snapshot.md':
        raise ValueError('Invalid batch guideline snapshot path')
    return Path(directory)/manifest['guideline_snapshot']


def eligible(source, guard):
    """Existing identity/exact/near guard plus exact dedup; no semantic labels."""
    pool = []; exclusions = []; texts = set(); ids = set()
    for row in sorted(source, key=lambda r: r.get('comment_id', '')):
        rid = row.get('comment_id', '')
        reason = None
        if row.get('clean_status') != 'KEEP': reason = 'CLEAN_STATUS_NOT_KEEP'
        elif not rid or not row.get('post_id') or not row.get('source_name'): reason = 'MISSING_IDENTITY_OR_SOURCE'
        elif row.get('record_type') not in ('comment', 'reply'): reason = 'MISSING_RECORD_TYPE'
        elif not row.get('text_clean', '').strip(): reason = 'EMPTY_CLEAN'
        elif rid in ids: reason = 'DUPLICATE_COMMENT_ID'
        if not reason:
            view = dict(record_id=rid, comment_id=rid, post_id=row['post_id'],
                text_raw=row.get('text_raw', ''), text_minimal=row['text_clean'], text_annotation_view=row['text_clean'])
            reason = guard_reason(view, guard)
        if not reason and normal(row['text_clean']) in texts: reason = 'EXACT_WITHIN_BATCH'
        if reason: exclusions.append(dict(comment_id=rid, reason=reason)); continue
        ids.add(rid); texts.add(normal(row['text_clean'])); pool.append(row)
    return pool, exclusions


def select(pool, random_count=160, hard_count=40):
    """Proportional stratified random cohort; distinct purposeful cue cohort."""
    rng = random.Random(SEED); bins = defaultdict(list)
    for r in sorted(pool, key=lambda r: r['comment_id']):
        bins[(r['source_name'], r['post_id'], r['record_type'])].append(r)
    if len(pool) < random_count + hard_count: raise ValueError('Insufficient eligible unique pool for 200')
    if len(bins) > random_count: raise ValueError('Too many strata for requested random cohort')
    allocation = {k: 1 for k in bins}
    # Each stratum represented; distribute remaining slots by N_h/current n_h.
    for _ in range(random_count-len(bins)):
        k = max((k for k in bins if allocation[k] < len(bins[k])), key=lambda k:(len(bins[k])/allocation[k], k))
        allocation[k] += 1
    selected = []; seen = []; selected_ids = set()
    def add(row, cohort, reason, stratum):
        if near_any(row['text_clean'], seen): return False
        selected.append({**row, 'sample_type': cohort, 'sample_reason': reason,
                         'sampling_stratum': list(stratum)})
        selected_ids.add(row['comment_id']); seen.append(fingerprints(row['text_clean']))
        return True
    for k in sorted(bins):
        candidates = bins[k][:]; rng.shuffle(candidates); count = 0
        for row in candidates:
            if add(row, 'random', 'STRATIFIED_RANDOM', k): count += 1
            if count == allocation[k]: break
        if count < allocation[k]: raise ValueError('Near-duplicate removal prevents fixed stratum quota; no silent relaxation')
    cues = defaultdict(list)
    for row in pool:
        if row['comment_id'] in selected_ids: continue
        text = row['text_clean']; key = None
        if re.search(r'(?iu)\b(không|chưa|chẳng|chả|ko|k)\b', text): key = 'NEGATION_CUE'
        elif re.search(r'(?iu)\b(nhưng|tuy|vừa)\b', text): key = 'CONTRAST_CUE'
        elif row['record_type'] == 'reply' and len(text.split()) <= 12: key = 'SHORT_REPLY_CUE'
        elif re.search(r'[:=;][()vV]|[^\w\s.,!?…\-]', text): key = 'EXPRESSION_CUE'
        elif '?' in text: key = 'QUESTION_CUE'
        if key: cues[key].append(row)
    for key in sorted(cues): cues[key].sort(key=lambda r:r['comment_id']); rng.shuffle(cues[key])
    hard_selected = 0
    while hard_selected < hard_count:
        progress = False
        for key in sorted(cues):
            while cues[key]:
                row = cues[key].pop()
                if add(row, 'hard', key, (row['source_name'], row['post_id'], row['record_type'])):
                    hard_selected += 1; progress = True; break
            if hard_selected == hard_count: break
        if not progress: raise ValueError('Insufficient distinct hard candidates; no invented labels')
    rng.shuffle(selected)
    return selected, [dict(source=k[0], post_id=k[1], record_type=k[2], N=len(bins[k]), n=allocation[k]) for k in sorted(bins)]


def prepare(source=SOURCE, directory=DEFAULT):
    source = Path(source).resolve(); directory = Path(directory).resolve()
    if not source.is_file(): raise FileNotFoundError('Source required')
    contract = guideline_contract()
    # Production reservation metadata and raw-only fingerprints; never locked labels.
    registry = ROOT/'data/test_reservations'
    if not list(registry.glob('*.json')): raise FileNotFoundError('Gold reservation registry required before sampling')
    before = sha(source)
    with source.open(encoding='utf-8-sig', newline='') as f: raw = list(csv.DictReader(f))
    guard = protection([], source.parent, ROOT)
    pool, rejected = eligible(raw, guard)
    allowed = pool
    # Verify sealed production contracts once, after filtering with existing guard.
    # Any remaining protected component stops the whole sample rather than bypassing it.
    assert_allowed([{**r, 'platform':'facebook', 'text_view':r['text_clean']} for r in allowed], 'active_learning')
    selected, strata = select(allowed)
    assert_allowed([{**r, 'platform':'facebook', 'text_view':r['text_clean']} for r in selected], 'active_learning')
    if sha(contract['guideline_file']) != contract['guideline_sha256']:
        raise ValueError('Official guideline changed during prepare')
    if sha(source) != before or any(sha(p) != h for p,h in guard['checksums'].items()):
        raise ValueError('Protected/source input changed during prepare')
    manifest = dict(**contract, source_file=str(source), source_sha256=before,
        source_records=len(raw), eligible_records=len(allowed), selected=200, random_count=160, hard_count=40,
        seed=SEED, strata=strata, protected_checksums=guard['checksums'],
        selected_rows=[dict(comment_id=r['comment_id'], text_sha256=digest(r['text_clean']),
            post_id=r['post_id'], movie_id=r.get('movie_id'), source=r['source_name'], record_type=r['record_type'],
            sample_type=r['sample_type'], sample_reason=r['sample_reason']) for r in selected],
        exposure=dict(purpose='development_annotation_not_independent_gold',
            post_ids=sorted({r['post_id'] for r in selected}), comment_ids=sorted(r['comment_id'] for r in selected),
            prohibition='Do not use pilot posts/IDs/exact or near duplicates as a future independent test'),
        counts=dict(sample_type=dict(Counter(r['sample_type'] for r in selected)),
            source=dict(Counter(r['source_name'] for r in selected)), record_type=dict(Counter(r['record_type'] for r in selected)),
            posts=len({r['post_id'] for r in selected}), movies=len({r['movie_id'] for r in selected})),
        exclusions=dict(Counter(r['reason'] for r in rejected)),
        near_duplicate_rule='Existing fingerprint trigrams, normalized text length >=40, Jaccard >=0.9; exact normalized text always checked',
        warning='160 random + 40 hard (20%); cues are not labels. No population sentiment estimates from purposeful hard cohort.')
    with staged(directory) as work:
        manifest.update(snapshot_guideline(work, directory, contract))
        save(work/'sampling_manifest.json', manifest)
        (work/'sampling_manifest.sha256').write_text(sha(work/'sampling_manifest.json')+'\n', encoding='ascii')
        save(work/'workbook_input.local.json', [dict(comment_id=r['comment_id'], text_clean=r['text_clean']) for r in selected])
        write_csv(work/'exclusions.local.csv', rejected, ['comment_id','reason'])
        guideline_note = 'Guideline chính thức: '+contract['guideline_file']+'. SHA256 tại prepare: '+contract['guideline_sha256']+'.'
        (work/'README.md').write_text('# Pilot sentiment text-only\n\n'+guideline_note+'\n'+'''

Hai workbook có cùng 200 ID/thứ tự, gồm 160 random + 40 hard, trộn mù; không có nhãn điền sẵn. Chỉ đọc text_clean, không parent/post; không dùng nhãn relevance cũ. Cột vàng sentiment_label/note để người gán điền; REVIEW phải có note ngắn, không có confidence bắt buộc. cleaning_issue dành cho lỗi text, không sửa text.
Tái lập: python -m src.annotation sentiment-pilot prepare --directory outputs/sentiment_pilot_NEW
Xuất Excel bằng scripts/export_sentiment_pilot.mjs với Node/@oai/artifact-tool bundled; builder không ghi đè workbook đã có.
Sau khi gán độc lập: python -m src.annotation sentiment-pilot compare --directory outputs/sentiment_pilot
Compare kiểm toàn bộ hai file trước khi xuất thư mục comparison riêng; lưu nhãn A/B, Kappa chính 5 nhãn, Kappa phụ 3 nhãn, disagreement và adjudication trống. Không ghi canonical/Gold. Không chạy compare trên workbook chưa điền.
Người dùng là adjudicator, không phải annotator thứ ba. Bảng adjudication có toàn bộ câu bất đồng và tối đa 20 câu đồng thuận ngẫu nhiên (seed cố định); hai cột final_label/adjudication_note trống để người dùng chốt. Xuất Excel tô cam/xanh: node scripts/export_sentiment_pilot.mjs outputs/sentiment_pilot/comparison --adjudication. Nhập kết quả riêng: python -m src.annotation sentiment-pilot adjudicate --directory outputs/sentiment_pilot --decisions outputs/sentiment_pilot/comparison/adjudication.xlsx. Không sửa A/B hoặc tính lại Kappa từ nhãn chốt.
sampling_manifest.json khóa seed, nguồn, text SHA, cohort và exposure. Pilot/cùng post phải loại khỏi independent test tương lai; dùng manifest này khi kiểm exposure. Không sửa frozen split hoặc reservation cũ.
''', encoding='utf8')
        (work/'REPORT.md').write_text('# Kết quả pilot sentiment\n\nChưa có nhãn sentiment thật; Kappa, agreement và confusion matrix: CHƯA CÓ.\n'+guideline_note+'\n', encoding='utf8')
    return {k: manifest[k] for k in ('status','eligible_records','selected','counts','exclusions')}


def select_round(pool, total=1000, cap=30, batch_size=200):
    """Seeded random within posts; census small-source strata up to post cap.

    Remaining slots use round-robin posts, not sentiment cues or random Facebook
    population sampling. Batches are balanced across posts, each exactly 200.
    """
    if total % batch_size:raise ValueError('Round size must divide into full batches')
    rng=random.Random(SEED);bins=defaultdict(list)
    for r in sorted(pool,key=lambda r:r['comment_id']):bins[r['post_id']].append(r)
    small={'KhenPhim','Cuồng Phim','XEM PHIM & BÌNH PHIM'}
    for records in bins.values():rng.shuffle(records)
    chosen=[];counts=Counter();small_counts=Counter()
    for pid in sorted(bins):
        records=bins[pid]
        if len({r['source_name'] for r in records})!=1:raise ValueError('Conflicting source metadata within post')
        if records[0]['source_name'] in small:
            take=min(cap,len(records));chosen.extend(records[:take]);counts[pid]+=take
            small_counts[records[0]['source_name']]+=take;bins[pid]=records[take:]
    if len(chosen)>total:raise ValueError('Small-source census exceeds requested sample; no silent truncation')
    post_order=sorted(bins);rng.shuffle(post_order)
    while len(chosen)<total:
        progress=False
        for pid in post_order:
            if bins[pid] and counts[pid]<cap:
                chosen.append(bins[pid].pop());counts[pid]+=1;progress=True
                if len(chosen)==total:break
        if not progress:raise ValueError('Insufficient post-capped unique pool; no quota relaxation')
    groups=[[] for _ in range(total//batch_size)];per_post=[Counter() for _ in groups]
    grouped=defaultdict(list)
    for r in chosen:grouped[r['post_id']].append(r)
    order=sorted(grouped);rng.shuffle(order)
    for pid in order:
        rng.shuffle(grouped[pid])
        for r in grouped[pid]:
            ties=list(range(len(groups)));rng.shuffle(ties)
            b=min((i for i in ties if len(groups[i])<batch_size),key=lambda i:(per_post[i][pid],len(groups[i])))
            groups[b].append(r);per_post[b][pid]+=1
    for group in groups:rng.shuffle(group)
    return groups,dict(small_counts)


def prepare_round(sources, directory, exclude_pilot):
    directory=Path(directory).resolve();sources=[Path(v).resolve() for v in sources]
    if len(sources)!=4 or len(set(sources))!=4:raise ValueError('Exactly four distinct V2 exports required')
    prior=Path(exclude_pilot).resolve();old=verify_manifest(prior)
    prior_ids={r['comment_id'] for r in old['selected_rows']};prior_posts={r['post_id'] for r in old['selected_rows']}
    contract=guideline_contract();inputs=[];raw=[];checks={}
    for path in sources:
        h=sha(path)
        with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        raw.extend(rows);inputs.append(dict(path=str(path),sha256=h,records=len(rows)));checks[str(path)]=h
    if len({r['comment_id'] for r in raw})!=len(raw):raise ValueError('Duplicate IDs across exports')
    guard=protection([],sources[0].parent,ROOT);checks.update(guard['checksums'])
    for name in ('sampling_manifest.json','sampling_manifest.sha256'):checks[str(prior/name)]=sha(prior/name)
    prior_rows=[]
    with Path(old['source_file']).open(encoding='utf-8-sig',newline='') as f:
        prior_rows=[r for r in csv.DictReader(f) if r['comment_id'] in prior_ids]
    prior_texts={normal(r['text_clean']) for r in prior_rows}
    prior_near=reference_index([fingerprints(r['text_clean']) for r in prior_rows])
    pool=[];excluded=[];reserved=Counter();seen=set();near={'sets':[],'postings':defaultdict(set)}
    for r in sorted(raw,key=lambda r:r['comment_id']):
        view=dict(record_id=r['comment_id'],comment_id=r['comment_id'],post_id=r['post_id'],text_raw=r['text_raw'],text_minimal=r['text_clean'],text_annotation_view=r['text_clean'])
        protected=guard_reason(view,guard)
        if protected:reserved[protected]+=1
        reason=None
        if r['clean_status']!='KEEP':reason='CLEAN_STATUS_NOT_KEEP'
        elif r['comment_id'] in prior_ids:reason='PILOT_ID'
        elif r['post_id'] in prior_posts:reason='PILOT_POST'
        elif protected:reason=protected
        elif not r['post_id'] or not r['source_name'] or not r['text_clean'].strip():reason='MISSING_IDENTITY_OR_TEXT'
        elif normal(r['text_clean']) in prior_texts:reason='EXACT_PILOT_TEXT'
        elif near_any(r['text_clean'],prior_near):reason='NEAR_PILOT_TEXT'
        elif normal(r['text_clean']) in seen:reason='EXACT_WITHIN_ROUND'
        elif near_any(r['text_clean'],near):reason='NEAR_WITHIN_ROUND'
        if reason:excluded.append(dict(comment_id=r['comment_id'],reason=reason));continue
        pool.append(r);seen.add(normal(r['text_clean']));fp=fingerprints(r['text_clean'])
        if fp:
            i=len(near['sets']);near['sets'].append(fp)
            for token in fp:near['postings'][token].add(i)
    groups,small=select_round(pool)
    all_selected=[r for group in groups for r in group]
    assert_allowed([{**r,'platform':'facebook','text_view':r['text_clean']} for r in all_selected],'active_learning')
    if any(sha(path)!=h for path,h in checks.items()):raise ValueError('Protected/source inputs changed')
    def counts(records):
        return dict(source=dict(Counter(r['source_name'] for r in records)),
                    post=dict(Counter(r['post_id'] for r in records)),movie=dict(Counter(r['movie_id'] for r in records)))
    meta=dict(seed=SEED,total=1000,batch_size=200,batches=5,post_cap=30,source_files=inputs,
              eligible=len(pool),input_records=len(raw),prior_pilot_manifest_sha256=sha(prior/'sampling_manifest.json'),
              prior_pilot_ids=len(prior_ids),prior_pilot_posts=len(prior_posts),reserved_guard_all_records=dict(reserved),
              exclusions=dict(Counter(r['reason'] for r in excluded)),small_source_selected=small,
              batches_counts={str(i+1):counts(g) for i,g in enumerate(groups)},
              sampling='Seeded random within posts; small-source census capped at 30/post; round-robin other posts; no sentiment cues',
              selected_rows=[dict(comment_id=r['comment_id'],text_sha256=digest(r['text_clean']),post_id=r['post_id'],movie_id=r['movie_id'],source=r['source_name'],batch=i+1) for i,g in enumerate(groups) for r in g])
    with staged(directory) as work:
        meta.update(snapshot_guideline(work,directory,contract))
        save(work/'selection_manifest.json',meta)
        write_csv(work/'selection.local.csv',[dict(batch=i+1,**r) for i,g in enumerate(groups) for r in g],['batch',*raw[0]])
        write_csv(work/'exclusions.local.csv',excluded,['comment_id','reason'])
        batch=work/'batch_01';batch.mkdir();final=directory/'batch_01'
        # Batch snapshot copied from this sealed round, never reread the official file.
        batch_contract=snapshot_guideline(batch,final,{**contract,'guideline_file':str(work/'guideline_snapshot.md')})
        batch_contract['guideline_source']=contract['guideline_file']
        selected=groups[0]
        manifest=dict(**batch_contract,batch_number=1,selected=200,seed=SEED,source_files=inputs,
            protected_checksums=checks,selected_rows=[dict(comment_id=r['comment_id'],text_sha256=digest(r['text_clean']),post_id=r['post_id'],movie_id=r['movie_id'],source=r['source_name'],record_type=r['record_type']) for r in selected],
            exposure=dict(purpose='official_development_annotation_not_gold',post_ids=sorted({r['post_id'] for r in all_selected}),comment_ids=sorted(r['comment_id'] for r in all_selected)),
            counts=counts(selected),round_manifest_sha256=sha(work/'selection_manifest.json'),
            note='Only batch 1 prepared; batches 2-5 are sealed selections, no workbooks or labels yet')
        save(batch/'sampling_manifest.json',manifest)
        (batch/'sampling_manifest.sha256').write_text(sha(batch/'sampling_manifest.json')+'\n',encoding='ascii')
        save(batch/'workbook_input.local.json',[dict(comment_id=r['comment_id'],text_clean=r['text_clean']) for r in selected])
        (work/'README.md').write_text('# Official annotation round\n\nOnly batch_01 prepared. Selection: 1000 in five disjoint sets of 200. No sentiment labels or training. All comment payloads local.\n',encoding='utf8')
    return dict(total=1000,eligible=len(pool),batch_1=counts(groups[0]),small_source_selected=small,guard=dict(reserved),output=str(directory))


def split_posts(rows, target=200, seed=SEED):
    """Metadata-only source strata; randomized whole posts, no text/labels used.

    Represent every source in T. A single-post source cannot occur in both sets.
    Stop at the nearest attainable count along this randomized stratified path.
    """
    rng=random.Random(seed);posts=defaultdict(list);strata=defaultdict(list)
    for r in sorted(rows,key=lambda r:r['comment_id']):posts[r['post_id']].append(r)
    for pid,group in sorted(posts.items()):
        names={r['source_name'] for r in group}
        if len(names)!=1:raise ValueError('Conflicting source metadata within post')
        strata[next(iter(names))].append(pid)
    if len({r['comment_id'] for r in rows})!=len(rows):raise ValueError('Duplicate split input IDs')
    chosen=set();taken=Counter();remaining={}
    for name in sorted(strata):
        values=strata[name][:];rng.shuffle(values)
        pid=values.pop();chosen.add(pid);taken[name]+=len(posts[pid]);remaining[name]=values
    selected=sum(taken.values())
    if selected>target:raise ValueError('One-post-per-source minimum exceeds target; explicit policy required')
    available={name:sum(len(posts[pid]) for pid in values) for name,values in remaining.items()}
    total_available=sum(available.values());budget=target-selected
    quotas={name:taken[name]+budget*available[name]/total_available for name in strata} if total_available else dict(taken)
    while selected<target:
        candidates=[name for name in sorted(strata) if remaining[name]]
        if not candidates:break
        name=max(candidates,key=lambda n:(quotas[n]-taken[n],n))
        pid=remaining[name][-1];size=len(posts[pid])
        if abs(selected+size-target)>=abs(selected-target):break
        remaining[name].pop();chosen.add(pid);taken[name]+=size;selected+=size
    t=sorted((r for r in rows if r['post_id'] in chosen),key=lambda r:r['comment_id'])
    u=sorted((r for r in rows if r['post_id'] not in chosen),key=lambda r:r['comment_id'])
    if not t or not u:raise ValueError('Whole-post split produced an empty set')
    return t,u


def split_counts(rows):
    return dict(records=len(rows),posts=len({r['post_id'] for r in rows}),movies=len({r['movie_id'] for r in rows}),
        source=dict(Counter(r['source_name'] for r in rows)),post=dict(Counter(r['post_id'] for r in rows)),
        movie=dict(Counter(r['movie_id'] for r in rows)))


def cross_split_duplicates(t,u):
    variants=lambda row:[row.get('text_raw',''),row['text_clean']]
    exact={normal(v) for r in u for v in variants(r) if normal(v)}
    near=reference_index([fingerprints(v) for r in u for v in variants(r)])
    return dict(exact=sum(any(normal(v) in exact for v in variants(r) if normal(v)) for r in t),
                near=sum(any(near_any(v,near) for v in variants(r)) for r in t))


def prepare_tu(round_directory, directory):
    round_directory=Path(round_directory).resolve();directory=Path(directory).resolve()
    verify_manifest(round_directory/'batch_01')  # Pins the original 1000-ID plan.
    plan=load(round_directory/'selection_manifest.json')
    expected={r['comment_id']:r for r in plan['selected_rows']}
    if len(expected)!=1000 or len(plan['selected_rows'])!=1000:raise ValueError('Expected sealed 1000-ID selection')
    checks={str(round_directory/'selection_manifest.json'):sha(round_directory/'selection_manifest.json')}
    rows=[]
    for entry in plan['source_files']:
        if sha(entry['path'])!=entry['sha256']:raise ValueError('Original export changed')
        checks[entry['path']]=entry['sha256']
        with Path(entry['path']).open(encoding='utf-8-sig',newline='') as f:
            rows.extend(r for r in csv.DictReader(f) if r['comment_id'] in expected)
    if len(rows)!=1000 or len({r['comment_id'] for r in rows})!=1000:raise ValueError('Selection source coverage mismatch')
    for r in rows:
        e=expected[r['comment_id']]
        if r['clean_status']!='KEEP' or digest(r['text_clean'])!=e['text_sha256'] or any(r[k]!=e[v] for k,v in [('post_id','post_id'),('movie_id','movie_id'),('source_name','source')]):
            raise ValueError('Selection text or metadata changed')
    assert_allowed([{**r,'platform':'facebook','text_view':r['text_clean']} for r in rows],'active_learning')
    t,u=split_posts(rows);duplicates=cross_split_duplicates(t,u)
    if any(duplicates.values()):raise ValueError('Cross T/U text duplicates; do not silently change selection')
    contract=guideline_contract()
    meta=dict(kind='POST_DISJOINT_TU',seed=SEED,target_T=200,selected=1000,counts={'T':split_counts(t),'U':split_counts(u)},
        protected_inputs=checks,guideline_sha256=contract['guideline_sha256'],
        splitting='Random post order within source; one post/source minimum in T; remaining budget weighted by available stratum size; nearest count on that path',
        limitation='Single-post sources occur only in T under the all-source T policy; source proportions are not population representative. T is protocol test, not independent Gold.',
        overlap=dict(comment_ids=0,post_ids=0,**duplicates),EC_status='WAITING_USER_EXAMPLE_IDS',
        prohibited_T_uses=['train','prompt_examples','preprocessing_tuning','hyperparameter_tuning'],
        stage_status='STEP_1_COMPLETE_ONLY_TU; E_C_PENDING; NO_AI_CHUNKS_OR_LABELS')
    with staged(directory) as work:
        for name,records in [('T',t),('U',u)]:
            folder=work/name;folder.mkdir();snapshot_guideline(folder,directory/name,contract)
            write_jsonl(folder/'records.local.jsonl',records)
        if any(sha(p)!=h for p,h in checks.items()):raise ValueError('Inputs changed during split')
        seal(work,meta)
    return meta


def prepare_blind_review(split_directory, directory):
    split_directory=Path(split_directory).resolve();directory=Path(directory).resolve()
    m=verify(split_directory)
    if m.get('kind')!='POST_DISJOINT_TU':raise ValueError('Expected sealed post-disjoint T/U split')
    rows=read_jsonl(split_directory/'T/records.local.jsonl')
    if len(rows)<50:raise ValueError('T has fewer than 50 records')
    selected=random.Random(SEED).sample(sorted(rows,key=lambda r:r['comment_id']),50)
    contract=dict(guideline_file=str(split_directory/'T/guideline_snapshot.md'),guideline_sha256=m['guideline_sha256'])
    if sha(contract['guideline_file'])!=contract['guideline_sha256']:raise ValueError('T guideline snapshot changed')
    with staged(directory) as work:
        snapshot_guideline(work,directory,contract)
        write_csv(work/'workbook_input.local.csv',[dict(comment_id=r['comment_id'],text_clean=r['text_clean'],label='',note='') for r in selected],['comment_id','text_clean','label','note'])
        save(work/'workbook_input.local.json',[dict(comment_id=r['comment_id'],text_clean=r['text_clean']) for r in selected])
        result=seal(work,dict(kind='T_BLIND_50',seed=SEED,selected=50,source_split=str(split_directory),
            source_manifest_sha256=sha(split_directory/'manifest.json'),guideline_sha256=m['guideline_sha256'],guideline_snapshot='guideline_snapshot.md',
            selected_rows=[dict(comment_id=r['comment_id'],text_sha256=digest(r['text_clean'])) for r in selected],
            status='AWAITING_USER_BLIND_LABELS_BEFORE_AI',EC_status='WAITING_USER_EXAMPLE_IDS',
            note='Only step 2 export; no labels imported, no AI chunks, no AI calls, no train/evaluate'))
    return result


def verify_manifest(directory):
    directory = Path(directory)
    if sha(directory/'sampling_manifest.json') != (directory/'sampling_manifest.sha256').read_text(encoding='ascii').strip():
        raise ValueError('Sampling manifest checksum changed')
    m = load(Path(directory)/'sampling_manifest.json')
    if m.get('round_manifest_sha256') and sha(Path(directory).parent/'selection_manifest.json')!=m['round_manifest_sha256']:
        raise ValueError('Round selection manifest changed')
    if sha(batch_guideline(directory,m)) != m['guideline_sha256']:
        raise ValueError('Pinned guideline snapshot changed')
    sources=m.get('source_files') or [dict(path=m['source_file'],sha256=m['source_sha256'])]
    for entry in sources:
        if sha(entry['path']) != entry['sha256']:raise ValueError('Pinned source changed')
    for p,h in m['protected_checksums'].items():
        if sha(p) != h: raise ValueError('Protected input changed')
    rows = m['selected_rows']
    if len(rows) != m['selected'] or len({r['comment_id'] for r in rows}) != m['selected']:
        raise ValueError('Invalid manifest ID coverage')
    expected = {r['comment_id']: r for r in rows}
    source = {}
    for entry in sources:
        with Path(entry['path']).open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('comment_id') in expected:
                    if r['comment_id'] in source:raise ValueError('Selected ID repeats across source exports')
                    source[r['comment_id']] = r
    if set(source) != set(expected) or any(digest(source[k]['text_clean']) != v['text_sha256'] for k,v in expected.items()):
        raise ValueError('Manifest text does not match pinned source')
    return m


def read_labels(path, manifest, annotator):
    headers, rows, tree = read_sheet(path, 'Gán nhãn')
    if headers != FIELDS: raise ValueError('Unexpected workbook schema')
    ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    for node in tree.findall('s:sheetData/s:row', ns)[1:]:
        cells = node.findall('s:c', ns)
        populated = [c for c in cells if c.findtext('s:v','',ns) or ''.join(c.itertext()).strip()]
        if populated and not any(re.fullmatch(r'A\d+',c.get('r','')) and ''.join(c.itertext()).strip() for c in populated):
            raise ValueError('Populated workbook row has no comment ID')
    expected = {r['comment_id']:r for r in manifest['selected_rows']}
    if len(rows) != len(expected) or len({r['comment_id'] for r in rows}) != len(rows) or {r['comment_id'] for r in rows} != set(expected):
        raise ValueError('Missing/duplicate/changed workbook IDs')
    result = []
    for row in rows:
        row = {k:literal_text(v) for k,v in row.items()}
        if digest(row['text_clean']) != expected[row['comment_id']]['text_sha256']: raise ValueError('Workbook text edited')
        if row['annotator_id'] != annotator: raise ValueError('Wrong annotator ID')
        label = row['sentiment_label'].strip().upper()
        if label not in LABELS: raise ValueError('Missing/invalid sentiment label')
        if label == 'REVIEW' and not row['note'].strip(): raise ValueError('REVIEW requires a note')
        result.append({**row, 'sentiment_label':label})
    return result


def metrics(left, right):
    if len(left) != len(right) or any(v not in LABELS for v in left+right): raise ValueError('Invalid decision pairs')
    if not left:
        return dict(n=0, agreement=None, kappa=None, kappa_reason='NO_PAIRS', categories=LABELS,
                    confusion_matrix=[[0]*5 for _ in LABELS], sentiment_only=None, sentiment_pair_count=0,
                    sentiment_kappa_reason='NO_SENTIMENT_PAIRS', sentiment_retention=0., label_counts_A={}, label_counts_B={}, review_exclude_disagreements=0)
    result = pair_metrics(left, right)
    result['kappa_reason'] = 'INSUFFICIENT_PAIRS' if len(left)<2 else 'DEGENERATE_MARGINALS' if result['kappa'] is None else None
    if len(left)<2: result['kappa'] = None
    sub = result['sentiment_only']; subset = [(a,b) for a,b in zip(left,right) if a in LABELS[:3] and b in LABELS[:3]]
    if sub is not None:
        reason = 'INSUFFICIENT_PAIRS' if len(subset)<2 else 'SINGLE_OBSERVED_CLASS' if len({x for pair in subset for x in pair})<2 else 'DEGENERATE_MARGINALS' if sub['kappa'] is None else None
        sub['kappa_reason'] = reason
        if reason: sub['kappa'] = None
    result.update(sentiment_retention=len(subset)/len(left), label_counts_A=dict(Counter(left)), label_counts_B=dict(Counter(right)),
                  sentiment_kappa_reason='NO_SENTIMENT_PAIRS' if sub is None else sub['kappa_reason'],
                  review_exclude_disagreements=sum(a!=b and (a in LABELS[3:] or b in LABELS[3:]) for a,b in zip(left,right)))
    return result


def adjudication_selection(left, right, agreement_audit_count=20):
    """All disagreements plus a separate SRS of agreements, no final labels."""
    if type(agreement_audit_count) is not int or agreement_audit_count < 0:
        raise ValueError('Agreement audit count must be a nonnegative integer')
    if len(left)!=len(right) or any(a['comment_id']!=b['comment_id'] or a['text_clean']!=b['text_clean'] for a,b in zip(left,right)):
        raise ValueError('Adjudication inputs must be aligned by ID and text')
    agreements = sorted((a['comment_id'] for a,b in zip(left,right) if a['sentiment_label']==b['sentiment_label']))
    audited = set(random.Random(SEED).sample(agreements, min(agreement_audit_count,len(agreements))))
    rows = []
    for a,b in zip(left,right):
        different = a['sentiment_label']!=b['sentiment_label']
        if not different and a['comment_id'] not in audited: continue
        data = dict(comment_id=a['comment_id'],text_clean=a['text_clean'],label_A=a['sentiment_label'],label_B=b['sentiment_label'],
                    note_A=a['note'],note_B=b['note'],final_label='',adjudication_note='')
        frozen = {k:data[k] for k in ADJUDICATION_SOURCE_FIELDS}
        rows.append(dict(data=data, review_type='DISAGREEMENT' if different else 'AGREEMENT_AUDIT',
                         immutable_sha256=digest(json.dumps(frozen,ensure_ascii=False,sort_keys=True))))
    # Put every disagreement first and retain original A order within each cohort.
    rows.sort(key=lambda r:r['review_type']!='DISAGREEMENT')
    return dict(seed=SEED,agreement_audit_requested=agreement_audit_count,agreement_available=len(agreements),
                agreement_audit_selected=len(audited),disagreements=len(left)-len(agreements),rows=rows,
                purpose='User adjudicator reviews A/B; not a third independent annotator; no automatic final labels or Gold')


def compare(directory=DEFAULT, output=None, agreement_audit_count=20):
    directory = Path(directory).resolve(); m = verify_manifest(directory)
    left_path=directory/'pilot_sentiment_annotator_A.xlsx'; right_path=directory/'pilot_sentiment_annotator_B.xlsx'
    hashes = {str(p):sha(p) for p in (left_path,right_path)}
    left = read_labels(left_path,m,'A'); right = read_labels(right_path,m,'B')
    lookup = {r['comment_id']:r for r in right}; right = [lookup[r['comment_id']] for r in left]
    result = metrics([r['sentiment_label'] for r in left], [r['sentiment_label'] for r in right])
    adjudication = adjudication_selection(left,right,agreement_audit_count)
    disagreements = [r['data'] for r in adjudication['rows'] if r['review_type']=='DISAGREEMENT']
    with staged(output or directory/'comparison') as work:
        write_jsonl(work/'annotator_A.local.jsonl',left); write_jsonl(work/'annotator_B.local.jsonl',right)
        save(work/'agreement.json',result)
        write_csv(work/'confusion_matrix.csv', [dict(label_A=cat, **dict(zip(LABELS,row))) for cat,row in zip(LABELS,result['confusion_matrix'])], ['label_A',*LABELS])
        write_csv(work/'disagreements.local.csv',disagreements,ADJUDICATION_SOURCE_FIELDS)
        write_csv(work/'adjudication.local.csv',[r['data'] for r in adjudication['rows']],ADJUDICATION_FIELDS)
        save(work/'adjudication_manifest.local.json',adjudication)
        save(work/'receipt.json',dict(manifest_sha256=sha(directory/'sampling_manifest.json'), workbook_sha256=hashes,
            created_at=datetime.now(timezone.utc).isoformat(), provenance='two independent human annotators; no automatic final label',
            agreement_sha256=sha(work/'agreement.json'),adjudication_manifest_sha256=sha(work/'adjudication_manifest.local.json'),
            guideline_status=m['guideline_status']))
        if any(sha(p)!=h for p,h in hashes.items()): raise ValueError('Workbook changed during comparison')
    return result


def import_adjudication(directory, comparison, decisions, output=None, adjudicator='user'):
    """Combine all A/B agreements and explicit review decisions; never write Gold."""
    directory=Path(directory).resolve();comparison=Path(comparison).resolve();decisions=Path(decisions).resolve()
    if not adjudicator.strip():raise ValueError('Adjudicator ID is required')
    m=verify_manifest(directory);receipt=load(comparison/'receipt.json')
    if sha(directory/'sampling_manifest.json')!=receipt['manifest_sha256']:raise ValueError('Pilot manifest changed')
    if sha(comparison/'agreement.json')!=receipt['agreement_sha256']:raise ValueError('Original A/B metrics changed')
    if sha(comparison/'adjudication_manifest.local.json')!=receipt['adjudication_manifest_sha256']:raise ValueError('Adjudication coordinator changed')
    for file,h in receipt['workbook_sha256'].items():
        if sha(file)!=h:raise ValueError('Original A/B workbook changed')
    coordinator=load(comparison/'adjudication_manifest.local.json')
    input_sha=sha(decisions)
    if decisions.suffix.lower()=='.xlsx':
        headers,rows,tree=read_sheet(decisions,'Đối soát')
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        for node in tree.findall('s:sheetData/s:row',ns)[1:]:
            cells=node.findall('s:c',ns)
            if any(''.join(c.itertext()).strip() for c in cells) and not any(re.fullmatch(r'A\d+',c.get('r','')) and ''.join(c.itertext()).strip() for c in cells):
                raise ValueError('Adjudication row has no ID')
        rows=[{k:literal_text(v) for k,v in r.items()} for r in rows]
    else:
        with decisions.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
    if headers!=ADJUDICATION_FIELDS:raise ValueError('Unexpected adjudication columns')
    expected={r['data']['comment_id']:r for r in coordinator['rows']}
    if len(rows)!=len(expected) or len({r['comment_id'] for r in rows})!=len(rows) or {r['comment_id'] for r in rows}!=set(expected):
        raise ValueError('Adjudication IDs missing, duplicated or changed')
    records=[]
    for row in rows:
        original=expected[row['comment_id']]
        frozen={k:row[k] for k in ADJUDICATION_SOURCE_FIELDS}
        if digest(json.dumps(frozen,ensure_ascii=False,sort_keys=True))!=original['immutable_sha256']:
            raise ValueError('Adjudication text or original A/B decision edited')
        label=(row['final_label'] or '').strip().upper()
        if label and label not in LABELS:raise ValueError('Invalid final_label')
        if label=='REVIEW' and not (row['adjudication_note'] or '').strip():raise ValueError('Final REVIEW requires a note')
        records.append({**row,'final_label':label,'review_type':original['review_type'],
                        'label_source':'ADJUDICATED' if label else 'PENDING_REVIEW','adjudicator_id':adjudicator if label else ''})
    left=read_labels(directory/'pilot_sentiment_annotator_A.xlsx',m,'A')
    right=read_labels(directory/'pilot_sentiment_annotator_B.xlsx',m,'B')
    by_id={r['comment_id']:r for r in left}
    left=[by_id[r['comment_id']] for r in m['selected_rows']]
    full,summary=final_decisions(left,right,records)
    if len(full)!=200 or {r['comment_id'] for r in full}!={r['comment_id'] for r in m['selected_rows']}:
        raise ValueError('Final pilot must contain exactly the original 200 unique IDs')
    trainable=[r for r in full if r['final_label'] in LABELS[:3] and r['label_source']!='PENDING_REVIEW']
    if sha(decisions)!=input_sha:raise ValueError('Adjudication input changed while reading')
    with staged(output or comparison/'adjudicated') as work:
        write_jsonl(work/'reviewed_decisions.local.jsonl',records)
        write_csv(work/'reviewed_decisions.local.csv',records,[*ADJUDICATION_FIELDS,'review_type','adjudicator_id'])
        fields=[*ADJUDICATION_FIELDS,'label_source','adjudicator_id','review_type','agreement_changed']
        write_csv(work/'pilot_final_decisions.local.csv',full,fields)
        write_csv(work/'pilot_trainable.local.csv',trainable,fields)
        save(work/'summary.json',summary)
        save(work/'receipt.json',dict(adjudicator=adjudicator,created_at=datetime.now(timezone.utc).isoformat(),
            comparison_receipt_sha256=sha(comparison/'receipt.json'),adjudication_input_sha256=input_sha,
            pilot_manifest_sha256=receipt['manifest_sha256'],guideline_sha256=m['guideline_sha256'],
            summary=summary,status=summary['status'],scope='guideline_development_pilot_not_gold_test',
            note='A/B originals and pre-adjudication Kappa unchanged; only agreements outside the review sample inherit A=B; no training or Gold import'))
        for file,h in receipt['workbook_sha256'].items():
            if sha(file)!=h:raise ValueError('Original A/B workbook changed during import')
        if sha(comparison/'agreement.json')!=receipt['agreement_sha256']:raise ValueError('Original Kappa changed during import')
    return summary


def final_decisions(left, right, reviewed):
    """Full pilot provenance; a blank required decision never inherits an A/B label."""
    a={r['comment_id']:r for r in left};b={r['comment_id']:r for r in right}
    review={r['comment_id']:r for r in reviewed}
    if len(a)!=len(left) or len(b)!=len(right) or set(a)!=set(b) or len(review)!=len(reviewed) or not set(review)<=set(a):
        raise ValueError('Full pilot IDs missing, duplicated or changed')
    full=[]
    for original in left:
        rid=original['comment_id'];other=b[rid];same=original['sentiment_label']==other['sentiment_label']
        if original['text_clean']!=other['text_clean']:raise ValueError('A/B text differs')
        if not same and rid not in review:raise ValueError('Missing required disagreement review row')
        row=dict(comment_id=rid,text_clean=original['text_clean'],label_A=original['sentiment_label'],label_B=other['sentiment_label'],
                 note_A=original['note'],note_B=other['note'])
        if rid in review:
            decision=review[rid]
            if any(decision[k]!=row[k] for k in ADJUDICATION_SOURCE_FIELDS):raise ValueError('Original A/B data edited in review')
            label=decision['final_label']
            if label and label not in LABELS:raise ValueError('Invalid final_label')
            if label=='REVIEW' and not decision['adjudication_note'].strip():raise ValueError('Final REVIEW requires a note')
            row.update(final_label=label,label_source='ADJUDICATED' if label else 'PENDING_REVIEW',
                       adjudicator_id=decision['adjudicator_id'] if label else '',adjudication_note=decision['adjudication_note'],
                       review_type=decision['review_type'],agreement_changed=bool(same and label and label!=row['label_A']))
        else:
            row.update(final_label=row['label_A'],label_source='AB_AGREE',adjudicator_id='',adjudication_note='',
                       review_type='AGREEMENT_NOT_SAMPLED',agreement_changed=False)
        full.append(row)
    counts=Counter(r['label_source'] for r in full);labels=Counter(r['final_label'] for r in full if r['final_label'])
    complete=not counts['PENDING_REVIEW'] and all(r['final_label'] in LABELS for r in full)
    summary=dict(total=len(full),label_sources={k:counts[k] for k in ('AB_AGREE','ADJUDICATED','PENDING_REVIEW')},
        final_label_counts={k:labels[k] for k in LABELS},trainable=sum(labels[k] for k in LABELS[:3]),
        review_exclude=labels['REVIEW']+labels['EXCLUDE'],changed_agreements=sum(r['agreement_changed'] for r in full),
        status='PILOT_ADJUDICATION_COMPLETE' if complete else 'INCOMPLETE_ADJUDICATION',scope='development_pilot_not_gold_test')
    return full,summary
