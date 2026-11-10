"""Metadata-only history audit. Absence from a file never proves non-exposure."""
from collections import Counter, defaultdict
import io
import json
from pathlib import Path
import zipfile

from .common import ROOT, csv_rows, digest, load, read_jsonl, save, seal, sha, staged, verify, write_csv
from .master import post_url
from src.crawler.parser import post_id as url_post_id


def references(value, wanted, pointer='$'):
    """Read identity fields only; never match names, comment text, scores or labels."""
    if isinstance(value, dict):
        found=set()
        if str(value.get('post_id','')) in wanted: found.add(str(value['post_id']))
        for field in ('post_url','url'):
            url=post_url(value.get(field)) if isinstance(value.get(field),str) else ''
            if url and url_post_id(url) in wanted: found.add(url_post_id(url))
        for pid in sorted(found): yield pid,pointer
        for key,child in value.items():
            if isinstance(child,(dict,list)):yield from references(child,wanted,pointer+'/'+str(key))
    elif isinstance(value,list):
        for i,child in enumerate(value):yield from references(child,wanted,pointer+'/'+str(i))


def history_references(master, wanted):
    """Use the sealed inventory, not browser profiles or arbitrary filesystem searches."""
    master=Path(master);verify(master)
    ledger=load(master/'exposure_ledger.json');pools=set(ledger.get('previous_selection_pool_sources',[]))
    findings=defaultdict(list);blocked=[];scanned=0
    for entry in load(master/'inventory.json'):
        relative=entry['path'];container,mark,member=relative.partition('!')
        suffix=Path(member if mark else relative).suffix.lower()
        if suffix not in {'.csv','.json','.jsonl'}:continue
        # These inputs are task-preparation pools, not claims every row was read.
        is_task_pool=(relative.startswith('data/tasks/') and '/coordinator/input' in relative and suffix=='.csv')
        selection=(relative in pools or is_task_pool or relative.startswith('outputs/negative_annotation_200_20261110/'))
        kind='prior_selection_or_annotation_pool' if selection else (
            'crawl_observation_or_export' if entry['role'] in {'raw_journal','export','archive_export'} else 'metadata_reference_only')
        try:
            path=(ROOT/container).resolve()
            if mark:
                with zipfile.ZipFile(path) as z:payload=z.read(member)
            else:payload=path.read_bytes()
            if digest(payload)!=entry['sha256']:raise ValueError('Sealed evidence checksum changed')
            if suffix=='.csv':values,_=csv_rows(payload)
            elif suffix=='.jsonl':values=[json.loads(s) for s in payload.decode('utf-8-sig').splitlines() if s.strip()]
            else:values=json.loads(payload.decode('utf-8-sig'))
            located=defaultdict(list)
            for pid,pointer in references(values,wanted):located[pid].append(pointer)
            for pid,pointers in located.items():
                findings[pid].append(dict(source_file=relative,sha256=entry['sha256'],kind=kind,
                    occurrences=len(pointers),example_metadata_pointers=pointers[:5]))
            scanned+=1
        except (OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:
            blocked.append(dict(source_file=relative,error=type(exc).__name__))
    return findings,blocked,scanned


def audit(master, availability, output):
    master=Path(master);manifest=verify(master)
    availability=Path(availability);wanted=set(load(availability)['source_candidates_requiring_exposure_audit'])
    findings,blocked,scanned=history_references(master,wanted)
    ledger=load(master/'exposure_ledger.json');known=set(ledger.get('known_exposed_post_ids',[]))
    master_rows=read_jsonl(master/'master.jsonl');by_post=defaultdict(list)
    for row in master_rows:
        if row['post_id'] in wanted:by_post[row['post_id']].append(row)
    posts=[]
    for pid in sorted(wanted):
        items=by_post[pid];evidence=findings.get(pid,[])
        selection=[e for e in evidence if e['kind']=='prior_selection_or_annotation_pool']
        # Never synthesize a positive unused attestation from negative search results.
        status='EXCLUDE_PRIOR_SELECTION_HISTORY' if selection or pid in known else 'UNRESOLVED_NO_AFFIRMATIVE_UNUSED_EVIDENCE'
        posts.append(dict(post_id=pid,status=status,confirmed_unused=False,test_eligible=False,
            movie_ids=sorted({r['movie_id'] for r in items}),post_urls=sorted({r['post_url'] for r in items}),
            master_records=len(items),selection_reference_files=len(selection),evidence=evidence,
            rationale='Prior task/pool metadata is conservative exclusion evidence; it does not establish which individual comments were read.'
                      if selection else 'Collection/absence from development is not proof unused for guideline or model selection.'))
    with staged(output) as work:
        save(work/'post_audit.json',posts)
        write_csv(work/'post_audit.csv',posts,['post_id','status','confirmed_unused','test_eligible','movie_ids','post_urls','master_records','selection_reference_files','rationale'])
        save(work/'unreadable_evidence.json',blocked)
        overlay=dict(known_exposed_post_ids=sorted(known|{p['post_id'] for p in posts if p['status']=='EXCLUDE_PRIOR_SELECTION_HISTORY'}),
            attested_unused_posts=[],policy='Unknown remains outside test pool; no unused attestations inferred',
            parent_master_manifest_sha256=sha(master/'manifest.json'))
        save(work/'exposure_overlay.json',overlay)
        return seal(work,dict(status='AUDITED_NO_UNUSED_POST_CONFIRMED',posts=len(posts),
            status_counts=dict(Counter(p['status'] for p in posts)),confirmed_unused=0,
            metadata_files_checked=scanned,unreadable_evidence=len(blocked),
            master_manifest_sha256=sha(master/'manifest.json'),availability_sha256=sha(availability),
            comments_displayed=False,sentiment_used_for_post_selection=False))
