"""Verify a real workbook and seal a private human train-annotation task."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.finalize_blind_workbooks import check_workbook
from src.dataset.common import load,save,seal,sha,staged,verify


def finalize(audit,workbook,output):
    audit,workbook=Path(audit),Path(workbook);manifest=verify(audit)
    if manifest['status']!='ANNOTATION_POOL_PREPARED_PENDING_WORKBOOK':raise ValueError('No complete candidate pool')
    rows=load(audit/'workbook_input.json')
    if not 200<=len(rows)<=300:raise ValueError('Require 200–300 actual candidates')
    check_workbook(workbook,rows)
    selection=load(audit/'selection_manifest.json')
    if selection['gold_created'] or selection['legacy_labels_used_for_selection']:raise ValueError('Legacy labels must not guide task')
    with staged(output) as work:
        shutil.copyfile(workbook,work/'legacy_train_candidates.xlsx')
        coordinator=work/'coordinator';coordinator.mkdir()
        for name in ('coordinator_mapping.json','selection_manifest.json','legacy_quality_report.json','config.json'):
            shutil.copyfile(audit/name,coordinator/name)
        save(coordinator/'task.json',dict(purpose='human_train_annotation_only_not_independent_test',
            rows=rows,guideline_version=selection['guideline_version'],guideline_sha256=selection['guideline_sha256'],
            input_source_sha256=selection['source_sha256'],gold_created=False))
        return seal(work,dict(status='READY_FOR_HUMAN_TRAIN_ANNOTATION',rows=len(rows),gold_created=False,
            parent_audit_manifest_sha256=sha(audit/'manifest.json'),workbook_source_sha256=sha(workbook),
            mutable_annotation_file='legacy_train_candidates.xlsx',
            training_permission_verified=False,independent_test=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','workbook','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=finalize(a.audit,a.workbook,a.output);print({'status':r['status'],'rows':r['rows']})


if __name__=='__main__':main()
