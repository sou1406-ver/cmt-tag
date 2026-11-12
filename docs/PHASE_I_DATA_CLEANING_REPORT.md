# Phase I — unified dataset, cleaning and annotation pilot

**Status: READY FOR EXTERNAL ANNOTATION; CODEX LABELING PENDING.** This phase
prepared local data only. It did not crawl, call an external API, label with an
LLM, train a model, or create an independent gold test.

## Sources and human-label provenance

The frozen Phase G master contains **39,842 records**: 10,154 with Facebook
platform provenance and 29,688 from `data_module1.csv`, whose original source
and `overall` labeling method remain unverified. All 39,842 `text_raw` values
were checked against the frozen master byte-for-byte at the string level; all
source identities and observations remain in the local unified corpus.

The 650 human decisions map to the three actual annotation rounds, not three
independent annotators:

| Round | Decisions | Sentiment labels | Other decisions |
| --- | ---: | ---: | ---: |
| Facebook pilot | 200 | included in 346 Facebook labels | REVIEW/EXCLUDE retained |
| Facebook multifilm | 200 | included in 346 Facebook labels | REVIEW/EXCLUDE retained |
| Legacy task 250 | 250 | 186 | 64 EXCLUDE |

Across the 532 human sentiment labels, the counts are **POS 189, NEG 221,
NEU 122**. The 400-row Facebook workbook has 346 sentiment labels, 50 EXCLUDE
and 4 REVIEW. The legacy task has 186 sentiment labels and 64 EXCLUDE. No human
decision was changed; the legacy `overall` values remain separate and are
explicitly marked unverified. The 532 rows are development annotations, not an
independent evaluation set.

The task mapping and human-import history were verified against their manifests,
the immutable source workbook/task snapshot and the pinned Phase E data contract.
The three original batches are identifiable as pilot, multifilm and legacy;
the two 200-row Facebook tasks each contain one user's decisions, not agreement
between multiple annotators.

## Text cleaning and quality

`text_raw` was preserved. `text_clean` and `text_annotation` are separate
views; the latter currently equals the former. `phase_i_basic_v1` applies only
NFC, valid semicolon-terminated HTML entity decoding outside URLs, whitespace
collapse, and removal of invalid control characters. It does not truncate long
comments. URL and mention text, names, capitalization, punctuation, emoji,
emoticons, negation, repetitions, teencode and underscores remain intact.

| Check | Result |
| --- | ---: |
| Rows with changed clean view | 1,186 (1,062 Facebook; 124 legacy) |
| Rows with NFC change | 34 |
| Rows with whitespace change | 1,158 |
| Rows with HTML entity detected | 0 |
| Rows with invalid control characters detected | 0 |
| Exact configured UI strings detected | 0 |
| Teencode corrections applied | 0 |
| Long comments truncated | 0 |

The NFC and whitespace counts overlap in 6 rows, so their sum is larger than the
number of changed rows. No high-confidence teencode replacement was justified;
`ko`, `k`, `khum`, `hok`, `đc`, `dc`, `j`, `z` and `vch` are detection cues only.
The same is true of underscore forms: no underscore was converted to a space.
Before/after examples are available only in the ignored local artifact.

| Source | Median characters | p90 | p95 | p99 | >256 | >512 | >1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Facebook | 50 | 218 | 345 | 876 | 806 | 249 | 89 |
| Legacy, provenance unverified | 78 | 297 | 454 | 1,044 | 3,694 | 1,197 | 312 |

Across the master there are 401 comments longer than 1,000 characters. No
comment was cut. Long-text, context and mixed-cue flags are review aids only;
they do not imply a sentiment label. 4,545 records received a context flag;
1,205 received a heuristic mixed-cue flag. In the quality decision layer,
39,175 are KEEP, 667 are REVIEW because a short reply may require parent
context, and 0 were automatically EXCLUDEd. These counts are separate from
human REVIEW/EXCLUDE labels.

The audit detected 8,090 rows with emoji or emoticon signals, 11,796 emoji
codepoints, 1,506 emoji aliases and 1,607 emoticon occurrences. Teencode cues
occur in 6,666 rows (11,347 matches); negation cues occur in 10,550 rows
(17,668 matches). Underscores occur in 9,024 rows (55,092 tokens). All remain
in annotation text; these are surface-signal counts, not sentiment evidence.

Exact normalized-text grouping found 3,661 duplicate rows among 36,181 exact
groups; all rows remain in the corpus. Direct near-duplicate diagnostics found
510 token 3-gram Jaccard edges at threshold 0.90, spanning 1,005 rows. This uses
a bounded candidate generator that skips shingles present in more than 256
records, so boilerplate-heavy near duplicates may be missed. The transitive
Phase G master group is retained for audit but is not used to discard its large
component.

## Blind pilot and test protection

After human-row, human-post, exact duplicate, detected direct near duplicate,
quality-review, master-review-flag and planned-test-source filters, the
annotation pool contains **30,184** eligible rows: 1,088 Facebook and 29,096
legacy. The 500-row pilot is selected with fixed seed `20261111`, balanced by
source (250 each), then round-robin stratified by length and presence of emoji,
teencode, negation, underscore and context cues. It is not a natural source
distribution sample and is not stratified by movie because legacy movie IDs are
not verified. Selection never reads a sentiment label or `overall` value.

The pilot has 184 short, 179 medium and 137 long comments; 208 contain emoji or
emoticons, 200 contain teencode cues, 225 contain negation, 63 contain
underscores and 21 have a context flag. The selected set has **0 exact duplicate
rows and 0 detected direct near-duplicate edges**. It contains 250 Facebook
and 250 legacy records. The identical UTF-8 files
`pilot_500_annotation_input.csv`, `claude_input.csv` and `gemini_input.csv` each
have exactly `id,text_annotation`; all three have the same SHA-256. They omit
labels, `overall`, platform/source, movie/post metadata and model outputs.

Phase G's blind-test manifest is **PARTIAL** with 0 of 180 rows reserved and no
reservation file. We did not claim an independent test exists. All 8 Facebook
posts still awaiting exposure verification were held out of this pilot; no
selected row comes from those posts. No whole-post quarantine artifact existed
in the scanned Phase G output tree.

## Annotation status and local outputs

Codex did not have an authorized, configured model-inference provider/runtime
for this task. Therefore no Codex predictions were created and the status is
`LABELING_PENDING`. No Claude/Gemini request was sent. Use the V2.1 protocol and
the instructions in [`CLAUDE_ANNOTATION_INSTRUCTIONS.md`](annotation/CLAUDE_ANNOTATION_INSTRUCTIONS.md)
and [`GEMINI_ANNOTATION_INSTRUCTIONS.md`](annotation/GEMINI_ANNOTATION_INSTRUCTIONS.md).
The validator refuses incomplete IDs, invalid statuses/codes, mismatched
guideline/prompt hashes or missing model provenance. It creates no consensus
unless all three real prediction files and metadata sidecars validate.

All comment-bearing data, IDs, labels, examples, candidate manifests, duplicate
pairs and predictions remain local under the ignored path
`outputs/phase_i/v5/`. The tracked dictionary is
[`DATA_DICTIONARY_PHASE_I.md`](reference/DATA_DICTIONARY_PHASE_I.md). Rebuild with the
pinned local environment:

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/prepare_phase_i.py
```

The output is immutable; an existing `outputs/phase_i/v5/` causes the builder
to stop rather than overwrite it. Only code, config, protocol and aggregate
documentation are tracked.
