"""Run only the ViSoBERT arm of the frozen E+C ablation on Modal."""

from hashlib import sha256
import json
from pathlib import Path
import sys
from time import sleep

import modal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ablate_v2_abbreviations import DEFAULT, REFERENCE, VIEWS
from src.dataset.common import load, save, seal, sha, staged, verify, write_jsonl

sys.path.insert(0, str(REFERENCE))
from modal_human_cv import app as cv_app, train_remote

app = modal.App('cmt-tag-v2-ablation-viet-tat')
app.include(cv_app)


@app.local_entrypoint()
def run(output: str = str(DEFAULT)):
    out = Path(output).resolve()
    inputs = out/'inputs'
    manifest = verify(inputs)
    assert not manifest['gold_T_used']
    assert manifest['modal_trainer_sha256']==sha(REFERENCE/'modal_human_cv.py')
    assert manifest['modal_runner_sha256']==sha(Path(__file__))
    frozen = sha(inputs/'manifest.json')
    cfg = load(inputs/'config.json')
    gpu = cfg['bert']['device'].removeprefix('Modal ')
    if gpu not in {'L4','A10'}:
        raise ValueError('Unsupported frozen GPU')
    train_for_run = train_remote if gpu == 'L4' else train_remote.with_options(gpu=gpu)
    labels = cfg['labels']
    roster = load(inputs/'roster.local.json')
    folds = load(inputs/'folds.local.json')
    encoded = load(inputs/'tokens.local.json')
    checkpoint = cfg['checkpoints']['visobert']
    jobs = []
    for view in VIEWS:
        tokens = encoded['views'][view]
        for fold in folds:
            seed, number = fold['seed'], fold['fold']
            target = out/'visobert'/f'{view}_{seed}_{number}'
            if target.exists():
                assert verify(target)['inputs_sha256']==frozen
                continue
            train, validation = fold['train'], fold['validation']
            payload = dict(train=[tokens[i] for i in train], c=[tokens[i] for i in validation],
                           labels=[labels.index(roster[i]['label']) for i in train], pad_id=encoded['pad_id'])
            digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()
            call = train_for_run.spawn('visobert', seed, checkpoint, cfg['bert'], payload, digest)
            jobs.append((view, seed, number, len(train), validation, target, digest, call))
            print('Submitted', view, seed, number, call.object_id, flush=True)
    failures = []
    while jobs:
        pending = []
        for view, seed, number, n_train, validation, target, digest, call in jobs:
            try:
                result = call.get(timeout=0)
            except TimeoutError:
                pending.append((view, seed, number, n_train, validation, target, digest, call))
                continue
            except Exception as err:
                failures.append((view, seed, number, str(err)))
                continue
            assert result['token_digest']==digest and result['revision']==checkpoint['revision']
            assert result['seed']==seed and result['n_train']==n_train
            assert gpu in result['gpu']
            predictions = result.pop('predictions')
            assert len(predictions)==len(validation) and all(0<=p<len(labels) for p in predictions)
            with staged(target) as work:
                save(work/'run.json', result)
                write_jsonl(work/'oof.local.jsonl',
                            [dict(view=view, seed=seed, fold=number, id=roster[i]['id'],
                                  label=roster[i]['label'], prediction=labels[p])
                             for i,p in zip(validation,predictions,strict=True)])
                seal(work, dict(kind='V2_DEV_ABLATION_VISOBERT_FOLD', inputs_sha256=frozen,
                                modal_call_id=call.object_id, gold_T_used=False))
            print('Complete', view, seed, number, result['elapsed'], flush=True)
        jobs = pending
        if jobs:
            sleep(5)
    if failures:
        raise RuntimeError(failures)
