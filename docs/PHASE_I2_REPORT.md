# Phase I.2 plain-text and quality review report

**PENDING_HUMAN_QUALITY_APPROVAL**. All 39,842 records were processed from original raw strings with one versioned pipeline. No API, annotation, crawl or research model training was run. Existing I/I.1 artifacts and human/test contracts remain immutable.

| Metric | Count |
| --- | ---: |
| Raw records | 39,842 |
| Raw/label mismatches | 0 |
| Changed rows | 7,015 |
| Compound replacements | 15,481 |
| Emoji replacements | 753 |
| Unresolved records | 8,155 |
| Unresolved token occurrences | 38,833 |
| KEEP | 14,673 |
| REVIEW | 25,169 |
| EXCLUDE | 0 |
| Eligible pool | 9,042 |
| Unapproved pilot | 500 |
| Audit workbook rows | 200 |
| New exact merge groups | 4 |
| New direct-near pair IDs | 7 |
| Conflicting-human-label exact groups preserved | 0 |

## Format audit

Token categories count matches/protected spans, not unique comments:

```json
{
  "ambiguous_alias": 6,
  "emoji_alias": 759,
  "hashtag_protected": 6,
  "identifier_protected": 2,
  "unknown": 38827,
  "vietnamese_segmentation": 15481
}
```

20.47% of records still contain unresolved token formatting and remain REVIEW. These include unknown lexical compounds, names, technical forms or ambiguous aliases. They were not guessed or placed in the eligible pilot. Plain-text consistency is therefore achieved for eligible rows under the declared dictionary, not guaranteed for every corpus row.

The lexical table is explicitly reviewed but limited; it does not identify a tokenizer or guarantee the interpretation of every bare compound. Bare emoji conversion uses complete known aliases plus Vietnamese context, and can still confuse literal alias discussion. These risks require human inspection rather than assuming unit tests prove meaning preservation. No teencode spelling corrections were applied.

## Quality and duplicates

The unchanged I.1 domain/context/repetition proposals were recomputed on clean text; 2 structural repetition risks remain. No row was truncated or split into sentiment samples. Exact groups and direct-near pairs were recalculated, retaining all records and human conflicts. New pair-ID counts may partly reflect changes of exact-group representatives. Detection still skips high-frequency shingles as described in Phase I. Master transitive components remain diagnostic.

```json
{
  "direct_near_duplicate_edges": 516,
  "direct_near_duplicate_rows": 1017,
  "exact_duplicate_rows": 3665,
  "exact_groups": 36177,
  "high_document_frequency_shingles_skipped": 2073,
  "near_duplicate_limit": "candidate generation skips shingles occurring in >256 records; may miss boilerplate-driven near duplicates",
  "near_duplicate_min_chars": 40,
  "near_duplicate_threshold": 0.9,
  "shingle_size": 3
}
```

The seeded 500-row preview contains {'facebook': 17, 'legacy_29k_unverified': 483}. It is a development candidate list, not a source-balanced corpus or released AI input. The 200-row audit samples source, underscore/alias changes, unchanged text, long/repeated/context cases and negation cues. It is not a random estimate of corpus quality.

## Workbook and integrity verification

Full regression suite: 285 tests ran successfully, 1 skipped. This covers seven
new raw-to-plain/workbook fixtures as well as previous regression guards. Separate real-data
checks cover all raw/human rows and 200 workbook records; neither fixtures nor
successful Excel opening establish semantic correctness of every transformation.

The Review sheet contains exactly 200 unique IDs and one full text_annotation column, with status/reasons and two blank human input columns. Raw & Changes has the same IDs and unchanged raw text, clean text and transform events. Instructions explains quality decisions and how to read long cells. Raw strings and human decisions match all 39,842 Phase I records. Raw-to-clean reconstruction and clean-text idempotence were independently checked for every record. Old artifact snapshot hashes passed. The existing fail-closed guard was invoked for the new pool; planned-test source duplicates are additionally held out after normalization.

The artifact-tool process reported export but exited nonzero at shutdown. The resulting workbook was independently parsed: full raw/clean values and transforms match, no formulas or truncated cells, 200 blank decision/note pairs, freeze panes and dropdown present. Excel itself then opened it read-only successfully with 3 sheets and 201 Review rows. All three sheet previews were visually inspected. The final file is usable; no Excel repair dialog was reported.

Local current artifacts:

- `outputs/phase_i2/workbook_v1/quality_review_200.xlsx`
- `outputs/phase_i2/v2/corpus.local.jsonl`
- `outputs/phase_i2/v2/transforms.local.jsonl`
- `outputs/phase_i2/v2/review_coordinator.local.jsonl` and `workbook_input.local.json`
- `outputs/phase_i2/v2/direct_near_duplicates.local.csv` and `new_direct_near_pairs.local.csv`
- `outputs/phase_i2/v2/pilot_500_candidate.csv` and `annotation_pool.local.jsonl`
- `outputs/phase_i2/v2/summary.json`, selection/protection manifests.

All comment-bearing artifacts are Git ignored. Follow [spec and review/import instructions](PHASE_I2_PREPROCESSING_SPEC.md). Human decisions are blank, no quality metrics are inferred, and no official provider input was released.
