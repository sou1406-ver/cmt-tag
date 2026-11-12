"""Read/import normalization decisions without approving a corpus or updating annotation."""
import json
from .common import load,verify,sha,staged,write_csv,seal,read_sheet,validate_review_ids,literal_text


def validate(path,coordinator,complete=False):
    verify(coordinator.parent);expected={r['record_id']:r for r in load(coordinator)}
    fields,rows,_=read_sheet(path,'Review');evidence_fields,evidence,_=read_sheet(path,'Raw I3 Normalized')
    if fields!=['id','text_normalized','change_categories','human_decision','human_note']:raise ValueError('Wrong normalization review columns')
    for values in (rows,evidence):
        validate_review_ids(values,expected,150,'Wrong 150 normalization IDs')
    literal=literal_text
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


def validate_cleaning(path,coordinator,complete=False):
    """Five-column v3.2 review; old blank=accept convention never applies."""
    manifest=verify(coordinator.parent);contract=load(coordinator)
    if (contract.get('kind')!='cleaning_v3_2' or manifest.get('preprocessing_version')!='plain_text_v3_2' or
        contract.get('candidate_content_sha256')!=sha(coordinator.parent/'candidate_corpus.local.jsonl')):raise ValueError('Wrong cleaning candidate/version checksum')
    expected={r['id']:r for r in contract['rows']};fields,rows,_=read_sheet(path,'Review')
    if fields!=['id','text_truoc','text_sau','decision','note']:raise ValueError('Wrong v3.2 review columns')
    if not 0<len(expected)<=100:raise ValueError('Wrong cleaning review size')
    validate_review_ids(rows,expected,len(expected),'Wrong cleaning review IDs')
    for r in rows:
        e=expected[r['id']]
        if any(literal_text(r[k])!=e[k] for k in ('text_truoc','text_sau')):raise ValueError('Cleaning review text changed')
        if r['decision'] not in ('','ACCEPT','REJECT'):raise ValueError('Invalid v3.2 decision')
        if complete and not r['decision']:raise ValueError('Incomplete v3.2 review; blank is pending')
    return rows


def import_cleaning(path,coordinator,output):
    rows=validate_cleaning(path,coordinator,complete=True)
    with staged(output) as out:
        write_csv(out/'human_normalization_decisions.local.csv',rows,['id','text_truoc','text_sau','decision','note'])
        return seal(out,dict(status='HUMAN_V3_2_REVIEW_IMPORTED_NOT_CORPUS_APPROVAL',rows=len(rows),input_sha256=sha(path),
            coordinator_sha256=sha(coordinator),normalization_version='plain_text_v3_2',annotation_pointer_updated=False,canonical_approved=False))
