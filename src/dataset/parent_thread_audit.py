"""Verify Facebook parent/reply metadata through the exact master mapping."""
from collections import Counter, defaultdict
import csv
import io
import json
from pathlib import Path

from src.dataset.common import ROOT, load, read_jsonl, save, seal, staged, verify


def _selected_source_record(master_record):
    """Read only the exact in-repository source row pinned by master provenance."""
    source = Path(master_record.get('source_file', ''))
    source = source.resolve() if source.is_absolute() else (ROOT/source).resolve()
    if not source.is_relative_to(ROOT.resolve()) or not source.is_file():
        return None, 'SOURCE_ROW_UNAVAILABLE'
    try:
        payload = source.read_bytes()
        offset = int(master_record['source_row']) - 1
        if source.suffix.lower() == '.csv':
            rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'), newline='')))
        elif source.suffix.lower() == '.jsonl':
            rows = [json.loads(line) for line in payload.decode('utf-8-sig').splitlines() if line.strip()]
        elif source.suffix.lower() == '.json':
            value = json.loads(payload.decode('utf-8-sig'))
            rows = value if isinstance(value, list) else []
        else:
            return None, 'UNSUPPORTED_SOURCE_FORMAT'
        if not 0 <= offset < len(rows):
            return None, 'SOURCE_ROW_OUT_OF_RANGE'
        return rows[offset], 'FOUND'
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return None, 'SOURCE_ROW_UNREADABLE'


def verified_parent(row, master_record):
    """Return parent/type only when exact selected source row and IDs verify."""
    if not master_record or row.get('master_id') != master_record.get('id'):
        return None, 'UNVERIFIED_MASTER_LINK', 'UNKNOWN'
    if master_record.get('source_platform') != 'facebook':
        return None, 'NON_FACEBOOK_OR_UNKNOWN', 'UNKNOWN'
    if (str(row.get('comment_id') or '') != str(master_record.get('comment_id') or '')
        or str(row.get('post_id') or '') != str(master_record.get('post_id') or '')):
        return None, 'UNVERIFIED_COMMENT_POST_MAPPING', 'UNKNOWN'
    source_row, source_status = _selected_source_record(master_record)
    if source_row is None:
        return None, source_status, 'UNKNOWN'
    if (str(source_row.get('comment_id') or '') != str(master_record.get('comment_id') or '')
        or str(source_row.get('post_id') or '') != str(master_record.get('post_id') or '')):
        return None, 'SOURCE_IDENTITY_MISMATCH', 'UNKNOWN'
    if 'parent_comment_id' not in source_row:
        return None, 'UNVERIFIABLE_MISSING_METADATA', 'UNKNOWN'
    record_type = source_row.get('record_type')
    if record_type not in {'comment', 'reply'}:
        return None, 'UNVERIFIABLE_MISSING_RECORD_TYPE', 'UNKNOWN'
    if 'parent_comment_id' in master_record.get('metadata_conflicts', {}):
        return None, 'AMBIGUOUS_PARENT_METADATA', record_type
    if str(source_row.get('parent_comment_id') or '').strip() != str(master_record.get('parent_comment_id') or '').strip():
        return None, 'PARENT_SOURCE_MASTER_MISMATCH', record_type
    if record_type == 'reply' and not str(source_row.get('parent_comment_id') or '').strip():
        return None, 'UNVERIFIABLE_REPLY_PARENT_MISSING', record_type
    if record_type == 'comment' and str(source_row.get('parent_comment_id') or '').strip():
        return None, 'UNEXPECTED_PARENT_ON_ROOT_COMMENT', record_type
    # A parent value must be present on the exact source observation selected by master.
    matches = [obs for obs in master_record.get('observations', [])
        if obs.get('source_file') == master_record.get('source_file')
        and str(obs.get('source_row')) == str(master_record.get('source_row'))
        and obs.get('source_platform') == 'facebook'
        and str(obs.get('comment_id') or '') == str(master_record.get('comment_id') or '')
        and str(obs.get('post_id') or '') == str(master_record.get('post_id') or '')
        and 'parent_comment_id' in obs]
    if len(matches) != 1:
        return None, 'NO_UNIQUE_PARENT_PROVENANCE', record_type
    return str(matches[0].get('parent_comment_id') or '').strip(), 'VERIFIED', record_type


def _fold_thread_overlaps(train, validation):
    """Count direct parent-child edges and sibling replies crossing a fold."""
    def identity(r): return (r.get('source_platform', ''), r.get('post_id', ''), r.get('comment_id', ''))
    train_keys = {identity(r) for r in train if r.get('post_id') and r.get('comment_id')}
    valid_keys = {identity(r) for r in validation if r.get('post_id') and r.get('comment_id')}
    direct = set()
    for side_a, side_b in ((train, validation), (validation, train)):
        side_b_keys = {identity(r) for r in side_b if r.get('post_id') and r.get('comment_id')}
        for row in side_a:
            parent = row.get('verified_parent_comment_id')
            key = (row.get('source_platform', ''), row.get('post_id'), parent) if parent and row.get('post_id') else None
            if key and key in side_b_keys:
                direct.add((key, identity(row)))
    train_parents = {(r.get('source_platform', ''), r['post_id'], r['verified_parent_comment_id']) for r in train
                     if r.get('post_id') and r.get('verified_parent_comment_id')}
    valid_parents = {(r.get('source_platform', ''), r['post_id'], r['verified_parent_comment_id']) for r in validation
                     if r.get('post_id') and r.get('verified_parent_comment_id')}
    shared_parents = train_parents & valid_parents
    train_posts = {(r.get('source_platform', ''), r.get('post_id')) for r in train if r.get('post_id')}
    valid_posts = {(r.get('source_platform', ''), r.get('post_id')) for r in validation if r.get('post_id')}
    return dict(shared_comment_ids=len(train_keys & valid_keys),
        shared_post_ids=len(train_posts & valid_posts),
        parent_child_edges_crossing=len(direct), sibling_parent_groups_crossing=len(shared_parents),
        shared_parent_ids=len({parent for _, _, parent in shared_parents}),
        affected_train_rows=sum((r.get('source_platform', ''), r.get('post_id'), r.get('verified_parent_comment_id')) in shared_parents for r in train),
        affected_validation_rows=sum((r.get('source_platform', ''), r.get('post_id'), r.get('verified_parent_comment_id')) in shared_parents for r in validation))


def audit(unified_dir='outputs/phase_g3/unified', master_dir='outputs/phase_g/master'):
    unified_dir, master_dir = ROOT/unified_dir, ROOT/master_dir
    verify(unified_dir); verify(master_dir)
    rows = read_jsonl(unified_dir/'unified.jsonl')
    records = {r['id']: r for r in read_jsonl(master_dir/'master.jsonl')}
    locked = load(unified_dir/'frozen_plan.json')
    fb = [r for r in rows if r['source_dataset'] == 'facebook_development']
    resolved = []
    status_counts = Counter()
    for row in fb:
        master_record = records.get(row.get('master_id'))
        parent, status, record_type = verified_parent(row, master_record)
        status_counts[status] += 1
        reply_status = ('ROOT_COMMENT' if status == 'VERIFIED' and record_type == 'comment'
                        else 'REPLY' if status == 'VERIFIED' and record_type == 'reply'
                        else 'UNKNOWN')
        resolved.append(dict(id=row['id'], original_id=row['original_id'], master_id=row['master_id'],
            source_platform='facebook', post_id=row.get('post_id', ''), comment_id=row.get('comment_id', ''),
            verified_parent_comment_id=parent if status == 'VERIFIED' else '',
            parent_status=status, verified_record_type=record_type, reply_status=reply_status))
    by_original = {r['original_id']: r for r in resolved}
    folds = []
    for fold in locked['folds']:
        train = [by_original[i] for i in fold['train_ids']]
        validation = [by_original[i] for i in fold['validation_ids']]
        overlap = _fold_thread_overlaps(train, validation)
        folds.append(dict(fold=fold['fold'], train_rows=len(train), validation_rows=len(validation),
            train_reply_rows=sum(r['reply_status'] == 'REPLY' for r in train),
            validation_reply_rows=sum(r['reply_status'] == 'REPLY' for r in validation),
            train_root_comments=sum(r['reply_status'] == 'ROOT_COMMENT' for r in train),
            validation_root_comments=sum(r['reply_status'] == 'ROOT_COMMENT' for r in validation),
            unknown_parent_rows=sum(r['reply_status'] == 'UNKNOWN' for r in train+validation), **overlap))
    direct_counts = [f[k] for f in folds for k in ('parent_child_edges_crossing', 'sibling_parent_groups_crossing',
                       'shared_comment_ids')]
    direct_counts += [f['shared_post_ids'] for f in folds]
    verified_all = status_counts == Counter({'VERIFIED': len(fb)})
    return dict(status='PASS' if verified_all and not any(direct_counts) else 'BLOCKED',
        mapping_method='unified.master_id -> master record -> exact selected observation source_file/source_row',
        parent_status_counts=dict(status_counts), facebook_rows=len(fb), folds=folds,
        limitations=['Root/reply status comes from source record_type, not an empty parent ID alone.',
                     'Thread ancestry beyond a directly observed parent is not inferred if its parent record is unavailable.',
                     'Identity keys are namespaced by platform and post.'],
        local_rows=resolved)


def write_audit(output='outputs/phase_g32/parent_audit_04'):
    result = audit()
    with staged(output) as work:
        public = {k: v for k, v in result.items() if k != 'local_rows'}
        save(work/'summary.json', public)
        save(work/'verified_parent_rows.local.json', result['local_rows'])
        return seal(work, dict(status=result['status'], rows=result['facebook_rows'],
            local_ids_only=True, raw_text_written=False))
