"""Normalize manual decision fields without changing the annotation importer."""
import argparse
import csv
import hashlib
import io
import json
import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.schema import LABELS, REVIEW_REASONS, STATES, validate_decision

FIELDS = ('id', 'movie_id', 'text_raw', 'status', 'label', 'review_reason', 'reason')
EDITABLE = frozenset(('status', 'label', 'review_reason', 'reason'))
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_input(path, sheet_name=None, header_row=1, last_column=None, text_field='text_raw'):
    """Read literal cell values only; never evaluate workbook formulas."""
    path = Path(path)
    if type(header_row) is not int or header_row < 1 or (last_column is not None and (type(last_column) is not int or last_column < 1)):
        raise ValueError('Header row and column bound must be positive integers')
    payload = path.read_bytes()
    if path.suffix.lower() == '.csv':
        if header_row != 1 or last_column is not None:
            raise ValueError('CSV uses its first row and all columns')
        reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig'), newline=''))
        fields, rows = reader.fieldnames, list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError('CSV rows must match the header columns')
    elif path.suffix.lower() == '.xlsx':
        with zipfile.ZipFile(io.BytesIO(payload)) as book:
            workbook = ET.fromstring(book.read('xl/workbook.xml'))
            sheets = workbook.findall('s:sheets/s:sheet', NS)
            if not sheets:
                raise ValueError('Workbook has no worksheets')
            sheet = next((s for s in sheets if s.get('name') == sheet_name), None) if sheet_name else sheets[0]
            if sheet is None:
                raise ValueError('Requested worksheet not found')
            rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            relationships = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
            relation = next(r for r in relationships if r.get('Id') == rid)
            if relation.get('TargetMode') == 'External':
                raise ValueError('External worksheets are not supported')
            target = relation.get('Target', '')
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            if not target.startswith('xl/worksheets/'):
                raise ValueError('Invalid worksheet path')
            shared = []
            if 'xl/sharedStrings.xml' in book.namelist():
                shared = [''.join(n.text or '' for n in item.iter('{' + NS['s'] + '}t'))
                          for item in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si', NS)]
            grid = {}
            for cell in ET.fromstring(book.read(target)).findall('.//s:sheetData/s:row/s:c', NS):
                address = cell.get('r')
                if cell.find('s:f', NS) is not None:
                    raise ValueError('Formula cell cannot be used as a manual annotation: ' + address)
                value = cell.findtext('s:v', '', NS)
                if cell.get('t') == 's':
                    value = shared[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(n.text or '' for n in cell.findall('.//s:t', NS))
                letters = ''.join(c for c in address if c.isalpha())
                number = int(''.join(c for c in address if c.isdigit()))
                column = 0
                for letter in letters:
                    column = column * 26 + ord(letter) - ord('A') + 1
                grid.setdefault(number, {})[column] = value
            headers = grid.get(header_row, {})
            columns = sorted(c for c, value in headers.items() if value and (last_column is None or c <= last_column))
            fields = [headers[c] for c in columns]
            rows = [{headers[c]: values.get(c, '') for c in columns}
                    for number, values in sorted(grid.items()) if number > header_row and any(values.get(c, '') for c in columns)]
    else:
        raise ValueError('Input must be CSV or XLSX')
    if text_field not in {'text_raw','text_view'}:
        raise ValueError('Unsupported text field')
    if not fields or len(fields) != len(set(fields)) or not {'id', text_field, 'label'}.issubset(fields):
        raise ValueError('Unique headers id, '+text_field+' and label are required')
    return fields, rows, hashlib.sha256(payload).hexdigest()


def normalize_file(input_path, task_path, output, overrides_path=None,
                   restore_task_whitespace=False, sheet_name=None):
    fields, original, input_sha = read_input(input_path, sheet_name)
    task_bytes = Path(task_path).read_bytes()
    task = json.loads(task_bytes)
    expected = {row['id']: row for row in task['rows']}
    ids = [row['id'] for row in original]
    if not original or len(expected) != len(task['rows']) or len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('Input must retain exactly the task IDs once; rows are joined by ID')
    rows = [{**{field: '' for field in FIELDS}, **row} for row in original]
    fields = list(FIELDS) + [field for field in fields if field not in FIELDS]
    actions, issues = [], []

    def change(row, number, field, value, kind, evidence=None):
        if row[field] != value:
            actions.append(dict(row=number, id=row['id'], field=field, before=row[field],
                                after=value, action=kind, evidence=evidence))
            row[field] = value

    override_document = None
    if overrides_path:
        override_document = json.loads(Path(overrides_path).read_text(encoding='utf-8'))
        lookup = {row['id']: (number, row) for number, row in enumerate(rows, 2)}
        seen = set()
        for override in override_document['rows']:
            rid = override['id']
            if rid in seen or rid not in lookup or not set(override['set']).issubset(EDITABLE):
                raise ValueError('Invalid or duplicate annotation override ID/field')
            seen.add(rid)
            number, row = lookup[rid]
            for field, value in override['set'].items():
                if not isinstance(value, str) or field not in override.get('expected', {}):
                    raise ValueError('Overrides must record the previous field value')
                if row[field] not in (override['expected'][field], value):
                    raise ValueError('Concurrent annotation conflicts with override: ' + rid)
                change(row, number, field, value, 'USER_CONFIRMED_OVERRIDE', override.get('evidence'))

    row_errors = set()
    for number, row in enumerate(rows, 2):
        def error(code):
            issues.append(dict(row=number, id=row['id'], code=code))
            row_errors.add(row['id'])
        reference = expected[row['id']]['text_raw']
        if row['text_raw'] != reference:
            if restore_task_whitespace and row['text_raw'].split() == reference.split():
                change(row, number, 'text_raw', reference, 'RESTORE_TASK_WHITESPACE')
            else:
                error('COMMENT_TEXT_EDITED')
        for field in ('status', 'label', 'review_reason'):
            change(row, number, field, row[field].strip().upper(), 'NORMALIZE_DECISION_TOKEN')
        status, label = row['status'], row['label']
        if label in ('REVIEW', 'EXCLUDE'):
            if status not in ('', label):
                error('STATUS_LABEL_CONFLICT')
            else:
                change(row, number, 'status', label, 'MOVE_STATE_FROM_LABEL')
                change(row, number, 'label', '', 'CLEAR_NON_SENTIMENT_LABEL')
        elif status in LABELS:
            if label and label != status:
                error('STATUS_LABEL_CONFLICT')
            else:
                change(row, number, 'label', status, 'MOVE_LABEL_FROM_STATUS')
                change(row, number, 'status', 'LABELED', 'SET_LABELED_STATUS')
        elif not status and label in LABELS:
            change(row, number, 'status', 'LABELED', 'FILL_LABELED_STATUS')
        status, label = row['status'], row['label']
        if status not in STATES:
            error('MISSING_DECISION' if not status and not label else 'INVALID_STATUS')
        elif status == 'LABELED' and label not in LABELS:
            error('MISSING_SENTIMENT_LABEL' if not label else 'INVALID_SENTIMENT_LABEL')
        elif status != 'LABELED' and label:
            error('NON_SENTIMENT_STATE_HAS_LABEL')
        if row['review_reason'] and row['review_reason'] not in REVIEW_REASONS:
            error('INVALID_REVIEW_REASON')
        elif status == 'REVIEW' and not row['review_reason']:
            error('MISSING_REVIEW_REASON')
        elif status != 'REVIEW' and row['review_reason']:
            error('REVIEW_REASON_ON_OTHER_STATE')
        if row['id'] not in row_errors:
            validate_decision(dict(label_source='human', status=status, label=label or None,
                                   review_reason=row['review_reason'] or None, confirmed=False,
                                   is_pseudo=False, needs_review=status == 'REVIEW'))

    sentiment = [r for r in rows if r['id'] not in row_errors and r['status'] == 'LABELED']
    review = [r for r in rows if r['status'] == 'REVIEW']
    exclude = [r for r in rows if r['status'] == 'EXCLUDE']
    assigned = {r['id'] for group in (sentiment, review, exclude) for r in group}
    pending = [r for r in rows if r['id'] not in assigned]
    assert len(sentiment) + len(review) + len(exclude) + len(pending) == len(rows)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)

    def write_csv(name, values, columns=fields):
        with (output / name).open('x', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(values)

    write_csv('original_input.csv', original, list(original[0]))
    write_csv('normalized.csv', rows)
    write_csv('sentiment_candidates.csv', sentiment)
    write_csv('review.csv', review)
    write_csv('exclude.csv', exclude)
    if pending:
        write_csv('pending.csv', pending)
    report = dict(input_name=Path(input_path).name, input_sha256=input_sha,
                  task_sha256=hashlib.sha256(task_bytes).hexdigest(),
                  input_rows=len(original), normalized_rows=len(rows),
                  sentiment_candidates=len(sentiment), sentiment_label_counts=dict(Counter(r['label'] for r in sentiment)),
                  review_rows=len(review), exclude_rows=len(exclude), pending_rows=len(pending),
                  import_ready=not issues, issues=issues, actions=actions,
                  rows_without_free_text_reason=sum(not r['reason'].strip() for r in rows),
                  user_overrides=override_document,
                  gold_release_created=False, models_trained=False, split_changed=False,
                  note='All source decisions retained. Sentiment candidates are one annotator decisions, not an adjudicated gold release. REVIEW/EXCLUDE remain outside the three-class subset. No sentiment or explanation was inferred from comment text.')
    report['outputs_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.csv')}
    report['input_unchanged'] = hashlib.sha256(Path(input_path).read_bytes()).hexdigest() == input_sha
    with (output / 'normalization_report.json').open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--overrides', type=Path)
    parser.add_argument('--sheet')
    parser.add_argument('--restore-task-whitespace', action='store_true',
                        help='Restore task text only when whitespace-separated tokens are identical; record every change')
    args = parser.parse_args()
    try:
        report = normalize_file(args.input, args.task, args.output, args.overrides,
                                args.restore_task_whitespace, args.sheet)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')
    print(json.dumps({k: report[k] for k in ('input_rows', 'normalized_rows', 'sentiment_candidates',
                                            'sentiment_label_counts', 'review_rows', 'exclude_rows',
                                            'pending_rows', 'import_ready', 'input_unchanged')}, ensure_ascii=True))
    return 0 if report['import_ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
