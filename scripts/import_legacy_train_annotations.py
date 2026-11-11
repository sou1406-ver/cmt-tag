"""Import explicitly completed human decisions; never promote legacy overall to gold."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.normalize_annotations import read_input
from src.dataset.blind import BLIND_FIELDS,assert_allowed
from src.dataset.common import load,save,seal,sha,staged,verify,write_csv
from src.data.schema import REVIEW_REASONS


def import_labels(task,input_path,output,annotator):
    # The working workbook is edited by the annotator. The immutable coordinator
    # contract still verifies every ID/text and every other task checksum.
    task,input_path=Path(task),Path(input_path);manifest=verify(task,mutable_files=('legacy_train_candidates.xlsx',))
    if manifest['status']!='READY_FOR_HUMAN_TRAIN_ANNOTATION' or not annotator.strip():raise ValueError('Valid train task and annotator required')
    contract=load(task/'coordinator/task.json');expected={r['id']:r for r in contract['rows']}
    fields,original,input_sha=read_input(input_path,text_field='text_view')
    if fields!=BLIND_FIELDS or len(original)!=len(expected) or len({r['id'] for r in original})!=len(original) or {r['id'] for r in original}!=set(expected):
        raise ValueError('All assigned IDs and blind fields required exactly once')
    decisions=[]
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
            if d['label'] or not d['reason'].strip():raise ValueError('EXCLUDE needs written reason')
        else:raise ValueError('Missing human decision')
        decisions.append(d)
    mapping={r['id']:r for r in load(task/'coordinator/coordinator_mapping.json')}
    assert_allowed([mapping[r['id']] for r in decisions],'train')
    with staged(output) as work:
        write_csv(work/'decisions.csv',decisions,BLIND_FIELDS)
        save(work/'history.json',[dict(id=d['id'],before=o,after=d) for o,d in zip(original,decisions)])
        save(work/'receipt.json',dict(annotator=annotator,input_sha256=input_sha,task_manifest_sha256=sha(task/'manifest.json'),
             label_source='human_single_annotator',legacy_labels_used=False,gold_created=False,
             guideline_version=contract['guideline_version'],guideline_sha256=contract['guideline_sha256'],
             purpose='train_development_only',source_rights_and_origin_still_require_verification=True))
        if sha(input_path)!=input_sha:raise ValueError('Annotation changed during import')
        return seal(work,dict(status='HUMAN_TRAIN_DECISIONS_IMPORTED',rows=len(decisions),gold_created=False,
            sentiment=sum(r['status']=='LABELED' for r in decisions),review=sum(r['status']=='REVIEW' for r in decisions),
            excluded=sum(r['status']=='EXCLUDE' for r in decisions)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('task','input','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--annotator',required=True);a=p.parse_args()
    r=import_labels(a.task,a.input,a.output,a.annotator);print({k:r[k] for k in ('status','rows','sentiment','review','excluded')})


if __name__=='__main__':main()
