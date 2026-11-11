"""Read-only format validation and append-only import; never changes sentiment."""
import json
from .quality_workbook import read_sheet
from .common import load,staged,seal,write_csv,sha


def validate(path,coordinator,complete=False):
    expected={r['record_id']:r for r in load(coordinator)}
    fields,rows,tree=read_sheet(path,'Validation');rawfields,rawrows,_=read_sheet(path,'Raw I2 I3')
    if fields!=['id','text_clean_i3','change_summary','format_decision','human_note']:raise ValueError('Invalid format review columns')
    for items in (rows,rawrows):
        if len(items)!=200 or len({r['id'] for r in items})!=200 or {r['id'] for r in items}!=set(expected):raise ValueError('Validation IDs changed')
    def literal(s):return s[1:] if s.startswith("'=") else s
    for r in rows:
        e=expected[r['id']]
        if literal(r['text_clean_i3'])!=e['text_clean_i3']:raise ValueError('Clean text changed/truncated')
        if r['format_decision'] not in ('','ACCEPT','REJECT','UNSURE'):raise ValueError('Invalid format decision')
        if complete and not r['format_decision']:raise ValueError('Incomplete format review')
    for r in rawrows:
        e=expected[r['id']]
        if any(literal(r[k])!=e[k] for k in ('text_raw','text_clean_i2','text_clean_i3')):raise ValueError('Comparison text changed')
        evidence=json.loads(''.join(literal(r[k]) for k in rawfields if k.startswith('transformation_evidence_')))
        if evidence!={k:e[k] for k in ('transform_events','format_evidence')}:raise ValueError('Evidence changed')
    return rows


def import_review(path,coordinator,output):
    rows=validate(path,coordinator,complete=True)
    with staged(output) as work:
        write_csv(work/'human_format_decisions.local.csv',rows,['id','format_decision','human_note'])
        seal(work,dict(status='HUMAN_FORMAT_REVIEW_IMPORTED',rows=200,input_sha256=sha(path),coordinator_sha256=sha(coordinator),sentiment_changed=False,pilot_ready=False))
    return len(rows)
