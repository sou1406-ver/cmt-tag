"""Import explicitly completed human decisions; never promote legacy overall to gold."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.normalize_annotations import read_input
from src.dataset.blind import BLIND_FIELDS,assert_allowed
from src.dataset.common import load,save,seal,sha,staged,verify,write_csv
from src.data.schema import REVIEW_REASONS


def import_labels(task,input_path,output,annotator,allow_missing_exclude_reason=False,authorization_note=''):
    if allow_missing_exclude_reason and not authorization_note.strip():
        raise ValueError('Explicit human authorization note required for missing EXCLUDE reasons')
    # The working workbook is edited by the annotator. The immutable coordinator
    # contract still verifies every ID/text and every other task checksum.
    task,input_path=Path(task),Path(input_path);manifest=verify(task,mutable_files=('legacy_train_candidates.xlsx',))
    if manifest['status']!='READY_FOR_HUMAN_TRAIN_ANNOTATION' or not annotator.strip():raise ValueError('Valid train task and annotator required')
    contract=load(task/'coordinator/task.json');expected={r['id']:r for r in contract['rows']}
    fields,original,input_sha=read_input(input_path,text_field='text_view')
    if fields!=BLIND_FIELDS or len(original)!=len(expected) or len({r['id'] for r in original})!=len(original) or {r['id'] for r in original}!=set(expected):
        raise ValueError('All assigned IDs and blind fields required exactly once')
    decisions=[];missing_reason_ids=[]
    for row in original:
        if row['text_view']!=expected[row['id']]['text_view']:raise ValueError('Source view changed')
        d=dict(row)
        for key in ('status','label','review_reason'):d[key]=d[key].strip().upper()
        if d['label'] in {'REVIEW','EXCLUDE'} and d['status'] in {'',d['label']}:d['status'],d['label']=d['label'],''
        if d['label'] in {'POS','NEG','NEU'} and not d['status']:d['status']='LABELED'
        if d['status']=='LABELED':
            if d['label'] not in {'POS','NEG','NEU'} or d['review_reason']:raise ValueError('Invalid sentiment decision')
        elif d['status']=='REVIEW':
            if d['label'] or d['review_reason'] not in REVIEW_REASONS:raise ValueError('REVIEW needs reason code')
        elif d['status']=='EXCLUDE':
            if d['label']:raise ValueError('EXCLUDE is a state, not a sentiment label')
            if not d['reason'].strip():
                if not allow_missing_exclude_reason:raise ValueError('EXCLUDE needs written reason')
                missing_reason_ids.append(d['id'])
        else:raise ValueError('Missing human decision')
        decisions.append(d)
    mapping={r['id']:r for r in load(task/'coordinator/coordinator_mapping.json')}
    assert_allowed([mapping[r['id']] for r in decisions],'train')
    with staged(output) as work:
        write_csv(work/'decisions.csv',decisions,BLIND_FIELDS)
        write_csv(work/'sentiment.csv',[d for d in decisions if d['status']=='LABELED'],BLIND_FIELDS)
        write_csv(work/'excluded.csv',[d for d in decisions if d['status']=='EXCLUDE'],BLIND_FIELDS)
        save(work/'history.json',[dict(id=d['id'],before=o,after=d,
            exclude_reason_missing=d['id'] in missing_reason_ids,
            audit_note='Người gán không cung cấp lý do' if d['id'] in missing_reason_ids else '')
            for o,d in zip(original,decisions)])
        shutil.copyfile(input_path,work/('input_snapshot'+input_path.suffix.lower()))
        save(work/'receipt.json',dict(annotator=annotator,input_sha256=input_sha,task_manifest_sha256=sha(task/'manifest.json'),
             imported_at=datetime.now(timezone.utc).isoformat(),
             allow_missing_exclude_reason=allow_missing_exclude_reason,authorization_note=authorization_note,
             missing_exclude_reason_ids=missing_reason_ids,missing_reasons_not_fabricated=True,
             label_source='human_single_annotator',legacy_labels_used=False,gold_created=False,
             guideline_version=contract['guideline_version'],guideline_sha256=contract['guideline_sha256'],
             purpose='train_development_only',source_rights_and_origin_still_require_verification=True))
        if sha(input_path)!=input_sha or sha(work/('input_snapshot'+input_path.suffix.lower()))!=input_sha:
            raise ValueError('Annotation changed during import')
        return seal(work,dict(status='HUMAN_TRAIN_DECISIONS_IMPORTED',rows=len(decisions),gold_created=False,
            missing_exclude_reason_count=len(missing_reason_ids),
            sentiment=sum(r['status']=='LABELED' for r in decisions),review=sum(r['status']=='REVIEW' for r in decisions),
            excluded=sum(r['status']=='EXCLUDE' for r in decisions)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('task','input','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--annotator',required=True)
    p.add_argument('--allow-missing-exclude-reason',action='store_true',help='Only after explicit human approval; preserve empty reasons and audit missingness')
    p.add_argument('--authorization-note',default='');a=p.parse_args()
    r=import_labels(a.task,a.input,a.output,a.annotator,a.allow_missing_exclude_reason,a.authorization_note)
    print({k:r[k] for k in ('status','rows','sentiment','review','excluded','missing_exclude_reason_count')})


if __name__=='__main__':main()
