"""Analyze sealed G.3.1 OOF predictions without fitting any model."""
from collections import Counter, defaultdict
import re
from statistics import median

from src.dataset.common import ROOT, csv_rows, load, read_jsonl, save, seal, staged, verify, write_csv
from src.dataset.master import normal
from src.data.quality import near_duplicate_candidates
from src.preprocessing.normalization import signals, normalize, BASIC, NEGATION
from src.baseline.core import metrics

LABELS = ('POS', 'NEG', 'NEU')
PAIRS = (('A', 'B'), ('C', 'D'))
TEENCODE = re.compile(r'(?<!\w)(?:ko|khum|hong|hok|hem|đc|dc|vch|vl|j)(?!\w)', re.I)


def _pair_stats(predictions, left, right):
    a, b = predictions[left], predictions[right]
    ids = sorted(a)
    if set(ids) != set(b):
        raise ValueError('Compared OOF predictions must have the same Facebook IDs')
    truth = {i: a[i]['human_label'] for i in ids}
    transition = Counter(f"{a[i]['predicted_label']}->{b[i]['predicted_label']}"
                         for i in ids if a[i]['predicted_label'] != b[i]['predicted_label'])
    by_true = defaultdict(Counter)
    regressed = []; corrected = []
    for i in ids:
        y = truth[i]; ac = a[i]['predicted_label'] == y; bc = b[i]['predicted_label'] == y
        by_true[y]['rows'] += 1
        by_true[y]['left_correct'] += ac
        by_true[y]['right_correct'] += bc
        by_true[y]['correct_to_wrong'] += ac and not bc
        by_true[y]['wrong_to_correct'] += not ac and bc
        if ac and not bc: regressed.append(i)
        if not ac and bc: corrected.append(i)
    return dict(left=left, right=right, rows=len(ids),
        left_metrics=metrics([truth[i] for i in ids], [a[i]['predicted_label'] for i in ids]),
        right_metrics=metrics([truth[i] for i in ids], [b[i]['predicted_label'] for i in ids]),
        left_correct_right_wrong=len(regressed), left_wrong_right_correct=len(corrected),
        prediction_transitions=dict(sorted(transition.items())),
        by_true_label={k:dict(v) for k,v in by_true.items()},
        regressed_ids=regressed, corrected_ids=corrected)


def _features(text):
    sig = signals(text)
    return dict(char_length=len(text), token_count=len(text.split()),
        negation=bool(NEGATION.search(text)), emoji_codepoints=sig['emoji_codepoints'],
        emoji_aliases=sig['emoji_aliases'], underscore_tokens=sig['underscore_tokens'],
        teencode_candidate=bool(TEENCODE.search(text)))


def _legacy_quality(legacy):
    by_text = defaultdict(list)
    for row in legacy:
        key = normal(row['text_view'])
        if key: by_text[key].append(row['id'])
    exact_groups = [ids for ids in by_text.values() if len(ids) > 1]
    candidates = defaultdict(set)
    for ids in exact_groups:
        for rid in ids: candidates[rid].add('EXACT_DUPLICATE_WITHIN_LEGACY')
    near = near_duplicate_candidates([dict(id=r['id'], text=r['text_view'],
        quality=dict(status='KEEP', duplicate_of=None)) for r in legacy],
        dict(threshold=.9, min_chars=40, shingle_size=3))
    for pair in near:
        candidates[pair['left']].add('NEAR_DUPLICATE_WITHIN_LEGACY')
        candidates[pair['right']].add('NEAR_DUPLICATE_WITHIN_LEGACY')
    feature_rows = [(r, _features(r['text_view'])) for r in legacy]
    short = [r for r,f in feature_rows if f['char_length'] < 20]
    for row in short: candidates[row['id']].add('SHORT_TEXT_POSSIBLE_CONTEXT_DEPENDENCE')
    return dict(rows=len(legacy), labels=dict(Counter(r['label'] for r in legacy)),
        blank=sum(not r['text_view'].strip() for r in legacy), char_length={
            'min':min(f['char_length'] for _,f in feature_rows),
            'median':median(f['char_length'] for _,f in feature_rows),
            'max':max(f['char_length'] for _,f in feature_rows)},
        under_20_chars=len(short), under_10_chars=sum(f['char_length'] < 10 for _,f in feature_rows),
        underscore_rows=sum(f['underscore_tokens'] > 0 for _,f in feature_rows),
        emoji_rows=sum(f['emoji_codepoints'] + f['emoji_aliases'] > 0 for _,f in feature_rows),
        negation_rows=sum(f['negation'] for _,f in feature_rows),
        teencode_candidate_rows=sum(f['teencode_candidate'] for _,f in feature_rows),
        exact_duplicate_groups=len(exact_groups), exact_duplicate_rows=sum(len(g) for g in exact_groups),
        near_duplicate_pairs=len(near), near_duplicate_rows=len({x for p in near for x in (p['left'],p['right'])}),
        candidate_ids=sorted(candidates), candidate_reasons={k:sorted(v) for k,v in candidates.items()},
        note='No label is changed or excluded; short/duplicate criteria are review cues, not errors.')


def _source_profile(rows):
    features = [_features(r['text_view']) for r in rows]
    lengths = [x['char_length'] for x in features]
    return dict(rows=len(rows), labels=dict(Counter(r['label'] for r in rows)),
        char_length=dict(min=min(lengths), median=median(lengths), max=max(lengths)),
        under_20_chars=sum(x['char_length'] < 20 for x in features),
        negation_rows=sum(x['negation'] for x in features),
        emoji_rows=sum(x['emoji_codepoints'] + x['emoji_aliases'] > 0 for x in features),
        underscore_rows=sum(x['underscore_tokens'] > 0 for x in features),
        teencode_candidate_rows=sum(x['teencode_candidate'] for x in features),
        normalization_changed_rows=sum(r['text_view'] != r['text_normalized'] for r in rows))


def analyze(output='outputs/phase_g32/error_analysis_v3'):
    prediction_dir = ROOT/'outputs/phase_g31/ablation'
    unified_dir = ROOT/'outputs/phase_g3/unified'
    prediction_manifest = verify(prediction_dir); unified_manifest = verify(unified_dir)
    raw, _ = csv_rows((prediction_dir/'oof_predictions.csv').read_bytes())
    predictions = {trial: {} for trial in 'ABCD'}
    for row in raw:
        predictions[row['experiment']][row['id']] = row
    rows = read_jsonl(unified_dir/'unified.jsonl'); by_id = {r['id']: r for r in rows}
    fb = [r for r in rows if r['source_dataset'] == 'facebook_development']
    legacy = [r for r in rows if r['source_dataset'] == 'legacy_human']
    if any(len(predictions[t]) != 346 for t in 'ABCD'):
        raise ValueError('Expected complete G.3.1 OOF predictions for A/B/C/D')
    summaries = {t: metrics([predictions[t][i]['human_label'] for i in sorted(predictions[t])],
                            [predictions[t][i]['predicted_label'] for i in sorted(predictions[t])]) for t in 'ABCD'}
    pairs = [_pair_stats(predictions, a, b) for a,b in PAIRS]
    fold_rows=[]; locked=load(unified_dir/'frozen_plan.json')
    for fold in locked['folds']:
        train=[by_id['fbdev::'+i] for i in fold['train_ids']]
        fold_rows.append(dict(fold=fold['fold'], facebook_train_labels=dict(Counter(r['label'] for r in train)),
            legacy_added_rows=len(legacy), legacy_labels=dict(Counter(r['label'] for r in legacy))))
    row_details=[]; grouped=defaultdict(lambda:Counter())
    for rid in sorted(predictions['A']):
        row=by_id[rid]; original=row['text_view']; normalized=normalize(original,BASIC)
        f=_features(original); truth=row['label']; detail=dict(id=rid, movie_id=row['movie_id'], post_id=row['post_id'],
            true_label=truth, text_raw=row['text_raw'], text_view=original, text_normalized=normalized,
            normalization_changed=original!=normalized, **f)
        for t in 'ABCD':
            pred=predictions[t][rid]['predicted_label'];detail[t+'_prediction']=pred;detail[t+'_correct']=pred==truth
        detail['A_to_B_changed']=detail['A_prediction']!=detail['B_prediction']
        detail['C_to_D_changed']=detail['C_prediction']!=detail['D_prediction']
        detail['A_to_C_normalization_changed_prediction']=detail['A_prediction']!=detail['C_prediction']
        detail['B_to_D_normalization_changed_prediction']=detail['B_prediction']!=detail['D_prediction']
        row_details.append(detail)
        for pair_name,left,right in [('A_to_B','A','B'),('C_to_D','C','D')]:
            key=(pair_name,row['movie_id'],row['post_id'])
            grouped[key]['rows']+=1
            grouped[key]['left_correct_right_wrong']+=detail[left+'_correct'] and not detail[right+'_correct']
            grouped[key]['left_wrong_right_correct']+=not detail[left+'_correct'] and detail[right+'_correct']
            grouped[key]['prediction_changed']+=detail[left+'_prediction']!=detail[right+'_prediction']
    feature_groups=defaultdict(lambda:Counter())
    bins=[(0,20,'<20'),(20,51,'20-50'),(51,101,'51-100'),(101,201,'101-200'),(201,10**9,'>200')]
    for d in row_details:
        length_bucket=next(name for lo,hi,name in bins if lo<=d['char_length']<hi)
        tags={'length':length_bucket,'negation':str(d['negation']),'emoji':str(bool(d['emoji_codepoints']+d['emoji_aliases'])),'underscore':str(d['underscore_tokens']>0),'teencode_candidate':str(d['teencode_candidate']),'normalized_changed':str(d['normalization_changed'])}
        for feature,value in tags.items():
            c=feature_groups[(feature,value)];c['rows']+=1
            for t in 'ABCD':c[t+'_correct']+=d[t+'_correct']
            c['A_to_B_prediction_changed']+=d['A_to_B_changed'];c['C_to_D_prediction_changed']+=d['C_to_D_changed']
    quality=_legacy_quality(legacy)
    local_rows=[]
    for d in row_details:
        local_rows.append({k:d[k] for k in ('id','movie_id','post_id','true_label','text_raw','text_view','text_normalized','char_length','token_count','negation','emoji_codepoints','emoji_aliases','underscore_tokens','teencode_candidate','normalization_changed','A_prediction','B_prediction','C_prediction','D_prediction','A_correct','B_correct','C_correct','D_correct','A_to_B_changed','C_to_D_changed','A_to_C_normalization_changed_prediction','B_to_D_normalization_changed_prediction')})
    needs=[]
    by_legacy={r['id']:r for r in legacy}
    for rid,reasons in quality['candidate_reasons'].items():
        r=by_legacy[rid]
        needs.append(dict(id=rid,label=r['label'],reason=';'.join(reasons),text_raw=r['text_raw'],text_view=r['text_view']))
    results=dict(status='COMPLETED_DIAGNOSTIC_ONLY',oof_predictions_verified=len(raw)==4*346,
        prediction_manifest_sha256=prediction_manifest['output_sha256']['oof_predictions.csv'],
        unified_manifest_sha256=unified_manifest['output_sha256']['unified.jsonl'],
        metrics_by_trial=summaries,pairwise_comparisons=pairs,fold_label_support=fold_rows,
        legacy_quality={k:v for k,v in quality.items() if k not in ('candidate_reasons',)},
        source_profiles={'facebook_development':_source_profile(fb), 'legacy_human':_source_profile(legacy)},
        feature_groups=[dict(feature=k[0],value=k[1],**dict(v)) for k,v in sorted(feature_groups.items())],
        grouped_movie_post=[dict(comparison=k[0],movie_id=k[1],post_id=k[2],**dict(v)) for k,v in sorted(grouped.items())],
        normalization=dict(facebook_rows=len(fb),changed_rows=sum(d['normalization_changed'] for d in row_details),
            A_to_C_prediction_changes=sum(d['A_to_C_normalization_changed_prediction'] for d in row_details),
            B_to_D_prediction_changes=sum(d['B_to_D_normalization_changed_prediction'] for d in row_details),
            normalization_changed_and_A_C_prediction_changed=sum(d['normalization_changed'] and d['A_to_C_normalization_changed_prediction'] for d in row_details),
            normalization_changed_and_B_D_prediction_changed=sum(d['normalization_changed'] and d['B_to_D_normalization_changed_prediction'] for d in row_details)))
    with staged(output) as work:
        save(work/'summary.json',results)
        write_csv(work/'movie_post_metrics.csv',results['grouped_movie_post'],['comparison','movie_id','post_id','rows','left_correct_right_wrong','left_wrong_right_correct','prediction_changed'])
        write_csv(work/'feature_metrics.csv',results['feature_groups'],['feature','value','rows','A_correct','B_correct','C_correct','D_correct','A_to_B_prediction_changed','C_to_D_prediction_changed'])
        source_profiles=[dict(source=name, rows=stats['rows'], **stats['char_length'],
            under_20_chars=stats['under_20_chars'], negation_rows=stats['negation_rows'],
            emoji_rows=stats['emoji_rows'], underscore_rows=stats['underscore_rows'],
            teencode_candidate_rows=stats['teencode_candidate_rows'],
            normalization_changed_rows=stats['normalization_changed_rows'], labels_json=__import__('json').dumps(stats['labels'],ensure_ascii=False))
            for name,stats in results['source_profiles'].items()]
        write_csv(work/'source_profiles.csv',source_profiles,
            ['source','rows','min','median','max','under_20_chars','negation_rows','emoji_rows','underscore_rows','teencode_candidate_rows','normalization_changed_rows','labels_json'])
        write_csv(work/'row_error_analysis.local.csv',local_rows,list(local_rows[0]))
        write_csv(work/'needs_human_recheck.local.csv',needs,['id','label','reason','text_raw','text_view'])
        return seal(work,dict(status=results['status'],facebook_rows=len(fb),legacy_rows=len(legacy),
            predictions=len(raw), contains_comments_local_only=True))
