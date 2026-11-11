"""Local-only unified dataset, conservative text cleaning and blinded AI pilot."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import html
import json
import random
import re
import unicodedata
from pathlib import Path

from .common import ROOT, csv_rows, digest, load, read_jsonl, save, seal, sha, staged, verify, write_csv, write_jsonl
from .master import normal
from src.preprocessing.normalization import BASIC, EMOJI, NEGATION, URL, inspect, normalize, signals

LABELS = {'POS', 'NEG', 'NEU'}
STATUSES = {'LABELED', 'REVIEW', 'EXCLUDE'}
REVIEW_CODES = {'REV_MIXED', 'REV_SARCASM', 'REV_TARGET', 'REV_CONTEXT', 'REV_OTHER'}
EXCLUDE_CODES = {'EXC_NON_TEXT', 'EXC_SPAM', 'EXC_PERSONAL_EVENT', 'EXC_IRRELEVANT', 'EXC_EMPTY_OR_UI'}
TEENCODE_WORDS = ('ko','k','khum','hok','đc','dc','j','z','vch')
TEENCODE = re.compile(r'(?<!\w)(?:'+'|'.join(map(re.escape,TEENCODE_WORDS))+r')(?!\w)', re.I)
EMOTICON = re.compile(r'(?::\)+|:-\)+|=\)+|:\(+|:-\(+|=\(+|:v|\bxD\b)', re.I)
POSITIVE_CUE = re.compile(r'\b(?:hay|đẹp|đỉnh|tốt|xuất sắc|thích|ấn tượng|tuyệt|cuốn|cảm động)\b', re.I)
NEGATIVE_CUE = re.compile(r'\b(?:dở|tệ|chán|nhạt|gượng|vô lý|thất vọng|dài dòng|khó chịu)\b', re.I)
URL_ONLY = re.compile(r'^(?:(?:https?://|www\.)\S+\s*)+$', re.I)
MENTION_ONLY = re.compile(r'^(?:[@#][\w.]+\s*)+$', re.UNICODE)
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
ENTITY_SCAN = re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);')


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def clean_record(text: str) -> tuple[str, dict]:
    """Only NFC, valid HTML entities and whitespace; preserve semantic signals."""
    normalized = normalize(text, BASIC)
    cleaned = normalize(CONTROL.sub('', normalized), BASIC)
    return cleaned, inspect(text, cleaned)


def quality(text: str, cleaned: str, row: dict, exact_ui: set[str]) -> tuple[str, list[str], dict]:
    reasons = []
    if not cleaned:
        reasons.append('EMPTY_AFTER_BASIC_CLEANING')
        status = 'EXCLUDE'
    elif cleaned.casefold() in exact_ui:
        reasons.append('EXACT_KNOWN_UI_STRING')
        status = 'EXCLUDE'
    else:
        status = 'KEEP'
        if URL_ONLY.fullmatch(cleaned):
            reasons.append('URL_ONLY_REQUIRES_REVIEW')
        if MENTION_ONLY.fullmatch(cleaned):
            reasons.append('MENTION_ONLY_REQUIRES_REVIEW')
        if CONTROL.search(text):
            reasons.append('CONTROL_CHAR_REMOVED')
        if row.get('parent_comment_id') and len(cleaned) <= 32:
            reasons.append('SHORT_REPLY_CONTEXT_MAY_BE_REQUIRED')
        if reasons:
            status = 'REVIEW'
    length = len(cleaned)
    flags = {
        'long_comment': length > 256,
        'over_512_chars': length > 512,
        'over_1000_chars': length > 1000,
        'mixed_sentiment_risk': bool(POSITIVE_CUE.search(cleaned) and NEGATIVE_CUE.search(cleaned)),
        'context_required': bool(row.get('parent_comment_id')) or len(cleaned) <= 12,
        'emoji_present': bool(EMOJI.search(cleaned) or EMOTICON.search(cleaned)),
        'teencode_present': bool(TEENCODE.search(cleaned)),
        'negation_present': bool(NEGATION.search(cleaned)),
        'underscore_present': '_' in cleaned,
        'control_char_present': bool(CONTROL.search(text)),
    }
    return status, reasons, flags


def annotation_registry(cfg: dict, master_rows: list[dict]) -> tuple[dict[str, list[dict]], list[dict], dict]:
    """Join human decisions by source IDs/provenance, never by row order or text guess."""
    by_development = defaultdict(list)
    for row in master_rows:
        for source_id in row.get('development_ids', []):
            by_development[source_id].append(row)
    fb, _ = csv_rows((ROOT / cfg['facebook_annotations']).read_bytes())
    legacy, _ = csv_rows((ROOT / cfg['legacy_decisions']).read_bytes())
    legacy_mapping = {r['id']:r for r in load(ROOT/cfg['legacy_mapping'])}
    registry = defaultdict(list)
    decision_rows = []
    source_rounds = Counter()
    for item in fb:
        matches = by_development.get(item['id'], [])
        if len(matches) != 1:
            raise ValueError('Facebook annotation provenance is not a unique master identity')
        master_id = matches[0]['id']
        round_name = item.get('source_round') or 'facebook_round_unresolved'
        if round_name not in {'pilot', 'multifilm'}:
            raise ValueError('Unexpected Facebook annotation round')
        source_rounds[round_name] += 1
        decision = dict(record_id=master_id, source_annotation_id=item['id'], annotation_round=round_name,
            source_dataset='facebook_development', status=item.get('status', ''), label=item.get('label', ''),
            review_reason=item.get('review_reason', ''), reason=item.get('reason', ''),
            source_file=item.get('source', ''), source_row=item.get('source_workbook_row', ''),
            source_sha256=item.get('source_workbook_sha256', ''), label_origin=item.get('label_origin', ''))
        registry[master_id].append(decision); decision_rows.append(decision)
    for item in legacy:
        if not any(r['id'] == item['id'] for r in master_rows):
            raise ValueError('Legacy annotation has no exact master identity')
        mapping = legacy_mapping.get(item['id'])
        if not mapping or mapping.get('text_view') != item.get('text_view'):
            raise ValueError('Legacy human decision is not linked to its immutable task snapshot')
        decision = dict(record_id=item['id'], source_annotation_id=item['id'], annotation_round='legacy_round_3',
            source_dataset='legacy_unverified', status=item.get('status', ''), label=item.get('label', ''),
            review_reason=item.get('review_reason', ''), reason=item.get('reason', ''),
            source_file=mapping.get('source_file') or cfg['legacy_source_name'],
            source_row=mapping.get('source_row',''), source_sha256=mapping.get('source_sha256',''),
            label_origin='human_single_annotator')
        registry[item['id']].append(decision); decision_rows.append(decision)
    for d in decision_rows:
        if d['status'] == 'LABELED' and d['label'] not in LABELS:
            raise ValueError('Human-labeled record has invalid three-class label')
        if d['status'] not in STATUSES:
            raise ValueError('Human decision has invalid status')
    label_counts = Counter(d['label'] if d['status'] == 'LABELED' else d['status'] for d in decision_rows)
    return registry, decision_rows, dict(rounds=dict(source_rounds), statuses=dict(Counter(d['status'] for d in decision_rows)),
        labels=dict(label_counts), sentiment_rows=sum(d['status'] == 'LABELED' for d in decision_rows), total=len(decision_rows))


def protection_set(cfg: dict, rows: list[dict]) -> tuple[set[str], set[str], set[str], dict]:
    """Read confirmed test reservation/quarantine; exclude unverified planned source posts too."""
    reserved_ids, reserved_comments, reserved_posts = set(), set(), set()
    reserve_path = ROOT / cfg['test_reservation']
    manifest_path = reserve_path.parent / 'manifest.json'
    manifest = load(manifest_path) if manifest_path.exists() else {}
    reservation_status = manifest.get('status', 'NO_RESERVATION_ARTIFACT')
    if manifest.get('status') != 'PARTIAL' and reserve_path.is_file():
        reservation = load(reserve_path)
        reserved_ids.update(reservation.get('ids', []))
        reserved_comments.update(reservation.get('comment_ids', []))
        reserved_posts.update(reservation.get('post_ids', []))
    # Candidate source posts with unresolved exposure are protected from this pilot.
    candidate_path = ROOT / cfg['test_source_candidates']
    candidate_posts = set()
    if candidate_path.exists():
        availability = load(candidate_path)
        candidate_posts.update(str(x) for x in availability.get('source_candidates_requiring_exposure_audit', []))
    # Any completed Phase G.1 whole-post quarantine is authoritative.
    quarantine_files = sorted((ROOT / cfg['test_quarantine_root']).rglob('post_quarantine.json'))
    for path in quarantine_files:
        q = load(path)
        reserved_ids.update(q.get('ids', [])); reserved_comments.update(q.get('comment_ids', []))
        reserved_posts.update(q.get('post_ids', []))
    return reserved_ids, reserved_comments, reserved_posts, dict(
        reservation_status=reservation_status, confirmed_reserved_ids=len(reserved_ids),
        confirmed_reserved_comment_ids=len(reserved_comments), confirmed_reserved_posts=len(reserved_posts),
        unverified_test_candidate_posts=len(candidate_posts), candidate_post_ids=candidate_posts,
        quarantine_files_checked=len(quarantine_files))


def duplicate_groups(rows: list[dict], threshold: float = .9, min_chars: int = 40,
                     shingle_size: int = 3, max_posting: int = 256) -> tuple[dict[str, str], set[str], dict]:
    """Exact groups and direct near-duplicate edges; no giant transitive master component."""
    exact = defaultdict(list)
    for row in rows:
        key = stable_hash(normal(row['text_clean'])) if row['text_clean'] else 'empty:' + row['record_id']
        exact[key].append(row['record_id'])
    exact_group = {}
    exact_duplicate_ids = set()
    for values in exact.values():
        group = 'ex_' + stable_hash('|'.join(sorted(values)))[:20]
        for rid in values:
            exact_group[rid] = group
        if len(values) > 1:
            exact_duplicate_ids.update(sorted(values)[1:])
    representatives = [r for r in rows if r['record_id'] not in exact_duplicate_ids and len(r['text_clean']) >= min_chars]
    postings = defaultdict(list); sizes = {}; near_neighbors = defaultdict(set)
    high_df = 0; edges = 0
    token_re = re.compile(r'\w+|[^\w\s]', re.UNICODE)
    for row in sorted(representatives, key=lambda x: x['record_id']):
        tokens = token_re.findall(row['text_clean'].casefold())
        shingles = {tuple(tokens[i:i+shingle_size]) for i in range(max(0, len(tokens)-shingle_size+1))}
        if not shingles:
            continue
        overlaps = Counter()
        for shingle in shingles:
            previous = postings[shingle]
            if len(previous) >= max_posting:
                high_df += 1
                continue
            overlaps.update(previous)
        current = row['record_id']
        for previous, intersection in overlaps.items():
            union = len(shingles) + sizes[previous] - intersection
            if union and intersection / union >= threshold:
                near_neighbors[current].add(previous); near_neighbors[previous].add(current); edges += 1
        sizes[current] = len(shingles)
        for shingle in shingles:
            if len(postings[shingle]) < max_posting:
                postings[shingle].append(current)
    summary = dict(exact_groups=len(exact), exact_duplicate_rows=len(exact_duplicate_ids), direct_near_duplicate_edges=edges,
        direct_near_duplicate_rows=len(near_neighbors), near_duplicate_threshold=threshold,
        near_duplicate_min_chars=min_chars, shingle_size=shingle_size,
        high_document_frequency_shingles_skipped=high_df,
        near_duplicate_limit='candidate generation skips shingles occurring in >256 records; may miss boilerplate-driven near duplicates')
    edge_rows=[]
    for left, right_set in near_neighbors.items():
        for right in right_set:
            if left < right:
                edge_rows.append(dict(left=left,right=right,method=f'token_{shingle_size}gram_jaccard_at_least_{threshold}'))
    return exact_group, exact_duplicate_ids, dict(summary=summary, neighbors=near_neighbors, edges=edge_rows)


def candidate_reason(row: dict, annotations: dict, exact_duplicate_ids: set[str], near_human_ids: set[str],
                     held_ids: set[str], held_comments: set[str], held_posts: set[str],
                     human_posts: set[str], test_candidate_posts: set[str]) -> list[str]:
    reasons = []
    if annotations.get(row['record_id']): reasons.append('HUMAN_DECISION_PRESENT')
    if row['record_id'] in exact_duplicate_ids: reasons.append('EXACT_DUPLICATE')
    if row['record_id'] in near_human_ids: reasons.append('DIRECT_NEAR_DUPLICATE_OF_HUMAN_ROW')
    if row['record_id'] in held_ids or row.get('comment_id') in held_comments: reasons.append('TEST_RESERVED')
    if row.get('post_id') in held_posts or row.get('post_id') in test_candidate_posts: reasons.append('TEST_SOURCE_POST_PROTECTED')
    if row.get('post_id') and row.get('source_platform') == 'facebook' and row['post_id'] in human_posts:
        reasons.append('DEVELOPMENT_POST_HELD_OUT')
    if row['quality_status'] != 'KEEP': reasons.append('QUALITY_NOT_KEEP')
    if row.get('review_flags') and set(row['review_flags']) - {'TEXT_VARIANTS_RETAINED'}:
        reasons.append('MASTER_IDENTITY_REVIEW_FLAG')
    return reasons


def sample_stratified(candidates: list[dict], neighbors: dict[str, set[str]], count: int, seed: int,
                      source_quota: dict[str, int]) -> list[dict]:
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for row in candidates:
        length = len(row['text_annotation'])
        length_bin = 'short' if length <= 80 else 'medium' if length <= 256 else 'long'
        signals_key = (row['flags']['emoji_present'], row['flags']['teencode_present'],
                       row['flags']['negation_present'], row['flags']['underscore_present'])
        buckets[(row['source_dataset'], length_bin, *signals_key)].append(row)
    for values in buckets.values():
        rng.shuffle(values)
    selected = []; chosen = set(); counts = Counter(); keys = list(buckets); rng.shuffle(keys)
    while len(selected) < count:
        changed = False
        for key in keys:
            source = key[0]
            if counts[source] >= source_quota.get(source, count):
                continue
            values = buckets[key]
            while values:
                row = values.pop()
                if row['record_id'] in chosen or (neighbors.get(row['record_id'], set()) & chosen):
                    continue
                selected.append(row); chosen.add(row['record_id']); counts[source] += 1; changed = True
                break
            if len(selected) == count:
                break
        if not changed:
            break
    return selected


def build(config_path: Path, output: Path) -> dict:
    cfg = load(config_path)
    if tuple(cfg.get('teencode_detection_only', [])) != TEENCODE_WORDS or cfg.get('teencode_replacements') != {}:
        raise ValueError('Only the reviewed detection-only teencode table is supported')
    master = ROOT / cfg['master_root']
    master_manifest = load(master/'manifest.json')
    if sha(master/'manifest.json') != cfg['master_manifest_sha256']:
        raise ValueError('Master manifest does not match the Phase I source contract')
    verify(master)
    from src.dataset.unified import source_rows as verify_annotation_lineage
    lineage_rows, _, _, _ = verify_annotation_lineage(load(ROOT/cfg['human_lineage_config']))
    if len(lineage_rows) != cfg['expected_sentiment_labels']:
        raise ValueError('Protected human-label lineage count changed')
    master_rows = read_jsonl(master/'master.jsonl')
    if len(master_rows) != cfg['expected_master_rows']:
        raise ValueError('Master row count changed')
    registry, decisions, human_summary = annotation_registry(cfg, master_rows)
    reserved_ids, reserved_comments, reserved_posts, test_protection = protection_set(cfg, master_rows)
    by_id = {r['id']: r for r in master_rows}
    human_ids = set(registry)
    exact_ui = {str(x).casefold() for x in cfg.get('exact_ui_strings', [])}
    protected_rows = []
    cleaned_rows = []
    long_lengths = Counter()
    rule_counts = Counter()
    before_after = []
    for item in master_rows:
        rid = item['id']; raw = item.get('text_raw') or ''
        cleaned, audit = clean_record(raw)
        source_file = item.get('source_file', '')
        dataset = 'facebook' if item.get('source_platform') == 'facebook' else (
            'legacy_29k_unverified' if source_file.endswith('data_module1.csv') else 'unknown_source')
        status, reasons, flags = quality(raw, cleaned, item, exact_ui)
        for reason in reasons:
            rule_counts[reason] += 1
        for limit in (256, 512, 1000):
            long_lengths[f'>{limit}'] += len(cleaned) > limit
        human = registry.get(rid, [])
        labels = {(d['status'], d['label']) for d in human}
        conflict = len(labels) > 1
        source_observations = item.get('observations', [])
        original_ids = sorted({str(o.get('original_internal_id') or '') for o in source_observations if o.get('original_internal_id')})
        row = dict(record_id=rid, original_id='|'.join(original_ids) if original_ids else rid,
            source_dataset=dataset, platform=item.get('source_platform') or 'unknown',
            source_file=source_file, source_row=item.get('source_row',''),
            movie_id=item.get('movie_id') or '', post_id=item.get('post_id') or '',
            comment_id=item.get('comment_id') or '', parent_comment_id=item.get('parent_comment_id') or '',
            post_url=item.get('post_url') or '', text_raw=raw, text_clean=cleaned, text_annotation=cleaned,
            quality_status=status, quality_reasons=reasons, flags=flags,
            duplicate_group_id='', master_group_id=item.get('group_id',''),
            human_decisions=human, human_label=next(iter(labels))[1] if len(labels)==1 and next(iter(labels))[0]=='LABELED' else '',
            human_label_source='human_single_annotator' if human else '',
            label_status=('HUMAN_GOLD' if human and all(d['status']=='LABELED' for d in human) and not conflict else
                          'HUMAN_DECISION_NON_SENTIMENT' if human and not conflict else 'HUMAN_CONFLICT' if conflict else
                          'LEGACY_UNVERIFIED' if dataset=='legacy_29k_unverified' else 'UNLABELED'),
            legacy_overall=item.get('label','') if dataset=='legacy_29k_unverified' else '',
            legacy_overall_status='UNVERIFIED_SOURCE_LABEL' if dataset=='legacy_29k_unverified' and item.get('label') else '',
            test_reserved=bool(rid in reserved_ids or item.get('comment_id') in reserved_comments or item.get('post_id') in reserved_posts),
            exposure_status=item.get('exposure_status','unknown_not_attested_unused'),
            preprocessing_version=cfg['preprocessing_version'],
            metadata_provenance=item.get('observations',[]),
            human_development_ids=item.get('development_ids',[]),
            source_platform=item.get('source_platform','unknown'), text_changed=audit['changed'],
            normalization_audit=audit)
        # Non-sentiment human decisions (REVIEW/EXCLUDE) stay outside human_label.
        cleaned_rows.append(row)
        before_after.append(dict(record_id=rid, source_dataset=dataset, text_raw=raw,
            text_clean=cleaned, changed=audit['changed'], flags=flags, reasons=reasons))
    # Preserve all versions of a conflicting human decision; never choose one silently.
    exact_group, exact_duplicate_ids, duplicate_info = duplicate_groups(cleaned_rows, **cfg['near_duplicate'])
    near_neighbors = duplicate_info['neighbors']
    for row in cleaned_rows:
        row['duplicate_group_id'] = exact_group[row['record_id']]
    human_posts_all = {r['post_id'] for r in cleaned_rows if r['human_decisions'] and r['platform']=='facebook' and r.get('post_id')}
    human_exact_hashes = {stable_hash(normal(by_id[rid]['text_raw'])) for rid in human_ids if by_id[rid]['text_raw']}
    near_human_ids = {rid for rid, neighbors in near_neighbors.items()
        if rid not in human_ids and any(n in human_ids for n in neighbors)}
    duplicate_lookup = defaultdict(list)
    for row in cleaned_rows:
        if row['text_clean']:
            duplicate_lookup[stable_hash(normal(row['text_clean']))].append(row['record_id'])
    near_human_ids |= {rid for h in human_exact_hashes for rid in duplicate_lookup.get(h, []) if rid not in human_ids}
    test_candidate_posts = test_protection.pop('candidate_post_ids')
    reasons_by_id = {}
    candidate_rows = []
    for row in cleaned_rows:
        source = row['source_dataset']
        reasons = candidate_reason(row, registry, exact_duplicate_ids, near_human_ids, reserved_ids, reserved_comments,
            reserved_posts, human_posts_all, test_candidate_posts)
        reasons_by_id[row['record_id']] = reasons
        row['annotation_pool_status'] = 'ELIGIBLE' if not reasons else 'HELD_OUT'
        row['annotation_pool_reasons'] = reasons
        if not reasons:
            candidate_rows.append(row)
    source_quota = cfg['pilot_source_quota']
    selected = sample_stratified(candidate_rows, duplicate_info['neighbors'], cfg['pilot_count'], cfg['seed'], source_quota)
    same_ids = [r['record_id'] for r in selected]
    if len(set(same_ids)) != len(same_ids):
        raise AssertionError('Pilot selection contains duplicate IDs')
    all_ai_rows = [[dict(id=r['record_id'], text_annotation=r['text_annotation']) for r in selected]][0]
    guideline = ROOT / cfg['guideline']
    pilot_hash = digest('\n'.join(r['id']+'\0'+r['text_annotation'] for r in all_ai_rows))
    length_summary = {}
    for source in sorted({r['source_dataset'] for r in cleaned_rows}):
        values = sorted(len(r['text_raw']) for r in cleaned_rows if r['source_dataset']==source)
        length_summary[source] = dict(count=len(values), median=percentile(values,.50), p90=percentile(values,.90),
            p95=percentile(values,.95), p99=percentile(values,.99), over_256=sum(x>256 for x in values),
            over_512=sum(x>512 for x in values), over_1000=sum(x>1000 for x in values))
    by_source = Counter(r['source_dataset'] for r in cleaned_rows)
    changed_source = Counter(r['source_dataset'] for r in cleaned_rows if r['text_changed'])
    before_counts = Counter(r['source_dataset'] for r in cleaned_rows if r['normalization_audit']['before']['emoji_codepoints'])
    teencode_counts = Counter(r['source_dataset'] for r in cleaned_rows if r['flags']['teencode_present'])
    negation_counts = Counter(r['source_dataset'] for r in cleaned_rows if r['flags']['negation_present'])
    underscore_counts = Counter(r['source_dataset'] for r in cleaned_rows if r['flags']['underscore_present'])
    status_counts = Counter(r['quality_status'] for r in cleaned_rows)
    pools = Counter(r['source_dataset'] for r in candidate_rows)
    filter_counts=Counter(reason for reasons in reasons_by_id.values() for reason in reasons)
    transform_counts=Counter()
    for r in cleaned_rows:
        raw=r['text_raw']; nfc=unicodedata.normalize('NFC',raw)
        if nfc!=raw:transform_counts['unicode_nfc_rows']+=1
        if ' '.join(nfc.split())!=nfc:transform_counts['whitespace_rows']+=1
        if CONTROL.search(raw):transform_counts['invalid_control_char_rows']+=1
        if ENTITY_SCAN.search(raw):transform_counts['html_entity_rows']+=1
    pilot_signal_counts=Counter()
    pilot_source_counts=Counter(r['source_dataset'] for r in selected)
    pilot_length_bins=Counter()
    pilot_source_lengths=defaultdict(list)
    pilot_strata=Counter()
    for r in selected:
        n=len(r['text_annotation']); pilot_source_lengths[r['source_dataset']].append(n)
        length_bin='short' if n<=80 else 'medium' if n<=256 else 'long'
        pilot_length_bins[length_bin]+=1
        pilot_strata['|'.join([r['source_dataset'],length_bin]+[
            name if r['flags'][field] else 'no_'+name for field,name in (
                ('emoji_present','emoji'),('teencode_present','teencode'),('negation_present','negation'),
                ('underscore_present','underscore'),('context_required','context') )])]+=1
        for field in ('emoji_present','teencode_present','negation_present','underscore_present',
                      'context_required','long_comment','mixed_sentiment_risk'):
            if r['flags'][field]:pilot_signal_counts[field]+=1
    pilot_summary=dict(source_counts=dict(pilot_source_counts),length_bins=dict(pilot_length_bins),
        signals=dict(pilot_signal_counts),strata=dict(pilot_strata),
        length_by_source={source:dict(count=len(vals),median=percentile(sorted(vals),.5),p90=percentile(sorted(vals),.9),
            over_256=sum(v>256 for v in vals),over_1000=sum(v>1000 for v in vals)) for source,vals in pilot_source_lengths.items()})
    summary = dict(dataset_version=cfg['dataset_version'], total_records=len(cleaned_rows), by_source=dict(by_source),
        quality_status=dict(status_counts), quality_rule_counts=dict(rule_counts), text_changed=len(changed_source) and sum(changed_source.values()) or 0,
        text_changed_by_source=dict(changed_source), length=length_summary,
        signal_counts=dict(emoji_codepoint_rows=dict(before_counts), teencode_rows=dict(teencode_counts),
            negation_rows=dict(negation_counts), underscore_rows=dict(underscore_counts),
            emoji_or_emoticon_rows=sum(r['flags']['emoji_present'] for r in cleaned_rows),
            emoji_codepoints=sum(r['normalization_audit']['before']['emoji_codepoints'] for r in cleaned_rows),
            emoji_aliases=sum(r['normalization_audit']['before']['emoji_aliases'] for r in cleaned_rows),
            emoticon_occurrences=sum(len(EMOTICON.findall(r['text_raw'])) for r in cleaned_rows),
            teencode_occurrences=sum(len(TEENCODE.findall(r['text_raw'])) for r in cleaned_rows),
            negation_occurrences=sum(len(NEGATION.findall(r['text_raw'])) for r in cleaned_rows),
            underscore_tokens=sum(r['normalization_audit']['before']['underscore_tokens'] for r in cleaned_rows),
            html_entity_rows=sum(r['normalization_audit']['before']['html_entities'] > 0 for r in cleaned_rows),
            url_rows=sum(r['normalization_audit']['before']['urls'] > 0 for r in cleaned_rows),
            mention_rows=sum(r['normalization_audit']['before']['mentions'] > 0 for r in cleaned_rows),
            mixed_sentiment_risk_rows=sum(r['flags']['mixed_sentiment_risk'] for r in cleaned_rows),
            context_required_rows=sum(r['flags']['context_required'] for r in cleaned_rows),
            control_char_rows=sum(r['flags']['control_char_present'] for r in cleaned_rows)),
        duplicate_summary=duplicate_info['summary'], transformation_rule_rows=dict(transform_counts),
        pilot_sample=pilot_summary, human_labels=human_summary,
        annotation_pool_exclusion_reasons=dict(filter_counts),
        annotation_pool=dict(eligible_rows=len(candidate_rows), by_source=dict(pools), selected=len(selected),
            selected_by_source=dict(Counter(r['source_dataset'] for r in selected)), target=cfg['pilot_count'], seed=cfg['seed'],
            status='READY' if len(selected)==cfg['pilot_count'] else 'PARTIAL'),
        test_protection={k:v for k,v in test_protection.items() if k!='candidate_post_ids'},
        unverified_test_candidate_posts_excluded=len(test_candidate_posts),
        codex_labeling_status='LABELING_PENDING', codex_labeling_reason='No authorized model inference provider/runtime configured; no predictions generated',
        legacy_overall_used_as_human_label=False, model_training_performed=False, crawl_performed=False)
    ai_sidecar = dict(schema_version='phase_i_blind_input_v1', pilot_manifest_hash=pilot_hash,
        guideline_sha256=sha(guideline), guideline_version='V2.1', rows=len(all_ai_rows), fields=['id','text_annotation'],
        labels_and_provenance_omitted=True)
    with staged(output) as work:
        write_jsonl(work/'unified_corpus.local.jsonl', cleaned_rows)
        write_csv(work/'unified_corpus.local.csv', cleaned_rows,
            ['record_id','original_id','source_dataset','platform','source_file','source_row','movie_id','post_id','comment_id',
             'parent_comment_id','post_url','text_raw','text_clean','text_annotation','quality_status','quality_reasons','flags',
             'duplicate_group_id','master_group_id','human_decisions','human_label','human_label_source','label_status',
             'legacy_overall','legacy_overall_status','test_reserved','exposure_status','preprocessing_version','metadata_provenance'])
        labeled = [r for r in cleaned_rows if r['human_decisions']]
        write_csv(work/'human_labeled.local.csv', labeled,
            ['record_id','original_id','source_dataset','source_file','source_row','movie_id','post_id','comment_id','text_raw',
             'text_clean','text_annotation','human_decisions','human_label','human_label_source','label_status'])
        write_csv(work/'annotation_pool.local.csv', [r for r in cleaned_rows if r['annotation_pool_status']=='ELIGIBLE'],
            ['record_id','source_dataset','movie_id','post_id','comment_id','text_annotation','quality_status','duplicate_group_id','annotation_pool_status'])
        write_csv(work/'quality_exceptions.local.csv', [r for r in cleaned_rows if r['quality_status']!='KEEP'],
            ['record_id','source_dataset','post_id','comment_id','text_raw','text_clean','quality_status','quality_reasons','flags'])
        write_csv(work/'annotation_pool_exclusions.local.csv',
            [dict(record_id=r['record_id'],source_dataset=r['source_dataset'],reasons=reasons_by_id[r['record_id']])
             for r in cleaned_rows if reasons_by_id[r['record_id']]], ['record_id','source_dataset','reasons'])
        write_csv(work/'direct_near_duplicates.local.csv', duplicate_info['edges'], ['left','right','method'])
        write_csv(work/'preprocessing_examples.local.csv', [r for r in before_after if r['changed'] or r['reasons']],
            ['record_id','source_dataset','text_raw','text_clean','changed','flags','reasons'])
        write_csv(work/'human_decisions.local.csv', decisions,
            ['record_id','source_annotation_id','annotation_round','source_dataset','status','label','review_reason','reason','source_file','source_row','source_sha256','label_origin'])
        for name in ('pilot_500_annotation_input.csv','claude_input.csv','gemini_input.csv'):
            write_csv(work/name, all_ai_rows, ['id','text_annotation'])
        save(work/'pilot_selection_manifest.local.json', dict(seed=cfg['seed'], target=cfg['pilot_count'],
            selected=len(selected), status=summary['annotation_pool']['status'], algorithm='stratified_round_robin_by_source_length_and_signal_v1',
            source_quota=source_quota, selected_ids=[r['record_id'] for r in selected],
            selected_source_counts=dict(pilot_source_counts), selected_length_bins=dict(pilot_length_bins),
            selected_signal_rows=dict(pilot_signal_counts), selected_strata=dict(pilot_strata),
            selected_sha256=pilot_hash, fields=['id','text_annotation'], exact_duplicates_in_pilot=0,
            direct_near_duplicate_edges_in_pilot=sum(bool(duplicate_info['neighbors'].get(r['record_id'],set()) & set(same_ids)) for r in selected)//2,
            excluded_test_candidate_posts=len(test_candidate_posts), test_reservation_status=test_protection['reservation_status'],
            sentiment_or_legacy_overall_used_for_selection=False, metadata_omitted_from_blind_files=True))
        save(work/'blind_input_manifest.local.json', ai_sidecar)
        save(work/'quality_report.local.json', summary)
        save(work/'preprocessing_config.local.json', dict(version=cfg['preprocessing_version'], rules=BASIC,
            invalid_control_characters='remove C0/DEL characters after entity decoding; whitespace controls collapse as whitespace',
            exact_ui_strings=cfg.get('exact_ui_strings',[]), teencode_detection_only=list(TEENCODE_WORDS),
            teencode_replacements={}, text_annotation='text_clean; no emoji, negation, punctuation, teencode, repetition, URL, mention, or underscore removal'))
        save(work/'source_contract.local.json', dict(master_manifest_sha256=sha(master/'manifest.json'),
            master_source_manifest_status=master_manifest.get('status'), source_hashes={
                cfg['facebook_annotations']:sha(ROOT/cfg['facebook_annotations']),
                cfg['legacy_decisions']:sha(ROOT/cfg['legacy_decisions']),
                cfg['legacy_import_manifest']:sha(ROOT/cfg['legacy_import_manifest']),
                cfg['legacy_mapping']:sha(ROOT/cfg['legacy_mapping']),
                'outputs/development/reviewed/manifest.json':sha(ROOT/'outputs/development/reviewed/manifest.json'),
                'outputs/phase_g2/annotation_task/manifest.json':sha(ROOT/'outputs/phase_g2/annotation_task/manifest.json'),
                'outputs/phase_g2/human_import_01/receipt.json':sha(ROOT/'outputs/phase_g2/human_import_01/receipt.json'),
                'outputs/phase_g/blind_test/manifest.json':sha(ROOT/'outputs/phase_g/blind_test/manifest.json'),
                'outputs/phase_g/blind_test/availability.json':sha(ROOT/'outputs/phase_g/blind_test/availability.json'),
                cfg['guideline']:sha(guideline)},
            config_sha256=sha(config_path), implementation_sha256=sha(ROOT/'src/dataset/phase_i.py'),
            lineage_config_sha256=sha(ROOT/cfg['human_lineage_config']), test_protection=test_protection,
            protected_source_rows=len(master_rows), human_decisions=human_summary))
        # Same input bytes and IDs/text are required for all three annotators.
        for name in ('pilot_500_annotation_input.csv','claude_input.csv','gemini_input.csv'):
            if sha(work/name) != sha(work/'pilot_500_annotation_input.csv'):
                raise AssertionError('Blind input files are not byte-identical')
        return seal(work, dict(phase='I',status=summary['annotation_pool']['status'],
            dataset_version=cfg['dataset_version'],rows=len(cleaned_rows),selected=len(selected),
            public_report='docs/PHASE_I_DATA_CLEANING_REPORT.md', private_data=True,
            output_sha256_scope='manifest integrity hashes are local only'))


def percentile(values: list[int], p: float):
    if not values:
        return 0
    return values[min(len(values)-1, int((len(values)-1)*p))]


def validate_predictions(path: Path, metadata_path: Path, expected_ids: list[str]) -> dict:
    rows, fields = csv_rows(path.read_bytes())
    required = {'id','status','label','review_reason','reason'}
    if set(fields) != required:
        raise ValueError('Prediction columns must be exactly id,status,label,review_reason,reason')
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)) or ids != expected_ids:
        raise ValueError('Prediction IDs must exactly match the pilot order, without duplicates')
    for row in rows:
        status = row['status']; label = row['label']; review_reason = row['review_reason']
        if status == 'LABELED':
            if label not in LABELS or review_reason:
                raise ValueError('LABELED output must have a sentiment label and no review code')
        elif status == 'REVIEW':
            if label or review_reason not in REVIEW_CODES:
                raise ValueError('REVIEW output needs blank label and valid REV_* code')
        elif status == 'EXCLUDE':
            if label or review_reason not in EXCLUDE_CODES:
                raise ValueError('EXCLUDE output needs blank label and valid EXC_* code')
        else:
            raise ValueError('Invalid annotation status')
    metadata = load(metadata_path)
    required_meta = {'annotator','provider','model_id','model_version','guideline_version','guideline_sha256','prompt_sha256','labeled_at','label_source'}
    if required_meta - metadata.keys() or any(not metadata.get(k) for k in required_meta):
        raise ValueError('Missing annotator/model/guideline provenance sidecar')
    if metadata['guideline_version'] != 'V2.1' or metadata['label_source'] != 'automatic':
        raise ValueError('Prediction provenance must identify automatic V2.1 annotation')
    if metadata['guideline_sha256'] != sha(ROOT/'docs/guidelines/MOVIE_SENTIMENT_V2_1.md'):
        raise ValueError('Guideline checksum does not match the current immutable V2.1 file')
    annotator = str(metadata['annotator']).casefold()
    prompt_file = (ROOT/'docs/PHASE_I_ANNOTATION_PROTOCOL.md' if annotator == 'codex' else
        ROOT/f'docs/annotation/{annotator.upper()}_ANNOTATION_INSTRUCTIONS.md')
    if not prompt_file.exists() or metadata['prompt_sha256'] != sha(prompt_file):
        raise ValueError('Prompt checksum does not match the annotator instructions')
    return dict(rows=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),label_counts=dict(Counter(r['label'] for r in rows if r['label'])),
        metadata=metadata)


def consensus(predictions: dict[str, list[dict]]) -> list[dict]:
    if set(predictions) != {'codex','claude','gemini'}:
        raise ValueError('Consensus requires all three independently completed prediction files')
    ids = set(r['id'] for r in predictions['codex'])
    if any(set(r['id'] for r in values) != ids for values in predictions.values()):
        raise ValueError('Prediction ID sets differ')
    indexed = {name:{r['id']:r for r in values} for name,values in predictions.items()}
    output=[]
    for rid in sorted(ids):
        values=[indexed[name][rid] for name in ('codex','claude','gemini')]
        labels=[r['label'] for r in values if r['status']=='LABELED']
        states=[r['status'] for r in values]
        if any(s in {'REVIEW','EXCLUDE'} for s in states):
            status='REVIEW_REQUIRED'; label=''
        elif len(set(labels))==1:
            status='SILVER_3_OF_3'; label=labels[0]
        elif max(Counter(labels).values())==2:
            status='SILVER_2_OF_3_REVIEW_REQUIRED'; label=Counter(labels).most_common(1)[0][0]
        else:
            status='DISAGREEMENT_REVIEW'; label=''
        output.append(dict(id=rid,status=status,label=label,label_source='silver_candidate_not_gold'))
    return output
