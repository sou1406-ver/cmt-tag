"""Read-only crawl inventory and manual relevance audit; no sentiment inference."""
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
import posixpath
import zipfile
import xml.etree.ElementTree as ET
import html
import statistics
import unicodedata

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
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.annotation.guidelines import GUIDELINE, resolve_guideline
DEFAULT_GUIDELINE = GUIDELINE
V2_RUNS = ('fb_54e6c18b6c514f9ab822354611ab3316', 'fb_541bedc5adb54db295e456ed1a5dc62c',
           'fb_cc583df7d16947a2aef7949550fa276d', 'fb_a767303a5ad8426d8fad5accb8a313cb')


def sha(path):
    return hashlib.sha256(resolve_guideline(path).read_bytes()).hexdigest()


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


def xlsx_rows(path, sheet_name, required):
    """Read literal cells only; no optional Excel dependency or formula labels."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next((s for s in wb.findall('s:sheets/s:sheet', ns) if s.get('name') == sheet_name), None)
        if sheet is None: raise ValueError('Missing worksheet: ' + sheet_name)
        rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel = next(r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if r.get('Id') == rid)
        target = rel.get('Target', '')
        target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        if rel.get('TargetMode') == 'External' or not target.startswith('xl/worksheets/'):
            raise ValueError('Invalid worksheet relationship')
        strings = [''.join(t.text or '' for t in x.iter('{' + ns['s'] + '}t'))
                   for x in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        header = None; output = []
        for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row', ns):
            cells = {}
            for cell in row.findall('s:c', ns):
                if cell.find('s:f', ns) is not None: raise ValueError('Formulas are not human annotation values')
                col = 0
                for c in re.sub(r'\d', '', cell.get('r')): col = col * 26 + ord(c) - 64
                value = cell.findtext('s:v', '', ns)
                if cell.get('t') == 's': value = strings[int(value)]
                elif cell.get('t') == 'inlineStr': value = ''.join(t.text or '' for t in cell.findall('.//s:t', ns))
                cells[col] = value[1:] if value.startswith("'=") else value
            if not header:
                if set(required) <= set(cells.values()):
                    header = {col: name for col, name in cells.items() if name}
                    if len(set(header.values())) != len(header): raise ValueError('Duplicate workbook header')
            else:
                item = {name: cells.get(col, '') for col, name in header.items()}
                if item.get('comment_id'): output.append(item)
        if header is None: raise ValueError('Missing workbook columns: ' + sheet_name)
    return output


def read_audit(directory, manifest, workbook=None):
    directory = Path(directory); original = read_csv(directory / 'audit_sample.csv')
    validate_audit(original, manifest)
    explicit_workbook = workbook is not None
    workbook = Path(workbook) if workbook else directory / 'audit_sample.xlsx'
    if not workbook.exists():
        if explicit_workbook:
            raise FileNotFoundError(workbook)
        return original
    reference = xlsx_rows(workbook, 'Đối chiếu', IMMUTABLE)
    check = [{**r, **{key: '' for key in EDITABLE}} for r in reference]
    validate_audit(check, manifest)
    review = xlsx_rows(workbook, 'Gán nhãn', ('comment_id', 'text_clean', *EDITABLE))
    expected = {r['comment_id']: r for r in original}
    if len(review) != len(expected) or len({r['comment_id'] for r in review}) != len(expected) or {r['comment_id'] for r in review} != set(expected):
        raise ValueError('Workbook IDs missing, repeated or unexpected')
    output = []
    for item in review:
        base = expected[item['comment_id']]
        if item['text_clean'] != base['text_clean']: raise ValueError('Workbook text edited: ' + item['comment_id'])
        for key in EDITABLE:
            if base[key].strip() and base[key].strip() != item[key].strip():
                raise ValueError('Workbook conflicts with an existing CSV decision: ' + item['comment_id'])
        output.append({**base, **{key: item[key] for key in EDITABLE}})
    validate_audit(output, manifest)
    return output


def write_report(directory, workbook=None):
    directory = Path(directory); manifest = json.loads((directory / 'sampling_manifest.json').read_text(encoding='utf8'))
    if sha(manifest['source_file']) != manifest['source_sha256']: raise ValueError('Source checksum changed')
    if sha(manifest['guideline_file']) != manifest['guideline_sha256']: raise ValueError('Guideline checksum changed')
    rows = read_audit(directory, manifest, workbook)
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
Tham chiếu guideline chính thức đã ghi SHA tại thời điểm chọn mẫu.
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


def crawl_inventory(rows):
    """Descriptive text/metadata diagnostics only; never infer sentiment or delete rows."""
    from src.dataset.common import normal
    from src.annotation.pilot import fingerprints
    if not rows: raise ValueError('Empty crawl inventory')
    ids = Counter(r['comment_id'] for r in rows); lookup = {r['comment_id']:r for r in rows}
    flags = defaultdict(list); exact = defaultdict(list); controls = Counter(); evidence = Counter()
    metadata = ('comment_id','post_id','post_url','parent_comment_id','movie_id','source_name','source_type',
                'collected_at','crawl_run_id','comment_created_at','reaction_count')
    url = re.compile(r'(?i)\b(?:https?://|www\.)\S+')
    emoticon = re.compile(r'(?i)(?:[:;=8][-^]?[)(DPpVv]+|:D|:P|-_-)')
    emoji = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')
    def number(r,k): return int(r.get(k) or 0)
    for r in rows:
        rid=r['comment_id']; text=r['text_clean']; raw=r['text_raw']
        signal = dict(empty_clean=not text.strip(),url_remaining=bool(url.search(text)),
            html_entity=html.unescape(text)!=text,not_nfc=unicodedata.normalize('NFC',text)!=text,
            replacement_character='\uFFFD' in text,underscore='_' in text,
            emoji_symbol=bool(emoji.search(text)),emoticon=bool(emoticon.search(text)),
            teencode=bool(re.search(r'(?iu)\b(ko|k|đc|cx|mn|khum)\b',text)),
            negation=bool(re.search(r'(?iu)\b(không|chưa|chẳng|chả|ko|k|đéo|đếch)\b',text)),
            very_long=len(text)>1000,short_2_words=len(text.split())<=2 and bool(text.strip()),
            raw_clean_changed=raw!=text,with_media=number(r,'non_text_media_count')>0,
            with_removed_mentions=number(r,'mention_count')>0,with_removed_urls=number(r,'url_count')>0,
            keep_without_letters=r['clean_status']=='KEEP' and not any(c.isalpha() for c in text))
        cc=Counter(f'U+{ord(c):04X}' for c in text if unicodedata.category(c)=='Cc' and c not in '\t\n\r')
        controls.update(cc);signal['control_character']=bool(cc)
        for key,value in signal.items():
            if value:flags[key].append(rid)
        if text.strip():exact[normal(text)].append(r)
        for event in json.loads(r.get('clean_evidence') or '[]'):evidence[event.get('kind','UNKNOWN')]+=1
    # Direct unique-text pairs only; no transitive giant components and no auto-removal.
    values=[];postings=defaultdict(set);near=[];near_ids=set();cross_pairs=0
    for text,group in sorted(exact.items()):
        features=fingerprints(text)
        if not features:continue
        overlap=Counter(i for key in features for i in postings[key])
        for i,n in overlap.items():
            old_features,old_group=values[i];score=n/(len(features)+len(old_features)-n)
            if score>=.9:
                near.append(dict(left_ids=[r['comment_id'] for r in old_group],right_ids=[r['comment_id'] for r in group],jaccard=score))
                near_ids.update(r['comment_id'] for r in old_group+group)
                cross_pairs+=sum(a['post_id']!=b['post_id'] for a in old_group for b in group)
        idx=len(values);values.append((features,group))
        for key in features:postings[key].add(idx)
    def distribution(key, subset):
        counts=Counter(r[key] for r in subset)
        return dict(sorted(counts.items(),key=lambda item:(-item[1],item[0])))
    def lengths(subset):
        def describe(values):
            values=sorted(values)
            return dict(median=statistics.median(values),p90=values[math.ceil(.9*len(values))-1],max=max(values)) if values else dict(median=None,p90=None,max=None)
        return dict(characters=describe([len(r['text_clean']) for r in subset]),words=describe([len(r['text_clean'].split()) for r in subset]))
    replies=[r for r in rows if r['record_type']=='reply']
    missing_parent=[r['comment_id'] for r in replies if not r.get('parent_comment_id') or r['parent_comment_id'] not in lookup]
    wrong_post=[r['comment_id'] for r in replies if r.get('parent_comment_id') in lookup and lookup[r['parent_comment_id']]['post_id']!=r['post_id']]
    groups=[g for g in exact.values() if len(g)>1]
    keep=[r for r in rows if r['clean_status']=='KEEP'];keep_ids={r['comment_id'] for r in keep}
    posts=distribution('post_id',rows);aliases={pid:f'P{i:03d}' for i,pid in enumerate(sorted(posts),1)}
    stats=dict(records=len(rows),clean_status=distribution('clean_status',rows),record_types=distribution('record_type',rows),
        duplicate_ids=sum(v-1 for v in ids.values()),missing_metadata={k:sum(not str(r.get(k) or '').strip() for r in rows) for k in metadata},
        post_count=len(posts),movie_id_count=len({r['movie_id'] for r in rows}),source_counts=distribution('source_name',rows),
        movie_counts=distribution('movie_id',rows),top_post_counts=[dict(alias=aliases[k],records=v) for k,v in list(posts.items())[:10]],
        lengths_all=lengths(rows),lengths_keep=lengths(keep),control_codepoints=dict(controls),clean_evidence_events=dict(evidence),
        removed_mentions=sum(number(r,'mention_count') for r in rows),removed_urls=sum(number(r,'url_count') for r in rows),
        indicators={key:dict(all=len(value),keep=sum(rid in keep_ids for rid in value)) for key,value in sorted(flags.items())},
        exact_text=dict(groups=len(groups),members=sum(len(g) for g in groups),excess=sum(len(g)-1 for g in groups),
            short_groups=sum(len(normal(g[0]['text_clean']))<40 for g in groups),
            cross_post_groups=sum(len({r['post_id'] for r in g})>1 for g in groups)),
        near_text=dict(distinct_text_pairs=len(near),records_involved=len(near_ids),cross_post_record_pairs=cross_pairs),
        context=dict(replies=len(replies),parent_absent=len(missing_parent),parent_wrong_post=len(wrong_post),
                     replies_with_empty_parent=sum(not r.get('parent_comment_id') for r in replies)))
    local=dict(flag_ids=dict(flags),missing_parent_ids=missing_parent,wrong_parent_post_ids=wrong_post,
               near_pairs=near,post_alias_mapping=aliases)
    return stats,local


def inventory_report(stats, inputs, collection, protection_counts):
    """Public report: aggregate values only; no comment IDs, URLs or text excerpts."""
    n=stats['records'];keep=stats['clean_status'].get('KEEP',0)
    pct=lambda x,d=n:f'{x:,} ({x/d:.2%})' if d else str(x)
    lines=['# Đánh giá sơ bộ corpus crawl Facebook V2','',
        'Ngày 15/11/2026. Audit dữ liệu, không phải đánh giá model hoặc sentiment Gold. Không gán nhãn tự động, không train, không sửa raw/cleaning/canonical/Gold.',
        '', '## Tổng quan', '',f'- {n:,} comment ID; {stats["post_count"]} bài có dữ liệu, {stats["movie_id_count"]} movie_id, {len(stats["source_counts"])} nguồn.',
        f'- ID trùng: {stats["duplicate_ids"]}. KEEP là đạt làm sạch kỹ thuật, chưa bảo đảm liên quan phim, hiểu độc lập hoặc đủ điều kiện train.',
        '- movie_id là metadata người dùng nhập, có cả phim dài tập/anime và tên chưa chuẩn hóa; không coi số mã là số tác phẩm đã xác minh.',
        '', '| clean_status | Số câu | Tỷ lệ |','|---|---:|---:|']
    for key in ('KEEP','REVIEW','EXCLUDE'):lines.append(f'| {key} | {stats["clean_status"].get(key,0):,} | {stats["clean_status"].get(key,0)/n:.2%} |')
    lines+=['','## Nguồn và mức tập trung','','| Nguồn | Số câu | Tỷ lệ |','|---|---:|---:|']
    for key,value in stats['source_counts'].items():lines.append(f'| {key} | {value:,} | {value/n:.2%} |')
    movie=list(stats['movie_counts'].items());top_posts=stats['top_post_counts']
    lines += ['',f'Top 2 nguồn chiếm {sum(list(stats["source_counts"].values())[:2])/n:.2%}; top 5 movie_id chiếm {sum(v for _,v in movie[:5])/n:.2%}; top 5 bài chiếm {sum(r["records"] for r in top_posts[:5])/n:.2%}.',
        '', '| movie_id (top 10) | Số câu |','|---|---:|']
    for key,value in movie[:10]:lines.append(f'| {key} | {value:,} |')
    lines+=['','## Độ dài và tín hiệu văn bản','','| Phạm vi | Trung vị ký tự | p90 ký tự | Dài nhất | Trung vị từ | p90 từ |','|---|---:|---:|---:|---:|---:|']
    for key,label in (('lengths_all','Toàn bộ'),('lengths_keep','KEEP')):
        a=stats[key];lines.append(f'| {label} | {a["characters"]["median"]} | {a["characters"]["p90"]} | {a["characters"]["max"]} | {a["words"]["median"]} | {a["words"]["p90"]} |')
    lines+=['','Số từ tách theo whitespace, không phải word segmentation tiếng Việt; p90 dùng nearest-rank. Đếm emoji/ký hiệu là proxy theo vùng Unicode, teencode/phủ định là dấu hiệu từ vựng, không phải nhãn POS/NEG.',
        '', '| Chỉ báo | Toàn bộ | Trong KEEP |','|---|---:|---:|']
    for key in ('empty_clean','url_remaining','html_entity','not_nfc','replacement_character','control_character','underscore',
                'emoji_symbol','emoticon','teencode','negation','short_2_words','very_long','with_media','with_removed_mentions','with_removed_urls','raw_clean_changed','keep_without_letters'):
        v=stats['indicators'].get(key,dict(all=0,keep=0));lines.append(f'| {key} | {pct(v["all"])} | {pct(v["keep"],keep)} |')
    lines += ['',f'Control codepoints trong text_clean: {stats["control_codepoints"] or "không phát hiện"}. Không sửa hoặc loại dòng trong audit.',
        f'Metadata ghi nhận {stats["removed_mentions"]:,} mention và {stats["removed_urls"]:,} URL/link đã loại. Đây là số do crawler ghi, không phải precision/recall xóa mention. Không đoán tên người từ chữ hoa để tự cắt text.',
        '', '## Metadata và ngữ cảnh','','| Trường | Thiếu |','|---|---:|']
    for k,v in stats['missing_metadata'].items():lines.append(f'| {k} | {pct(v)} |')
    c=stats['context'];lines += ['',f'Comment/reply: {stats["record_types"]}. Trong {c["replies"]:,} reply, {pct(c["parent_absent"],c["replies"])} không tra được parent trong 4 export; {c["parent_wrong_post"]} parent tìm thấy nhưng khác bài.',
        'parent_comment_id rỗng ở comment gốc là hợp lệ; không dùng tỷ lệ thiếu parent trên toàn bộ làm tỷ lệ lỗi. Không suy thời điểm đăng từ collected_at, không điền reaction giả.',
        'Guideline V3.1 đang được rà soát quy định text-only: không đưa parent/post vào đầu vào chỉ để cứu câu mơ hồ. Thiếu parent là chẩn đoán dữ liệu, không tự động EXCLUDE; câu không quyết định được từ chính text cần xử lý theo guideline đã chốt.',
        '', '## Trùng văn bản và bảo vệ test', '',f'- Exact sau NFC + casefold + gộp whitespace: {stats["exact_text"]}. Bỏ qua text trống khi đếm.',
        f'- Near duplicate trực tiếp: {stats["near_text"]}. Trigram token Jaccard ≥0,9, độ dài normalized ≥40 ký tự; loại cặp exact khỏi chỉ số near.',
        '- Không nối bắc cầu thành giant component. Câu ngắn giống nhau có thể là ý kiến độc lập; near là cờ cần kiểm tra, không phải bằng chứng sao chép và không tự xóa.',
        f'- Cờ so với test/reserved/holdout qua guard hiện có: {protection_counts}. Chỉ so fingerprint/metadata nguồn được bảo vệ, không đọc nhãn Gold hoặc chạy model trên Gold.',
        '- Các cờ này chưa phải tập train được duyệt. Giữ post/ID và duplicate protection khi chia train/dev; toàn bộ corpus đã audit là nguồn phát triển, không tự coi một phần tách lại là independent Gold.',
        '', '## Giới hạn thu thập', '',f'Tổng từ journal/report của 4 run: {collection}. DOM parse observations có thể lặp cùng một lỗi; không phải số comment duy nhất bị thiếu.',
        'Thu thập bị giới hạn theo bài, số vòng và timeout; không phải lấy mẫu ngẫu nhiên từ Facebook. Success có thể là đạt cap hoặc hết DOM đang tải được, không chứng minh coverage toàn bài. Bài không đóng góp comment mới có thể liên quan dedup hoặc khả năng truy cập/DOM; không suy nguyên nhân chỉ từ số 0.',
        '', '## Kết luận và việc tiếp theo', '',
        ('**NOT_READY**: cần xử lý lỗi identity/raw/KEEP rỗng trước khi dùng.' if stats['duplicate_ids'] or collection.get('raw_validation_errors',0) or stats['missing_metadata']['comment_id'] or stats['indicators'].get('empty_clean',{}).get('keep',0)
         else '**READY_WITH_LIMITATIONS** để chuẩn bị gán nhãn/phát triển, không phải tuyên bố corpus đã sạch ngữ nghĩa hay sẵn sàng train có giám sát.'),
        '1. Giữ nguyên nguồn. Kiểm tra cờ control/URL/encoding nếu có trên bản làm việc riêng trước khi thay preprocessing; không tự sửa artifact đã khóa.',
        '2. Chốt đúng byte guideline V3.1, rồi A/B gán pilot 200 độc lập; người dùng adjudicate. Đếm KEEP không thay thế nhãn sentiment.',
        '3. Rà text-only cho câu ngắn/mơ hồ; không mặc định NEU hoặc bỏ toàn bộ reply. Lấy mẫu kiểm tra cả trường hợp không bị flag, không suy chất lượng từ độ dài.',
        '4. Kiểm soát tập trung nguồn/phim, nhóm theo post và cặp duplicate khi thiết kế dev; không giả định đã cân bằng POS/NEG/NEU.',
        'Audit relevance 107 câu trước là audit phụ trợ, chưa hoàn thành mẫu ngẫu nhiên và chỉ thuộc một phần nguồn: không suy rộng tỷ lệ liên quan của audit đó lên 12k câu này. Không có Macro-F1/Kappa sentiment V3.1 mới trong báo cáo.',
        '', '## Tái lập và bảo toàn', '',
        '`python scripts/sample_audit.py inventory` đọc đúng 4 export gốc, không cộng thêm CSV gộp (sẽ nhân đôi ID). Dữ liệu local/diagnostics không commit; báo cáo public không có text, tên người, ID comment/post hoặc URL nguồn cá nhân.',
        '', '| Export | Dòng | SHA256 CSV |','|---|---:|---|']
    for item in inputs:lines.append(f'| {item["path"]} | {item["records"]:,} | `{item["sha256"]}` |')
    return '\n'.join(lines)+'\n'


def inventory(sources, output):
    import sys
    sys.path.insert(0,str(Path.cwd()))
    from src.annotation.pilot import protection,guard_reason
    from src.dataset.common import ROOT,normal
    inputs=[];rows=[];collection=Counter();checks={}
    for path in sources:
        path=Path(path);before=sha(path);part=read_csv(path);rows.extend(part)
        inputs.append(dict(path=path.as_posix(),sha256=before,records=len(part)));checks[str(path)]=before
        run_ids={r['crawl_run_id'] for r in part}
        if len(run_ids)!=1:raise ValueError('Use original one-run CSV exports, not a merged file')
        run=ROOT/'data/crawl_runs'/next(iter(run_ids));report=run/'crawl_report.json';raw=run/'raw_comments.jsonl'
        info=json.loads(report.read_text(encoding='utf8'));checks[str(report)]=sha(report);checks[str(raw)]=sha(raw)
        if info['raw_sha256']!=checks[str(raw)] or info['total_records']!=len(part):raise ValueError('Raw/export lineage mismatch')
        for k in ('requested_posts','posts_without_result','raw_validation_errors','dom_parse_observations'):collection[k]+=info[k]
        for k,v in info['post_status_counts'].items():collection['posts_'+k]+=v
    stats,local=crawl_inventory(rows)
    guard=protection([],sources[0].parent,ROOT);checks.update(guard['checksums']);blocked=Counter()
    for r in rows:
        reason=guard_reason(dict(record_id=r['comment_id'],comment_id=r['comment_id'],post_id=r['post_id'],
            text_raw=r['text_raw'],text_minimal=r['text_clean'],text_annotation_view=r['text_clean']),guard)
        if reason:blocked[reason]+=1;local.setdefault('test_protection_flags',[]).append(dict(comment_id=r['comment_id'],reason=reason))
    result=inventory_report(stats,inputs,dict(collection),dict(blocked))
    if any(sha(p)!=h for p,h in checks.items()):raise ValueError('Input changed during audit')
    output=Path(output)
    if output.exists():raise FileExistsError('Choose a new audit output directory')
    output.mkdir(parents=True)
    (output/'REPORT.md').write_text(result,encoding='utf8')
    (output/'metrics.local.json').write_text(json.dumps(dict(stats=stats,inputs=inputs,collection=dict(collection),
        protection_counts=dict(blocked),input_checksums=checks,local=local),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return dict(records=stats['records'],clean_status=stats['clean_status'],duplicate_ids=stats['duplicate_ids'],
                exact=stats['exact_text'],near=stats['near_text'],context=stats['context'],protection_flags=dict(blocked),output=str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='cmd', required=True)
    p = commands.add_parser('sample'); p.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); p.add_argument('--guideline', type=Path, default=DEFAULT_GUIDELINE)
    p = commands.add_parser('summarize'); p.add_argument('--directory', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--workbook', type=Path, help='Filled Excel; otherwise prefer DIRECTORY/audit_sample.xlsx when present')
    p=commands.add_parser('inventory',help='Aggregate read-only V2 crawl diagnostics; no sentiment labels/model evaluation')
    p.add_argument('--sources',type=Path,nargs='+',default=[Path('data/imports')/run/'comments.csv' for run in V2_RUNS])
    p.add_argument('--output',type=Path,default=Path('outputs/v2_preliminary_audit_20261115'))
    args = parser.parse_args()
    try:
        if args.cmd=='inventory':result=inventory(args.sources,args.output)
        else:result = sample(args.source, args.output, args.guideline) if args.cmd == 'sample' else write_report(args.directory, args.workbook)
        print(json.dumps(result))
    except (ValueError, OSError) as error: parser.exit(2, str(error) + '\n')


if __name__ == '__main__': main()
