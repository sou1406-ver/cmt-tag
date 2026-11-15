# Historical sentiment pilot: A/B comparison, adjudication and provenance mismatch

Date: 2026-11-15. Development pilot: 160 random-stratified and 40 deliberately difficult examples. Not an independent Gold Test.

## Task definition and guideline versions

Project V2 targets the overall sentiment expressed by the author in `text_clean`, toward any subject, not only the film. V1 labels targeted film sentiment under V2.0/V2.1 and are not interchangeable with these labels. No V1 label migration or pooling was performed.

The unchanged manifest pins `SENTIMENT_GUIDELINE_V3_1_PROPOSED.md`, SHA `f079ce7b5ecedd6242d99808ee0b010b28ea6f8b8afc4ba01f7cf86552d08433`, with `PROPOSAL_NOT_APPROVED` / `DRAFT_GUIDELINE_SOURCE_MISSING`. Workbook B retains a DRAFT header and PROPOSED reference. However, the actual A/B delivery package's `DOC_TRUOC_KHI_GAN.txt` instructs annotators to read the accompanying `SENTIMENT_GUIDELINE_V3_1.md`, SHA `2ba9f0ec3c755754181a194c3f7ef4bd9dde200d0f3726de7be7b20125583a81`, rather than PROPOSED. The packaged file matches that SHA. The user confirms annotators read this accompanying file. Thus the manifest/header and delivered/read guideline disagree. Do not attribute the Kappa to validation of only one version. Original manifests, decisions and metrics remain unchanged. See [changelog](guidelines/GUIDELINE_CHANGELOG.md).

## Original A/B decisions

Both workbooks passed validation: 200 unique expected IDs, unchanged text and valid labels. All original REVIEW decisions have notes. A/B provenance and AI assistance are unverified; these numbers describe workbook agreement, not verified independent human inter-annotator reliability.

- Agreement: 144/200 (72%).
- Five-decision Cohen's Kappa: 0.597339565; 56 disagreements.
- Sentiment-only Kappa: 0.777762894; agreement 137/158 (86.71%). This subset retains 79% of the pilot and does not replace the primary five-decision result.

| Decision | A | B | Final |
|---|---:|---:|---:|
| POS | 27 | 27 | 31 |
| NEG | 84 | 86 | 92 |
| NEU | 56 | 71 | 55 |
| REVIEW | 16 | 16 | 16 |
| EXCLUDE | 17 | 0 | 6 |

Original confusion matrix: rows A, columns B.

| A / B | POS | NEG | NEU | REVIEW | EXCLUDE |
|---|---:|---:|---:|---:|---:|
| POS | 22 | 0 | 2 | 3 | 0 |
| NEG | 0 | 74 | 8 | 2 | 0 |
| NEU | 2 | 9 | 41 | 4 | 0 |
| REVIEW | 3 | 3 | 3 | 7 | 0 |
| EXCLUDE | 0 | 0 | 17 | 0 | 0 |

## Adjudication

The user reviewed all 56 disagreements and a seeded random sample of 20 agreements. All final labels were initially blank. The user explicitly confirmed that unchanged agreement rows retain A=B: 17 blank agreement rows were recorded as confirmed, and three sampled agreements were changed. No blank disagreement was inherited automatically.

Final coverage: 200 decisions; 76 reviewed decisions and 124 unchanged agreements outside the review sample. No pending decisions. There are 178 POS/NEG/NEU records, 16 REVIEW and six EXCLUDE. REVIEW and EXCLUDE remain outside three-class training; no training or dataset activation was performed.

Eleven explicitly selected REVIEW decisions lacked per-row reasons. The user authorized retaining those labels and recording that no per-row reason was supplied. The user also stated that REVIEW cases mostly lack context; this general statement was not fabricated into reasons for individual records.

A/B workbooks, their original labels and pre-adjudication Kappa were preserved. User decisions and the normalization of explicitly confirmed blank agreement rows were recorded separately with input hashes.

## Limits and local files

For this historical pilot, approval and provenance were unresolved at delivery. Completed adjudication does not repair the manifest/delivery mismatch, establish annotation independence, or create Gold. The enriched difficult-case sample cannot estimate corpus-wide label proportions.

Local-only outputs: `outputs/sentiment_pilot_v3_1/comparison_received_20261115/`: original A/B snapshots, `agreement.json`, `adjudication.xlsx`, user confirmation history, and `adjudicated/pilot_final_decisions.local.csv` plus `pilot_trainable.local.csv`. No comment text, record IDs or per-record labels are included in this public report.

## Superseded A/B batch plan (2026-11-15)

The five-batch human-annotation plan is superseded by [the active AI-web labeling + user-review protocol](annotation/QUY_TRINH_GAN_NHAN.md). Batch 1 was prepared but **not delivered**; its blank A/B workbooks must not be handed out. No additional A/B batches will be delivered. The previously proposed small-source supplement is also superseded, not a pending action.

The selection of 1,000 records in `outputs/annotation_round_01/` remains unchanged for reuse by the new protocol. Four V2 exports contained 12,795 records; the sealed selection used KEEP, pilot-post/ID, reserved and exact/near duplicate exclusions, leaving 9,590 eligible records, then a 30/post cap. The historical batch 1 partition contains 200 records, 61 posts and 49 movie_id values: Maybe You Never Watched This Movie 130; Chê Phim Review 52; XEM PHIM & BÌNH PHIM 6; Cuồng Phim 6; KhenPhim 6. These counts describe the abandoned partition, not the new T/U sets.

All original pilot IDs, labels, selection/annotation manifests, old snapshot `b25482675c3a6387321f281579e318565999fd3a579e12dadc3897938bb39714`, Gold V1 and canonical remain unchanged. The previous official guideline is archived as `guidelines/history/SENTIMENT_GUIDELINE_b2548267.md`. The new official guideline removes operational workbook/process sections and the goosebumps example, and adds score rules. Its exact SHA is recorded in the changelog and the active protocol's fixed-input section.

The earlier guideline/documentation update did not execute the protocol. In the subsequent authorized task, only the T/U portion of step 1 and the blind-50 export of step 2 were performed, as recorded below. No E selection, C split, AI chunks/calls/labeling, imports, calibration, model training or evaluation occurred. `AI_LABEL_PROMPT.md` has not been supplied; no prompt was invented. Pilot label SHA provenance is not silently migrated to the new guideline.

## Protocol steps 1–2: post-disjoint T/U and blind-50 export

From the unchanged 1,000-ID selection, seed 20261115 selects randomized whole posts within source strata. T represents each of the five sources with at least one post; the remaining budget is allocated by available source-stratum size, stopping at the nearest count on that randomized path. This yielded exactly 200 T records (10 posts, 10 movie_id) and 800 U records (51 posts, 42 movie_id). No text/sentiment cues are used to choose posts.

| Source | T | U |
|---|---:|---:|
| Maybe You Never Watched This Movie | 78 | 582 |
| Chê Phim Review | 32 | 218 |
| Cuồng Phim | 30 | 0 |
| KhenPhim | 30 | 0 |
| XEM PHIM & BÌNH PHIM | 30 | 0 |

The three small sources each have only one post in the selection. Representing all sources in T places each such post wholly into T; they cannot also appear in U. T therefore overrepresents these sources and must not be described as a representative estimate of natural corpus proportions. Three movie_id values occur in both sets; only post separation is required. ID, post, normalized exact and existing token-trigram near-duplicate checks across T/U all return zero, including raw/clean text variants. The near rule is Jaccard >=0.9 at normalized length >=40 characters, not a guarantee against all semantic similarity.

A fresh directory contains 50 random T IDs in shuffled order and one blank workbook with only `comment_id,text_clean,label,note`. No source/post/movie, prior labels or AI predictions are embedded. The user has not yet labeled/imported these records; no labeled hash lock exists. New snapshots match the official guideline SHA `2e4ba18c3c12c97b3bf4c33f39e11a87a684c71af1459e671860aec046d9568e`. E/C are not created pending user-supplied example IDs. No step 3 or later was performed. Gold V1, canonical, old pilot labels and the original selection remain unchanged.

Local files: `outputs/annotation_tu_01/REPORT.md` contains full source/post/movie distributions; `outputs/annotation_blind_50_01/T_blind_50.xlsx` is the only workbook for the user. The T/U split is a test of this protocol, not independent Gold. Reproducibility and unit tests use metadata/fixtures; no model is run on T.
