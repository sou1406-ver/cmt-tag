# Phase G.3.1 — Giant component and direct leakage audit

**Status: direct-overlap audit passed; all four fixed development ablations ran.**
The original Phase G master graph remains immutable. This phase introduces a
separate, explicitly narrower evaluation protocol and does not relabel the old
full-component rule or change the frozen folds.

**G.3.2 correction:** the G.3.1 overlap checker listed `parent_comment_id`, but
the unified rows did not carry that source field. Its earlier zero count was
therefore not evidence about reply threads. Phase G.3.2 verifies it from each
exact source observation and adds the thread-level result; see
`docs/archive/PHASE_G3_2_REPORT.md`.

## Why the full-master graph became giant

The pinned Phase G master contains 39,842 records. The component cited in G.3
contains 10,275 records: 8,631 Facebook records across **17** Facebook post
IDs, and 1,644 records with unknown platform provenance. Recounting the
canonical master records gives 17 distinct Facebook post IDs; the earlier G.3
report's count of 14 was incorrect and is corrected there.

The graph edge ablation shows the main source of transitive growth:

| Edges included | Largest component | Components over 1,000 |
| --- | ---: | ---: |
| Identity only (post, URL, comment, frozen development group) | 2,103 | 2 |
| Identity + exact text | 10,115 | 1 |
| Identity + near-duplicate | 2,309 | 2 |
| All edge types | 10,275 | 1 |

Across the master, exact-text grouping creates 4,568 spanning links over 3,058
repeated exact-text groups; 1,312 groups have fewer than 40 characters. There
are 1,483 direct near-duplicate edges overall. These are structural counts,
not a claim that every edge is a false match. They do show that exact-text
bridges, including short repeated text, account for most of the giant
component's expansion; near-duplicate edges alone do not create a component of
that scale.

The G.3 bridge witnesses contain multi-edge paths through master records. A
path linking two fold sides is therefore not itself proof that their annotated
texts are duplicates. The audit distinguishes a direct pair that crosses a
fold from a transitive path through one or more other records.

## Direct checks on the unchanged folds

The same three Phase E folds were checked without changing group assignment.
Validation sizes are 152, 104, and 90. Per fold, the direct overlap counts
were all zero for:

- Facebook post ID, post URL, comment ID, parent comment ID, and the frozen
  development group.
- Exact text hashes across the full retained master aliases, both original
  and normalized views.
- Direct near-duplicate pairs at the pinned 0.90 token 3-gram Jaccard rule,
  including pairs from the full master alias graph.
- Exact and near-text overlaps between each validation fold and the 186
  legacy-human rows.

Thus the full-master component gate was stricter than direct cross-fold
isolation for the 346 Facebook examples. The legacy source has no verified
post/comment IDs, so same-post provenance for those 186 rows remains
**unverifiable**. Their observed exact/near overlap with validation is zero,
but this cannot prove they did not originate from the same posts. B/D are
therefore exploratory development augmentation, not a fully provenance-isolated
evaluation or an independent test.

The machine-readable, text-free audit is
`outputs/phase_g31/audit/component_and_fold_audit.json`. The original master,
G.3 artifacts, source labels, frozen split, and reserved test state were not
modified.

## Separate direct-isolation protocol and results

Protocol `direct_fold_isolation_v1` hard-checks known identity overlap,
full-alias exact-text overlap, and direct near-duplicate pairs across each
train/validation boundary. It reports full-master transitive connectivity as a
separate diagnostic rather than treating it as direct contamination. It keeps
the historical frozen folds because all measurable direct checks pass; it
does not invent new folds. All four models use the exact Phase E estimator and
fit vectorizers inside each fold.

| Trial | Training rows | Macro-F1 | Accuracy | POS recall | NEG recall | NEU recall | Fit seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A — Facebook, original | 346 | 0.580159 | 0.6185 | 0.4364 | 0.8819 | 0.4239 | 0.204 |
| B — Facebook + legacy, original | 532 | 0.542666 | 0.5723 | 0.5091 | 0.7569 | 0.3587 | 0.519 |
| C — Facebook, basic | 346 | 0.587578 | 0.6243 | 0.4364 | 0.8819 | 0.4457 | 0.183 |
| D — Facebook + legacy, basic | 532 | 0.552875 | 0.5809 | 0.5364 | 0.7500 | 0.3696 | 0.528 |

A reproduced the Phase E predictions and metrics exactly. On these same three
folds, basic normalization changed Macro-F1 by +0.0074 for Facebook-only and
by +0.0102 for the augmented comparison (D vs B). Adding legacy data changed
Macro-F1 by -0.0375 on original text (B vs A) and -0.0347 on basic text (D vs
C). The per-fold Macro-F1 values were:

| Trial | Fold 0 | Fold 1 | Fold 2 |
| --- | ---: | ---: | ---: |
| A | 0.5739 | 0.5098 | 0.6529 |
| B | 0.5391 | 0.4751 | 0.6075 |
| C | 0.5896 | 0.5079 | 0.6515 |
| D | 0.5506 | 0.4862 | 0.6169 |

These are three fixed development folds, not independent observations or a
final test. The small normalization differences are not evidence of a reliable
gain. The lower B/D scores also cannot establish that legacy labels are
intrinsically worse: the legacy source's origins and post identities remain
unknown. No hyperparameters, thresholds, labels, or folds were tuned.

## Reproduction and outputs

```powershell
python scripts/audit_phase_g31_component.py
python scripts/run_phase_g31_ablation.py
```

Artifacts are local and immutable under `outputs/phase_g31/audit/` and
`outputs/phase_g31/ablation/`. The result status is development-only; no
independent gold test was run. `outputs/phase_g3/ablation/` remains the original
strict-gate PARTIAL result and has not been overwritten.
