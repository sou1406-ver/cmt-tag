# Phase G.3.2 — Parent/thread verification and legacy diagnostics

**Status: PASS for the directly measurable Facebook identity, post, exact-text,
near-text, and reply-thread checks on the three frozen development folds.** The
186 legacy rows still lack post-level provenance; augmented trials remain
exploratory. No label, frozen split, Phase G graph, or earlier model artifact
was changed.

## Parent/reply provenance audit

The G.3.1 unified rows did not actually carry `parent_comment_id`; its earlier
zero count for that field was not a valid check. G.3.2 instead resolves each of
the 346 Facebook examples through its exact `master_id` and the master's
selected `source_file`/`source_row`. It reads that row only when the path is
inside this repository and checks the source `comment_id`, `post_id`,
`record_type`, and parent field against the master observation. The verified
identity key is namespaced by platform and post. No parent value is inferred.

All **346/346** source rows verified: 233 source records are `comment`, and
113 are `reply` with an observed parent ID. Across each fold, same post ID,
comment ID, parent-child edge, shared parent/sibling group, and direct
reply-thread overlap are all zero. The known direct exact/near-text checks from
G.3.1 also remain zero.

| Fold | FB train root/reply | FB validation root/reply | Shared post/comment | Parent-child edges | Shared sibling-parent groups |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 137 / 57 | 96 / 56 | 0 / 0 | 0 | 0 |
| 1 | 160 / 82 | 73 / 31 | 0 / 0 | 0 | 0 |
| 2 | 169 / 87 | 64 / 26 | 0 / 0 | 0 | 0 |

An empty `parent_comment_id` is treated as a root only when the exact source
row says `record_type=comment`. A reply missing a parent ID, an absent field,
an ambiguous value, or an unresolvable source row makes the audit BLOCKED;
none occurred in these 346 examples. Thread ancestry beyond a verified
direct-parent relation is not guessed when the parent record is unavailable.

**Interpretation:** the new parent/thread check does not invalidate the frozen
Facebook folds, so the G.3.1 direct-isolation development protocol remains
usable for FB-only work. It does not resolve unknown post identity for the
legacy source. Consequently FB+legacy results are not independent or
provenance-isolated estimates.

## Legacy effect from sealed OOF predictions

No model was refit. The 1,384 saved G.3.1 predictions (346 IDs × four trials)
were read from their sealed artifact. Confusion matrix rows are true labels and
columns are predicted labels in order POS, NEG, NEU.

```text
A: [[48, 45,17], [10,127, 7], [22, 31,39]]
B: [[56, 39,15], [25,109,10], [23, 36,33]]
C: [[48, 42,20], [10,127, 7], [18, 33,41]]
D: [[59, 35,16], [25,108,11], [24, 34,34]]
```

| Trial | Macro-F1 | Accuracy | POS P/R/F1 | NEG P/R/F1 | NEU P/R/F1 | Predicted POS/NEG/NEU |
| --- | ---: | ---: | --- | --- | --- | --- |
| A — FB original | 0.5802 | 0.6185 | .600/.436/.505 | .626/.882/.732 | .619/.424/.503 | 80/203/63 |
| B — FB + legacy original | 0.5427 | 0.5723 | .538/.509/.523 | .592/.757/.665 | .569/.359/.440 | 104/184/58 |
| C — FB basic | 0.5876 | 0.6243 | .632/.436/.516 | .629/.882/.734 | .603/.446/.513 | 76/202/68 |
| D — FB + legacy basic | 0.5529 | 0.5809 | .546/.536/.541 | .610/.750/.673 | .557/.370/.444 | 108/177/61 |

For A→B, **44** comments went correct→wrong and **28** went wrong→correct,
net 16 fewer correct predictions. By true class, correct predictions changed
POS +8, NEG -18, NEU -6. For C→D the corresponding counts are 43 and 28, net
15 fewer correct; POS +11, NEG -19, NEU -7.

The prediction transitions directly support the observed POS shift:

| Transition | A→B | C→D |
| --- | ---: | ---: |
| NEG→POS | 32 | 31 |
| NEU→POS | 10 | 14 |
| POS→NEG | 9 | 8 |
| POS→NEU | 9 | 5 |
| NEG→NEU | 11 | 14 |
| NEU→NEG | 15 | 12 |

The model predicts POS 24 more times in B than A, and 32 more times in D than
C. POS recall rises, while NEG and NEU recall fall in both comparisons. The
loss is therefore concentrated in NEG/NEU recognition, not a uniform decrease
across classes. Fold-level Macro-F1 also falls in every fold when legacy is
added: A→B `-.0348, -.0347, -.0454`; C→D `-.0390, -.0217, -.0346`.

These are observed changes, not causal attribution. The legacy training labels
are more POS-heavy and less NEU-heavy than Facebook overall, although
`class_weight=balanced` is in use. The legacy language is also markedly
longer and more underscore-heavy. Both label-feature differences and the
unverified source/annotation process could contribute; this analysis cannot
separate them. No result establishes that a particular legacy label is wrong.

## Source and text diagnostics

| Profile | FB development (346) | Legacy human (186) |
| --- | ---: | ---: |
| POS / NEG / NEU | 110 / 144 / 92 | 79 / 77 / 30 |
| Median characters | 126.5 | 508 |
| Under 20 characters | 16 | 7 |
| Rows with negation cue | 110 | 118 |
| Rows with emoji/codepoint or alias | 93 | 34 |
| Rows containing `_` tokens | 2 | 63 |
| Candidate teencode pattern* | 62 | 35 |
| Basic normalization changed | 64 | 0 |

*The teencode count is a fixed descriptive cue list (`ko`, `khum`, `hong`,
`hok`, `hem`, `đc`, `dc`, `vch`, `vl`, `j`), not a language detector or label
rule. The greater legacy length and underscore frequency and lower emoji rate
are measurable source-style differences; their effect on the model is not
isolated causally. Only two Facebook rows contain underscore tokens, so that
Facebook error slice is too small for a stable conclusion.

Basic normalization changed 64 Facebook inputs and no legacy input. It changed
9 OOF predictions in A→C and 13 in B→D; only 1 and 3, respectively, were rows
whose own displayed text changed. Changes to training examples can also alter
the fitted TF-IDF/SVM representation for unchanged validation text. The small
Macro-F1 gains (+0.0074 FB-only and +0.0102 augmented) are descriptive on these
same three folds, not an independently validated improvement. No normalization
rule was adjusted from validation results.

The 186 legacy rows have no blank text and no exact or near duplicates within
the set under the pinned audit. Seven short rows (<20 characters, one <10)
were placed in a local human recheck list as context-dependence cues. This does
not mark them incorrect. Sixty-three rows contain underscores; the marker is
retained and is not treated as proof of correct word segmentation. There is
not enough provenance/context to automatically classify comments as
out-of-domain. Legacy `overall` labels were never used.

## Local artifacts and reproducibility

The following outputs are local/gitignored and contain IDs or comment text:

- Parent/thread summary and ID-level source mapping:
  `outputs/phase_g32/parent_audit_04/`.
- Confusion matrices, class metrics, fold/source diagnostics, and ID-level
  errors: `outputs/phase_g32/error_analysis_v3/`.
- `needs_human_recheck.local.csv` is a review aid only; it does not edit labels.
- Movie/post aggregates and feature-slice metrics are local CSVs.

Tracked scripts are `scripts/audit_parent_threads_g32.py` and
`scripts/analyze_legacy_effect_g32.py`; neither fits a model or calls an API.
Previous artifacts from G.3, G.3.1, Phase E, and the frozen manifests remain
unchanged. G.3.2 does not claim an independent test.
