"""Read-only quality workbook validation/import; immutable text joined by ID."""
import json
from .common import load,sha,save,write_csv,staged,seal,read_sheet,NS,validate_review_ids,literal_text

def validate(path,input_json,require_complete=False):
    expected={r['record_id']:r for r in load(input_json)}
    headers,rows,tree=read_sheet(path,'Review');_,raw_rows,_=read_sheet(path,'Raw & Changes')
    if headers!=['id','text_annotation','quality_status_proposed','quality_reasons','human_quality_decision','human_note']:raise ValueError('Wrong review schema')
    for data in (rows,raw_rows):
        validate_review_ids(data,expected,200,'Workbook IDs differ')
    for r in rows:
        e=expected[r['id']]
        text=literal_text(r['text_annotation'])
        if text!=e['text_annotation'] or r['quality_status_proposed']!=e['quality_status'] or r['quality_reasons']!='; '.join(e['quality_reason_code']):raise ValueError('Source text/proposals edited')
        if r['human_quality_decision'] not in ('','KEEP','REVIEW','EXCLUDE'):raise ValueError('Invalid human decision')
        if require_complete and not r['human_quality_decision']:raise ValueError('Incomplete human quality review')
    for r in raw_rows:
        e=expected[r['id']]
        for key in ('text_raw','text_clean'):
            val=literal_text(r[key])
            if val!=e[key]:raise ValueError('Raw/clean sheet text edited or truncated')
        if json.loads(r['transform_events'])!=e['transform_events']:raise ValueError('Transform evidence changed')
    if tree.find('s:sheetViews/s:sheetView/s:pane',NS) is None or tree.find('s:dataValidations',NS) is None:raise ValueError('Missing freeze/dropdown')
    return rows


def import_review(path,input_json,output):
    rows=validate(path,input_json,require_complete=True)
    with staged(output) as work:
        write_csv(work/'human_quality_decisions.local.csv',rows,['id','human_quality_decision','human_note'])
        seal(work,dict(status='HUMAN_QUALITY_REVIEW_IMPORTED',rows=len(rows),input_sha256=sha(path),coordinator_sha256=sha(input_json),sentiment_labels_changed=False,pilot_release_approved=False))
    return len(rows)
