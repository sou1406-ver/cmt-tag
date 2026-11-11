"""Checksum-bound domain/spam workbooks, immutable human ledger, no auto approval."""
from collections import Counter
from .common import ROOT,load,sha,digest,verify,staged,save,seal,write_csv
from .quality_workbook import read_sheet
from .quality_readiness import DOMAINS,SPAM,quality_metrics

FIELDS=['id','text_view','human_domain_decision','human_spam_decision','human_note']
EVIDENCE=['id','text_raw','text_previous','source_view','text_sha256']


def validate(path,coordinator,complete=False):
    verify(coordinator.parent);contract=load(coordinator);expected={r['record_id']:r for r in contract['rows']}
    cfg=load(coordinator.parent/'config.json');source=ROOT/cfg['source'];verify(source)
    if contract['source_manifest_sha256']!=sha(source/'manifest.json'):raise ValueError('Source checksum changed')
    if contract['kind']=='holdout':
        reserved=load(ROOT/cfg['holdout_reservation'])['ids']
        if len(expected)!=40 or set(expected)!=set(reserved):raise ValueError('Original 40 holdout IDs required')
    fields,rows,_=read_sheet(path,'Review');efields,evidence,_=read_sheet(path,'Source')
    if fields!=FIELDS or efields!=EVIDENCE:raise ValueError('Wrong domain/spam workbook schema')
    for values in (rows,evidence):
        if len(values)!=len(expected) or len({r['id'] for r in values})!=len(expected) or {r['id'] for r in values}!=set(expected):raise ValueError('Wrong/repeated review IDs')
    literal=lambda s:s[1:] if s.startswith("'=") else s
    for row in rows:
        e=expected[row['id']]
        if literal(row['text_view'])!=e['text_view'] or digest(e['text_view'])!=e['text_sha256']:raise ValueError('Review text/checksum changed')
        if row['human_domain_decision'] not in DOMAINS|{''} or row['human_spam_decision'] not in SPAM|{''}:raise ValueError('Invalid domain/spam decision; sentiment not allowed')
        if complete and (not row['human_domain_decision'] or not row['human_spam_decision']):raise ValueError('Incomplete domain/spam review')
    for row in evidence:
        if any(literal(row[k])!=expected[row['id']][k] for k in EVIDENCE[1:]):raise ValueError('Source/evidence changed')
    return rows,contract


def import_review(path,coordinator,output):
    rows,contract=validate(path,coordinator,True);expected={r['record_id']:r for r in contract['rows']}
    enriched=[dict(expected[r['id']],**r) for r in rows]
    # Held-out rule evaluation requires the rule/config frozen before reviewing labels.
    metrics=quality_metrics(enriched) if contract['kind']=='development' else None
    with staged(output) as out:
        write_csv(out/'human_quality_decisions.local.csv',enriched,['id','human_domain_decision','human_spam_decision','human_note','text_sha256'])
        save(out/'metrics.json',dict(status='AVAILABLE_SAMPLE_DIAGNOSTICS' if metrics else 'HOLDOUT_LABELS_IMPORTED_NOT_USED_FOR_RULE_TUNING',metrics=metrics))
        return seal(out,dict(status='HUMAN_QUALITY_REVIEW_IMPORTED',kind=contract['kind'],rows=len(rows),workbook_sha256=sha(path),coordinator_sha256=sha(coordinator),
            source_manifest_sha256=contract['source_manifest_sha256'],normalization_version=contract['normalization_version'],annotation_pointer_updated=False,
            domain_counts=dict(Counter(r['human_domain_decision'] for r in rows)),spam_counts=dict(Counter(r['human_spam_decision'] for r in rows))))
