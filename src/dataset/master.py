"""Inventory local sources and reconcile observations without inventing identity."""
from collections import Counter, defaultdict
import io
import json
import os
from pathlib import Path
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import zipfile

from .common import ROOT, csv_rows, digest, load, save, seal, sha, staged, write_csv, write_jsonl
from src.crawler.parser import facebook_url, post_id as url_post_id
from src.data.quality import near_duplicate_candidates
from src.data.split import UnionFind

TEXT_KEYS = ('text_raw', 'text', 'comment', 'body')
META = ('comment_id', 'post_id', 'post_url', 'parent_comment_id', 'movie_id', 'collected_at')
SKIP = {'.git', 'node_modules', '__pycache__', 'selenium_cache', '.playwright-browsers', '.agents', '.codex', '.aws'}


def normal(text):
    return ' '.join(unicodedata.normalize('NFC', text).split()).casefold()


def post_url(value):
    """Strip tracking and comment anchors; retain only post identity parameters."""
    if not value: return ''
    try:
        canonical = facebook_url(value)
        parts = urlsplit(canonical); query = parse_qs(parts.query)
        query = {key: query[key][0] for key in ('story_fbid', 'id', 'fbid', 'v') if key in query}
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    except ValueError: return ''


def source_platform(row, role):
    """Explicit platform first; never identify a comment's platform from a movie name."""
    explicit=str(row.get('platform') or row.get('source_platform') or row.get('source') or '').strip().casefold()
    if explicit in {'facebook','momo','unknown'}:return explicit
    host=urlsplit(row.get('post_url') or row.get('url') or '').hostname
    if host in {'momo.vn','www.momo.vn'}:return 'momo'
    if host in {'facebook.com','www.facebook.com','m.facebook.com','web.facebook.com'}:return 'facebook'
    return 'unknown' if role in {'legacy_unverified','platform_export'} else 'facebook'


def platform_url(value, platform):
    if platform=='facebook':return post_url(value)
    if platform=='momo' and value:
        parts=urlsplit(value)
        if parts.scheme=='https' and parts.hostname in {'momo.vn','www.momo.vn'} and not parts.username and not parts.password:
            return urlunsplit(('https','www.momo.vn',parts.path.rstrip('/'),'', ''))
    return ''


def safe_files(roots, excluded=()):
    """Never descend into browser profiles, credentials, environments or symlinks."""
    excluded = [Path(p).resolve() for p in excluded]
    seen = set()
    for root in roots:
        root = Path(root).resolve()
        for base, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.lower().startswith(
                ('.venv', 'browser', 'chrome_profile', 'credentials', '.cache'))
                and not (Path(base)/d).is_symlink()
                and not any((Path(base)/d).resolve().is_relative_to(p) for p in excluded))
            for name in sorted(names):
                p = Path(base)/name
                sensitive = name.lower()
                if sensitive.startswith('.env') or any(term in sensitive for term in
                    ('credential','cookie','secret','api_key','access_token','refresh_token')): continue
                if p.is_symlink() or p.resolve() in seen: continue
                if p.suffix.lower() in {'.csv', '.json', '.jsonl', '.xlsx', '.zip'}:
                    seen.add(p.resolve()); yield p


def source_role(path, root, archive=False):
    name = path.name; rel = path.as_posix()
    if archive: return 'archive_export'
    if name == 'raw_comments.jsonl' and '/data/crawl_runs/' in rel: return 'raw_journal'
    if name == 'comments.csv' and ('/data/imports/' in rel or '/data/crawl_runs/' in rel): return 'export'
    if '/data/imports/' in rel and name in {'reviews.csv','reviews.json','reviews.jsonl','comments.json','comments.jsonl'}:
        return 'platform_export'
    if name == 'data_module1.csv' or (path.parent == root/'crawl' and path.suffix == '.csv'):
        return 'legacy_unverified'
    return 'derived_or_support_not_new_source'


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


def inventory(roots, root, excluded):
    entries, observations, inputs = [], [], {}

    def inspect(path, payload, suffix, role, container_sha=None):
        entry = dict(path=path, format=suffix[1:], sha256=digest(payload), bytes=len(payload), role=role,
                     rows=None, movies=None, posts=None, metadata=[], status='indexed')
        if container_sha: entry['archive_sha256'] = container_sha
        entries.append(entry)
        if suffix not in {'.csv', '.json', '.jsonl'}: return
        try:
            rows, fields = read_payload(payload, suffix)
            entry.update(rows=len(rows), metadata=[f for f in META if f in fields],
                         movies=len({r.get('movie_id') for r in rows if r.get('movie_id')}),
                         posts=len({r.get('post_id') for r in rows if r.get('post_id')}))
            key = next((k for k in TEXT_KEYS if k in fields), None)
            if not key: return
            entry['text_column'] = key
            if role == 'derived_or_support_not_new_source': return
            for number, row in enumerate(rows, 1):
                if not isinstance(row.get(key), str): raise ValueError('Nonliteral comment text')
                clean = row.get('text_without_mentions')
                mention = isinstance(clean, str) and row.get('text_extraction_version') == 'dom_text_v2'
                platform=source_platform(row,role)
                pid = str(row.get('post_id') or '')
                url = platform_url(row.get('post_url') or row.get('url') or '',platform)
                parsed = url_post_id(url) if url and platform=='facebook' else None
                identity_error = bool(pid and parsed and pid != parsed)
                source = str(row.get('source_dataset') or row.get('crawl_run_id') or path)
                observations.append(dict(text_raw=row[key], text_view=clean if mention else row[key],
                    mention_policy='existing_dom_text_v2' if mention else 'unchanged_no_name_guess',
                    source_dataset=source, source_file=path, source_row=number,
                    input_sha256=entry['sha256'], role=role,
                    **{k: str(row.get(k) or '') for k in META if k not in {'post_id', 'post_url','comment_id'}},
                    comment_id=str(row.get('comment_id') or (row.get('review_id') if platform=='momo' else '') or ''),
                    post_id=pid or (parsed or ''), post_url=url, metadata_identity_error=identity_error,
                    original_internal_id=str(row.get('internal_record_id') or ''),
                    original_label=row.get('overall', row.get('nhan_may', '')),
                    original_label_source='unverified_external' if 'overall' in row else ('legacy_machine' if row.get('nhan_may') else ''),
                    extraction_version=row.get('text_extraction_version', ''),
                    extraction_status=row.get('extraction_status', ''),
                    source_platform=platform,platform=platform,source=platform))
        except (ValueError, UnicodeError, csv_error()) as exc:
            entry['status'] = type(exc).__name__; entry['reason'] = 'Invalid or incomplete data; not silently repaired'
            # A malformed source must not contribute a partially read prefix.
            observations[:] = [r for r in observations if r['source_file'] != path]

    for path in safe_files(roots, excluded):
        relative = os.path.relpath(path, root).replace('\\', '/')
        try:
            checksum = sha(path); inputs[str(path.resolve())] = checksum
            if path.suffix.lower() == '.xlsx':
                # Workbook XML dimensions only; source CSV and reviewed canonical snapshot govern labels.
                with zipfile.ZipFile(path) as book:
                    import xml.etree.ElementTree as ET
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    sheets = []
                    for member in book.namelist():
                        if member.startswith('xl/worksheets/sheet') and member.endswith('.xml'):
                            xml = ET.fromstring(book.read(member))
                            sheets.append(dict(member=member, stored_rows=len(xml.findall('s:sheetData/s:row', ns))))
                entries.append(dict(path=relative, format='xlsx', sha256=checksum, bytes=path.stat().st_size,
                    role='workbook_copy_not_new_source', status='indexed_xml_dimensions_only', sheets=sheets,
                    rows=None, metadata=[], movies=None, posts=None))
            elif path.suffix.lower() == '.zip':
                entries.append(dict(path=relative, format='zip', sha256=checksum, bytes=path.stat().st_size,
                    role='archive_container', status='indexed', rows=None, metadata=[], movies=None, posts=None))
                with zipfile.ZipFile(path) as archive:
                    for item in archive.infolist():
                        # Inspect in memory only, without extracting potentially unsafe member paths.
                        if item.filename.endswith('.csv'):
                            inspect(relative+'!'+item.filename, archive.read(item), '.csv', 'archive_export', checksum)
            else: inspect(relative, path.read_bytes(), path.suffix.lower(), source_role(path, root))
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            entries.append(dict(path=relative, status='unreadable_'+type(exc).__name__, role='unprocessed',
                                rows=None, metadata=[], movies=None, posts=None))
    return entries, observations, inputs


def csv_error():
    import csv
    return csv.Error


def reconcile(observations, development, near_config):
    """Merge only corroborated source identity. Same text alone never merges rows."""
    buckets = defaultdict(list)
    for i, row in enumerate(observations):
        platform = row.get('source_platform', 'facebook')
        pid = row.get('post_id') or row.get('post_url', '')
        if row.get('metadata_identity_error'):
            key = ('identity_error', row['source_file'], row['source_row'])
        elif platform in {'facebook','momo'} and row.get('comment_id') and pid:
            key = (platform, 'cid_post', row['comment_id'], pid)
        elif platform in {'facebook','momo'} and row.get('original_internal_id') and pid:
            key = (platform, 'internal_post', row['original_internal_id'], pid)
        else: key = (platform, 'observation', row['source_file'], row['source_row'])
        buckets[key].append(row)
    records, conflicts = [], []
    for key, rows in sorted(buckets.items(), key=lambda pair: str(pair[0])):
        def priority(r):
            # Verified identity and explicit DOM mention extraction outrank completeness.
            # Timestamp/length never decides which observation is correct.
            return (-bool(r.get('post_url') and r.get('post_id') and not r.get('metadata_identity_error')),
                    -(r.get('extraction_version') == 'dom_text_v2'),
                    -(r.get('extraction_status') == 'complete'),
                    -sum(bool(r.get(k)) for k in META), r['source_file'], r['source_row'])
        chosen = min(rows, key=priority)
        variants = sorted({r['text_raw'] for r in rows})
        rid = 'm_'+digest(json.dumps(key, ensure_ascii=False, separators=(',', ':')))
        record = {k: chosen.get(k, '') for k in (*META, 'text_raw', 'source_dataset', 'source_file', 'source_row', 'source_platform')}
        record.update(platform=chosen['source_platform'],source=chosen['source_platform'])
        record.update(id=rid, text_view=chosen['text_view'], mention_policy=chosen.get('mention_policy', ''),
            annotation_status='UNLABELED', label='', label_source='', human_decisions=[], development_ids=[],
            development_groups=[], development=False, observations=rows, text_variants=variants,
            metadata_conflicts={}, metadata_alternatives={}, review_flags=[], original_labels=[dict(value=r['original_label'],
                source=r['original_label_source'], source_file=r['source_file'], source_row=r['source_row'])
                for r in rows if r.get('original_label') not in (None, '')])
        for field in META:
            values = sorted({r.get(field, '') for r in rows if r.get(field)})
            if not record[field] and len(values) == 1: record[field] = values[0]
            if len(values) > 1:
                record['metadata_alternatives'][field] = values
                # Multiple observation timestamps and URL aliases are expected across crawls.
                if field in {'post_id','movie_id','parent_comment_id'}: record['metadata_conflicts'][field] = values
        if len({normal(s) for s in variants}) > 1: record['review_flags'].append('TEXT_VARIANTS_RETAINED')
        if record['metadata_conflicts']: record['review_flags'].append('METADATA_CONFLICT')
        if any(r.get('metadata_identity_error') for r in rows): record['review_flags'].append('URL_POST_ID_CONFLICT')
        records.append(record)
    # Conflicting uses of a source ID are not silently collapsed across posts.
    by_cid = defaultdict(list)
    for row in records:
        if row['source_platform'] == 'facebook' and row['comment_id']: by_cid[row['comment_id']].append(row)
    for cid, rows in by_cid.items():
        if len(rows) > 1:
            for row in rows: row['review_flags'].append('COMMENT_ID_IDENTITY_UNRESOLVED')
            conflicts.append(dict(kind='COMMENT_ID_IDENTITY_UNRESOLVED', comment_id=cid, ids=[r['id'] for r in rows]))
    mapping = []
    for decision in development:
        matches = [r for r in by_cid.get(decision['comment_id'], []) if r['post_id'] == decision['post_id']
                   and not r['metadata_conflicts'].get('post_id') and 'URL_POST_ID_CONFLICT' not in r['review_flags']]
        if len(matches) != 1:
            raise ValueError('Development decision cannot be linked uniquely without identity guessing: '+decision['id'])
        row = matches[0]
        row['human_decisions'].append(dict(decision))  # Full original text/decision/review event retained.
        row['development_ids'].append(decision['id']); row['development_groups'].append(decision['group_id'])
        row['development'] = True
        mapping.append(dict(development_id=decision['id'], master_id=row['id'], original_group_id=decision['group_id']))
    for row in records:
        decisions = row['human_decisions']
        signatures = {(d['status'], d['label']) for d in decisions}
        if len(signatures) > 1:
            row['review_flags'].append('HUMAN_IDENTITY_LABEL_CONFLICT')
            conflicts.append(dict(kind='HUMAN_IDENTITY_LABEL_CONFLICT', ids=[row['id']]))
        elif decisions:
            row['annotation_status'], row['label'] = next(iter(signatures))
            row['label_source'] = 'human_single_annotator_development'
        elif row['original_labels']:
            row['label_source'] = 'unverified_or_machine_not_human'
    # Group every observed text variant, not just the selected rendering; bridges are transitive.
    uf = UnionFind([r['id'] for r in records]); seen = {}; variants = {}; text_owners = defaultdict(set)
    for row in records:
        keys = []
        for field in ('post_id', 'post_url', 'comment_id'):
            if row.get(field): keys.append((row['source_platform'], field, row[field]))
        for old in row['development_groups']: keys.append(('old_development_component', old))
        for text in [*row['text_variants'], row['text_view'], *(d['text_raw'] for d in row['human_decisions'])]:
            normalized = normal(text)
            if not normalized: continue
            key = digest(normalized); variants[key] = normalized; text_owners[key].add(row['id'])
            keys.append(('exact_text', key))
        for key in keys:
            if key in seen: uf.union(row['id'], seen[key])
            else: seen[key] = row['id']
    near_records = [dict(id=h, text=t, quality=dict(status='KEEP', duplicate_of=None)) for h, t in sorted(variants.items())]
    pairs = near_duplicate_candidates(near_records, near_config)
    for pair in pairs:
        left = min(text_owners[pair['left']]); right = min(text_owners[pair['right']])
        uf.union(left, right)
        pair.update(left_master_id=left, right_master_id=right)
    components = defaultdict(list)
    for row in records: components[uf.find(row['id'])].append(row['id'])
    group_ids = {key: 'mg_'+digest('\n'.join(sorted(ids))) for key, ids in components.items()}
    for row in records: row['group_id'] = group_ids[uf.find(row['id'])]
    # Same text with incompatible human labels needs review even across different source IDs.
    human_text = defaultdict(list)
    for row in records:
        for decision in row['human_decisions']: human_text[normal(decision['text_raw'])].append((row, decision))
    for key, items in human_text.items():
        if key and len({(d['status'], d['label']) for _, d in items}) > 1:
            ids = sorted({r['id'] for r, _ in items})
            conflicts.append(dict(kind='EXACT_TEXT_HUMAN_LABEL_CONFLICT', ids=ids))
            for row, _ in items: row['review_flags'].append('EXACT_TEXT_HUMAN_LABEL_CONFLICT')
    stats = dict(observations=len(observations), records=len(records),
        reconciled_identity_observations=len(observations)-len(records),
        exact_text_groups=sum(len(owners) > 1 for owners in text_owners.values()), near_duplicate_pairs=len(pairs),
        connected_groups=len(components), human_decisions=sum(len(r['human_decisions']) for r in records),
        human_labeled_records=sum(r['annotation_status'] == 'LABELED' for r in records),
        unverified_or_machine_records=sum(bool(r['original_labels']) for r in records),
        unlabeled_records=sum(r['annotation_status'] == 'UNLABELED' for r in records),
        metadata_present={k: sum(bool(r[k]) for r in records) for k in META},
        missing_required_metadata=sum(not all(r[k] for k in ('comment_id','post_id','post_url','movie_id')) for r in records),
        identity_unlinked_records=sum(not (r['source_platform']=='facebook' and r['comment_id'] and r['post_id']) for r in records),
        movies=len({r['movie_id'] for r in records if r['movie_id']}),
        posts=len({(r['source_platform'], r['post_id']) for r in records if r['post_id']}),
        source_datasets=len({o['source_dataset'] for r in records for o in r['observations']}),
        by_platform=dict(Counter(r['source_platform'] for r in records)),
        provenance_observations=sum(len(r['observations']) for r in records),
        label_counts=dict(Counter(r['label'] if r['annotation_status']=='LABELED' else r['annotation_status'] for r in records)))
    return records, mapping, pairs, conflicts, stats


def build(config_path, output):
    cfg = load(config_path); root = Path(cfg.get('repository_root', ROOT)).resolve()
    roots = [Path(p).resolve() for p in cfg['inventory_roots']]
    protected = {}
    for relative in cfg.get('protect_paths', []):
        target = root/relative
        if not target.exists(): raise ValueError('Required protected input missing: '+relative)
        paths = [target] if target.is_file() else sorted(p for p in target.rglob('*') if p.is_file())
        protected.update({str(p.resolve()): sha(p) for p in paths})
    reviewed = root/cfg['reviewed_root']
    from scripts.import_development_review import verify_files, verify_reviewed_dataset
    reviewed_manifest = load(reviewed/'manifest.json')
    if sha(reviewed/'manifest.json') != cfg['reviewed_manifest_sha256']: raise ValueError('Reviewed manifest changed')
    verify_files(reviewed, reviewed_manifest)
    development, _ = csv_rows((reviewed/'annotations.csv').read_bytes())
    verify_reviewed_dataset(reviewed, development, reviewed_manifest)
    if len(development) != cfg['expected_development_rows']: raise ValueError('Development row count changed')
    entries, observations, inputs = inventory(roots, root, [Path(output), root/'outputs/phase_g',
        root/'outputs/phase_g_support', root/'configs'])
    inputs.update(protected)
    missing = []
    for relative in cfg['expected_optional_sources']:
        if not (root/relative).exists(): missing.append(relative)
    records, mapping, pairs, conflicts, stats = reconcile(observations, development, cfg['near_duplicate'])
    # Record checksum-protected exposure evidence. Unknown posts are NOT attested unused.
    exposure = load(root/cfg['exposure_ledger'])
    exposure['evidence_source_checksums'] = {}
    evidence_posts = set(exposure.get('known_exposed_post_ids', []))
    def collect_ids(value):
        if isinstance(value, dict):
            if value.get('post_id'): evidence_posts.add(str(value['post_id']))
            for child in value.values(): collect_ids(child)
        elif isinstance(value, list):
            for child in value: collect_ids(child)
    for relative in exposure.get('previous_selection_pool_sources', []):
        path = root/relative
        if not path.is_file(): raise ValueError('Exposure evidence source missing: '+relative)
        exposure['evidence_source_checksums'][relative] = sha(path)
        collect_ids(load(path))
    exposure['known_exposed_post_ids'] = sorted(evidence_posts)
    exposed_posts = {str(p) for p in exposure.get('known_exposed_post_ids', [])}
    development_posts = {r['post_id'] for r in development}
    exposed_groups = {r['group_id'] for r in records if r['development'] or r['post_id'] in exposed_posts}
    for row in records:
        row['exposure_status'] = 'exposed_development_component' if row['group_id'] in exposed_groups else 'unknown_not_attested_unused'
    with staged(output) as work:
        write_jsonl(work/'master.jsonl', records)
        fields = ['id','text_raw','platform','source','source_platform','source_dataset','source_file','source_row',*META,'annotation_status','label','label_source','group_id',
                  'text_view','mention_policy','development_ids','exposure_status','review_flags']
        write_csv(work/'master.csv', records, list(dict.fromkeys(fields)))
        write_csv(work/'inventory.csv', entries, ['path','format','sha256','bytes','role','status','rows','movies','posts','metadata'])
        save(work/'inventory.json', entries); save(work/'quality_report.json', stats)
        save(work/'development_mapping.json', mapping); save(work/'near_duplicates.json', pairs)
        save(work/'conflicts.json', conflicts); save(work/'exposure_ledger.json', exposure)
        save(work/'human_review_history.json', load(reviewed/'review_history.json'))
        save(work/'config.json', cfg)
        changed = [path for path, checksum in inputs.items() if sha(path) != checksum]
        if changed: raise ValueError('Inventory input changed during build')
        manifest = seal(work, dict(schema_version='1.0', dataset_version=cfg['dataset_version'],
            phase='G', purpose='master_reconciliation_not_gold', status='MASTER_CREATED',
            inventory_roots=[str(p) for p in roots], sensitive_directories_not_read=True,
            inventory_exclusions=['browser profiles/credentials/environments', 'configs (not datasets)', 'Phase G own outputs/support'],
            protected_input_sha256=protected,
            input_sha256=inputs, config_sha256=sha(config_path), development_manifest_sha256=cfg['reviewed_manifest_sha256'],
            expected_optional_missing=missing, inaccessible=[e['path'] for e in entries if e['status'].startswith('unreadable')],
            original_development_post_ids=sorted(development_posts), source_scope='Accessible configured workspace only; other computers and sensitive directories not searched',
            **stats))
    return manifest
