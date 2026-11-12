"""Checksum-bound domain/spam workbooks, immutable human ledger, no auto approval."""
from collections import Counter
from .common import ROOT,load,sha,digest,verify,staged,save,seal,write_csv,read_sheet,validate_review_ids,literal_text,read_jsonl,csv_rows
from .quality_readiness import DOMAINS,SPAM,quality_metrics,layers

FIELDS=['id','text_view','human_domain_decision','human_spam_decision','human_note']
EVIDENCE=['id','text_raw','text_previous','source_view','text_sha256']


def validate(path,coordinator,complete=False):
    verify(coordinator.parent);contract=load(coordinator);expected={r['record_id']:r for r in contract['rows']}
    cfg=load(coordinator.parent/'config.json');source=ROOT/cfg['source'];verify(source)
    if contract['source_manifest_sha256']!=sha(source/'manifest.json'):raise ValueError('Source checksum changed')
    if contract['kind']=='canonical':
        manifest=load(coordinator.parent/'manifest.json')
        if (manifest.get('dataset_version')!=contract.get('dataset_version') or
            contract.get('canonical_content_sha256')!=sha(coordinator.parent/'normalized_annotation_view.local.jsonl')):
            raise ValueError('Canonical review source/version checksum changed')
    if contract['kind']=='holdout':
        reserved=load(ROOT/cfg['holdout_reservation'])['ids']
        if len(expected)!=40 or set(expected)!=set(reserved):raise ValueError('Original 40 holdout IDs required')
    fields,rows,_=read_sheet(path,'Review');efields,evidence,_=read_sheet(path,'Source')
    if fields!=FIELDS or efields!=EVIDENCE:raise ValueError('Wrong domain/spam workbook schema')
    for values in (rows,evidence):
        validate_review_ids(values,expected,len(expected),'Wrong/repeated review IDs')
    literal=literal_text
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
        save(out/'metrics.json',dict(status='AVAILABLE_SAMPLE_DIAGNOSTICS' if metrics else 'CANONICAL_REVIEW_IMPORTED_NO_APPROVAL' if contract['kind']=='canonical' else 'HOLDOUT_LABELS_IMPORTED_NOT_USED_FOR_RULE_TUNING',metrics=metrics))
        return seal(out,dict(status='CANONICAL_QUALITY_REVIEW_IMPORTED_NO_APPROVAL' if contract['kind']=='canonical' else 'HUMAN_QUALITY_REVIEW_IMPORTED',kind=contract['kind'],rows=len(rows),workbook_sha256=sha(path),coordinator_sha256=sha(coordinator),
            source_manifest_sha256=contract['source_manifest_sha256'],normalization_version=contract['normalization_version'],annotation_pointer_updated=False,
            **(dict(canonical_content_sha256=contract['canonical_content_sha256'],dataset_version=contract['dataset_version']) if contract['kind']=='canonical' else {}),
            domain_counts=dict(Counter(r['human_domain_decision'] for r in rows)),spam_counts=dict(Counter(r['human_spam_decision'] for r in rows))))


def evaluate(source,imported,output):
    """Evaluate the unchanged recorded rules only after real complete import."""
    verify(source);m=verify(imported);contract=load(source/'contract.json');kind=m['kind']
    coordinator=source/('holdout_input.local.json' if kind=='holdout' else 'semantic_review_input.local.json')
    if m['status']!='HUMAN_QUALITY_REVIEW_IMPORTED' or m['coordinator_sha256']!=sha(coordinator) or m['source_manifest_sha256']!=contract['source_manifest_sha256']:raise ValueError('Import/source mismatch')
    if contract['implementation_sha256']!=sha(ROOT/'src/dataset/quality_readiness.py'):raise ValueError('Quality rules changed after holdout reservation/export; do not tune on holdout')
    decisions,_=csv_rows((imported/'human_quality_decisions.local.csv').read_bytes());expected={r['record_id']:r for r in load(coordinator)['rows']}
    if len(decisions)!=len(expected) or {d['id'] for d in decisions}!=set(expected):raise ValueError('Imported IDs changed')
    rows={r['record_id']:r for r in read_jsonl(source/'quality_proposals.local.jsonl')};enriched=[]
    for d in decisions:
        r=rows[d['id']];e=expected[d['id']]
        if d['text_sha256']!=e['text_sha256']:raise ValueError('Text checksum changed')
        enriched.append(dict(r,**layers(r),text_view=e['text_view'],human_domain_decision=d['human_domain_decision'],human_spam_decision=d['human_spam_decision']))
    result=quality_metrics(enriched)
    with staged(output) as out:
        save(out/'metrics.json',result);return seal(out,dict(status='QUALITY_SAMPLE_EVALUATED',kind=kind,rows=len(enriched),import_manifest_sha256=sha(imported/'manifest.json'),contract_sha256=sha(source/'contract.json')))


def main(argv=None):
    """Canonical quality CLI; old scripts delegate with unchanged defaults."""
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Quality preparation, human review, evaluation and explicit release gates')
    sub=parser.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare');prepare.add_argument('--config',type=Path,default=Path('configs/phase_j_v1.json'))
    prepare.add_argument('--output',type=Path,default=Path('outputs/phase_j/v2'))
    human=sub.add_parser('import');human.add_argument('--input',type=Path,required=True);human.add_argument('--coordinator',type=Path,required=True)
    human.add_argument('--output',type=Path,required=True)
    evaluation=sub.add_parser('evaluate');evaluation.add_argument('--imported',type=Path,required=True);evaluation.add_argument('--output',type=Path,required=True)
    freezing=sub.add_parser('freeze')
    for name in ('format','normalization','domain','holdout'):freezing.add_argument('--'+name+'-import',type=Path,required=True)
    publishing=sub.add_parser('export');publishing.add_argument('--frozen',type=Path,required=True);publishing.add_argument('--candidate',type=Path,required=True)
    for target in (evaluation,freezing,publishing):target.add_argument('--source',type=Path,default=Path('outputs/phase_j/v2'))
    for target in (freezing,publishing):target.add_argument('--approval',type=Path,required=True);target.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command=='prepare':
        from .quality_readiness import build
        result=build(args.config,args.output);keys=('status','rows','eligible_proposed','eligible_approved')
    elif args.command=='import':result=import_review(args.input,args.coordinator,args.output);keys=('status','kind','rows')
    elif args.command=='evaluate':result=evaluate(args.source,args.imported,args.output);keys=('status','kind','rows')
    else:
        from .quality_release import freeze,export
        result=freeze(args.source,{name:getattr(args,name+'_import') for name in ('format','normalization','domain','holdout')},args.approval,args.output) if args.command=='freeze' else export(args.frozen,args.source,args.candidate,args.approval,args.output)
        keys=('status','rows')
    print({key:result[key] for key in keys})


if __name__=='__main__':main()
