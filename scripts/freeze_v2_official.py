"""Freeze the labeled V2 train and T2 inputs without fitting or scoring models."""

import argparse
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from scripts.chuan_hoa_binh_luan_v2 import normalize_v2, technical_text
from src.annotation.pilot import fingerprints, near_any, reference_index
from src.dataset.common import ROOT, load, normal, read_jsonl, save, seal, sha, staged, verify, write_jsonl
from src.models.core import GOLD_CONFIG, LABELS, V2_BASELINE_OPTIONS


TECHNICAL_SNAPSHOT = ROOT / 'outputs/02_Du_lieu_va_nhan/05_Chuan_hoa_ky_thuat_V2'
SCORE_GROUPS = {'T_original': 189, 'T_supplement': 424}
INPUT_ROLES = {'normalize_v2': 'primary', 'original': 'secondary'}


def freeze(snapshot, output, input_view):
    source = verify(snapshot)
    rows = read_jsonl(snapshot / 'V2_chuan_hoa_va_giu_nhan.local.jsonl')
    ids = {row['comment_id'] for row in rows}
    if len(ids) != len(rows):
        raise ValueError('The technical snapshot contains duplicate comment IDs')
    decisions = [row for row in rows if row['split_role'] in {'T2_SCORE', 'T2_REVIEW_OR_EXCLUDE'}]
    scored = [row for row in decisions if row['split_role'] == 'T2_SCORE']
    if len(decisions) != 652 or Counter(row['label_source'] for row in scored) != SCORE_GROUPS:
        raise ValueError('The technical snapshot differs from the 652 frozen T2 decisions')
    if any(row['label'] not in LABELS for row in scored):
        raise ValueError('T2_SCORE contains a label outside the three sentiment classes')

    def views(row):
        return (technical_text(row['text_source']), normalize_v2(row['text_source']))

    test_views = [views(row) for row in decisions]
    test_posts = {row['post_id'] for row in decisions}
    test_ids = {row['comment_id'] for row in decisions}
    original, normalized = zip(*test_views, strict=True)
    test_exact = tuple({normal(text) for text in view} for view in (original, normalized))
    test_near = tuple(reference_index(fingerprints(text) for text in view) for view in (original, normalized))
    text_index = ('original', 'normalize_v2').index(input_view)
    input_role = INPUT_ROLES[input_view]

    def model_row(row, text):
        return dict(id=row['comment_id'], post_id=row['post_id'], movie_id=row['movie_id'],
                    source=row['source_name'], origin=row['label_source'], label=row['label'], text=text)

    exclusions = Counter()
    train = []
    candidates = [row for row in rows if row['split_role'] == 'TRAIN_CANDIDATE' and row['label'] in LABELS]
    for row in candidates:
        if row['comment_id'] in test_ids or row['post_id'] in test_posts:
            exclusions['shared_id_or_post'] += 1
            continue
        texts = views(row)
        if any(normal(text) in test_exact[i] for i, text in enumerate(texts)):
            exclusions['exact_text'] += 1
            continue
        if any(near_any(text, test_near[i]) for i, text in enumerate(texts)):
            exclusions['near_text'] += 1
            continue
        train.append(model_row(row, texts[text_index]))
    test = [model_row(row, views(row)[text_index]) for row in scored]
    if not train or {row['label'] for row in train} != set(LABELS) or len(test) != 613:
        raise ValueError('The frozen data do not have the required three classes and T2 size')

    proofs = ROOT / 'data/local_models/v2_fresh_checkpoints'
    checkpoints = {name: load(proofs / f'{name}.json') for name in ('phobert', 'visobert')}
    config = dict(input_view=input_view, input_role=input_role, evaluation_views=INPUT_ROLES,
                  labels=LABELS, baselines=GOLD_CONFIG,
                  baseline_preprocessing=dict(entrypoint='src.models.core.v2_baseline_model',
                                              lowercase=True, preserve_emoji_emoticons=True,
                                              **asdict(V2_BASELINE_OPTIONS)),
                  checkpoints={model: {key: proof[key] for key in ('repository', 'revision', 'files')}
                               for model, proof in checkpoints.items()},
                  seeds=[20261123, 20261124, 20261125], epochs=4, learning_rate=2e-5,
                  batch_size=16, max_length=128, warmup_ratio=0.10, weight_decay=0.01,
                  class_weights='N / (3 * n_label)', early_stopping=False,
                  tokenizer_preprocessing={'phobert': 'PyVi', 'visobert': 'direct'})
    with staged(output) as folder:
        save(folder / 'config.json', config)
        write_jsonl(folder / 'train.local.jsonl', train)
        write_jsonl(folder / 'T2.local.jsonl', test)
        seal(folder, dict(kind='V2_OFFICIAL_FROZEN_INPUTS', scored=False, input_view=input_view,
                          input_role=input_role, evaluation_views=INPUT_ROLES,
                          source_sha256=sha(snapshot / 'manifest.json'),
                          T2_source_manifest_sha256=source['t2_manifest_sha256'],
                          code_sha256={path: sha(ROOT / path) for path in (
                              'scripts/freeze_v2_official.py', 'scripts/chuan_hoa_binh_luan_v2.py',
                              'src/annotation/pilot.py', 'src/dataset/common.py',
                              'src/models/core.py', 'src/preprocessing/model.py')},
                          train_candidates=len(candidates), train_size=len(train),
                          train_labels=dict(Counter(row['label'] for row in train)),
                          exclusions=dict(exclusions), test_size=len(test), test_groups=SCORE_GROUPS))
    manifest = verify(output)
    print({key: manifest[key] for key in ('input_view', 'input_role', 'train_size', 'train_labels', 'exclusions', 'test_size')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=TECHNICAL_SNAPSHOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--input-view', choices=tuple(INPUT_ROLES), required=True)
    args = parser.parse_args()
    freeze(args.snapshot, args.output, args.input_view)
