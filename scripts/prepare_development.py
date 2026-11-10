"""Prepare one development dataset; retain originals and require human review."""
import argparse
import csv
import hashlib
import json
import math
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.normalize_annotations import normalize_file
from src.annotation.guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline
from src.data.quality import near_duplicate_candidates
from src.data.split import build_groups


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, '') for k in fields} for r in rows)


def grouped_records(rows):
    """Use the existing duplicate grouping policy, without modifying Phase B."""
    records = []
    for row in rows:
        text = ' '.join(unicodedata.normalize('NFC', row['text_raw']).split())
        records.append(dict(id=row['id'], text=text, text_hash=hashlib.sha256(text.casefold().encode()).hexdigest(),
                            post_namespace='facebook', post_id=row['post_id'], post_url=row['post_url'],
                            comment_id=row['comment_id'], quality=dict(status='KEEP', duplicate_of=None)))
    pairs = near_duplicate_candidates(records, dict(threshold=0.9, min_chars=40, shingle_size=3))
    groups = build_groups(records, pairs)
    return records, pairs, groups


def summarize(rows, key):
    values = defaultdict(Counter)
    for r in rows:
        values[r[key]][r['label'] if r['status'] == 'LABELED' else r['status']] += 1
    return [dict(value=k, total=sum(v.values()), **{s: v[s] for s in ('POS','NEG','NEU','REVIEW','EXCLUDE')})
            for k, v in sorted(values.items())]


def dependence(rows):
    """Descriptive association for this selected sample; not a population test."""
    rows = [r for r in rows if r['status'] == 'LABELED' and not r['validation_issues']]
    cells = Counter((r['movie_id'], r['label']) for r in rows)
    movies, labels = Counter(r['movie_id'] for r in rows), Counter(r['label'] for r in rows)
    n = len(rows)
    if not n:
        return dict(n=0, cramers_v=None, mutual_information_nats=None)
    chi = sum((cells[m,l] - movies[m]*labels[l]/n)**2 / (movies[m]*labels[l]/n)
              for m in movies for l in labels)
    denom = min(len(movies)-1, len(labels)-1)
    mi = sum(count/n*math.log(count*n/(movies[m]*labels[l])) for (m,l),count in cells.items())
    return dict(n=n, cramers_v=math.sqrt(chi/(n*denom)) if denom else None,
                mutual_information_nats=mi, sparse_cells=sum(cells[m,l]<5 for m in movies for l in labels),
                note='Uncorrected descriptive association only; selected, exposed development data. movie_id is source topic, not necessarily the evaluated film.')


def _prepare(config_path, output):
    cfg = load(config_path)
    output = Path(output)
    if output.exists():
        raise FileExistsError('Output exists; preserve human work and choose a new empty output directory')
    # Validate every immutable input before creating output.
    inputs = {}
    for spec in cfg['sources']:
        for key in ('input', 'task', 'selection'):
            path = ROOT/spec[key]
            actual = sha(path)
            if actual != spec[key+'_sha256']:
                raise ValueError('Source changed; review before regenerating: '+spec[key])
            inputs[spec[key]] = actual
        task = load(ROOT/spec['task'])
        validate_guideline(task['guideline_version'], task['guideline_sha256'])
    audit_path = ROOT/cfg['audit']
    if sha(audit_path) != cfg['audit_sha256']:
        raise ValueError('Audit source changed')
    inputs[cfg['audit']] = sha(audit_path)
    audit = load(audit_path)
    if audit['source_sha256'] not in {spec['input_sha256'] for spec in cfg['sources']}:
        raise ValueError('Audit belongs to a different annotation snapshot')
    output.mkdir(parents=True)
    rows, reports, contracts = [], {}, {}
    provenance = output/'provenance'
    provenance.mkdir()
    for spec in cfg['sources']:
        name = spec['name']
        task = load(ROOT/spec['task'])
        selection = load(ROOT/spec['selection'])
        mapping = {r['id']:r for r in selection[spec['mapping_key']]}
        task_rows = {r['id']:r for r in task['rows']}
        overrides = None
        if spec.get('confirmed_overrides'):
            overrides = provenance/(name+'_confirmed_decisions.json')
            save(overrides, spec['confirmed_overrides'])
        report = normalize_file(ROOT/spec['input'], ROOT/spec['task'], provenance/name,
                                overrides_path=overrides, restore_task_whitespace=True)
        reports[name] = report
        contracts[name] = {k:task[k] for k in ('dataset_version','guideline_version','guideline_sha256')}
        issues = defaultdict(list)
        for issue in report['issues']:
            issues[issue['id']].append(issue['code'])
        normalized = read_csv(provenance/name/'normalized.csv')
        # Parent IDs for the pilot are in its input, not the selection manifest.
        extra = {r['comment_id']:r for r in read_csv(ROOT/spec['source_input'])} if spec.get('source_input') else {}
        if spec.get('source_input'):
            if sha(ROOT/spec['source_input']) != spec['source_input_sha256']:
                raise ValueError('Source provenance CSV changed')
            inputs[spec['source_input']] = sha(ROOT/spec['source_input'])
        for number, row in enumerate(normalized, 2):
            meta = mapping[row['id']]
            ref = task_rows[row['id']]
            source_extra = extra.get(meta['comment_id'], {})
            rows.append(dict(**row, source_round=name, source='facebook', source_workbook_row=number,
                             source_workbook_sha256=spec['input_sha256'],
                             movie_id_source_topic=meta['movie_id'],
                             post_id=meta['post_id'], post_url=meta['post_url'], comment_id=meta['comment_id'],
                             parent_comment_id=meta.get('parent_comment_id',source_extra.get('parent_comment_id','')),
                             crawl_run_id=meta['crawl_run_id'],
                             source_kind=meta.get('source_kind','group'), selection_cohort=ref['cohort'],
                             original_guideline_version=task['guideline_version'],
                             original_guideline_sha256=task['guideline_sha256'],
                             validation_issues=';'.join(issues[row['id']]), audit_pending='',
                             label_origin='human_single_annotator', independent_test=False))
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate internal ID across rounds')
    by_id = {r['id']:r for r in rows}
    # Emotional POS are retained under the active guide, not put up for automatic reversal.
    protected = set(cfg['protected_pos_ids'])
    review = []
    contexts = {r['excel_row']:r.get('parent_text','') for r in audit['verified_parent_context'] if r.get('parent_found')}
    for item in audit['suggestions']:
        if item['excel_row'] in cfg['retain_emotional_pos_rows']:
            protected.add(item['id'])
            continue
        row = by_id[item['id']]
        current = row['label'] if row['status']=='LABELED' else row['status']
        # Full text must match; only documented trailing whitespace restoration is allowed.
        if row['text_raw'].rstrip() != item['text_raw'].rstrip() or current != item['current_label']:
            raise ValueError('Audit no longer matches the human source')
        row['audit_pending'] = 'LABEL_REVIEW'
        review.append(dict(id=row['id'], source_round=row['source_round'], source_workbook_row=row['source_workbook_row'],
                           movie_id=row['movie_id'], text_raw=row['text_raw'], current_label=item['current_label'],
                           proposal=item['suggestion'], review_note=item['reason'],
                           verified_parent_text=contexts.get(item['excel_row'],''),
                           decision='', label='', review_reason='', reason=''))
    for row in rows:
        if row['validation_issues']:
            row['audit_pending'] = row['validation_issues']
            if row['id'] not in {r['id'] for r in review}:
                review.append(dict(id=row['id'], source_round=row['source_round'],source_workbook_row=row['source_workbook_row'],
                                   movie_id=row['movie_id'],text_raw=row['text_raw'],current_label=row['status'],
                                   proposal='',review_note=row['validation_issues'],verified_parent_text='',
                                   decision='',label='',review_reason='',reason=''))
        if row['id'] in protected and row['label'] != 'POS':
            raise ValueError('Confirmed emotional POS changed')
    records, pairs, groups = grouped_records(rows)
    hashes = Counter(r['text_hash'] for r in records)
    comment_ids = Counter(r['comment_id'] for r in rows if r['comment_id'])
    for row, record in zip(rows, records):
        row['group_id'] = groups[row['id']]
        row['exact_duplicate_count'] = hashes[record['text_hash']]
        row['source_id_duplicate_count'] = comment_ids[row['comment_id']]
        row['ready_for_development'] = (row['status']=='LABELED' and not row['validation_issues'] and not row['audit_pending'])
    write_csv(output/'annotations.csv', rows, list(rows[0]))
    write_csv(output/'review_decisions.csv', review, list(review[0]))
    for name, subset in [('sentiment_candidates', [r for r in rows if r['status']=='LABELED' and not r['validation_issues']]),
                         ('review', [r for r in rows if r['status']=='REVIEW']),
                         ('exclude', [r for r in rows if r['status']=='EXCLUDE'])]:
        write_csv(provenance/(name+'.csv'), subset, list(rows[0]))
    statistics = {key:summarize(rows,key) for key in ('source_round','movie_id','post_id','selection_cohort','source_kind')}
    statistics['movie_label_dependence'] = dependence(rows)
    statistics['dependence_by_round'] = {name:dependence([r for r in rows if r['source_round']==name]) for name in reports}
    statistics['dependence_by_cohort'] = {name:dependence([r for r in rows if r['selection_cohort']==name]) for name in sorted({r['selection_cohort'] for r in rows})}
    save(output/'statistics.json', statistics)
    manifest = dict(purpose='exploratory_development_only', rows=len(rows),
                    active_guideline=dict(version=GUIDELINE_VERSION, sha256=sha(GUIDELINE)),
                    original_task_contracts=contracts, original_task_contracts_unchanged=True,
                    input_sha256=inputs, config_sha256=sha(config_path),
                    normalization={name:{k:v for k,v in report.items() if k not in ('actions','user_overrides')} for name,report in reports.items()},
                    pending_review_ids=[r['id'] for r in review], protected_pos_ids=sorted(protected),
                    duplicate_comment_ids={k:v for k,v in comment_ids.items() if v>1},
                    exact_duplicate_groups=sum(v>1 for v in hashes.values()), near_duplicate_pairs=pairs,
                    connected_post_groups=len(set(groups.values())), all_human_review_resolved=False,
                    independent_test=False, gold_created=False, models_trained=False,
                    output_sha256={p.name:sha(p) for p in output.glob('*') if p.is_file()})
    if any(sha(ROOT/p)!=value for p,value in inputs.items()):
        raise ValueError('Input changed during preparation')
    save(output/'manifest.json', manifest)
    return manifest


def prepare(config_path, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Output exists; preserve human work and choose a new empty output directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.development-', dir=output.parent) as temporary:
        staged = Path(temporary)/'prepared'
        result = _prepare(config_path, staged)
        staged.rename(output)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'configs/annotations_development.json')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/development')
    args = p.parse_args()
    try:
        result = prepare(args.config,args.output)
    except (ValueError,OSError,KeyError) as exc:
        p.exit(2, f'{type(exc).__name__}: {exc}\n')
    print(json.dumps({k:result[k] for k in ('rows','connected_post_groups','models_trained','gold_created')}))
    print('Pending human decisions: '+str(len(result['pending_review_ids'])))


if __name__ == '__main__':
    main()
