"""Audit transitive master components separately from direct fold overlaps."""
from collections import Counter, defaultdict
from pathlib import Path

from src.data.split import UnionFind
from src.data.quality import near_duplicate_candidates
from src.dataset.common import ROOT, digest, load, read_jsonl
from src.dataset.master import normal
from src.preprocessing.normalization import BASIC, normalize


def _components(ids, links):
    uf = UnionFind(ids)
    for left, right in links:
        uf.union(left, right)
    sizes = Counter(uf.find(value) for value in ids)
    return dict(component_count=len(sizes), largest_component=max(sizes.values(), default=0),
                components_over_1000=sum(size > 1000 for size in sizes.values()))


def _master_edge_audit(master_rows, near_pairs):
    ids = [row['id'] for row in master_rows]
    edge_sets = {key: [] for key in ('identity', 'exact_text', 'near_duplicate')}
    key_owners = defaultdict(list)
    text_owners = defaultdict(set)
    text_lengths = {}
    for row in master_rows:
        for field in ('post_id', 'post_url', 'comment_id'):
            value = row.get(field)
            if value:
                key_owners[('identity', row.get('source_platform', ''), field, value)].append(row['id'])
        for group in row.get('development_groups', []):
            key_owners[('identity', 'old_development_group', group)].append(row['id'])
        aliases = [*row.get('text_variants', []), row.get('text_view', '')]
        aliases.extend(decision.get('text_raw', '') for decision in row.get('human_decisions', []))
        for text in aliases:
            value = normal(text)
            if value:
                key = digest(value)
                text_owners[key].add(row['id'])
                text_lengths[key] = len(value)
    for key, owners in key_owners.items():
        unique = sorted(set(owners))
        edge_sets['identity'].extend((unique[0], value) for value in unique[1:])
    repeated = []
    for key, owners in text_owners.items():
        unique = sorted(owners)
        if len(unique) > 1:
            repeated.append(dict(owners=len(unique), chars=text_lengths[key]))
            edge_sets['exact_text'].extend((unique[0], value) for value in unique[1:])
    near_ids = set(ids)
    for pair in near_pairs:
        left, right = pair['left_master_id'], pair['right_master_id']
        if left in near_ids and right in near_ids:
            edge_sets['near_duplicate'].append((left, right))
    def combine(*names):
        return [edge for name in names for edge in edge_sets[name]]
    giant_id = 'mg_b1b2bec0584310374593afd4e980172e59c82f4eb9d3638cfeae84cba58af7e4'
    giant = [r for r in master_rows if r.get('group_id') == giant_id]
    platform = Counter(r.get('source_platform', 'unknown') for r in giant)
    posts = {r.get('post_id') for r in giant if r.get('source_platform') == 'facebook' and r.get('post_id')}
    return dict(
        master_records=len(master_rows), giant_component_id=giant_id, giant_records=len(giant),
        giant_platform_records=dict(platform), giant_facebook_post_count=len(posts),
        direct_spanning_links_by_type={key: len(value) for key, value in edge_sets.items()},
        repeated_exact_text_groups=len(repeated),
        repeated_exact_groups_under_40_chars=sum(x['chars'] < 40 for x in repeated),
        max_records_per_exact_text=max((x['owners'] for x in repeated), default=0),
        near_duplicate_edge_count=len(edge_sets['near_duplicate']),
        component_ablation={
            'identity_only': _components(ids, combine('identity')),
            'identity_plus_exact': _components(ids, combine('identity', 'exact_text')),
            'identity_plus_near': _components(ids, combine('identity', 'near_duplicate')),
            'all_edge_types': _components(ids, combine('identity', 'exact_text', 'near_duplicate')),
        },
    )


def _candidate_near_pairs(rows, view):
    aliases = []
    for row in rows:
        texts = row.get('alias_texts') or [row['text_view']]
        for index, text in enumerate(sorted(set(texts))):
            if view == 'basic':
                text = normalize(text, BASIC)
            if text:
                aliases.append(dict(id=f"{row['id']}|{index}", row_id=row['id'], text=text,
                    quality=dict(status='KEEP', duplicate_of=None)))
    pairs = near_duplicate_candidates(aliases, dict(threshold=.9, min_chars=40, shingle_size=3))
    id_rows = {record['id']: record['row_id'] for record in aliases}
    return {(id_rows[p['left']], id_rows[p['right']]) for p in pairs
            if id_rows[p['left']] != id_rows[p['right']]}


def direct_gate_passes(folds):
    """Pass only when measurable hard-ID, exact-text and direct-near checks are clear."""
    return all(not any(f['identity_overlap'].values())
        and not any(f['exact_text_hash_overlap'].values())
        and not any(v['selected_alias_pairs'] or v['full_master_alias_pairs']
                    for v in f['near_duplicate_pairs'].values())
        and not any(f['legacy_exact_overlap_rows'].values())
        and not any(v['selected_alias_pairs'] or v['full_master_alias_pairs']
                    for v in f['legacy_near_duplicate_pairs'].values())
        and f['frozen_group_overlap'] == 0 for f in folds)


def audit(master_dir='outputs/phase_g/master', unified_dir='outputs/phase_g3/unified'):
    master_dir, unified_dir = ROOT/master_dir, ROOT/unified_dir
    master = read_jsonl(master_dir/'master.jsonl')
    master_near_pairs = load(master_dir/'near_duplicates.json')
    rows = read_jsonl(unified_dir/'unified.jsonl')
    locked = load(unified_dir/'frozen_plan.json')
    by_original = {r['original_id']: r for r in rows if r['source_dataset'] == 'facebook_development'}
    legacy = [r for r in rows if r['source_dataset'] == 'legacy_human']
    all_near = {view: _candidate_near_pairs(rows, view) for view in ('original', 'basic')}
    master_near = {(p['left_master_id'], p['right_master_id']) for p in master_near_pairs}
    master_near |= {(right, left) for left, right in list(master_near)}

    def aliases(row, view):
        values = row.get('alias_texts') or [row['text_view']]
        if view == 'basic':
            values = [normalize(text, BASIC) for text in values]
        return {digest(normal(text)) for text in values if normal(text)}

    folds = []
    for fold in locked['folds']:
        train_fb = [by_original[i] for i in fold['train_ids']]
        valid = [by_original[i] for i in fold['validation_ids']]
        valid_ids = {r['id'] for r in valid}
        valid_master = {r['master_id'] for r in valid}
        identity = {}
        for field in ('post_id', 'post_url', 'comment_id', 'parent_comment_id'):
            tr_keys = {(r.get('platform', ''), r.get(field, '')) for r in train_fb if r.get(field)}
            va_keys = {(r.get('platform', ''), r.get(field, '')) for r in valid if r.get(field)}
            identity[field] = len(tr_keys & va_keys)
        exact = {}
        near = {}
        legacy_exact = {}
        legacy_near = {}
        for view in ('original', 'basic'):
            tr_hash = set().union(*(aliases(r, view) for r in train_fb))
            va_hash = set().union(*(aliases(r, view) for r in valid))
            lg_hash_by_id = {r['id']: aliases(r, view) for r in legacy}
            exact[view] = len(tr_hash & va_hash)
            legacy_exact[view] = sum(bool(hashes & va_hash) for hashes in lg_hash_by_id.values())
            cross_fb = sum(1 for left, right in all_near[view]
                if (left in {r['id'] for r in train_fb} and right in valid_ids)
                or (right in {r['id'] for r in train_fb} and left in valid_ids))
            cross_legacy = sum(1 for left, right in all_near[view]
                if (left in {r['id'] for r in legacy} and right in valid_ids)
                or (right in {r['id'] for r in legacy} and left in valid_ids))
            # Also count edges built from the full master alias graph, which may include
            # historical projections not selected as the row's displayed text.
            selected_master = {r['master_id'] for r in train_fb}
            direct_master_near = sum(1 for left in selected_master for right in valid_master
                                     if (left, right) in master_near)
            direct_legacy_master_near = sum(1 for r in legacy for v in valid
                if (r['master_id'], v['master_id']) in master_near)
            near[view] = dict(selected_alias_pairs=cross_fb,
                              full_master_alias_pairs=direct_master_near)
            legacy_near[view] = dict(selected_alias_pairs=cross_legacy,
                                     full_master_alias_pairs=direct_legacy_master_near)
        group_by_id = locked.get('group_by_id', {})
        train_groups = {group_by_id.get(i) for i in fold['train_ids']}
        validation_groups = {group_by_id.get(i) for i in fold['validation_ids']}
        folds.append(dict(fold=fold['fold'], train_facebook=len(train_fb), validation_facebook=len(valid),
            validation_posts=len({r['post_id'] for r in valid if r.get('post_id')}),
            identity_overlap=identity, exact_text_hash_overlap=exact, near_duplicate_pairs=near,
            legacy_rows=len(legacy), legacy_identity_provenance='unavailable',
            legacy_exact_overlap_rows=legacy_exact, legacy_near_duplicate_pairs=legacy_near,
            frozen_group_overlap=len((train_groups - {None}) & (validation_groups - {None}))))
    master_graph = _master_edge_audit(master, master_near_pairs)
    direct_zero = direct_gate_passes(folds)
    return dict(protocol='direct_fold_isolation_v1', master_graph=master_graph, folds=folds,
        direct_overlap_gate='PASS' if direct_zero else 'BLOCKED',
        legacy_identity_gate='UNVERIFIABLE_MISSING_SOURCE_METADATA',
        interpretation=('Direct, measurable overlap checks pass; this does not establish legacy post independence.'
                        if direct_zero else 'At least one direct fold overlap remains; block the comparison.'))
