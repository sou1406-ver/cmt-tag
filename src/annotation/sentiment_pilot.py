"""Offline two-person text-only pilot. No canonical writes, models or API calls."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import random
import re

from src.dataset.common import (ROOT, digest, load, normal, read_sheet, literal_text,
    save, sha, staged, write_csv, write_jsonl)
from src.dataset.blind import assert_allowed
from .core import pair_metrics
from .pilot import fingerprints, near_any, protection, guard_reason

SEED = 20261115
LABELS = ['POS', 'NEG', 'NEU', 'REVIEW', 'EXCLUDE']
FIELDS = ['comment_id', 'text_clean', 'sentiment_label', 'note', 'annotator_id', 'cleaning_issue']
DEFAULT = ROOT/'outputs/sentiment_pilot_v3_1'
SOURCE = ROOT/'data/imports/fb_54e6c18b6c514f9ab822354611ab3316/comments.csv'
PROPOSAL = ROOT/'docs/guidelines/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md'


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
    if not source.is_file() or not PROPOSAL.is_file(): raise FileNotFoundError('Source/proposal required')
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
    if sha(source) != before or any(sha(p) != h for p,h in guard['checksums'].items()):
        raise ValueError('Protected/source input changed during prepare')
    manifest = dict(status='DRAFT_GUIDELINE_SOURCE_MISSING', guideline_status='PROPOSAL_NOT_APPROVED',
        guideline_file=str(PROPOSAL), guideline_sha256=sha(PROPOSAL), source_file=str(source), source_sha256=before,
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
        save(work/'sampling_manifest.json', manifest)
        (work/'sampling_manifest.sha256').write_text(sha(work/'sampling_manifest.json')+'\n', encoding='ascii')
        save(work/'workbook_input.local.json', [dict(comment_id=r['comment_id'], text_clean=r['text_clean']) for r in selected])
        write_csv(work/'exclusions.local.csv', rejected, ['comment_id','reason'])
        (work/'README.md').write_text('''# Pilot sentiment text-only — DRAFT

Chưa tìm được V3 gốc. Bản bổ sung nằm ở docs/guidelines/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md; chưa coi là V3.1 chính thức. Đối chiếu V3 trước khi giao gán.
Hai workbook có cùng 200 ID/thứ tự, gồm 160 random + 40 hard, trộn mù; không có nhãn điền sẵn. Chỉ đọc text_clean, không parent/post; không dùng nhãn relevance cũ. Cột vàng sentiment_label/note để người gán điền; REVIEW phải có note ngắn, không có confidence bắt buộc. cleaning_issue dành cho lỗi text, không sửa text.
Tái lập: python -m src.annotation sentiment-pilot prepare --directory outputs/sentiment_pilot_NEW
Xuất Excel bằng scripts/export_sentiment_pilot.mjs với Node/@oai/artifact-tool bundled; builder không ghi đè workbook đã có.
Sau khi gán độc lập: python -m src.annotation sentiment-pilot compare --directory outputs/sentiment_pilot_v3_1
Compare kiểm toàn bộ hai file trước khi xuất thư mục comparison riêng; lưu nhãn A/B, Kappa chính 5 nhãn, Kappa phụ 3 nhãn, disagreement và adjudication trống. Không ghi canonical/Gold. Không chạy compare trên workbook chưa điền.
sampling_manifest.json khóa seed, nguồn, text SHA, cohort và exposure. Pilot/cùng post phải loại khỏi independent test tương lai; dùng manifest này khi kiểm exposure. Không sửa frozen split hoặc reservation cũ.
''', encoding='utf8')
        (work/'REPORT.md').write_text('# Kết quả pilot sentiment\n\nChưa có nhãn sentiment thật; Kappa, agreement và confusion matrix: CHƯA CÓ.\nGuideline đang là đề xuất do thiếu V3 gốc. Không tự phê duyệt.\n', encoding='utf8')
    return {k: manifest[k] for k in ('status','eligible_records','selected','counts','exclusions')}


def verify_manifest(directory):
    directory = Path(directory)
    if sha(directory/'sampling_manifest.json') != (directory/'sampling_manifest.sha256').read_text(encoding='ascii').strip():
        raise ValueError('Sampling manifest checksum changed')
    m = load(Path(directory)/'sampling_manifest.json')
    for key, h in [('source_file','source_sha256'), ('guideline_file','guideline_sha256')]:
        if sha(m[key]) != m[h]: raise ValueError('Pinned source/guideline changed')
    for p,h in m['protected_checksums'].items():
        if sha(p) != h: raise ValueError('Protected input changed')
    rows = m['selected_rows']
    if len(rows) != m['selected'] or len({r['comment_id'] for r in rows}) != m['selected']:
        raise ValueError('Invalid manifest ID coverage')
    expected = {r['comment_id']: r for r in rows}
    source = {}
    with Path(m['source_file']).open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('comment_id') in expected: source[r['comment_id']] = r
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


def compare(directory=DEFAULT, output=None):
    directory = Path(directory).resolve(); m = verify_manifest(directory)
    left_path=directory/'pilot_sentiment_annotator_A.xlsx'; right_path=directory/'pilot_sentiment_annotator_B.xlsx'
    hashes = {str(p):sha(p) for p in (left_path,right_path)}
    left = read_labels(left_path,m,'A'); right = read_labels(right_path,m,'B')
    lookup = {r['comment_id']:r for r in right}; right = [lookup[r['comment_id']] for r in left]
    result = metrics([r['sentiment_label'] for r in left], [r['sentiment_label'] for r in right])
    disagreements = [dict(comment_id=a['comment_id'], text_clean=a['text_clean'], label_A=a['sentiment_label'],
        note_A=a['note'], label_B=b['sentiment_label'], note_B=b['note'], label_final='', note_final='')
        for a,b in zip(left,right) if a['sentiment_label'] != b['sentiment_label']]
    with staged(output or directory/'comparison') as work:
        write_jsonl(work/'annotator_A.local.jsonl',left); write_jsonl(work/'annotator_B.local.jsonl',right)
        save(work/'agreement.json',result)
        write_csv(work/'confusion_matrix.csv', [dict(label_A=cat, **dict(zip(LABELS,row))) for cat,row in zip(LABELS,result['confusion_matrix'])], ['label_A',*LABELS])
        fields=['comment_id','text_clean','label_A','note_A','label_B','note_B','label_final','note_final']
        write_csv(work/'disagreements.local.csv',disagreements,fields[:-2])
        write_csv(work/'adjudication.local.csv',disagreements,fields)
        save(work/'receipt.json',dict(manifest_sha256=sha(directory/'sampling_manifest.json'), workbook_sha256=hashes,
            created_at=datetime.now(timezone.utc).isoformat(), provenance='two independent human annotators; no automatic final label',
            guideline_status=m['guideline_status']))
        if any(sha(p)!=h for p,h in hashes.items()): raise ValueError('Workbook changed during comparison')
    return result
