"""Final, fixed-prediction cluster bootstrap. No model fit, ranking or tuning."""
from collections import Counter, defaultdict
import random

import numpy as np
from sklearn.metrics import f1_score

LABELS = ['POS','NEG','NEU']


def cluster_draws(rows, replicates=2000, seed=20261111):
    if type(replicates) is not int or replicates < 2000: raise ValueError('At least 2000 replicates required')
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        if not row.get('post_id'): raise ValueError('Post identity required for every evaluation row')
        groups[row['post_id']].append(i)
    if len(groups) < 2: raise ValueError('At least two posts required for cluster bootstrap')
    rng = random.Random(seed); posts = sorted(groups)
    for _ in range(replicates):
        yield [i for post in rng.choices(posts, k=len(posts)) for i in groups[post]]


def evaluate(rows, replicates=2000, seed=20261111):
    """Missing true class => undefined class F1; macro undefined if any class absent.

    Supported class with no predicted positives has genuine F1=0. Percentile CIs
    condition on valid replicates, with counts and missing-class warnings exposed.
    """
    if not rows or len({r['id'] for r in rows}) != len(rows): raise ValueError('Unique evaluation IDs required')
    if any(r.get('label') not in LABELS or r.get('prediction') not in LABELS or not r.get('movie_id') for r in rows):
        raise ValueError('Final resolved three-class labels, predictions and movie metadata required')
    samples = {k: [] for k in ['macro_f1', *LABELS]}; invalid = Counter()

    def score(subset):
        y = [r['label'] for r in subset]; pred = [r['prediction'] for r in subset]
        present = set(y)
        values = f1_score(y, pred, labels=LABELS, average=None, zero_division=0)
        result = {label: float(value) if label in present else None for label, value in zip(LABELS, values)}
        result['macro_f1'] = float(np.mean(values)) if present == set(LABELS) else None
        return result

    for indices in cluster_draws(rows, replicates, seed):
        values = score([rows[i] for i in indices])
        for key, value in values.items():
            if value is None: invalid[key] += 1
            else: samples[key].append(value)
    point = score(rows)
    intervals = {key: dict(point=point[key], ci95=np.percentile(values, [2.5,97.5]).tolist() if values else None,
                           valid_replicates=len(values), invalid_replicates=invalid[key]) for key, values in samples.items()}
    warnings = []
    posts = len({r['post_id'] for r in rows}); movies = Counter(r['movie_id'] for r in rows)
    if posts < 30: warnings.append('Few post clusters; percentile intervals may be unstable')
    if max(movies.values())/len(rows) > .3: warnings.append('One movie exceeds 30% of the evaluation rows')
    if invalid['macro_f1']: warnings.append('Macro CI conditions on replicates containing all three true classes; inspect invalid count')
    if min(Counter(r['label'] for r in rows).get(k, 0) for k in LABELS) < 20:
        warnings.append('At least one class has fewer than 20 observations')
    return dict(method='whole_post_cluster_bootstrap_percentile', confidence=.95, replicates=replicates, seed=seed,
                posts=posts, movies=len(movies), rows=len(rows), support=dict(Counter(r['label'] for r in rows)),
                by_movie=dict(movies), metrics=intervals, warnings=warnings,
                model_selection_allowed=False, threshold_tuning_allowed=False)
