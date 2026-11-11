# Phase I.1 quality audit

**PENDING_HUMAN_QUALITY_APPROVAL**. Old Phase I pilot is paused; no new official AI inputs, API calls, labels, crawl or research training were produced.

Audited 39,842 records. Technical/domain/repetition statuses are proposals, not validated semantic judgments. No quality precision/recall is claimed.

| Metric | Count |
| --- | ---: |
| KEEP | 20,014 |
| REVIEW | 19,828 |
| Automatic EXCLUDE | 0 |
| Structural EXCLUDE candidates | 0 |
| Repetition risk | 2 |
| OFF_TOPIC_LIKELY | 0 |
| UNCERTAIN | 17,208 |
| CONTEXT_NEEDED | 1,932 |
| Colon-wrapped alias replacements | 0 |
| Bare alias review rows | 501 |
| Teencode replacements | 0 |
| Teencode matches preserved | 11,347 |
| Long text >1000 requiring review | 401 |
| Eligible unlabeled pool | 14,355 |
| Pilot candidates | 500 |
| Human audit rows | 200 |

## Per-source aggregate diagnostics

```json
{
  "facebook": {
    "alias_replacements": 0,
    "alias_rows": 0,
    "domain": {
      "CONTEXT_NEEDED": 1932,
      "IN_DOMAIN_LIKELY": 5764,
      "UNCERTAIN": 2458
    },
    "exclude_candidates": 0,
    "lengths": {
      "median": 50,
      "over_1000": 89,
      "over_2000": 9,
      "over_256": 805,
      "over_512": 249,
      "p90": 218,
      "p95": 344,
      "p99": 876
    },
    "mixed_script_signal": 15,
    "quality": {
      "KEEP": 5655,
      "REVIEW": 4499
    },
    "repetition_risk": 0,
    "rows": 10154,
    "technically_valid": 10154,
    "teencode_preserved": 3180
  },
  "legacy_29k_unverified": {
    "alias_replacements": 0,
    "alias_rows": 0,
    "domain": {
      "IN_DOMAIN_LIKELY": 14938,
      "UNCERTAIN": 14750
    },
    "exclude_candidates": 0,
    "lengths": {
      "median": 78,
      "over_1000": 312,
      "over_2000": 24,
      "over_256": 3694,
      "over_512": 1197,
      "p90": 297,
      "p95": 454,
      "p99": 1044
    },
    "mixed_script_signal": 15,
    "quality": {
      "KEEP": 14359,
      "REVIEW": 15329
    },
    "repetition_risk": 2,
    "rows": 29688,
    "technically_valid": 29688,
    "teencode_preserved": 8167
  }
}
```

## User examples and failure analysis

Phase I KEEP had no domain or internal-repetition gate. The provided Saqar-term example exists in the frozen corpus; new exact-block coverage raises repetition review risk. Its numeric evidence is below, without comment text or IDs. The term is used only to locate the supplied example, never as a filtering feature.

```json
[
  {
    "repetition_ratio": 0.605,
    "longest_repeated_span_tokens": 32,
    "repeated_block_count": 19,
    "repetition_risk": true,
    "repetition_status": "REVIEW",
    "phase_i_quality_status": "KEEP"
  }
]
```

The supplied laughing alias occurs in 47 rows as a bare name; no colon-wrapped form occurs. Bare names are preserved and flagged rather than guessed. All six supported colon-wrapped aliases produced zero actual replacements in this corpus. There is no evidence of an import/crawl mutation in Phase I: raw strings match its master contract; the earlier origin of bare aliases remains unverified.

## Review and limitations

The 501 bare-alias rows are held for review, including 47 with the provided
laughing-name example. Another 53 rows are symbol/emoji-only context cases;
1,932 short replies require parent context. All 401 texts above 1,000 characters
are retained intact and proposed for review. No actual OFF_TOPIC_LIKELY or
EXCLUDE candidate was emitted; 17,208 UNCERTAIN cases need evidence rather than
an inferred off-topic label. The supplied repeated example has 60.5% repeated
coverage, below the 65% strong-candidate gate, so remains REVIEW.

The preview pilot contains 493 legacy and 7 Facebook rows after the inherited
development-post/test exclusions and new review gates. This reflects pool
availability and proportional seeded sampling, not a recommended training
distribution. Source balance and missed off-topic cases remain points to inspect
before approval. Counts of KEEP or REVIEW alone do not establish improvement.

Validation: `python -m unittest discover -s tests` in `.venv-phase-e` ran
278 tests: OK, 1 skipped. New regressions cover the repeated-block failure,
long-period repetition, URL/identifier protection, alias preservation, negation,
ambiguous teencode/underscores, stretched/emoji emphasis and script-neutral
domain handling. Aggregate integration checks confirm old artifact hashes,
raw/human decisions, empty human quality cells and candidate eligibility.

Rules are described in [preprocessing rules](PHASE_I1_PREPROCESSING_RULES.md). Domain cues cannot establish semantic relevance or reliable off-topic prevalence. In particular, verified film-post provenance can still contain unrelated conversation; inspect provenance-only KEEP cases. Script mixture is only a script signal, not verified multilingual content. No names, identities, viewpoints or scripts are blacklisted. Exact repetition heuristics can miss paraphrased spam and can flag deliberate quotation; candidate statuses require review. Near-duplicate candidate generation retains the Phase I high-frequency-shingle limitation.

The 200-row stratified audit includes source, quality, long text, repetition, alias and domain strata when present. No EXCLUDE candidate stratum existed. Human decisions are blank. Quality accuracy is unknown until genuine review. The pilot uses a fixed seeded shuffle, no fixed Facebook/legacy quota, only KEEP plus inherited and fresh leakage checks. It remains unapproved.

Local artifacts:

- `outputs/phase_i1/v2/quality_review_200.csv` — fill human_quality_decision only.
- `outputs/phase_i1/v2/quality_review_coordinator.local.jsonl` — full evidence/provenance.
- `outputs/phase_i1/v2/pilot_500_candidate.csv` — preview only.
- `outputs/phase_i1/v2/annotation_pool.local.jsonl` — eligible pool.
- `outputs/phase_i1/v2/quality_evidence.local.jsonl` — repetition/domain/underscore evidence.
- `outputs/phase_i1/v2/alias_before_after.local.jsonl` — replacement examples (empty when no valid aliases).
- `outputs/phase_i1/v2/summary.json`, `selection_manifest.local.json`, `protected_inputs.local.json`, `manifest.json`.

All comment-bearing artifacts are Git ignored. All 39,842 raw strings and all human decisions match Phase I. Snapshot hashes confirm old Phase I/master/human/test artifacts were preserved. The existing test guard was invoked without relaxation.
