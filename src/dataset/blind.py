"""Read-only frozen reservation and whole-post quarantine protection."""
from pathlib import Path
from .common import ROOT, load, sha, verify, normal
from .master import post_url

REGISTRY = ROOT/'data/test_reservations'


class ReservedDataError(ValueError):
    """A valid reservation forbids this row, rather than a corrupt contract."""

def assert_intakes_allowed(rows,purpose,registry=REGISTRY):
    for path in sorted(Path(registry).glob('*.json')):
        entry=load(path);plan=Path(entry['plan_root'])
        if sha(plan/'manifest.json')!=entry['plan_manifest_sha256']:raise ValueError('Intake registry checksum changed')
        verify(plan)
        if entry.get('candidate_quarantine_sha256') and sha(plan/'candidate_quarantine.json')!=entry['candidate_quarantine_sha256']:
            raise ValueError('Candidate quarantine checksum changed')
        quarantine=load(plan/'candidate_quarantine.json')
        deny_reserved(rows,purpose,dict(ids=[],groups=[],comment_ids=[],text_hashes=[],
            post_ids=quarantine['post_ids'],post_urls=quarantine['post_urls']))
        if entry.get('collection_root'):
            collection=Path(entry['collection_root']);m=load(collection/'manifest.json')
            if (sha(collection/'manifest.json')!=entry['collection_manifest_sha256'] or
                    sha(collection/'post_quarantine.json')!=m['output_sha256']['post_quarantine.json']):
                raise ValueError('Whole-post component quarantine changed')
            deny_reserved(rows,purpose,load(collection/'post_quarantine.json'))
        if entry.get('reservation_root'):
            directory=Path(entry['reservation_root']);m=verify(directory)
            if sha(directory/'manifest.json')!=entry['reservation_manifest_sha256']:raise ValueError('Registered reservation changed')
            if m['status']!='PARTIAL':deny_reserved(rows,purpose,load(directory/'reservation.json'))

PROHIBITED = ('train', 'validation', 'model_selection', 'active_learning', 'pseudo_labeling',
              'prompt_tuning', 'guideline_tuning', 'threshold_tuning')

def assert_allowed(rows, purpose, reservation_root=None, registry=None):
    """Mandatory at new data-use boundaries, including AI/pseudo labeling.

    The default local reservation is absent before Phase G, or sealed PARTIAL with
    zero reservations. A present but corrupt/incomplete reservation fails closed.
    """
    assert_intakes_allowed(rows,purpose,REGISTRY if registry is None else registry)
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
            raise ReservedDataError('Reserved blind-test component cannot be used for '+purpose)

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
