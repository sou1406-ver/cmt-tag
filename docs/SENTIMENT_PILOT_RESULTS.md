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

## Protocol revision: new T/U, E/C and chunk export (2026-11-16)

The original all-source-T split and blind-50 workbook were unused. They were marked SUPERSEDED and removed from local outputs on 25 November 2026. With seed 20261115, the replacement assigns one of the three small-source posts to T and two to U, then allocates the remaining T budget in proportion to the two major sources' counts (660:250), keeping whole posts. This yields T=202 and U=798. The locked T and U labels are under `outputs/02_Du_lieu_va_nhan/Nguon_V2/`.

| Source | T | U |
|---|---:|---:|
| Maybe You Never Watched This Movie | 125 | 535 |
| Chê Phim Review | 47 | 203 |
| KhenPhim | 30 | 0 |
| Cuồng Phim | 0 | 30 |
| XEM PHIM & BÌNH PHIM | 0 | 30 |

T: 12 posts / 11 movie_id. U: 49 posts / 39 movie_id. One movie_id is shared; post, ID, normalized exact and existing token-trigram near-duplicate overlap remain zero. T is a protocol test set, not independent Gold or an estimate of natural corpus source proportions.

E contains exactly the 41 user-provided pilot IDs. C is the 159-record complement. The final supplied recheck file contains 17 filled labels: each is used as USER_RECHECK_V_CURRENT; there are no blank-recheck exclusions. The remaining C labels are unchanged pilot final decisions; historical guideline provenance is not silently migrated. Seventeen rounded scientific-notation IDs were resolved only with unique exact-text match, matching old label and Decimal rounding consistency, with local mapping and byte-identical original input snapshots. No original pilot labels were overwritten.

The user's prompt contains exactly those 41 E examples and no C examples. The local-only file `docs/annotation/AI_LABEL_PROMPT.md` has SHA `528021b7b88bfacbc5eaba24b2e1bc4762248396ac2f7264acebddf558f77a17`; it is ignored by Git. Each output manifest pins that SHA and matching guideline snapshot. No real example text or per-record labels appear in this public report.

Thirteen two-column, shuffled CSV chunks were prepared: C=100+59; T=100+100+2; U=7×100+98. They contain only comment_id,text_clean. No provider request or step 4+ operation has occurred. A new blank blind-50 workbook belongs to the replacement T. Do not send T chunks to any AI before those new 50 blind labels have been imported and hash-locked.

Local outputs: `outputs/annotation_tu_02/REPORT.md`, `outputs/annotation_blind_50_02/T_blind_50.xlsx`, `outputs/annotation_ec_01/` and `outputs/annotation_chunks_01/`. Old artifacts, selection, canonical and Gold V1 remain unchanged. This supersedes the earlier 200/800 split and its source distribution; counts are not model or AI-labeling results.
