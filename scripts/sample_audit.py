"""Reproducible manual film-relevance audit; no sentiment inference or data edits."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil

SEED = 20261114
LABELS = ('RELEVANT', 'IRRELEVANT', 'UNCERTAIN')
EDITABLE = ('semantic_relevance', 'audit_reason', 'needs_context', 'confidence')
FIELDS = ('comment_id', 'post_id', 'post_url', 'source', 'source_type', 'movie_id',
          'comment_type', 'parent_comment_id', 'text_raw', 'text_clean', 'clean_status',
          'sample_stratum', 'sample_type', 'sample_reason', 'population_stratum_size',
          'random_stratum_n', 'inclusion_probability', 'sampling_weight', *EDITABLE)
IMMUTABLE = tuple(f for f in FIELDS if f not in EDITABLE)
DEFAULT_SOURCE = Path('data/imports/fb_54e6c18b6c514f9ab822354611ab3316/comments.csv')
DEFAULT_OUTPUT = Path('outputs/semantic_audit_20261114')
DEFAULT_GUIDELINE = Path('docs/guidelines/MOVIE_SENTIMENT_V2_1.md')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_hash(row):
    payload = json.dumps({k: row[k] for k in IMMUTABLE}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode('utf8')).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Missing/repeated CSV columns')
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('Malformed CSV row')
    return rows


def load_source(path):
    rows = read_csv(path)
    required = ('comment_id', 'post_id', 'post_url', 'source_name', 'movie_id',
                'record_type', 'parent_comment_id', 'text_raw', 'text_clean', 'clean_status')
    if not rows or any(not set(required) <= r.keys() for r in rows):
        raise ValueError('Source schema missing required columns')
    if len({r['comment_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate source comment IDs')
    eligible = [r for r in rows if r['clean_status'] == 'KEEP']
    for r in eligible:
        if (not all(r[k].strip() for k in ('comment_id', 'post_id', 'source_name', 'movie_id')) or
                r['record_type'] not in ('comment', 'reply')):
            raise ValueError('KEEP record lacks reliable identity/source/type')
    return rows, eligible


def allocate(sizes, total, minimum, maximum, weights):
    quotas = dict(minimum)
    if not sum(quotas.values()) <= total <= sum(maximum.values()):
        raise ValueError('Requested sample incompatible with fixed coverage/caps')
    while sum(quotas.values()) < total:
        candidates = [k for k in sorted(sizes) if quotas[k] < maximum[k]]
        key = max(candidates, key=lambda k: weights[k] / (quotas[k] + 1))
        quotas[key] += 1
    return quotas


def hard_flags(row, known_ids):
    """Sampling cues only, never relevance or sentiment labels."""
    text = row['text_clean']; flags = []
    short = len(text.split()) <= 6 or len(text) <= 35
    if short: flags.append('short')
    if re.search(r':\)+|=\)+|/s\b|mỉa mai|châm biếm', text, re.I): flags.append('sarcasm_cue')
    if re.search(r'\b(?:bạn|mày|ông|bà|fan|tranh luận|ý kiến|đồng ý)\b', text, re.I): flags.append('argument_cue')
    if '?' in text: flags.append('question')
    if row['record_type'] == 'reply' and (short or row['parent_comment_id'] not in known_ids):
        flags.append('reply_context_candidate')
    return flags


def frame_diagnostics(all_rows, eligible):
    known = {r['comment_id'] for r in all_rows}
    replies = [r for r in eligible if r['record_type'] == 'reply']
    return {'keep_replies': len(replies),
        'keep_replies_parent_not_in_export': sum(r['parent_comment_id'] not in known for r in replies),
        'keep_with_media': sum(int(r.get('non_text_media_count') or 0) > 0 for r in eligible),
        'keep_missing_created_at': sum(not r.get('comment_created_at') for r in eligible),
        'keep_missing_reaction_count': sum(r.get('reaction_count', '') == '' for r in eligible),
        'post_text_not_exported': not any('post_text' in r for r in all_rows)}


def select_sample(eligible, seed=SEED, random_count=240, hard_count=60):
    strata = defaultdict(list)
    for r in eligible: strata[(r['post_id'], r['record_type'])].append(r)
    sizes = {k: len(v) for k, v in strata.items()}
    post_sizes = Counter()
    minimum = Counter()
    for (post, kind), n in sizes.items():
        post_sizes[post] += n; minimum[post] += min(2, n)
    post_n = allocate(post_sizes, random_count, minimum,
        {p: min(n, 14) for p, n in post_sizes.items()}, {p: math.sqrt(n) for p, n in post_sizes.items()})
    quotas = {}
    for post in sorted(post_sizes):
        subset = {k: n for k, n in sizes.items() if k[0] == post}
        quotas.update(allocate(subset, post_n[post], {k: min(n, 2) for k, n in subset.items()}, subset, subset))
    rng = random.Random(seed); sampled = []; manifest_strata = []
    for key in sorted(strata):
        candidates = sorted(strata[key], key=lambda r: r['comment_id'])
        n, population = quotas[key], sizes[key]
        if len({(r['source_name'], r['movie_id']) for r in candidates}) != 1:
            raise ValueError('Source/movie inconsistent within post stratum')
        manifest_strata.append({'key': key[0] + '::' + key[1], 'post_id': key[0],
            'comment_type': key[1], 'source': candidates[0]['source_name'], 'movie_id': candidates[0]['movie_id'],
            'N': population, 'n': n, 'probability': n / population})
        sampled.extend((r, 'random', '') for r in rng.sample(candidates, n))
    chosen = {r['comment_id'] for r, _, _ in sampled}
    known = {r['comment_id'] for r in eligible}
    remaining = [r for r in sorted(eligible, key=lambda r: r['comment_id']) if r['comment_id'] not in chosen]
    flags = {r['comment_id']: hard_flags(r, known) for r in remaining}
    categories = ('short', 'sarcasm_cue', 'argument_cue', 'question', 'reply_context_candidate')
    buckets = {tag: [r for r in remaining if tag in flags[r['comment_id']]] for tag in categories}
    for bucket in buckets.values(): rng.shuffle(bucket)
    hard_posts = Counter(); hard_selected = 0
    while hard_selected < hard_count:
        progress = False
        for tag in categories:
            while buckets[tag]:
                r = buckets[tag].pop()
                if r['comment_id'] in chosen or hard_posts[r['post_id']] >= 6: continue
                reason = 'primary=' + tag + '; cues=' + ','.join(flags[r['comment_id']])
                sampled.append((r, 'hard', reason)); chosen.add(r['comment_id'])
                hard_posts[r['post_id']] += 1; hard_selected += 1; progress = True
                break
            if hard_selected == hard_count: break
        if not progress: raise ValueError('Insufficient hard candidates under cap 6/post; protocol not relaxed')
    rng.shuffle(sampled); output = []
    for r, typ, reason in sampled:
        key = (r['post_id'], r['record_type']); N, n = sizes[key], quotas[key]
        item = {k: '' for k in FIELDS}
        item.update({k: r.get(k, '') for k in ('comment_id', 'post_id', 'post_url', 'source_type',
                     'movie_id', 'parent_comment_id', 'text_raw', 'text_clean', 'clean_status')})
        item.update(source=r['source_name'], comment_type=r['record_type'],
            sample_stratum=key[0] + '::' + key[1], sample_type=typ, sample_reason=reason,
            population_stratum_size=str(N), random_stratum_n=str(n),
            inclusion_probability=format(n / N, '.17g') if typ == 'random' else '',
            sampling_weight=format(N / n, '.17g') if typ == 'random' else '')
        output.append(item)
    if len({r['comment_id'] for r in output}) != random_count + hard_count:
        raise ValueError('Sample IDs not unique')
    return output, manifest_strata


def estimate(rows, strata, label):
    """Finite-population stratified SRSWOR; hard rows never enter the estimator."""
    N = sum(h['N'] for h in strata); point = variance = 0.; census = True; variance_estimable = True
    for h in strata:
        selected = [r for r in rows if r['sample_type'] == 'random' and r['sample_stratum'] == h['key']]
        if len(selected) != h['n'] or any(not r['semantic_relevance'].strip() for r in selected): return None
        values = [float(r['semantic_relevance'].strip().upper() == label) for r in selected]
        n = h['n']; p = sum(values) / n; weight = h['N'] / N
        point += weight * p
        if n < h['N']:
            census = False
            if n < 2:
                variance_estimable = False
                continue
            s2 = sum((v - p) ** 2 for v in values) / (n - 1)
            variance += weight ** 2 * (1 - n / h['N']) * s2 / n
    # Zero observed variance outside a census does not establish certainty.
    ci = None if not variance_estimable or variance == 0 and not census else [max(0., point - 1.96 * math.sqrt(variance)),
                                                   min(1., point + 1.96 * math.sqrt(variance))]
    return {'rate': point, 'variance': variance if variance_estimable else None, 'ci95': ci}


def validate_audit(rows, manifest):
    expected = {r['comment_id']: r for r in manifest['selected']}
    if len(rows) != len(expected) or {r['comment_id'] for r in rows} != set(expected):
        raise ValueError('Missing, repeated or unexpected audit ID')
    for r in rows:
        if row_hash(r) != expected[r['comment_id']]['immutable_sha256']:
            raise ValueError('Source text/metadata/sampling fields edited: ' + r['comment_id'])
        label = r['semantic_relevance'].strip().upper()
        if label and label not in LABELS: raise ValueError('Invalid relevance label: ' + r['comment_id'])
        if label:
            if r['needs_context'].strip().upper() not in ('YES', 'NO') or r['confidence'].strip().upper() not in ('HIGH', 'MEDIUM', 'LOW'):
                raise ValueError('Fill needs_context/confidence: ' + r['comment_id'])
            if label != 'RELEVANT' and not r['audit_reason'].strip():
                raise ValueError('Reason required for IRRELEVANT/UNCERTAIN: ' + r['comment_id'])


def write_report(directory):
    directory = Path(directory); manifest = json.loads((directory / 'sampling_manifest.json').read_text(encoding='utf8'))
    if sha(manifest['source_file']) != manifest['source_sha256']: raise ValueError('Source checksum changed')
    if sha(manifest['guideline_file']) != manifest['guideline_sha256']: raise ValueError('Guideline checksum changed')
    rows = read_csv(directory / 'audit_sample.csv'); validate_audit(rows, manifest)
    labelled = [r for r in rows if r['semantic_relevance'].strip()]
    lines = ['# Audit semantic relevance — chưa phải Gold/sentiment', '',
        'Audit phụ trợ về mức liên quan phim; không thay mục tiêu cảm xúc chung của V2, không tự lọc dữ liệu.',
        f"Nguồn: {manifest['source_records']} dòng; KEEP frame: {manifest['eligible_records']}; seed {manifest['seed']}.",
        f"Mẫu {len(rows)} = {manifest['random_count']} random + {manifest['hard_count']} hard, {len({r['post_id'] for r in rows})} bài, {len({r['source'] for r in rows})} nguồn.",
        f'Đã có quyết định: {len(labelled)}/{len(rows)}. Không có nhãn AI hoặc nhãn tự động.', '',
        '## Sampling', '', '| Cohort | Comment | Reply | Bài | Nguồn |', '|---|---:|---:|---:|---:|']
    for typ in ('random', 'hard'):
        cohort = [r for r in rows if r['sample_type'] == typ]; counts = Counter(r['comment_type'] for r in cohort)
        lines.append(f"| {typ} | {counts['comment']} | {counts['reply']} | {len({r['post_id'] for r in cohort})} | {len({r['source'] for r in cohort})} |")
    lines += ['', 'Random: post × comment/reply; quota theo sqrt(quy mô bài), tối đa 14/post; SRSWOR trong mỗi tầng.',
        'Mỗi tầng không census có ít nhất 2 mẫu. Hard: cues ngắn/mỉa mai/tranh luận/câu hỏi/reply, tối đa 6/post; cues không phải nhãn.',
        'Giữ mọi bài/nguồn có KEEP. Mẫu hiện là quan sát phát triển, không dùng làm independent test.', '',
        '## Nhãn thực tế và ước lượng', '']
    diagnostics = manifest.get('frame_diagnostics')
    if diagnostics:
        lines[-2:-2] = ['## Giới hạn ngữ cảnh', '',
            f"Reply KEEP có parent không nằm trong export: {diagnostics['keep_replies_parent_not_in_export']}/{diagnostics['keep_replies']}.",
            f"KEEP có media: {diagnostics['keep_with_media']}; không OCR/ảnh trong audit. Thiếu created_at: {diagnostics['keep_missing_created_at']}; thiếu reaction: {diagnostics['keep_missing_reaction_count']}.",
            'Audit CSV không kèm parent_text/post_text. Có thể đối chiếu cha qua ID trong nguồn local được phép; nếu không có thì ghi needs_context, không đoán từ movie_id.', '']
    if not labelled:
        lines += ['Chờ người gán: tỷ lệ RELEVANT/IRRELEVANT/UNCERTAIN, lý do và ví dụ xác nhận đều **chưa có**.',
                  'Chưa kết luận nguồn/bài nào kém hoặc dataset đã sạch; chưa có CI vì thiếu nhãn.']
    for typ in ('random', 'hard'):
        cohort = [r for r in labelled if r['sample_type'] == typ]
        if cohort:
            counts = Counter(r['semantic_relevance'].strip().upper() for r in cohort)
            lines.append(f"- {typ}: n đã gán={len(cohort)}; " + '; '.join(f'{label}={counts[label]} ({counts[label]/len(cohort):.1%})' for label in LABELS) + '. Đây là tỷ lệ trong phần đã gán, không phải ước lượng quần thể.')
    if labelled:
        lines += ['', '| Nhãn | Ước lượng KEEP frame | CI 95% xấp xỉ |', '|---|---:|---|']
        for label in LABELS:
            result = estimate(rows, manifest['strata'], label)
            if result is None: lines.append(f'| {label} | Chờ đủ nhãn random | — |')
            else:
                ci = result['ci95']; bounds = f'{ci[0]:.1%} – {ci[1]:.1%}' if ci is not None else 'Không ước lượng được đáng tin từ phương sai mẫu'
                lines.append(f"| {label} | {result['rate']:.1%} | {bounds} |")
    lines += ['', 'Ước lượng chỉ cho KEEP frame đã crawl, không cho 2.521 dòng hay toàn Facebook. Không đưa hard vào ước lượng.',
        'CI dùng phương sai SRS phân tầng có finite-population correction, không coi 300 dòng là IID; CI normal là xấp xỉ, không đo lỗi gán nhãn.', '',
        '## Theo loại, nguồn và bài', '', '| Nhóm | Giá trị | Random n | Hard n | Đã gán | RELEVANT (random) | IRRELEVANT (random) | UNCERTAIN (random) |', '|---|---|---:|---:|---:|---|---|---|']
    for key in ('comment_type', 'source', 'post_id'):
        for value in sorted({r[key] for r in rows}):
            subset = [r for r in rows if r[key] == value]; done = [r for r in subset if r['semantic_relevance'].strip()]
            domain = [h for h in manifest['strata'] if h[key] == value]
            cells = []
            for label in LABELS:
                result = estimate(rows, domain, label)
                if result is None: cells.append('Chờ nhãn random')
                else:
                    ci = result['ci95']
                    bounds = f" [{ci[0]:.1%}, {ci[1]:.1%}]" if ci else ' (CI chưa đủ căn cứ)'
                    cells.append(f"{result['rate']:.1%}" + bounds)
            lines.append(f"| {key} | {value} | {sum(r['sample_type']=='random' for r in subset)} | {sum(r['sample_type']=='hard' for r in subset)} | {len(done)} | " + ' | '.join(cells) + ' |')
    lines += ['', 'Tỷ lệ theo nhóm dùng random và trọng số N_h/n_h; hard chỉ báo số lượng. CI xấp xỉ có thể rất rộng ở bài ít mẫu; không xếp hạng nguồn chỉ theo điểm ước lượng.', '', '## Lý do và ví dụ', '']
    reasons = Counter((r['sample_type'], r['audit_reason'].split(':', 1)[0].strip()) for r in labelled if r['semantic_relevance'].strip().upper() == 'IRRELEVANT')
    lines += [f'- {cohort}, {reason}: {n}' for (cohort, reason), n in sorted(reasons.items())] or ['Chờ nhãn người.']
    for label in LABELS:
        for r in sorted((r for r in labelled if r['semantic_relevance'].strip().upper() == label), key=lambda r: r['comment_id'])[:2]:
            text = r['text_clean'].replace('|', '\\|').replace('\n', ' ')
            lines.append(f"- {label}, {r['sample_type']}, ID {r['comment_id']}: {text[:240]}{'…' if len(text)>240 else ''}")
    lines += ['', 'Không tự loại dòng hoặc đổi sentiment. Chưa nên mở rộng chỉ để đạt 10k trước khi có audit; sau gán xem riêng random theo nguồn/bài và số mẫu, không kết luận từ hard hay một vài ca.',
        '', '## Tái lập', '', 'Xem sampling_manifest.json cho SHA, N_h/n_h, xác suất, ID và hash trường bất biến. Hướng dẫn lệnh ở REPRODUCE.md.']
    (directory / 'audit_report.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    return {'rows': len(rows), 'labelled': len(labelled), 'random': manifest['random_count'], 'hard': manifest['hard_count']}


def sample(source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT, guideline=DEFAULT_GUIDELINE):
    source, output, guideline = Path(source).resolve(), Path(output).resolve(), Path(guideline).resolve()
    if output.exists(): raise FileExistsError('Choose a new output directory')
    before = sha(source); all_rows, eligible = load_source(source)
    # Existing guard, metadata only. No gold text/labels are inspected.
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from src.dataset.blind import assert_allowed
    assert_allowed([{'comment_id': r['comment_id'], 'post_id': r['post_id'], 'post_url': r['post_url'], 'platform': 'facebook'} for r in eligible], 'guideline_tuning')
    rows, strata = select_sample(eligible)
    manifest = {'source_file': str(source), 'source_sha256': before, 'source_records': len(all_rows),
        'eligible_records': len(eligible), 'guideline_file': str(guideline), 'guideline_sha256': sha(guideline),
        'seed': SEED, 'random_count': 240, 'hard_count': 60, 'random_post_cap': 14, 'hard_post_cap': 6,
        'strata': strata, 'selected': [{'comment_id': r['comment_id'], 'sample_type': r['sample_type'],
            'immutable_sha256': row_hash(r)} for r in rows], 'source_code_sha256': sha(__file__),
        'frame_diagnostics': frame_diagnostics(all_rows, eligible),
        'scope': 'auxiliary film-relevance audit, development exposure, not independent test or sentiment labels'}
    output.mkdir(parents=True)
    with (output / 'audit_sample.csv').open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    (output / 'sampling_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (output / 'audit_guideline.md').write_text('''# Hướng dẫn audit relevance (không gán sentiment)

Đọc text_clean; text_raw chỉ để đối chiếu. Không sửa text, ID, metadata hoặc cột sampling.
Tham chiếu MOVIE_SENTIMENT_V2_1.md (mới hơn V2_0), giữ nguyên bản chính thức và hash.
Đây là audit phụ trợ về phim; không tự thay mục tiêu cảm xúc chung của V2 hoặc lọc dataset.

- RELEVANT: nhận xét/thái độ/thông tin/câu hỏi trực tiếp về phim, kịch bản, diễn xuất trong phim,
  hình ảnh, âm thanh, nhân vật hoặc trải nghiệm xem theo guideline. Thông tin trung lập có thể relevant.
- IRRELEVANT: chỉ tag/gọi bạn, công kích người bình luận, đời tư/ngoại hình diễn viên ngoài phim,
  spam hoặc chuyện ngoài lề mà không còn nội dung về phim. Không suy từ NEU thành IRRELEVANT.
- UNCERTAIN: thiếu parent/post/media hoặc không biết đối tượng được nói tới. Không đoán từ movie_id,
  từ khóa, emoji hay tên nhóm. Có vẻ mỉa mai không tự đồng nghĩa relevant/irrelevant.

Chỉ điền semantic_relevance, audit_reason, needs_context (YES/NO), confidence (HIGH/MEDIUM/LOW).
IRRELEVANT/UNCERTAIN phải có lý do. Có thể ghi mã: TAG_CALL, PERSON_ATTACK, OFF_TOPIC, SPAM,
NON_EVALUATIVE_CHAT, CONTEXT_MISSING, TARGET_AMBIGUOUS, OTHER, rồi : mô tả.
Confidence nói về quyết định relevance, không phải xác suất sentiment.
Không có ngữ cảnh được xác thực thì needs_context=YES và thường UNCERTAIN. Không tự tìm thêm trên web.
Tên phim/diễn viên viết thuần và câu hỏi thông tin phim không bị loại chỉ vì thiếu khen/chê.

Random/hard là cách lấy mẫu, không phải nhãn. Hard cues không có giá trị gợi ý nhãn chính thức.
Không xem toàn bộ 300 như mẫu IID: chỉ random có xác suất chọn được xác định, hard không dùng ước lượng.
Chỉ ước lượng cho KEEP frame hiện có. Không có nhãn AI/overall hoặc POS/NEG/NEU trong file này.

CSV UTF-8: nếu dùng Excel, import ID ở dạng Text, không mở theo cách tự chuyển ID thành số/khoa học.
Giữ bản gốc và chỉ sửa bốn cột cho người gán; script tổng hợp sẽ kiểm ID và hash các trường còn lại.
''', encoding='utf8')
    shutil.copyfile(Path(__file__).resolve(), output / 'sample_audit.py')
    (output / 'REPRODUCE.md').write_text(f'''# Nguồn và tái lập

Nguồn: `{source}`; SHA-256: `{before}`.
Seed: {SEED}. Một script dùng hai chế độ, không thêm wrapper/framework.
Chạy từ root repo với Python hiện có, không cần API hoặc dependency mới:

```powershell
python scripts/sample_audit.py sample --source "{source}" --output outputs/semantic_audit_NEW
python scripts/sample_audit.py summarize --directory outputs/semantic_audit_20261114
```

Trong thư mục output có snapshot `sample_audit.py` cùng SHA code để tái lập; có thể dùng snapshot
thay đường dẫn script trong lệnh trên, vẫn chạy từ root repo. Không ghi đè output đã có.
Summarize chỉ cập nhật audit_report.md; không sửa CSV, raw, labels, canonical hay Gold.
Mẫu random: phân tầng post × type, điều tiết quota sqrt(N_post), cap 14/post,
min(2,N_h)/tầng, SRSWOR n_h/N_h; hard chọn sau random, cap 6/post, round-robin cues.
Hard và random không trùng ID. Các trường quyết định người để trống lúc xuất.
Không dùng mẫu này hoặc các post đã audit làm independent test về sau.
''', encoding='utf8')
    if sha(source) != before: raise ValueError('Source changed during sampling')
    return write_report(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='cmd', required=True)
    p = commands.add_parser('sample'); p.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); p.add_argument('--guideline', type=Path, default=DEFAULT_GUIDELINE)
    p = commands.add_parser('summarize'); p.add_argument('--directory', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = sample(args.source, args.output, args.guideline) if args.cmd == 'sample' else write_report(args.directory)
        print(json.dumps(result))
    except (ValueError, OSError) as error: parser.exit(2, str(error) + '\n')


if __name__ == '__main__': main()
