"""Audit sealed Phase G provenance/labels and export local source summaries."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.common import ROOT, csv_rows, load, read_jsonl, save, seal, sha, staged, verify, write_csv


def validate(master, reservation, output):
    master, reservation=Path(master),Path(reservation)
    manifest=verify(master); task=verify(reservation)
    if task['master_manifest_sha256']!=sha(master/'manifest.json'):raise ValueError('Reservation belongs to another master')
    changed=[path for path,value in manifest['input_sha256'].items() if sha(path)!=value]
    if changed:raise ValueError('Source input changed after master snapshot')
    protected=manifest['protected_input_sha256']
    if any(sha(path)!=value for path,value in protected.items()):raise ValueError('Protected research artifact changed')
    rows=read_jsonl(master/'master.jsonl');inventory=load(master/'inventory.json')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Repeated master identity')
    index={r['path']:r for r in inventory}; seen=set()
    for row in rows:
        for observation in row['observations']:
            key=(observation['source_file'],observation['source_row'])
            if key in seen:raise ValueError('Lost or multiply attributed provenance observation')
            seen.add(key)
            if observation['input_sha256']!=index[observation['source_file']]['sha256']:
                raise ValueError('Observation source checksum mismatch')
            if observation['text_raw'] not in row['text_variants']:raise ValueError('Raw text variant lost')
    expected=sum(r['rows'] or 0 for r in inventory if r['role'] in {'raw_journal','export','archive_export','legacy_unverified'}
                 and r.get('text_column') and r['status']=='indexed')
    if len(seen)!=expected or len(seen)!=manifest['observations']:raise ValueError('Source row coverage mismatch')
    cfg=load(master/'config.json');source=ROOT/cfg['reviewed_root']
    original,_=csv_rows((source/'annotations.csv').read_bytes())
    original_by_id={r['id']:r for r in original}
    preserved=[d for r in rows for d in r['human_decisions']]
    if len(preserved)!=len(original) or {d['id'] for d in preserved}!=set(original_by_id):raise ValueError('Human decision coverage changed')
    if any(d!=original_by_id[d['id']] for d in preserved):raise ValueError('Human decision/text/history altered')
    history=load(master/'human_review_history.json')
    if history!=load(source/'review_history.json'):raise ValueError('Human review history changed')
    old_groups=defaultdict(set)
    for row in rows:
        for old in row['development_groups']:old_groups[old].add(row['group_id'])
    if any(len(values)!=1 for values in old_groups.values()):raise ValueError('An original development group was split')
    if task['status']=='PARTIAL':
        if task['selected'] or (reservation/'reservation.json').exists():raise ValueError('Partial run must not claim a reserved test')
    else:
        reserved=load(reservation/'reservation.json')
        dev_groups={r['group_id'] for r in rows if r['development']}
        if dev_groups & set(reserved['groups']):raise ValueError('Development/test connected leakage')
    posts=defaultdict(list)
    for row in rows:
        if row['post_id']:posts[(row['source_platform'],row['post_id'])].append(row)
    summaries=[]
    for (platform,post),items in sorted(posts.items()):
        summaries.append(dict(source_platform=platform,post_id=post,
            post_urls=sorted({r['post_url'] for r in items if r['post_url']}),movie_ids=sorted({r['movie_id'] for r in items}),
            master_records=len(items),human_decisions=sum(len(r['human_decisions']) for r in items),
            connected_groups=sorted({r['group_id'] for r in items}),source_datasets=sorted({o['source_dataset'] for r in items for o in r['observations']})))
    roles=Counter(r['role'] for r in inventory)
    with staged(output) as work:
        write_csv(work/'sources_by_post.csv',summaries,['source_platform','post_id','post_urls','movie_ids','master_records','human_decisions','connected_groups','source_datasets'])
        source_files=[r for r in inventory if r['role'] in {'raw_journal','export','archive_export','legacy_unverified'}]
        write_csv(work/'source_files.csv',source_files,['path','role','format','rows','movies','posts','metadata','sha256'])
        result=dict(status='PASS',master_records=len(rows),provenance_observations=len(seen),
            original_decisions_preserved=len(preserved),review_history_events_preserved=len(history),
            protected_files_unchanged=len(protected),source_checksums_unchanged=len(manifest['input_sha256']),
            original_development_groups_not_split=len(old_groups),inventory_entries=len(inventory),roles=dict(roles),
            master_manifest_sha256=sha(master/'manifest.json'),reservation_manifest_sha256=sha(reservation/'manifest.json'),
            phase_g_status='PARTIAL' if task['status']=='PARTIAL' else task['status'],independent_test_rows=task['selected'])
        save(work/'validation.json',result);seal(work,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',type=Path,default=Path('outputs/phase_g/master'))
    p.add_argument('--reservation',type=Path,default=Path('outputs/phase_g/blind_test'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_g/audit'))
    a=p.parse_args();r=validate(a.master,a.reservation,a.output)
    print({k:r[k] for k in ('status','master_records','provenance_observations','original_decisions_preserved','protected_files_unchanged','phase_g_status')})


if __name__=='__main__':main()
