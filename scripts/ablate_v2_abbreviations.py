"""Paired E+C ablation using the previously frozen grouped folds."""

import argparse
from collections import Counter
from pathlib import Path
from statistics import mean, stdev

from src.annotation.pilot import fingerprints, near_any, reference_index
from src.dataset.common import ROOT, load, normal, read_jsonl, save, seal, sha, staged, verify, write_csv, write_jsonl
from src.models.core import gold_model, metrics
from src.models.transformer_demo import text_view
from scripts.apply_v2_abbreviations import GLOSSARY, SUPPLEMENT, load_glossary, load_supplement, make_normalizer
from scripts.chuan_hoa_binh_luan_v2 import normalize_v2, technical_text


REFERENCE = ROOT / 'outputs/annotation_v2_fixed_c_3seed_01'
DEFAULT = ROOT / 'outputs/03_Thu_nghiem/02_CV_learning_curve_va_tien_xu_ly/Ablation_viet_tat_V2'
VIEWS = ('original', 'normalized')


def prepare(output, gpu='L4', recipe='abbreviations'):
    source = REFERENCE / 'human_cv/inputs'
    verify(source)
    cfg = load(source/'config.json')
    roster = load(source/'roster.local.json')
    folds = load(source/'folds.local.json')
    assert not cfg['gold_T_used'] and cfg['validation_n'] == 184
    assert cfg['seeds'] == [20261123, 20261124] and len(folds) == 10
    assert len({r['id'] for r in roster}) == len(roster)
    original = [r['text'] for r in roster]
    if recipe=='normalize_v2':
        original = [technical_text(text) for text in original]
        normalized = [normalize_v2(text) for text in original]
    else:
        standardize = make_normalizer(load_glossary(GLOSSARY), load_supplement(SUPPLEMENT))
        normalized = [standardize(text)[0] for text in original]
    texts = {'original': original, 'normalized': normalized}
    excluded_per_fold = []
    for fold in folds:
        valid = fold['validation']
        posts = {roster[i]['post'] for i in valid}
        by_normal = {normal(normalized[i]) for i in valid}
        near = reference_index(fingerprints(normalized[i]) for i in valid)
        assert not any(roster[i]['post'] in posts for i in fold['train'])
        retained = []
        excluded = []
        for i in fold['train']:
            if normal(normalized[i]) in by_normal or near_any(normalized[i], near):
                excluded.append(roster[i]['id'])
            else:
                retained.append(i)
        fold['train'] = retained
        excluded_per_fold.append(dict(seed=fold['seed'], fold=fold['fold'], ids=excluded))
    validation_ids = []
    for seed in cfg['seeds']:
        ids = [i for f in folds if f['seed'] == seed for i in f['validation']]
        assert len(ids) == len(set(ids)) == 184
        assert Counter(roster[i]['origin'] for i in ids) == {'E':35, 'C':149}
        validation_ids.append(set(ids))
    assert validation_ids[0] == validation_ids[1]
    checkpoint = cfg['checkpoints']['visobert']
    proof = load(ROOT/'data/local_models/v2_fresh_checkpoints/visobert.json')
    assert all(proof[key] == value for key, value in checkpoint.items())
    local = Path(proof['path'])
    tokenizer_files = {key:value for key,value in checkpoint['files'].items()
                       if not key.endswith(('.bin','.safetensors'))}
    # Local preparation loads only the tokenizer. The Modal trainer verifies the weights.
    assert tokenizer_files and all(sha(local/key)==value for key,value in tokenizer_files.items())
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True, use_fast=True)
    encoded = {}
    for view in VIEWS:
        encoded[view] = tokenizer([text_view(t, 'visobert') for t in texts[view]],
                                  truncation=True, max_length=cfg['bert']['max_length'],
                                  return_attention_mask=False, return_token_type_ids=False)['input_ids']
    cfg['primary_selection_rule'] = 'ViSoBERT mean pooled OOF macro-F1; exact tie uses original'
    cfg['bert']['eval'] = 'Local E+C OOF after final fixed epoch'
    cfg['bert']['device'] = f'Modal {gpu}'
    cfg['views'] = list(VIEWS)
    cfg['normalization_recipe'] = recipe
    with staged(output/'inputs') as out:
        save(out/'config.json', cfg)
        save(out/'folds.local.json', folds)
        save(out/'roster.local.json', roster)
        save(out/'texts.local.json', texts)
        save(out/'tokens.local.json', {'pad_id': tokenizer.pad_token_id, 'views': encoded})
        save(out/'excluded.local.json', excluded_per_fold)
        seal(out, dict(kind='V2_DEV_ABLATION_INPUT', gold_T_used=False,
                       reference_sha256=sha(source/'manifest.json'),
                       original_folds_sha256=sha(source/'folds.local.json'),
                       normalization_sha256=sha(ROOT/'scripts/apply_v2_abbreviations.py'),
                       normalization_engine_sha256=sha(ROOT/'scripts/chuan_hoa_binh_luan_v2.py'),
                       normalization_recipe=recipe, tokenizer_files_sha256=tokenizer_files,
                       normalization_inputs={p.name: sha(p) for p in (GLOSSARY,SUPPLEMENT)},
                       code_sha256=sha(Path(__file__)),
                       modal_trainer_sha256=sha(REFERENCE/'modal_human_cv.py'),
                       modal_runner_sha256=sha(ROOT/'scripts/modal_v2_abbreviations.py'),
                       normalized_roster_rows=sum(a != b for a,b in zip(*texts.values(), strict=True)),
                       new_duplicate_exclusions=[len(f['ids']) for f in excluded_per_fold]))
    print(load(output/'inputs/manifest.json')['new_duplicate_exclusions'], flush=True)


def baseline(output):
    inputs = output/'inputs'
    verify(inputs)
    roster = load(inputs/'roster.local.json')
    folds = load(inputs/'folds.local.json')
    texts = load(inputs/'texts.local.json')
    predictions = []
    for view in VIEWS:
        for fold in folds:
            ti, vi = fold['train'],fold['validation']
            model = gold_model('tfidf_word_svm')
            model.set_params(model__random_state=fold['seed'])
            model.fit([texts[view][i] for i in ti], [roster[i]['label'] for i in ti])
            predicted = model.predict([texts[view][i] for i in vi])
            predictions.extend(dict(view=view, seed=fold['seed'], fold=fold['fold'],
                                    id=roster[i]['id'], label=roster[i]['label'], prediction=p)
                               for i,p in zip(vi,predicted,strict=True))
    with staged(output/'baseline') as out:
        write_jsonl(out/'oof.local.jsonl', predictions)
        seal(out, dict(kind='V2_DEV_ABLATION_BASELINE', inputs_sha256=sha(inputs/'manifest.json')))
    for view in VIEWS:
        for seed in (20261123, 20261124):
            rows = [r for r in predictions if (r['view'],r['seed']) == (view,seed)]
            print('LinearSVC',view,seed,metrics([r['label'] for r in rows],[r['prediction'] for r in rows])['macro_f1'])


def summarize(output):
    inputs = output/'inputs'
    frozen = sha(inputs/'manifest.json')
    verify(inputs)
    assert verify(output/'baseline')['inputs_sha256']==frozen
    cfg = load(inputs/'config.json')
    sets = {'tfidf_word_svm': read_jsonl(output/'baseline/oof.local.jsonl'), 'visobert': []}
    roster = load(inputs/'roster.local.json')
    expected = {(f['seed'],f['fold']): {roster[i]['id']: roster[i]['label'] for i in f['validation']}
                for f in load(inputs/'folds.local.json')}
    for view in VIEWS:
        for seed, fold in expected:
            target = output/'visobert'/f'{view}_{seed}_{fold}'
            assert verify(target)['inputs_sha256']==frozen
            sets['visobert'].extend(read_jsonl(target/'oof.local.jsonl'))
    comparisons = []
    per_seed = []
    predictions = []
    for name, rows in sets.items():
        for view in VIEWS:
            scores = []
            for seed in cfg['seeds']:
                selected = [r for r in rows if (r['view'], r['seed']) == (view, seed)]
                assert len(selected) == len({r['id'] for r in selected}) == 184
                assert all(expected[seed,r['fold']][r['id']]==r['label'] for r in selected)
                score = metrics([r['label'] for r in selected], [r['prediction'] for r in selected])
                numbers = {'macro_f1': score['macro_f1'], 'accuracy': score['accuracy']}
                per_seed.append(dict(model=name, view=view, seed=seed, **numbers))
                predictions.extend(dict(model=name, **r) for r in selected)
                scores.append(numbers)
            comparisons.append(dict(model=name, view=view, **{
                f'{metric}_{statistic}': func([r[metric] for r in scores])
                for metric in scores[0] for statistic,func in [('mean',mean),('std',stdev)]
            }))
    best = max((r for r in comparisons if r['model']=='visobert'), key=lambda row: row['macro_f1_mean'])
    with staged(output/'results') as out:
        write_csv(out/'comparison.csv', comparisons, list(comparisons[0]))
        write_csv(out/'per_seed.csv', per_seed, list(per_seed[0]))
        write_jsonl(out/'oof.local.jsonl', predictions)
        seal(out, dict(kind='V2_DEV_ABLATION_SELECTION', inputs_sha256=frozen,
                       selected_view=best['view'], selection_rule=cfg['primary_selection_rule'],
                       gold_T_used=False))
    for row in comparisons:
        print(row)
    print('Selected',best['view'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','baseline','summarize'))
    parser.add_argument('--output', type=Path, default=DEFAULT)
    parser.add_argument('--gpu', choices=('L4','A10'), default='L4', help='GPU to freeze when preparing')
    parser.add_argument('--recipe', choices=('abbreviations','normalize_v2'), default='abbreviations')
    args = parser.parse_args()
    if args.action=='prepare':
        prepare(args.output, args.gpu, args.recipe)
    else:
        {'baseline':baseline,'summarize':summarize}[args.action](args.output)
