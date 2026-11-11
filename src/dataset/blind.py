"""Fail-closed reservation of independent, unlabeled source-post clusters."""
from collections import Counter, defaultdict
from pathlib import Path
import random

from .common import ROOT, load, read_jsonl, save, seal, sha, staged, verify, write_csv
from .master import normal, post_url
from src.annotation.guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline
from src.crawler.parser import post_id as url_post_id

BLIND_FIELDS = ['id', 'text_view', 'status', 'label', 'review_reason', 'reason']
PROHIBITED = ('train', 'validation', 'model_selection', 'active_learning', 'pseudo_labeling',
              'prompt_tuning', 'guideline_tuning', 'threshold_tuning')


def sample(rows, count, per_post, per_movie, seed):
    """Seeded movie/post shuffle, then round-robin draws from shuffled post lists.

    This is a quota design, NOT a uniform comment sample or natural-distribution test.
    Input order, text length, sentiment and predictions never affect selection.
    """
    if any(type(v) is not int or v <= 0 for v in (count, per_post, per_movie)) or type(seed) is not int:
        raise ValueError('Positive integer quotas and integer seed required')
    if len({r['id'] for r in rows}) != len(rows): raise ValueError('Repeated candidate ID')
    rng = random.Random(seed); movies = defaultdict(lambda: defaultdict(list))
    for row in sorted(rows, key=lambda r: r['id']): movies[row['movie_id']][row['post_id']].append(row)
    movie_order = sorted(movies); rng.shuffle(movie_order)
    post_order = {}; cursors = Counter()
    for movie in movie_order:
        post_order[movie] = sorted(movies[movie]); rng.shuffle(post_order[movie])
        for post in post_order[movie]: rng.shuffle(movies[movie][post])
    chosen = []; post_counts = Counter(); movie_counts = Counter()
    while len(chosen) < count:
        added = False
        for movie in movie_order:
            if movie_counts[movie] >= per_movie: continue
            for post in post_order[movie]:
                values = movies[movie][post]
                if cursors[post] >= len(values) or post_counts[post] >= per_post: continue
                chosen.append(values[cursors[post]]); cursors[post] += 1
                post_counts[post] += 1; movie_counts[movie] += 1; added = True
                break
            if len(chosen) == count: break
        if not added: break
    return chosen


def eligible(rows, development_ids, ledger):
    dev = {r['group_id'] for r in rows if r.get('development') or set(r.get('development_ids', [])) & set(development_ids)}
    exposed_posts = set(ledger.get('known_exposed_post_ids', []))
    exposed_groups = {r['group_id'] for r in rows if r['post_id'] in exposed_posts} | dev
    attestations = {}
    for item in ledger.get('attested_unused_posts', []):
        # Attestations must be explicit evidence, not absence from the development workbook.
        if not item.get('evidence') or not item.get('not_used_for_guideline_or_model_selection') is True:
            raise ValueError('Incomplete unused-post attestation')
        key = (item['post_id'], post_url(item['post_url']))
        if not key[0] or not key[1] or key in attestations: raise ValueError('Invalid/repeated unused post')
        attestations[key] = item
    usable, rejected = [], []
    for row in rows:
        reasons = []
        if row['group_id'] in exposed_groups: reasons.append('DEVELOPMENT_OR_EXPOSED_CONNECTED_COMPONENT')
        if not all(row.get(k) for k in ('comment_id','post_id','post_url','movie_id')):
            reasons.append('MISSING_INDEPENDENCE_METADATA')
        if (not str(row.get('comment_id', '')).isdigit() or not post_url(row.get('post_url'))
                or url_post_id(post_url(row.get('post_url'))) != row.get('post_id')):
            reasons.append('SOURCE_IDENTITY_NOT_CORROBORATED_BY_POST_URL')
        if row.get('source_platform') != 'facebook': reasons.append('NOT_VERIFIED_FACEBOOK_IDENTITY')
        if row.get('platform',row.get('source_platform')) != 'facebook' or row.get('source',row.get('source_platform'))!='facebook':
            reasons.append('PLATFORM_NOT_IN_FACEBOOK_TEST_PROTOCOL')
        if set(row.get('review_flags', [])) - {'TEXT_VARIANTS_RETAINED'}:
            reasons.append('UNRESOLVED_IDENTITY_OR_LABEL_REVIEW')
        if (row['post_id'], post_url(row['post_url'])) not in attestations:
            reasons.append('EXPOSURE_UNKNOWN_NOT_ATTESTED_UNUSED')
        if not normal(row['text_view']): reasons.append('EMPTY_AFTER_DOCUMENTED_MENTION_VIEW')
        if row.get('human_decisions') or row.get('annotation_status') != 'UNLABELED': reasons.append('ALREADY_HUMAN_ANNOTATED')
        if reasons: rejected.append(dict(id=row['id'], post_id=row['post_id'], reasons=reasons))
        else: usable.append(row)
    # Text duplicates across identities remain in master, but selecting two identical texts is redundant.
    # Their component is reserved as a whole; no label or length is used to pick representatives.
    return usable, rejected


def validate_selection(selected, rows, cfg):
    if len({r['id'] for r in selected}) != len(selected): raise ValueError('Duplicate test ID')
    post_counts = Counter(r['post_id'] for r in selected); movies = Counter(r['movie_id'] for r in selected)
    if max(post_counts.values(), default=0) > cfg['max_per_post'] or max(movies.values(), default=0) > cfg['max_per_movie']:
        raise ValueError('Test quota violated')
    development_groups = {r['group_id'] for r in rows if r.get('development')}
    if development_groups & {r['group_id'] for r in selected}: raise ValueError('Connected development/test leakage')


def prepare(config_path, output):
    cfg = load(config_path); master = ROOT/cfg['master_root']; manifest = verify(master)
    if sha(master/'manifest.json') != cfg['master_manifest_sha256']: raise ValueError('Master manifest changed')
    validate_guideline(GUIDELINE_VERSION, sha(GUIDELINE))
    if GUIDELINE_VERSION != 'V2.1': raise ValueError('Blind task requires frozen V2.1')
    rows = read_jsonl(master/'master.jsonl'); ledger = load(master/'exposure_ledger.json')
    mapping = load(master/'development_mapping.json')
    usable, exclusions = eligible(rows, [r['development_id'] for r in mapping], ledger)
    selected = sample(usable, cfg['target'], cfg['max_per_post'], cfg['max_per_movie'], cfg['seed'])
    validate_selection(selected, rows, cfg)
    enough = len(selected) == cfg['target']
    with staged(output) as work:
        save(work/'config.json', cfg); save(work/'exclusions.json', exclusions)
        save(work/'availability.json', dict(target=cfg['target'], eligible_before_quota=len(usable),
            attainable_under_quota=len(selected), shortfall=cfg['target']-len(selected),
            rejection_reason_counts=dict(Counter(reason for e in exclusions for reason in e['reasons'])),
            eligible_posts=len({r['post_id'] for r in usable}), eligible_movies=len({r['movie_id'] for r in usable}),
            source_candidates_requiring_exposure_audit=sorted({r['post_id'] for r in rows
                if not r.get('development') and r['post_id'] and r['exposure_status']=='unknown_not_attested_unused'})))
        entries = []
        if enough:
            groups = {r['group_id'] for r in selected}
            entries = [{k: r[k] for k in ('id','comment_id','post_id','post_url','movie_id','group_id')} for r in selected]
            # Reserve all aliases and ALL members of selected connected components, not just 180 IDs.
            reserved_rows = [r for r in rows if r['group_id'] in groups]
            reservation = dict(status='reserved_blind_test', entries=entries, groups=sorted(groups),
                platform='facebook',source='facebook',
                ids=sorted({r['id'] for r in reserved_rows} | {x for r in reserved_rows for x in r['development_ids']}),
                comment_ids=sorted({r['comment_id'] for r in reserved_rows if r['comment_id']}),
                post_ids=sorted({r['post_id'] for r in reserved_rows if r['post_id']}),
                post_urls=sorted({r['post_url'] for r in reserved_rows if r['post_url']}),
                text_hashes=sorted({__import__('hashlib').sha256(normal(t).encode()).hexdigest()
                    for r in reserved_rows for t in [r['text_view'], *r['text_variants']] if normal(t)}),
                prohibited_uses=list(PROHIBITED), master_manifest_sha256=cfg['master_manifest_sha256'])
            save(work/'reservation.json', reservation)
            a = list(selected); random.Random(cfg['seed']+1).shuffle(a)
            b = random.Random(cfg['seed']+2).sample(sorted(selected, key=lambda r: r['id']), cfg['second_annotator_count'])
            def blinded(items): return [dict(id=r['id'], text_view=r['text_view'], status='',label='',review_reason='',reason='') for r in items]
            write_csv(work/'test_annotator_a.csv', blinded(a), BLIND_FIELDS)
            write_csv(work/'test_annotator_b_50.csv', blinded(b), BLIND_FIELDS)
            # The artifact-tool builder consumes only whitelisted blind fields; no hidden coordinator sheet.
            save(work/'workbook_input.json', dict(a=blinded(a), b=blinded(b)))
            save(work/'coordinator_mapping.json', entries)
        result = seal(work, dict(phase='G', status='RESERVED_PENDING_WORKBOOKS' if enough else 'PARTIAL',
            target=cfg['target'], selected=len(entries), eligible_before_quota=len(usable), attainable_under_quota=len(selected),
            dataset_version=manifest['dataset_version'], master_manifest_sha256=cfg['master_manifest_sha256'],
            source_checksums=manifest['input_sha256'], seed=cfg['seed'], max_per_post=cfg['max_per_post'],
            max_per_movie=cfg['max_per_movie'], algorithm='seeded_movie_post_round_robin_without_replacement_v1',
            quota_sample_not_natural_facebook_distribution=True, guideline_version=GUIDELINE_VERSION,
            guideline_sha256=sha(GUIDELINE), gold_created=False, labels_imported=False, predictions_opened=False,
            platform='facebook',source='facebook',
            blind_text_field='text_view', blind_text_policy='existing_dom_text_v2_when_available_else_unchanged_raw',
            blocker='' if enough else 'Insufficient provably unused sources; no quota relaxed and no annotation files emitted'))
    return result


def assert_allowed(rows, purpose, reservation_root=None):
    """Mandatory at new data-use boundaries, including AI/pseudo labeling.

    The default local reservation is absent before Phase G, or sealed PARTIAL with
    zero reservations. A present but corrupt/incomplete reservation fails closed.
    """
    from .test_posts import assert_intakes_allowed
    assert_intakes_allowed(rows,purpose)
    directory = Path(reservation_root) if reservation_root else ROOT/'outputs/phase_g/blind_test'
    if not directory.exists(): return
    manifest = verify(directory)
    if manifest['status'] == 'PARTIAL':
        if manifest['selected'] != 0 or (directory/'reservation.json').exists():
            raise ValueError('Invalid partial reservation')
        return
    reserved = load(directory/'reservation.json')
    deny_reserved(rows,purpose,reserved)


def deny_reserved(rows,purpose,reserved):
    if purpose not in PROHIBITED: raise ValueError('Explicit prohibited use required at this boundary')
    keys = {k: set(reserved[k]) for k in ('ids','groups','comment_ids','post_ids','post_urls','text_hashes')}
    from .common import digest
    typed_comments=set(reserved.get('platform_comment_keys',[]));typed_posts=set(reserved.get('platform_post_keys',[]))
    for row in rows:
        platform=row.get('platform') or row.get('source_platform') or 'facebook'
        same_platform=platform==reserved.get('platform','facebook')
        if (row.get('id') in keys['ids'] or row.get('group_id') in keys['groups']
            or platform+':'+str(row.get('comment_id','')) in typed_comments
            or platform+':'+str(row.get('post_id','')) in typed_posts
            or (same_platform and (row.get('comment_id') in keys['comment_ids'] or row.get('post_id') in keys['post_ids']
                or post_url(row.get('post_url')) in keys['post_urls']))
            or any(digest(normal(row[k])) in keys['text_hashes'] for k in ('text_raw','text','text_view') if row.get(k))):
            raise ValueError('Reserved blind-test component cannot be used for '+purpose)


def quarantine_posts(rows,post_ids,platform='facebook'):
    """Entire post components, including unsampled comments and cross-platform duplicates."""
    from .common import digest
    groups={r['group_id'] for r in rows if r['source_platform']==platform and r['post_id'] in set(post_ids)}
    members=[r for r in rows if r['group_id'] in groups]
    return dict(platform=platform,source=platform,groups=sorted(groups),
        ids=sorted({r['id'] for r in members}|{d for r in members for d in r.get('development_ids',[])}),
        comment_ids=sorted({r['comment_id'] for r in members if r['source_platform']==platform and r['comment_id']}),
        post_ids=sorted({r['post_id'] for r in members if r['source_platform']==platform and r['post_id']}),
        post_urls=sorted({r['post_url'] for r in members if r['source_platform']==platform and r['post_url']}),
        platform_comment_keys=sorted({r['source_platform']+':'+r['comment_id'] for r in members if r['comment_id']}),
        platform_post_keys=sorted({r['source_platform']+':'+r['post_id'] for r in members if r['post_id']}),
        text_hashes=sorted({digest(normal(t)) for r in members for t in [r['text_view'],*r['text_variants']] if normal(t)}),
        member_records=len(members),quarantine_scope='all approved post components, not only sampled test IDs')
