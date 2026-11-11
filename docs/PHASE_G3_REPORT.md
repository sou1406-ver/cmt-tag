# Phase G.3 — Unified human dataset and normalization ablation

**Status: PARTIAL.** The unified human-labeled corpus and normalization audit
were built. The historical Phase E reference was reproduced exactly. The
requested four-way comparison was not run: the unchanged frozen folds fail the
strict full-master connected-component isolation gate.

## Scope and data

The local immutable artifact `outputs/phase_g3/unified/` contains 532
supervised human-labeled rows: 346 Facebook development rows and 186 imported
legacy-human rows. Label totals are POS 189, NEG 221, NEU 122. The original
labels and source text are retained; legacy `overall` values are not used as
training labels. Facebook REVIEW/EXCLUDE rows are available only to preserve
grouping evidence, not as supervised examples. No raw dataset or per-comment
prediction artifact is tracked in Git.

The legacy rows have no verified original Facebook post/movie provenance. The
import receipt verifies the human annotation workflow and source snapshot, but
does not establish the origin or reliability of the old `overall` field.

## Normalization audit

The deterministic `basic_v1` view applies NFC, collapses whitespace, and
decodes complete semicolon-terminated HTML entities outside URLs. It preserves
case, punctuation, emoji, negation, mentions, URLs, underscores, repetitions,
and teencode. It does not segment words or infer sentiment.

| Source | Rows changed | Character delta | Token delta | Empty results | Detected sentiment-information loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| Facebook development | 64/346 | -435 | 0 | 0 | 0 |
| Legacy human | 0/186 | 0 | 0 | 0 | 0 |

The changed rows are consistent with whitespace normalization; no URL,
mention, emoji, or HTML entity was detected in these two annotated subsets.
The legacy subset contains 1,539 underscore-bearing tokens. They were retained:
1,538 are classified as possible joined-letter tokens, which is only a signal
for review and does not prove a segmentation issue. Before/after rows and
representative examples are local artifacts; examples are not copied into this
public report.

## Frozen-fold reference reproduction

The original Phase E setup was rerun on the same 346 Facebook examples and
same three locked folds, with the pinned char TF-IDF + LinearSVC estimator.
OOF predictions and aggregate metrics matched the Phase E reference exactly.
This is a historical reproduction, not a new leakage-qualified estimate.

| Fold | Validation POS/NEG/NEU | Accuracy | Macro-F1 | POS recall | NEG recall | NEU recall | Errors |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 58/47/47 | 0.586 | 0.574 | 0.448 | 0.915 | 0.426 | 63 |
| 1 | 29/48/27 | 0.577 | 0.510 | 0.310 | 0.854 | 0.370 | 44 |
| 2 | 23/49/18 | 0.722 | 0.653 | 0.565 | 0.878 | 0.500 | 25 |
| OOF total | 110/144/92 | 0.618 | **0.580159** | 0.436 | 0.882 | 0.424 | 132 |

Fold 0 contributes the largest raw number of errors (63), and fold 1 has the
lowest macro-F1 (0.510). This identifies where errors occurred; it does not
establish why. The fold supports and error counts differ, so raw error totals
should not be interpreted as comparable difficulty by themselves.

## Strict isolation blocker

The required old folds are retained unchanged. The full Phase G master graph
places Facebook examples from both sides of every fold in the same connected
component. The shared component contains 10,275 master records, 14 Facebook
posts, and 259 of the original 400 development rows; 222 of the 346 supervised
Facebook examples are in it. Shared train/validation component rows by fold are
90/132, 148/74, and 206/16. Each fold is therefore blocked.

Hash-only bridge witnesses are stored in
`outputs/phase_g3/ablation/bridge_witnesses.json`; the paths combine metadata,
exact-text and/or near-duplicate edges. These witnesses establish a structural
component intersection. They do **not** prove the endpoint comments are direct
duplicates or that fitted vocabulary leaked. The strict protocol nevertheless
requires stopping rather than disregarding master-graph links or silently
changing folds.

Consequently A/B/C/D are all marked `BLOCKED_STRICT_COMPONENT_ISOLATION`,
with zero qualified experiment fits. No legacy augmentation or normalization
comparison is claimed. In particular, do not use this report to claim that
normalization improved or degraded model quality.

## Reproducibility and artifacts

Tracked implementation/configuration:

- `src/preprocessing/normalization.py`
- `src/dataset/unified.py`
- `src/baseline/normalization_ablation.py`
- `configs/unified_dataset.json`
- `configs/normalization_ablation.json`
- `scripts/build_unified_dataset.py`
- `scripts/run_normalization_ablation.py`

Local immutable data/results are under `outputs/phase_g3/unified/` and
`outputs/phase_g3/ablation/`. The unified artifact records input hashes and
protects prior guideline, annotation, model, master and legacy-import inputs.
No Phase E/E.1/E.2/G/G.2 artifact, guideline, human label, split, or reserved
test data was modified. No API, crawler, Transformer, hyperparameter search,
or independent test was used.

Commands from the repository root:

```powershell
python scripts/build_unified_dataset.py
python scripts/run_normalization_ablation.py
```

The build commands refuse to overwrite an existing immutable output. The
runner exits nonzero after writing its truthful PARTIAL artifact when strict
isolation blocks the comparison.

## Next decision

The planned ablation cannot satisfy both the requirement to keep the historical
folds and the requirement to isolate full-master connected components. The
artifacts document the conflict. No fold reassignment or graph relaxation was
performed in this phase.
