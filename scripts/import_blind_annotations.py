"""Future explicit blind-label import. Never creates gold or changes source files."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.normalize_annotations import read_input
from src.dataset.blind import BLIND_FIELDS
from src.dataset.common import csv_rows, load, save, seal, sha, staged, verify, write_csv
from src.data.schema import REVIEW_REASONS


def import_labels(reservation_root, annotation_file, output, annotator, worksheet=None, role='a'):
    root = Path(reservation_root); manifest = verify(root)
    if manifest['status'] not in {'RESERVED_PENDING_WORKBOOKS','BLIND_READY'}:
        raise ValueError('No independent test reserved')
    if not annotator.strip(): raise ValueError('Annotator identity required; stored coordinator-side only')
    fields, rows, input_sha = read_input(Path(annotation_file), sheet_name=worksheet)
    if list(fields) != BLIND_FIELDS: raise ValueError('Unexpected annotation fields or metadata')
    if role not in {'a','b'}: raise ValueError('Annotator role must be a or b')
    expected, _ = csv_rows((root/('test_annotator_a.csv' if role=='a' else 'test_annotator_b_50.csv')).read_bytes())
    lookup = {r['id']: r for r in expected}
    if len({r['id'] for r in rows}) != len(rows) or set(lookup) != {r['id'] for r in rows}:
        raise ValueError('Annotator must decide every assigned ID exactly once')
    resolved = []
    for original in rows:
        row = dict(original)
        if row['text_raw'] != lookup[row['id']]['text_raw']: raise ValueError('Blind task text modified')
        for key in ('status','label','review_reason'): row[key] = row[key].strip().upper()
        # Support the familiar single decision in label while separating states explicitly.
        if row['label'] in {'REVIEW','EXCLUDE'} and row['status'] in {'', row['label']}:
            row['status'], row['label'] = row['label'], ''
        if row['label'] in {'POS','NEG','NEU'} and not row['status']: row['status'] = 'LABELED'
        if row['status'] == 'LABELED':
            if row['label'] not in {'POS','NEG','NEU'} or row['review_reason']: raise ValueError('Invalid sentiment decision')
        elif row['status'] == 'REVIEW':
            if row['label'] or row['review_reason'] not in REVIEW_REASONS: raise ValueError('REVIEW needs an explicit reason code')
        elif row['status'] == 'EXCLUDE':
            if row['label'] or not row['reason'].strip(): raise ValueError('EXCLUDE needs a written reason')
        else: raise ValueError('Missing or unknown human decision')
        row['original_decision'] = original; resolved.append(row)
    with staged(output) as work:
        write_csv(work/'decisions.csv', resolved, BLIND_FIELDS)
        save(work/'history.json', [dict(id=r['id'], before=r['original_decision'], after={k:r[k] for k in BLIND_FIELDS}) for r in resolved])
        save(work/'receipt.json', dict(annotator=annotator, role=role, evidence_mode='blind', input_sha256=input_sha,
             reservation_manifest_sha256=sha(root/'manifest.json'), guideline_sha256=manifest['guideline_sha256'],
             gold_created=False, note='Single annotator decisions; REVIEW excluded from final evaluation pending explicit resolution'))
        if sha(annotation_file) != input_sha: raise ValueError('Workbook changed during import')
        return seal(work, dict(status='BLIND_LABELS_IMPORTED_NOT_AUTOMATIC_GOLD', rows=len(rows),
                sentiment=sum(r['status']=='LABELED' for r in resolved), review=sum(r['status']=='REVIEW' for r in resolved),
                excluded=sum(r['status']=='EXCLUDE' for r in resolved), gold_created=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reservation', type=Path, required=True); p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--annotator', required=True)
    p.add_argument('--sheet', default=None)
    p.add_argument('--role',choices=['a','b'],default='a')
    a=p.parse_args(); result=import_labels(a.reservation,a.input,a.output,a.annotator,a.sheet,a.role)
    print(json.dumps({k:result[k] for k in ('status','rows','sentiment','review','excluded')}))


if __name__=='__main__':main()
