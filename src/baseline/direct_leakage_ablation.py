"""Run G.3.1 fixed ablations after auditable direct-overlap checks pass."""
from importlib.metadata import version
from pathlib import Path
import time
from collections import Counter

from src.dataset.common import ROOT, load, read_jsonl, csv_rows, save, seal, sha, staged, verify, write_csv
from src.dataset.unified import check_protection, guard
from src.dataset.blind import assert_allowed
from src.baseline.core import metrics
from src.baseline.preprocessing_experiments import offline_network
from src.baseline.normalization_ablation import pipeline
from src.baseline.bow_robustness import inputs as phase_e_inputs, validate_reference

TRIALS = [dict(id='A', augment=False, view='original'), dict(id='B', augment=True, view='original'),
          dict(id='C', augment=False, view='basic'), dict(id='D', augment=True, view='basic')]
MODEL = dict(feature='char_wb', ngram_range=[3, 5], C=1, class_weight='balanced', seed=42, extra_l2=True)


def run(config_path='configs/normalization_ablation_direct.json', output='outputs/phase_g31/ablation'):
    cfg = load(config_path)
    if cfg['protocol'] != 'direct_fold_isolation_v1' or cfg['trials'] != TRIALS or cfg['model'] != MODEL:
        raise ValueError('G.3.1 protocol, trials and model are pinned')
    audit_dir = ROOT/cfg['audit']; unified_dir = ROOT/cfg['unified']
    audit_manifest = verify(audit_dir); unified_manifest = verify(unified_dir)
    if sha(audit_dir/'manifest.json') != cfg['audit_manifest_sha256']:
        raise ValueError('Pinned direct-overlap audit changed')
    if audit_manifest['status'] != 'PASS':
        raise ValueError('Direct identity/exact/near leakage audit did not pass')
    if sha(unified_dir/'manifest.json') != cfg['unified_manifest_sha256']:
        raise ValueError('Pinned unified corpus changed')
    audit = load(audit_dir/'component_and_fold_audit.json')
    if audit['direct_overlap_gate'] != 'PASS' or len(audit['folds']) != 3:
        raise ValueError('Required direct overlap checks are blocked')
    protected = load(unified_dir/'protected_inputs.json'); check_protection(protected)
    rows = read_jsonl(unified_dir/'unified.jsonl')
    by_id = {r['id']: r for r in rows}
    by_original = {r['original_id']: r for r in rows if r['source_dataset'] == 'facebook_development'}
    legacy_ids = sorted(r['id'] for r in rows if r['source_dataset'] == 'legacy_human')
    locked = load(unified_dir/'frozen_plan.json')
    _, old_locked, phase_e, old_cfg = phase_e_inputs(load(ROOT/load(unified_dir/'config.json')['facebook_contract']))
    if old_locked != locked:
        raise ValueError('Frozen Facebook folds do not match Phase E')
    reference_predictions, _ = csv_rows((ROOT/'outputs/phase_e/predictions.csv').read_bytes())
    all_results = []; all_predictions = []
    with offline_network():
        for trial in TRIALS:
            fold_metrics = []; trial_predictions = []
            field = 'text_view' if trial['view'] == 'original' else 'text_normalized'
            for fold in locked['folds']:
                train_fb = [by_original[i] for i in fold['train_ids']]
                valid = [by_original[i] for i in fold['validation_ids']]
                train = train_fb + ([by_id[i] for i in legacy_ids] if trial['augment'] else [])
                # The separate audit checks source post/comment IDs and every master text alias.
                # Legacy post provenance is missing, so augmentation remains development-only.
                if ({r['original_id'] for r in train_fb} & {r['original_id'] for r in valid}
                    or any(r['source_dataset'] != 'facebook_development' for r in valid)):
                    raise ValueError('Frozen split identity or validation source changed')
                assert_allowed(train, 'train'); assert_allowed(valid, 'validation')
                guard(train, 'train'); guard(valid, 'validation')
                model = pipeline(); started = time.perf_counter()
                model.fit([r[field] for r in train], [r['label'] for r in train])
                predictions = model.predict([r[field] for r in valid])
                elapsed = time.perf_counter() - started
                truth = [r['label'] for r in valid]
                fold_metrics.append(dict(fold=fold['fold'], train_facebook=len(train_fb),
                    train_legacy=len(legacy_ids) if trial['augment'] else 0, validation_facebook=len(valid),
                    train_counts=dict(Counter(r['label'] for r in train)),
                    validation_counts=dict(Counter(truth)), seconds=elapsed,
                    metrics=metrics(truth, predictions)))
                trial_predictions.extend(dict(experiment=trial['id'], fold=fold['fold'], id=r['id'],
                    human_label=r['label'], predicted_label=str(pred)) for r, pred in zip(valid, predictions))
            summary = metrics([r['human_label'] for r in trial_predictions],
                              [r['predicted_label'] for r in trial_predictions])
            trial_result = dict(experiment=trial['id'], view=trial['view'], augmented=trial['augment'],
                metrics=summary, folds=fold_metrics,
                legacy_identity_provenance='unverifiable; exploratory augmentation only' if trial['augment'] else 'not_applicable')
            if trial['id'] == 'A':
                validate_reference(dict(metrics=summary, folds=[dict(fold=x['fold'], metrics=x['metrics']) for x in fold_metrics]),
                                   [dict(id=r['id'].removeprefix('fbdev::'), fold=r['fold'], human_label=r['human_label'],
                                         predicted_label=r['predicted_label']) for r in trial_predictions],
                                   phase_e, reference_predictions, cfg['phase_e_run_id'])
            all_results.append(trial_result); all_predictions.extend(trial_predictions)
    comparisons = []
    scores = {r['experiment']: r['metrics']['macro_f1'] for r in all_results}
    for name, left, right in [('legacy_original', 'B', 'A'), ('basic_fb', 'C', 'A'),
                              ('basic_with_legacy', 'D', 'B'), ('legacy_basic', 'D', 'C')]:
        comparisons.append(dict(name=name, left=left, right=right, macro_f1_difference=scores[left]-scores[right]))
    with staged(output) as work:
        save(work/'results.json', dict(status='DEVELOPMENT_ONLY', protocol=audit['protocol'],
            direct_overlap_gate='PASS', full_master_component_gate='NOT_USED_FOR_DIRECT_LEAKAGE',
            legacy_identity_provenance='UNVERIFIABLE_MISSING_SOURCE_METADATA',
            independent_test=False, historical_reference_macro_f1=cfg['phase_e_macro_f1_reference'],
            reference_A_reproduced=True, results=all_results, comparisons=comparisons))
        write_csv(work/'oof_predictions.csv', all_predictions,
                  ['experiment', 'fold', 'id', 'human_label', 'predicted_label'])
        save(work/'audit_snapshot.json', audit); save(work/'config.json', cfg)
        save(work/'environment.json', dict(packages={p: version(p) for p in ('scikit-learn','numpy','scipy')},
                                           offline=True, model=MODEL))
        check_protection(protected)
        return seal(work, dict(status='DEVELOPMENT_ONLY', fits=12, direct_overlap_gate='PASS',
            legacy_identity_provenance='UNVERIFIABLE', reference_A_macro_f1=scores['A'],
            independent_test=False, unified_manifest_sha256=sha(unified_dir/'manifest.json'),
            audit_manifest_sha256=sha(audit_dir/'manifest.json')))
