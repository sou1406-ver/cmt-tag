"""Import explicit human review decisions; never infer a replacement label."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.normalize_annotations import read_input
from scripts.prepare_development import dependence, grouped_records, load, read_csv, save, sha, summarize, write_csv
from src.annotation.guidelines import GUIDELINE, GUIDELINE_VERSION, validate_guideline
from src.data.schema import LABELS, validate_decision

DECISION_FIELDS = ('status','label','review_reason','reason')
EDITABLE = frozenset(('decision','label','review_reason','reason'))
REVIEW_METADATA = ('review_disposition','review_event_id','review_annotator_id','reviewed_at',
                   'review_guideline_version','review_guideline_sha256')


def verify_files(directory, manifest):
    for name, checksum in manifest['output_sha256'].items():
        if Path(name).name != name or sha(Path(directory)/name) != checksum:
            raise ValueError('Prepared data checksum mismatch: '+name)
    if not {'annotations.csv','review_decisions.csv','statistics.json'}.issubset(manifest['output_sha256']):
        raise ValueError('Incomplete prepared snapshot checksums')


def review_input(path, parent_rows, restore_trailing_spaces=False, normalizations=None):
    path = Path(path)
    expected = {r['id']:r for r in parent_rows}
    def restore(row, sheet):
        original=expected.get(row['id'],{}).get('text_raw')
        observed=row['text_raw']
        if (restore_trailing_spaces and original is not None and observed!=original
                and observed.rstrip(' ')==original.rstrip(' ')):
            if normalizations is not None:
                normalizations.append(dict(sheet=sheet,id=row['id'],field='text_raw',
                    operation='RESTORE_TRAILING_ASCII_SPACES_FROM_PARENT',
                    observed_sha256=hashlib.sha256(observed.encode()).hexdigest(),
                    original_sha256=hashlib.sha256(original.encode()).hexdigest()))
            row['text_raw']=original
    if path.suffix.lower()=='.xlsx':
        _, decisions, checksum = read_input(path, 'Duyet nhan', header_row=5)
        _, snapshot, snapshot_sha = read_input(path, '400 binh luan', last_column=14)
        if snapshot_sha != checksum:
            raise ValueError('Workbook changed while reading')
        if len(snapshot)!=len(expected) or len({r['id'] for r in snapshot})!=len(snapshot) or set(expected)!={r['id'] for r in snapshot}:
            raise ValueError('Workbook source sheet IDs changed')
        for row in snapshot:
            restore(row,'400 binh luan')
            if any(value != expected[row['id']].get(key) for key,value in row.items()):
                raise ValueError('Workbook source sheet edited; use Duyet nhan only: '+row['id'])
        for row in decisions:
            restore(row,'Duyet nhan')
            # The original working workbook omitted this immutable metadata column.
            # Recover it from the locked ID mapping, never from a guessed label or row order.
            if 'source_round' not in row and row['id'] in expected:
                row['source_round']=expected[row['id']]['source_round']
                if normalizations is not None:
                    normalizations.append(dict(sheet='Duyet nhan',id=row['id'],field='source_round',
                        operation='RESTORE_SOURCE_ROUND_BY_LOCKED_ID',value=row['source_round']))
        return decisions, checksum
    _, decisions, checksum = read_input(path)
    for row in decisions:restore(row,'CSV')
    return decisions, checksum


def validate_row(row, require_review_explanation=True):
    if row['status']!='LABELED' and row['label']:
        raise ValueError('REVIEW/EXCLUDE cannot carry a sentiment label')
    if row['status']!='REVIEW' and row['review_reason']:
        raise ValueError('Only REVIEW can carry review_reason')
    if not row['text_raw'].strip():
        raise ValueError('Empty comment text requires review')
    validate_decision(dict(label_source='human',status=row['status'],label=row['label'] or None,
                           review_reason=row['review_reason'] or None,confirmed=False,is_pseudo=False,
                           needs_review=row['status']=='REVIEW'))
    if require_review_explanation and row['status']=='REVIEW' and row['review_reason']=='REV_OTHER' and not row['reason'].strip():
        raise ValueError('REV_OTHER requires an explanation')


def resolve(parent_rows, template, decisions, actor, timestamp, guideline, input_sha, parent_sha,
            allow_missing_change_reason=False):
    """Pure replay by immutable IDs; both import and baseline receipt verification use it."""
    if not actor.strip():
        raise ValueError('Annotator ID required')
    if datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError('Review timestamp must include timezone')
    expected={r['id']:r for r in template}
    if len(expected)!=len(template) or len(decisions)!=len(expected) or len({r['id'] for r in decisions})!=len(decisions) or {r['id'] for r in decisions}!=set(expected):
        raise ValueError('Review must contain exactly the pending IDs once')
    parent={r['id']:r for r in parent_rows}
    if len(parent)!=len(parent_rows) or not set(expected).issubset(parent):
        raise ValueError('Review IDs do not match source data')
    unfinished=[expected[r['id']]['source_workbook_row'] for r in decisions if not r['decision'].strip()]
    if unfinished:
        raise ValueError('Missing human decisions at source workbook rows: '+', '.join(unfinished))
    rows=deepcopy(parent_rows); lookup={r['id']:r for r in rows}
    events=[]; previous_hash=None
    for entry in sorted(decisions,key=lambda r:r['id']):
        rid=entry['id']; ref=expected[rid]; row=lookup[rid]
        if set(entry)!=set(ref) or any(entry[k]!=ref[k] for k in ref if k not in EDITABLE):
            raise ValueError('Non-editable review fields changed: '+rid)
        before={k:row[k] for k in DECISION_FIELDS}
        current=row['label'] if row['status']=='LABELED' else row['status']
        if ref['current_label']!=current or ref['text_raw']!=row['text_raw']:
            raise ValueError('Stale review snapshot: '+rid)
        action=entry['decision'].strip().upper()
        label=entry['label'].strip().upper()
        code=entry['review_reason'].strip().upper()
        reason=entry['reason'].strip()
        if action not in ('KEEP','CHANGE','DEFER'):
            raise ValueError('Unknown review action: '+rid)
        if action=='KEEP':
            if label not in ('',current):
                raise ValueError('KEEP cannot change a label: '+rid)
            if code and row['status']!='REVIEW':
                raise ValueError('Review reason is only valid for REVIEW: '+rid)
            if row['review_reason'] and code not in ('',row['review_reason']):
                raise ValueError('Use CHANGE to replace a review reason: '+rid)
            if code:row['review_reason']=code
            if reason:row['reason']=reason
        elif action=='CHANGE':
            if not reason and not allow_missing_change_reason:
                raise ValueError('CHANGE requires a human explanation: '+rid)
            if label not in LABELS | {'REVIEW','EXCLUDE'}:
                raise ValueError('CHANGE requires POS/NEG/NEU/REVIEW/EXCLUDE: '+rid)
            row.update(status='LABELED' if label in LABELS else label,
                       label=label if label in LABELS else '',review_reason=code,reason=reason)
        else:
            if label or code or not reason:
                raise ValueError('DEFER requires an explanation and blank label/review_reason: '+rid)
        if action!='DEFER':
            # Never clear a technical issue without validating the actual resulting decision.
            allowed_issues={'MISSING_REVIEW_REASON'}
            if set(filter(None,row['validation_issues'].split(';')))-allowed_issues:
                raise ValueError('Unresolved source data issue: '+rid)
            validate_row(row)
            row['validation_issues']=''
        row['audit_pending']=''
        row.update(review_disposition=action,review_annotator_id=actor.strip(),reviewed_at=timestamp,
                   review_guideline_version=guideline['version'],review_guideline_sha256=guideline['sha256'])
        event=dict(id=rid,action=action,annotator_id=actor.strip(),decided_at=timestamp,
                   evidence_mode='assisted',guideline=guideline,parent_manifest_sha256=parent_sha,
                   decision_input_sha256=input_sha,text_sha256=hashlib.sha256(row['text_raw'].encode()).hexdigest(),
                   before=before,after={k:row[k] for k in DECISION_FIELDS},human_note=reason,
                   previous_event_sha256=previous_hash)
        if action=='CHANGE' and not reason:
            event.update(reason_provided=False,
                         reason_omission_authorization='Explicit user authorization; annotator did not provide a reason')
        previous_hash=hashlib.sha256(json.dumps(event,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        event['event_sha256']=previous_hash
        row['review_event_id']=previous_hash
        events.append(event)
    for row in rows:
        for key in REVIEW_METADATA:row.setdefault(key,'')
        if row.get('review_disposition')!='DEFER':
            validate_row(row,require_review_explanation=bool(row.get('review_disposition')))
        row['ready_for_development']=str(row['status']=='LABELED' and not row['validation_issues']
                                         and not row['audit_pending'] and row['review_disposition']!='DEFER')
    if any(r['audit_pending'] for r in rows):
        raise ValueError('Some pending review rows were not covered')
    return rows,events


def verify_reviewed_dataset(directory, rows, manifest):
    """A flag alone cannot unlock training: replay the saved human evidence."""
    directory=Path(directory)
    receipt=manifest.get('human_review')
    if not receipt:
        raise ValueError('Human review receipt required before fitting')
    parent_dir=directory/'provenance'/'parent'
    parent_manifest=load(parent_dir/'manifest.json')
    if sha(parent_dir/'manifest.json')!=receipt['parent_manifest_sha256']:
        raise ValueError('Review parent checksum mismatch')
    verify_files(parent_dir,parent_manifest)
    parent_rows=read_csv(parent_dir/'annotations.csv')
    template=read_csv(parent_dir/'review_decisions.csv')
    if set(parent_manifest['pending_review_ids'])!={r['id'] for r in template}:
        raise ValueError('Parent pending review IDs differ')
    input_path=directory/'provenance'/receipt['input_name']
    if Path(receipt['input_name']).name!=receipt['input_name'] or sha(input_path)!=receipt['input_sha256']:
        raise ValueError('Review input checksum mismatch')
    normalizations=[]
    decisions,input_sha=review_input(input_path,parent_rows,receipt.get('restore_trailing_spaces',False),normalizations)
    if normalizations!=receipt.get('input_normalizations',[]):
        raise ValueError('Review whitespace restoration log mismatch')
    validate_guideline(receipt['guideline']['version'],receipt['guideline']['sha256'])
    replay,events=resolve(parent_rows,template,decisions,receipt['annotator_id'],receipt['decided_at'],
                          receipt['guideline'],input_sha,receipt['parent_manifest_sha256'],
                          receipt.get('allow_missing_change_reason',False))
    if replay!=rows or load(directory/'review_history.json')!=events:
        raise ValueError('Reviewed data/history does not match human decisions')
    deferred=sorted(r['id'] for r in rows if r['review_disposition']=='DEFER')
    if manifest.get('deferred_review_ids')!=deferred or receipt['event_count']!=len(events):
        raise ValueError('Review receipt count/disposition mismatch')
    return receipt


def import_review(source, input_path, output, annotator, restore_trailing_spaces=False,
                  allow_missing_change_reason=False):
    source=Path(source).resolve();input_path=Path(input_path).resolve();output=Path(output).resolve()
    manifest=load(source/'manifest.json');verify_files(source,manifest)
    if manifest['purpose']!='exploratory_development_only' or manifest['independent_test']:
        raise ValueError('Expected exposed development data, not an independent gold release')
    if not manifest['pending_review_ids']:
        raise ValueError('No pending review task in source')
    parent_rows=read_csv(source/'annotations.csv');template=read_csv(source/'review_decisions.csv')
    if set(manifest['pending_review_ids'])!={r['id'] for r in template}:
        raise ValueError('Pending review task mismatch')
    payload=input_path.read_bytes()
    normalizations=[]
    decisions,input_sha=review_input(input_path,parent_rows,restore_trailing_spaces,normalizations)
    if hashlib.sha256(payload).hexdigest()!=input_sha:
        raise ValueError('Review input changed while reading')
    parent_sha=sha(source/'manifest.json')
    guideline=dict(version=GUIDELINE_VERSION,sha256=sha(GUIDELINE))
    validate_guideline(guideline['version'],guideline['sha256'])
    if manifest['active_guideline']!=guideline:
        raise ValueError('Review guideline differs from prepared task; explicit migration required')
    if output.exists():
        existing=load(output/'manifest.json');receipt=existing.get('human_review',{})
        if (receipt.get('input_sha256'),receipt.get('parent_manifest_sha256'),receipt.get('annotator_id'),receipt.get('guideline'),
            receipt.get('restore_trailing_spaces',False),receipt.get('allow_missing_change_reason',False))!=(
                input_sha,parent_sha,annotator.strip(),guideline,restore_trailing_spaces,allow_missing_change_reason):
            raise FileExistsError('Reviewed output exists with different decisions; preserve it and choose another output')
        verify_files(output,existing)
        verify_reviewed_dataset(output,read_csv(output/'annotations.csv'),existing)
        return existing
    timestamp=datetime.now(timezone.utc).isoformat()
    rows,events=resolve(parent_rows,template,decisions,annotator,timestamp,guideline,input_sha,parent_sha,
                        allow_missing_change_reason)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.review-',dir=output.parent) as temporary:
        staged=Path(temporary)/'reviewed';staged.mkdir()
        provenance=staged/'provenance';parent_dir=provenance/'parent';parent_dir.mkdir(parents=True)
        for name in ('manifest.json',*manifest['output_sha256']):shutil.copyfile(source/name,parent_dir/name)
        input_name='review_input'+input_path.suffix.lower()
        (provenance/input_name).write_bytes(payload)
        write_csv(staged/'annotations.csv',rows,list(rows[0]))
        write_csv(staged/'review_decisions.csv',decisions,list(template[0]))
        save(staged/'review_history.json',events)
        stats={k:summarize(rows,k) for k in ('source_round','movie_id','post_id','selection_cohort','source_kind')}
        stats['movie_label_dependence']=dependence(rows)
        for key in ('source_round','selection_cohort'):
            stats['dependence_by_'+('round' if key=='source_round' else 'cohort')]={
                value:dependence([r for r in rows if r[key]==value]) for value in sorted({r[key] for r in rows})}
        save(staged/'statistics.json',stats)
        for name,subset in [('sentiment_candidates',[r for r in rows if r['ready_for_development']=='True']),
                            ('review',[r for r in rows if r['status']=='REVIEW']),
                            ('exclude',[r for r in rows if r['status']=='EXCLUDE']),
                            ('deferred',[r for r in rows if r['review_disposition']=='DEFER'])]:
            write_csv(provenance/(name+'.csv'),subset,list(rows[0]))
        _,pairs,groups=grouped_records(rows)
        if any(r['group_id']!=groups[r['id']] for r in rows):
            raise ValueError('Post/duplicate groups changed during review')
        result=deepcopy(manifest)
        result.update(pending_review_ids=[],all_human_review_resolved=True,models_trained=False,
                      gold_created=False,independent_test=False,
                      deferred_review_ids=sorted(r['id'] for r in rows if r['review_disposition']=='DEFER'),
                      human_review=dict(annotator_id=annotator.strip(),decided_at=timestamp,guideline=guideline,
                                        input_name=input_name,input_sha256=input_sha,parent_manifest_sha256=parent_sha,
                                        event_count=len(events),evidence_mode='assisted',
                                        restore_trailing_spaces=restore_trailing_spaces,
                                        input_normalizations=normalizations,
                                        allow_missing_change_reason=allow_missing_change_reason),
                      current_validation_issues={r['id']:r['validation_issues'] for r in rows if r['validation_issues']},
                      legacy_review_without_explanation_ids=[r['id'] for r in rows if r['status']=='REVIEW'
                          and r['review_reason']=='REV_OTHER' and not r['reason'].strip() and not r['review_disposition']],
                      sentiment_candidates=sum(r['ready_for_development']=='True' for r in rows),
                      output_sha256={p.name:sha(p) for p in staged.iterdir() if p.is_file()})
        save(staged/'manifest.json',result)
        verify_files(staged,result);verify_reviewed_dataset(staged,read_csv(staged/'annotations.csv'),result)
        if sha(input_path)!=input_sha or sha(source/'manifest.json')!=parent_sha:
            raise ValueError('Input changed during import')
        verify_files(source,manifest)
        staged.rename(output)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'outputs/development')
    p.add_argument('--input',type=Path,default=ROOT/'outputs/development/annotations.xlsx')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/development/reviewed')
    p.add_argument('--annotator',required=True)
    p.add_argument('--restore-trailing-spaces',action='store_true',help='Restore only trailing ASCII space differences from source; audit each cell')
    p.add_argument('--allow-missing-change-reason',action='store_true',help='Only with explicit human authorization: preserve missing CHANGE explanations in history')
    args=p.parse_args()
    try:result=import_review(args.source,args.input,args.output,args.annotator,
                             args.restore_trailing_spaces,args.allow_missing_change_reason)
    except (ValueError,OSError,KeyError) as exc:p.exit(2,f'{type(exc).__name__}: {exc}\n')
    print(json.dumps(dict(rows=result['rows'],pending=len(result['pending_review_ids']),
                          deferred=len(result['deferred_review_ids']),sentiment_candidates=result['sentiment_candidates'],
                          independent_test=False,models_trained=False)))


if __name__=='__main__':main()
