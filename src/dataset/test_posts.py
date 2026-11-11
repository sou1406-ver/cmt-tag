"""Preflight new blind-test posts, reuse the crawler CLI, then reserve by quota."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from .common import ROOT, csv_rows, digest, load, read_jsonl, save, seal, sha, staged, verify, write_csv
from .exposure import history_references, references
from .master import post_url
from src.crawler.parser import post_id as url_post_id

INPUT_FIELDS = ['candidate_id','movie_slot','movie_id','post_url','post_id',
                'selected_from_post_content_only','unused_exposure_evidence','notes']
REGISTRY = ROOT/'data/test_reservations'


def live_crawl_references(data_root, wanted):
    """Only scheduled/visited post metadata, never comment bodies or browser state."""
    found=defaultdict(set)
    for config in sorted((Path(data_root)/'crawl_runs').glob('*/config.json')):
        values=[load(config)]
        inputs=config.parent/'interactive_inputs.jsonl'
        if inputs.exists():values.extend(read_jsonl(inputs))
        for pid,_ in references(values,wanted):found[pid].add(config.parent.name)
    return {pid:sorted(runs) for pid,runs in found.items()}


def registry_posts(registry):
    result=set()
    for path in sorted(Path(registry).glob('*.json')):
        entry=load(path);plan=Path(entry['plan_root'])
        if sha(plan/'manifest.json')!=entry['plan_manifest_sha256']:raise ValueError('Intake registry checksum changed')
        verify(plan);result.update(entry['post_ids'])
    return result


def receipt(path, row):
    path=Path(path).resolve()
    if (not path.is_relative_to(ROOT.parent) or path.suffix.lower()!='.json'
            or any(any(term in part.lower() for term in ('browser','credential','cookie','secret','.env')) for part in path.parts)):
        raise ValueError('Evidence must be a local JSON selection receipt within the workspace')
    payload=path.read_bytes();value=json.loads(payload.decode('utf-8-sig'))
    expected=dict(post_id=row['post_id'],post_url=row['post_url'],movie_id=row['movie_id'])
    if any(value.get(k)!=v for k,v in expected.items()):raise ValueError('Evidence receipt identity mismatch')
    if any(value.get(k) is not True for k in ('selected_from_post_content_only','comments_not_inspected',
                                              'not_used_for_guideline_or_model_selection')):
        raise ValueError('Affirmative selection/exposure attestation missing')
    if not str(value.get('attested_by','')).strip() or not str(value.get('evidence','')).strip():
        raise ValueError('Named attestor and concrete evidence required')
    at=datetime.fromisoformat(value.get('recorded_at','').replace('Z','+00:00'))
    if at.tzinfo is None or at>datetime.now(timezone.utc):raise ValueError('Evidence needs a past timezone-aware timestamp')
    return dict(path=str(path),sha256=digest(payload),receipt=value)


def preflight(input_path, master, output, registry=REGISTRY, data_root=None):
    input_path=Path(input_path).resolve();master=Path(master).resolve();verify(master)
    input_sha=sha(input_path);rows,fields=csv_rows(input_path.read_bytes())
    if fields!=INPUT_FIELDS or not rows:raise ValueError('Use the eight-column test_posts.csv schema with at least one row')
    ledger=load(master/'exposure_ledger.json');master_rows=read_jsonl(master/'master.jsonl')
    old_posts={r['post_id'] for r in master_rows if r['post_id']}
    exposed=set(ledger.get('known_exposed_post_ids',[]));already=registry_posts(registry)
    reports=[];candidate_counts=Counter(r['candidate_id'].strip() for r in rows)
    for number,original in enumerate(rows,2):
        row={k:v.strip() for k,v in original.items()};reasons=[]
        if not row['candidate_id'] or candidate_counts[row['candidate_id']]!=1:reasons.append('MISSING_OR_DUPLICATE_CANDIDATE_ID')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',row['movie_id']):reasons.append('MISSING_OR_INVALID_MOVIE_ID')
        canonical=post_url(row['post_url']);parsed=url_post_id(canonical) if canonical else None
        if not canonical or not parsed:reasons.append('MISSING_OR_INVALID_FACEBOOK_POST_URL')
        if row['post_id'] and row['post_id']!=parsed:reasons.append('POST_ID_URL_MISMATCH')
        row['post_url']=canonical;row['post_id']=parsed or row['post_id']
        if row['selected_from_post_content_only'].lower() not in {'true','yes','1'}:
            reasons.append('SELECTION_FROM_POST_ONLY_NOT_CONFIRMED')
        if row['post_id'] in old_posts:reasons.append('POST_ALREADY_IN_MASTER_INDEPENDENCE_NOT_NEW')
        if row['post_id'] in exposed:reasons.append('KNOWN_EXPOSED_POST')
        if row['post_id'] in already:reasons.append('POST_ALREADY_QUARANTINED')
        proof=None
        if not row['unused_exposure_evidence']:reasons.append('MISSING_UNUSED_EXPOSURE_RECEIPT')
        elif canonical and parsed and row['movie_id']:
            try:proof=receipt(input_path.parent/row['unused_exposure_evidence'],row)
            except (ValueError,OSError,KeyError,TypeError):reasons.append('UNVERIFIED_EXPOSURE_RECEIPT')
        reports.append(dict(source_row=number,**row,reasons=reasons,proof=proof))
    wanted={r['post_id'] for r in reports if r['post_id']}
    findings,unreadable,scanned=history_references(master,wanted)
    live=live_crawl_references(data_root or ROOT/'data',wanted)
    duplicates=Counter(r['post_id'] for r in reports if r['post_id']);slots=defaultdict(set)
    for row in reports:
        if row['movie_slot'] and row['movie_id']:slots[row['movie_slot']].add(row['movie_id'])
    for row in reports:
        pid=row['post_id']
        if pid and duplicates[pid]>1:row['reasons'].append('DUPLICATE_POST_ID_IN_INPUT')
        if pid in findings:row['reasons'].append('POST_HAS_PREEXISTING_METADATA_HISTORY')
        if pid in live:row['reasons'].append('POST_ALREADY_SCHEDULED_OR_VISITED_BY_CRAWLER')
        if len(slots[row['movie_slot']])>1:row['reasons'].append('MOVIE_SLOT_IDENTITY_CONFLICT')
        if unreadable:row['reasons'].append('EXPOSURE_HISTORY_INCOMPLETE')
        row['status']='BLOCKED' if row['reasons'] else 'READY'
        row['history_references']=findings.get(pid,[]);row['previous_crawl_runs']=live.get(pid,[])
    ready=all(r['status']=='READY' for r in reports)
    with staged(output) as work:
        save(work/'rows.json',reports);save(work/'evidence_gaps.json',unreadable)
        write_csv(work/'validation.csv',reports,['source_row','candidate_id','movie_slot','movie_id','post_id','post_url','status','reasons'])
        if ready:
            write_csv(work/'crawl_posts.csv',reports,['movie_id','post_url'])
            save(work/'candidate_quarantine.json',dict(post_ids=sorted(wanted),post_urls=sorted({r['post_url'] for r in reports})))
        if sha(input_path)!=input_sha:raise ValueError('User input changed during preflight')
        if any(r['proof'] and sha(r['proof']['path'])!=r['proof']['sha256'] for r in reports):
            raise ValueError('Selection evidence changed during preflight')
        result=seal(work,dict(status='READY_FOR_CRAWL' if ready else 'BLOCKED',input_file=str(input_path),input_sha256=input_sha,
            master_root=str(master),master_manifest_sha256=sha(master/'manifest.json'),rows=len(reports),
            ready_rows=sum(r['status']=='READY' for r in reports),blocked_rows=sum(r['status']=='BLOCKED' for r in reports),
            history_metadata_files_checked=scanned,source_dataset='blind_test_'+input_sha[:16],
            created_at=datetime.now(timezone.utc).isoformat(),comments_inspected_for_selection=False,
            source_identity_verification='URL syntax/embedded ID and local metadata; not remote accessibility or film-content verification',
            source_receipts_are='explicit human attestations, checksum pinned; not independently proven by absence of history'))
    if ready:
        registry=Path(registry);registry.mkdir(parents=True,exist_ok=True)
        save(registry/(sha(Path(output)/'manifest.json')+'.json'),dict(plan_root=str(Path(output).resolve()),
            plan_manifest_sha256=sha(Path(output)/'manifest.json'),post_ids=sorted(wanted)))
    return result


def verified_plan(plan):
    plan=Path(plan).resolve();manifest=verify(plan)
    if manifest['status']!='READY_FOR_CRAWL':raise ValueError('Preflight blocked; do not crawl')
    if sha(manifest['input_file'])!=manifest['input_sha256']:raise ValueError('User post list changed; rerun preflight')
    master=Path(manifest['master_root']);verify(master)
    if sha(master/'manifest.json')!=manifest['master_manifest_sha256']:raise ValueError('Master changed after preflight')
    rows=load(plan/'rows.json')
    for row in rows:
        proof=row['proof']
        if sha(proof['path'])!=proof['sha256']:raise ValueError('Selection evidence changed after preflight')
    return manifest,rows


def require_registration(plan,registry):
    expected=sha(Path(plan)/'manifest.json')
    if not any(load(p).get('plan_manifest_sha256')==expected for p in Path(registry).glob('*.json')):
        raise ValueError('Candidate posts must be registered for quarantine before collection')


def crawl(plan, data_root, channel='brave', profile=None, resume=None, runner=subprocess.run, registry=REGISTRY,
          post_timeout=300,max_rounds=50,settle_ms=1500,max_actions=20):
    manifest,rows=verified_plan(plan);data_root=Path(data_root)
    require_registration(plan,registry)
    live=live_crawl_references(data_root,{r['post_id'] for r in rows})
    if any(set(runs)-({resume} if resume else set()) for runs in live.values()):
        raise ValueError('Posts were scheduled/crawled after preflight; review before continuing')
    if resume:verify_run(plan,data_root,resume)
    if any(type(v) is not int or v<=0 for v in (post_timeout,max_rounds,settle_ms,max_actions)):
        raise ValueError('Positive collection safety budgets required')
    args=[sys.executable,'-m','src.crawler','crawl-batch','--data-root',str(data_root),'--channel',channel]
    if profile:args+=['--profile',str(profile)]
    if resume:args+=['--resume',resume]
    else:args+=['--input',str(Path(plan).resolve()/'crawl_posts.csv'),'--source-dataset',manifest['source_dataset'],
                '--max-comments','all','--max-rounds',str(max_rounds),'--post-timeout',str(post_timeout),
                '--settle-ms',str(settle_ms),'--max-actions',str(max_actions)]
    # Same crawler, Store and run_posts; inherited terminal allows manual login. No shell URL interpolation.
    return runner(args,cwd=ROOT,check=False).returncode


def verify_run(plan, data_root, run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('Invalid crawler run ID')
    manifest,rows=verified_plan(plan);path=Path(data_root)/'crawl_runs'/run_id
    config=load(path/'config.json')
    expected={(r['post_id'],r['post_url'],r['movie_id']) for r in rows}
    actual={(url_post_id(post_url(r['post_url'])),post_url(r['post_url']),r['movie_id']) for r in config['posts']}
    if config.get('source_dataset')!=manifest['source_dataset'] or actual!=expected or len(config['posts'])!=len(rows):
        raise ValueError('Crawler run does not match this preflight selection')
    if config.get('max_comments','missing') is not None:
        raise ValueError('Phase G.1 requires an uncapped run; preserve old capped runs and create a new run with --max-comments all')
    created=datetime.fromisoformat(config['created_at'].replace('Z','+00:00'))
    if created<datetime.fromisoformat(manifest['created_at']):raise ValueError('Run predates blind preflight')
    if (path/'interactive_inputs.jsonl').exists():raise ValueError('Blind run cannot append unapproved interactive posts')
    return path


def reserve(plan, data_root, run_id, output, registry=REGISTRY):
    """New master + full duplicate graph against all development; never edit old snapshots."""
    from .master import build
    from .blind import prepare,quarantine_posts
    from src.crawler.locking import RunLock
    manifest,posts=verified_plan(plan);run=verify_run(plan,data_root,run_id)
    require_registration(plan,registry)
    if not (run/'raw_comments.jsonl').exists():raise ValueError('No crawler journal')
    raw_sha=sha(run/'raw_comments.jsonl')
    old=Path(manifest['master_root']);old_manifest=verify(old);ledger=load(old/'exposure_ledger.json')
    ledger['attested_unused_posts']=[dict(post_id=r['post_id'],post_url=r['post_url'],
        not_used_for_guideline_or_model_selection=True,evidence=r['proof'],
        selection_protocol='post-only choice; no comment screening before collection') for r in posts]
    # Build only from a standard crawler journal location, avoiding silent source omission.
    if Path(data_root).resolve()!=ROOT/'data':raise ValueError('Reserve requires the repository data root; custom crawl roots need explicit importer configuration')
    # Each child snapshot is atomic and immutable. The outer manifest and registry
    # are published only after all checks pass; failed attempts remain inspectable.
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Output exists; use a new intake version')
    output.mkdir(parents=True)
    with RunLock(run/'.browser.lock'):
        work=output
        save(work/'exposure_ledger.json',ledger)
        cfg=load(old/'config.json');cfg['dataset_version']='blind_intake_'+run_id
        cfg['exposure_ledger']=str((work/'exposure_ledger.json').resolve())
        save(work/'master_config.json',cfg)
        build(work/'master_config.json',work/'master')
        master_rows=read_jsonl(work/'master/master.jsonl')
        save(work/'post_quarantine.json',quarantine_posts(master_rows,{r['post_id'] for r in posts}))
        blind_cfg=dict(master_root=str((work/'master').resolve()),master_manifest_sha256=sha(work/'master/manifest.json'),
                       target=180,max_per_post=10,max_per_movie=20,seed=20261111,second_annotator_count=50)
        save(work/'blind_config.json',blind_cfg);result=prepare(work/'blind_config.json',work/'blind_test')
        if sha(run/'raw_comments.jsonl')!=raw_sha:raise ValueError('Crawler journal changed during reservation')
        seal(work,dict(status=result['status'],selected=result['selected'],run_id=run_id,raw_sha256=raw_sha,
            plan_manifest_sha256=sha(Path(plan)/'manifest.json'),parent_master_manifest_sha256=sha(old/'manifest.json'),
            comments_selected_using_sentiment=False,quotas_relaxed=False,master_records=len(master_rows),
            entire_master_retained=True,sampling_does_not_filter_master=True))
    registry=Path(registry);registry.mkdir(parents=True,exist_ok=True)
    save(registry/('reservation_'+sha(Path(output)/'manifest.json')+'.json'),dict(plan_root=str(Path(plan).resolve()),
        plan_manifest_sha256=sha(Path(plan)/'manifest.json'),post_ids=sorted({r['post_id'] for r in posts}),
        collection_root=str(Path(output).resolve()),collection_manifest_sha256=sha(Path(output)/'manifest.json'),
        reservation_root=str((Path(output)/'blind_test').resolve()),reservation_manifest_sha256=sha(Path(output)/'blind_test/manifest.json')))
    return result


def assert_intakes_allowed(rows,purpose,registry=REGISTRY):
    from .blind import deny_reserved
    for path in sorted(Path(registry).glob('*.json')):
        entry=load(path);plan=Path(entry['plan_root'])
        if sha(plan/'manifest.json')!=entry['plan_manifest_sha256']:raise ValueError('Intake registry checksum changed')
        verify(plan);quarantine=load(plan/'candidate_quarantine.json')
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
