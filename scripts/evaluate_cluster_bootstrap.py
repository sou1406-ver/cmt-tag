"""Future final evaluation only; requires complete frozen predictions and blind receipts."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.common import csv_rows, load, save, seal, sha, staged, verify
from src.dataset.bootstrap import evaluate


def final_evaluate(reservation, labels, predictions, output, model_contract, replicates=2000, seed=20261111):
    reservation, labels, predictions, model_contract = map(Path, (reservation, labels, predictions, model_contract))
    task = verify(reservation); imported = verify(labels)
    if task['status'] != 'BLIND_READY': raise ValueError('Blind workbooks and reservation must be finalized first')
    if imported['review']: raise ValueError('Resolve REVIEW explicitly before opening final predictions')
    receipt = load(labels/'receipt.json')
    if receipt.get('role') != 'a' or receipt['evidence_mode'] != 'blind' or receipt['reservation_manifest_sha256'] != sha(reservation/'manifest.json'):
        raise ValueError('Blind import receipt does not match this reservation')
    # Must be committed/frozen before labeling. Never pick a model using this evaluation.
    contract = load(model_contract)
    if not contract.get('frozen_before_test_labels') or not contract.get('model_sha256') or not contract.get('frozen_commit'):
        raise ValueError('Provide a pre-label model freeze contract; this command does not train or select models')
    decision_rows, _ = csv_rows((labels/'decisions.csv').read_bytes())
    pred_rows, fields = csv_rows(predictions.read_bytes())
    if fields != ['id','prediction']: raise ValueError('Expected only id,prediction; score/threshold tuning is unsupported')
    pred = {r['id']:r['prediction'] for r in pred_rows}
    if len(pred) != len(pred_rows) or set(pred) != {r['id'] for r in decision_rows}:
        raise ValueError('Predictions must cover every reserved ID exactly once, including excluded decisions')
    mapping = {r['id']:r for r in load(reservation/'coordinator_mapping.json')}
    if set(mapping) != set(pred): raise ValueError('Coordinator IDs changed')
    rows = [dict(id=r['id'],label=r['label'],prediction=pred[r['id']],post_id=mapping[r['id']]['post_id'],
                 movie_id=mapping[r['id']]['movie_id']) for r in decision_rows if r['status']=='LABELED']
    before = {str(p):sha(p) for p in (predictions,model_contract,labels/'manifest.json',reservation/'manifest.json')}
    result = evaluate(rows, replicates, seed)
    result.update(reserved=len(decision_rows), excluded=imported['excluded'], input_sha256=before,
                  quota_design_not_natural_facebook_distribution=True, final_once_no_tuning=True)
    with staged(output) as work:
        save(work/'bootstrap.json', result)
        if any(sha(p)!=value for p,value in before.items()): raise ValueError('Evaluation input changed')
        seal(work, dict(status='FINAL_EVALUATION_OPENED_NO_MORE_TUNING', input_sha256=before))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reservation','labels','predictions','output','model-contract'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/cluster_bootstrap.json'))
    p.add_argument('--replicates',type=int,default=None);p.add_argument('--seed',type=int,default=None)
    a=p.parse_args();cfg=load(a.config)
    r=final_evaluate(a.reservation,a.labels,a.predictions,a.output,a.model_contract,
                     cfg['replicates'] if a.replicates is None else a.replicates,cfg['seed'] if a.seed is None else a.seed)
    print(json.dumps(dict(posts=r['posts'],rows=r['rows'],metrics=r['metrics'],warnings=r['warnings'])))


if __name__=='__main__':main()
