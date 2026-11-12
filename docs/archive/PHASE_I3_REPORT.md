# Phase I.3 recovery and sampling report

**PENDING_HUMAN_FORMAT_APPROVAL.** This is technical recovery plus a proposed validation sample. Human transformation accuracy is unknown. No LLM annotation, external API, crawl, SVM/Transformer training, label rewrite or official annotation release occurred.

## Token inventory and provenance

| Metric | Count |
| --- | ---: |
| Raw records audited | 39,842 |
| I.2 unresolved occurrences | 38,833 |
| Unique I.2 unresolved tokens | 6,045 |
| Restored old occurrences | 26,561 |
| Protected old occurrences | 8 |
| Remaining unresolved occurrences | 12,264 |
| Remaining unresolved records | 5,343 |
| Rows cleared of format ambiguity | 2,812 |
| Format-only REVIEW to KEEP proposals | 1,917 |
| Changed clean rows versus I.2 | 6,832 |
| New exact merge groups | 11 |
| New near-pair IDs | 21 |
| Pending pilot | 500 |

The complete 38,833 occurrences comprise 6,045 unique tokens: 38,830 occurrences are legacy and 3 Facebook. There were 5,630 I.2 comments whose sole quality-review reason was unresolved format. These are not 38,833 unique tokens or invalid comments. Local frequency rows include the top 200 tokens, source counts, token length, parts, shape and roundtrip result; raw examples remain in the private comparisons/coordinator.

Frequency bins across unique tokens: 2,666 occur once, 2,071 occur 2–5 times, 903 occur 6–20 times and 405 occur more than 20 times. Length bins: 5,383 unique tokens <=10 characters, 614 at 11–20 and 48 above 20. Shape candidates account for 37,050 occurrences; 1,681 remain unsupported by shape, 94 have ambiguous name/uppercase shape and 8 are protected identifiers. These are signals, not validated linguistic categories.

The exact outcome partition of the old inventory is:

```json
{
  "PROTECTED_IDENTIFIER": 8,
  "UNKNOWN_PRESERVED": 12163,
  "RESTORED_HIGH_CONFIDENCE": 26561,
  "AMBIGUOUS_NEEDS_REVIEW": 101
}
```

26,561 occurrences were restored; 8 were explicitly protected; 12,264 remain unresolved (12,163 UNKNOWN_PRESERVED plus 101 AMBIGUOUS_NEEDS_REVIEW). Thus 12,272 old occurrences were not converted, but they are not all format errors. The new unresolved inventory spans 5,343 records. 2,812 records clear their old ambiguity and 1,917 format-only quality REVIEW records now meet KEEP proposals after recovery. These are rule outcomes awaiting human confirmation, not proven false-review corrections. Removing format from the quality-status layer alone is not counted as successful recovery.

Source/library provenance remains unverified. The existing import/audit documentation identifies a third-party legacy CSV with unknown original processing. Underscore patterns and the offline roundtrip support recovery candidates but cannot identify the original tokenizer or show all legacy rows were segmented uniformly. No real RESTORED_VERIFIED_SOURCE event was generated. An attestation pathway exists only with source namespace, exact checksum and format evidence; fixtures test this boundary.

The installed underthesea 8.3.0 local word segmenter supports 2,814 candidate token types, with model hashes recorded locally. The pipeline rebuilds from raw using shape gates, protected regions, reviewed normalization and exact roundtrip evidence. It is not a larger hand-written dictionary and does not use sentiment labels. Case/name and ambiguous forms remain pending. [Recovery specification](PHASE_I3_PLAIN_TEXT_SPEC.md) documents risks and versioning.

## Signals, duplication and decision layers

All raw strings, IDs and 650 human decisions (532 sentiment labels) match I.2 and the frozen-source contract. Full-corpus deterministic raw reconstruction and clean idempotence passed. Old artifact hashes passed. Automated I.2/I.3 comparisons found zero rows losing detected negation, emoticons or Unicode emoji and zero rows with changed counts of ! ? . , : ; ( ). These are surface-preservation checks, not semantic accuracy. Full before/after/event evidence is local.

Technical quality, format, domain, repetition and eligibility remain separate. Unknown underscores do not imply spam or off-topic content. There are still 2 repetition-risk records, without truncation or propagated sentiment labels. Exact/direct-near duplicates were rebuilt; no human conflicts are merged and no whole giant component is discarded. New near-pair counts include representative effects.

```json
{
  "direct_near_duplicate_edges": 532,
  "direct_near_duplicate_rows": 1049,
  "exact_duplicate_rows": 3676,
  "exact_groups": 36166,
  "high_document_frequency_shingles_skipped": 2075,
  "near_duplicate_limit": "candidate generation skips shingles occurring in >256 records; may miss boilerplate-driven near duplicates",
  "near_duplicate_min_chars": 40,
  "near_duplicate_threshold": 0.9,
  "shingle_size": 3
}
```

## Facebook funnel and sampling repair

Counts below are nonexclusive and sequentially exclusive, respectively. Full pairwise overlaps are in facebook_funnel.json.

| Rule | Nonexclusive rows | Newly removed in sequence | Remaining |
| --- | ---: | ---: | ---: |
| human | 400 | 400 | 9,754 |
| same_development_post | 6,787 | 6,387 | 3,367 |
| test_protection | 298 | 298 | 3,069 |
| exact_duplicate | 3,322 | 1,924 | 1,145 |
| direct_near_duplicate | 141 | 54 | 1,091 |
| quality_review | 4,499 | 834 | 257 |
| format_unresolved | 0 | 0 | 257 |
| unverified_facebook_identity | 2,949 | 156 | 101 |
| other_guard | 141 | 0 | 101 |

Facebook starts at 10,154 records. The human step counts 400 annotated records (346 sentiment plus REVIEW/EXCLUDE), all overlapping the 6,787 development-post records; these counts cannot be added. For example, 1,398 exact duplicates overlap development posts and 1,956 overlap quality review. The complete overlap matrix is preserved locally.

I.2 already had 257 eligible Facebook versus 8,785 legacy records. Its pooled random sample produced 17 Facebook; that was mainly a sampling-design consequence of the 2.84% Facebook pool share, not proof that Facebook text was worse. Most Facebook exclusions originate in development-post reuse, duplicates and protected sources; the quality proposals are unvalidated. Format ambiguity removes zero Facebook records at this stage.

A provenance check found 156 of those 257 remaining Facebook records lack complete comment ID/post ID/URL identity: 99 lack post ID, while another 57 have incomplete other identity metadata. They are now held out, since comment/post identity and development/test post overlap cannot be fully checked for them. This additional identity hold tightens protection and is unrelated to sentiment or text quality. Only the provable-identity records are used to fill Facebook quota; no guard is relaxed.

Eligible-pool profile:

```json
{
  "emoji_rows": 1597,
  "facebook_posts": 3,
  "facebook_without_post_id": 0,
  "median": 96,
  "negation_rows": 3360,
  "p90": 296,
  "rows": 10787,
  "sources": {
    "facebook": 101,
    "legacy_29k_unverified": 10686
  },
  "teencode_rows": 2092
}
```

Pilot profile:

```json
{
  "emoji_rows": 82,
  "facebook_posts": 3,
  "facebook_without_post_id": 0,
  "median": 97,
  "negation_rows": 139,
  "p90": 308,
  "rows": 500,
  "sources": {
    "facebook": 101,
    "legacy_29k_unverified": 399
  },
  "teencode_rows": 115
}
```

The final Facebook allocation falls below the target of 200 because only 101 eligible identity-backed rows remain. It represents 3 distinct post IDs, with per-post selected counts [33, 33, 35]. These are not independent gold-test sources. The remaining pilot slots are eligible legacy records. Source stratification deliberately oversamples Facebook relative to the pool and changes the sampling distribution; future agreement/quality estimates must account for the design. Post/community/movie generalization remains limited. No human, reserved/planned-test or detected direct-duplicate records were used to top up quota.

## Format validation and local handoff

Final regression suite: **293 tests ran, OK, 1 skipped**. Source-bound recovery,
foreign-script preservation, name/identifier/URL/code protection, no negation or
emoji loss, long text, idempotence, source sampling and funnel overlap fixtures
are included. Full-corpus raw reconstruction/idempotence and human/raw integrity
were checked separately from unit fixtures. No semantic transformation accuracy
is inferred from either check.

The final XLSX opened successfully in Excel read-only: 3 sheets, 201 Validation
rows including the header, one filter table, frozen header and the exact
ACCEPT/REJECT/UNSURE dropdown. All three rendered sheets were visually checked;
both human input fields remain empty for all 200 IDs. Long cell values and all
comparison/evidence chunks passed round-trip verification without truncation.

The workbook has exactly 200 unique records, one I.3 text column on Validation, blank format_decision/human_note inputs and ACCEPT/REJECT/UNSURE choices. The comparison sheet preserves full raw, I.2, I.3 and transformation evidence. The targeted sample covers common/rare/multiple underscores, possible names, protected forms, aliases, negation, unchanged and long text across sources. Protected test-source rows were excluded from this human validation sample and from resource construction. It is not a population-random accuracy sample.

Current local outputs:

- `outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx`
- `outputs/phase_i3/v3/token_frequency.local.csv` and `top_200_tokens.local.jsonl`
- `outputs/phase_i3/v3/source_preprocessing_provenance.json` and `accepted_tokens.local.json`
- `outputs/phase_i3/v3/facebook_funnel.json`
- `outputs/phase_i3/v3/comparisons.local.jsonl`, `corpus.local.jsonl`, `annotation_pool.local.jsonl`
- `outputs/phase_i3/v3/pilot_500_candidate.csv`, duplicate evidence and selection/protection manifests
- `outputs/phase_i3/verification_v3/checks.json`

All comment-bearing artifacts remain Git ignored. Full text, IDs, transform evidence and blank human fields were round-trip checked. Earlier I/I.1/I.2 artifacts and models were not overwritten. The pilot remains unapproved. Unverified source processing, 5,343 unresolved records, possible lowercase-name/alias interpretation errors and the 3-post Facebook concentration are blockers to claiming complete recovery or broad semantic quality. Fill only format decisions/notes; [import instructions](PHASE_I3_PLAIN_TEXT_SPEC.md) save a new artifact without altering sentiment.

## Targeted validation sample coverage

The final validation sample adds explicit boundary-case anchors before filling source/format/length strata. This ensures names and protected identifiers are inspected, rather than relying on incidental random inclusion. Only the final coordinator under `outputs/phase_i3/validation_v1/` corresponds to the handoff workbook. Corpus-stage preliminary audit inputs are retained but are not the final handoff.

```json
{
  "available": {
    "common_token": 6568,
    "emoji_alias": 604,
    "facebook": 9856,
    "legacy": 29688,
    "long_text": 401,
    "multiple_underscores": 973,
    "negation": 10499,
    "possible_name": 84,
    "protected_identifier_or_region": 9,
    "rare_token": 2751,
    "sarcasm_emoticon_surface_cue": 1295,
    "unchanged_i2": 32712
  },
  "method": "boundary-case anchors then seeded source-format-length round robin; not population random",
  "seed": 20261115,
  "selected": {
    "common_token": 69,
    "emoji_alias": 4,
    "facebook": 66,
    "legacy": 134,
    "long_text": 95,
    "multiple_underscores": 20,
    "negation": 123,
    "possible_name": 2,
    "protected_identifier_or_region": 1,
    "rare_token": 44,
    "sarcasm_emoticon_surface_cue": 13,
    "unchanged_i2": 139
  }
}
```

These are surface cues, not verified sarcasm or name labels. The sample deliberately includes many long/risk cases; it is not representative of natural prevalence. The 200 format decisions and notes remain blank.
