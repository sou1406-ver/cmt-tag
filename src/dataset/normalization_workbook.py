"""Read/import normalization decisions without approving a corpus or updating annotation."""
import json
from .common import load,verify,sha,staged,write_csv,seal
from .quality_workbook import read_sheet


def validate(path,coordinator,complete=False):
    verify(coordinator.parent);expected={r['record_id']:r for r in load(coordinator)}
    fields,rows,_=read_sheet(path,'Review');evidence_fields,evidence,_=read_sheet(path,'Raw I3 Normalized')
    if fields!=['id','text_normalized','change_categories','human_decision','human_note']:raise ValueError('Wrong normalization review columns')
    for values in (rows,evidence):
        if len(values)!=150 or len({r['id'] for r in values})!=150 or {r['id'] for r in values}!=set(expected):raise ValueError('Wrong 150 normalization IDs')
    literal=lambda s:s[1:] if s.startswith("'=") else s
    for row in rows:
        e=expected[row['id']];category='; '.join(e['change_categories']) or ('PROTECTION_OR_INHERITED_FORMAT' if e['changed_vs_i3'] else 'UNCHANGED_CONTROL')
        if literal(row['text_normalized'])!=e['text_normalized'] or row['change_categories']!=category:raise ValueError('Normalized text/category changed')
        if row['human_decision'] not in ('','ACCEPT','REJECT','UNSURE'):raise ValueError('Invalid human normalization decision')
        if complete and not row['human_decision']:raise ValueError('Incomplete human normalization review')
    for row in evidence:
        e=expected[row['id']]
        if any(literal(row[k])!=e[k] for k in ('text_raw','text_clean_i3','text_normalized')):raise ValueError('Comparison text changed/truncated')
        events=json.loads(''.join(literal(row[k]) for k in evidence_fields if k.startswith('transform_events_')))
        if events!=dict(events=e['normalization_events'],flags=e['normalization_flags']):raise ValueError('Transform evidence changed')
    return rows


def import_review(path,coordinator,output):
    rows=validate(path,coordinator,complete=True)
    with staged(output) as out:
        write_csv(out/'human_normalization_decisions.local.csv',rows,['id','human_decision','human_note'])
        return seal(out,dict(status='HUMAN_NORMALIZATION_REVIEW_IMPORTED_NOT_CORPUS_APPROVAL',rows=150,input_sha256=sha(path),
            coordinator_sha256=sha(coordinator),normalization_version='plain_text_v3_1',annotation_pointer_updated=False))
