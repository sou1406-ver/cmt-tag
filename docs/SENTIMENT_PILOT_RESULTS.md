# V3.1 sentiment pilot: A/B comparison and user adjudication

Date: 2026-11-15. Development pilot: 160 random-stratified and 40 deliberately difficult examples. Not an independent Gold Test.

## Task definition and guideline versions

Project V2 targets the overall sentiment expressed by the author in `text_clean`, toward any subject, not only the film. V1 labels targeted film sentiment under V2.0/V2.1 and are not interchangeable with these labels. No V1 label migration or pooling was performed.

The user supplied [guideline V3.2](guidelines/SENTIMENT_GUIDELINE_V3_2.md) after this V3.1 pilot. The original decisions, adjudication and Kappa below are historical V3.1 results, not validation of V3.2. Some V3.2 examples differ from adjudicated V3.1 decisions; adopting V3.2 requires a separately recorded review, never silent relabeling. V3.1 bytes and manifest remain unchanged.

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

The exact guideline byte approval remains pending. Completed adjudication does not approve the guideline, establish annotation independence, or create Gold. The enriched difficult-case sample cannot estimate corpus-wide label proportions.

Local-only outputs: `outputs/sentiment_pilot_v3_1/comparison_received_20261115/`: original A/B snapshots, `agreement.json`, `adjudication.xlsx`, user confirmation history, and `adjudicated/pilot_final_decisions.local.csv` plus `pilot_trainable.local.csv`. No comment text, record IDs or per-record labels are included in this public report.
