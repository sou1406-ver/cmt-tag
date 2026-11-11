"""Evaluate completed human quality review against the recorded, unchanged rules."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.common import ROOT,load,read_jsonl,verify,sha,staged,save,seal,csv_rows
from src.dataset.quality_readiness import quality_metrics,layers

def evaluate(source,imported,output):
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
        # Holdout proposals first computed now, with recorded rules unchanged.
        enriched.append(dict(r,**layers(r),text_view=e['text_view'],human_domain_decision=d['human_domain_decision'],human_spam_decision=d['human_spam_decision']))
    result=quality_metrics(enriched)
    with staged(output) as out:
        save(out/'metrics.json',result);return seal(out,dict(status='QUALITY_SAMPLE_EVALUATED',kind=kind,rows=len(enriched),import_manifest_sha256=sha(imported/'manifest.json'),contract_sha256=sha(source/'contract.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=Path('outputs/phase_j/v2'));p.add_argument('--imported',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();m=evaluate(a.source,a.imported,a.output);print({k:m[k] for k in ('status','kind','rows')})
