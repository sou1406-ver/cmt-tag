# Phase I.4 human quality validation protocol

## Current boundary

The corpus is TECHNICALLY_PREPARED and PENDING_HUMAN_REVIEW. Neither format
recovery nor domain/spam classification is human-approved. Phase I.4 creates no
new preprocessing version, sentiment labels, official AI inputs or final pilot.
It preserves the I.3 corpus, 650 human decisions and all existing test guards.

Format and domain are different tasks. The I.3 format workbook asks whether raw
content survives the conversion. The new semantic workbook asks whether the
comment discusses film and whether structural spam is present. A well-formatted
spam message may receive ACCEPT for format; a badly formatted film comment is
not thereby OFF_TOPIC. Domain OFF_TOPIC is never sentiment NEU.

## Review files

1. Complete the existing
   `outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx`:
   ACCEPT / REJECT / UNSURE plus notes, with no sentiment edits.
2. Open `outputs/phase_i4/workbook_v2/semantic_quality_review_200.xlsx`.
   Fill only human_domain_decision and human_note on Review.

Domain choices:

- IN_DOMAIN: film evaluation, film information/questions, characters, acting,
  script, visuals, sound or viewing experience attributable to the film.
- OFF_TOPIC: clear unrelated content, such as a personal event/food-price story
  that does not discuss the film. Do not decide from missing keywords.
- CONTEXT_REQUIRED: actual parent/post content is needed; do not invent it or
  inherit the post author's sentiment.
- UNSURE: insufficient evidence even after reading the available text.

For explicit spam review, start the note with [SPAM], [NOT_SPAM] or
[SPAM_UNSURE] if you have made that assessment. This is optional structured
evidence; absence of a marker means spam remains unreviewed. OFF_TOPIC is not
automatically spam. Film-related spam may still be IN_DOMAIN with a [SPAM] note.
Long reviews, quotations and repeated emoji are not automatically spam. Read the
complete value using the formula bar/F2 when display height is capped.

Review contains one full text_annotation column. Raw & Evidence contains the
same IDs, raw/clean text, verified-or-unknown source description and rule evidence.
Instructions explains the boundaries. No human sentiment label or legacy
overall value is shown. All proposals are PROPOSED_UNVALIDATED. In particular,
film-post metadata alone is displayed as UNCERTAIN rather than proof of relevance.
This presentation distinction is not a newly validated semantic classifier.

## Sampling and holdout

The fixed seed is 20261116. Reserved/planned-test IDs, exact groups and detected
direct-near neighbors are excluded, as are I.3 format-review IDs and their exact
groups/direct-near neighbors. Sampling units are one stable representative per
exact group. Unknown legacy post provenance limits claims of post independence.

The disjoint sampling frames are 50 random KEEP representatives and 150 REVIEW
representatives. REVIEW is stratified by source, domain proposal, repetition,
film metadata, very short/long text and formatting changes. Quotas are allocated
round-robin across strata and drawn without replacement. The manifest records
N_h, n_h and exact n_h/N_h inclusion probabilities within this representative
frame. These are not inclusion probabilities for all 39,842 raw observations.
Do not present unweighted review error rates as natural corpus prevalence.

Forty additional records are reserved for future quality-rule validation, with
disjoint review IDs/exact groups/direct-near links and Facebook post IDs. No
second workbook or holdout labels were issued. This is a development quality
holdout, not the independent sentiment test. Keep it away from rule tuning;
post independence remains unknown for identity-incomplete sources, including legacy and Facebook archives. If real review identifies fixes,
compare on unchanged review IDs and then check fixes on that separate holdout.
Do not claim improvement solely on cases used to devise a rule.

## Validation, import and metrics

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/prepare_phase_i4.py
.\.venv-phase-e\Scripts\python.exe scripts/import_format_validation.py --input outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx --output outputs/phase_i4/format_import_01
.\.venv-phase-e\Scripts\python.exe scripts/import_semantic_quality_review.py --input outputs/phase_i4/workbook_v2/semantic_quality_review_200.xlsx --output outputs/phase_i4/domain_import_01
```

Existing outputs are immutable. Re-run preparation with a new --output path to
refresh the format summary after real review. Import requires the sealed
coordinator checksum, exact IDs/text/proposals/raw evidence and complete valid
human decisions. It rejects formulas, missing IDs, changed text, sentiment values
in domain columns and blank decisions. Outputs append separate decision ledgers;
they never overwrite the corpus, sentiment labels or input workbook.

Format summaries report ACCEPT/REJECT/UNSURE by source/rule/confidence category
only after completion. Per-rule rejection counts are co-occurrence diagnostics,
not proof that a particular operation caused an error. Notes identify actual
failure mechanisms. Acceptance in this targeted sample is not corpus accuracy.

Domain metrics run only after complete human review. They report the proposal
vs human confusion table, source counts, OFF_TOPIC precision/recall on definite
IN_DOMAIN/OFF_TOPIC human cases, context/unsure abstentions and OFF_TOPIC found
inside KEEP. Undefined precision/recall is null. False exclusions count only
human IN_DOMAIN plus explicit [NOT_SPAM] against an EXCLUDE proposal; absence of
spam evidence cannot prove a false exclusion. Spam markers remain separate from
domain decisions. Metrics are unweighted reviewed-sample diagnostics. No current
domain/spam metrics exist.

## Annotation release gate

`require_release` and `export_approved_inputs` require real complete format,
domain and >=40-record quality-holdout imports, disjoint review/holdout IDs,
matching corpus/import hashes, resolved issues and an explicit reviewer/date
approval tied to exact candidate bytes. Domain/holdout imports must refer to the
same frozen corpus. No approval or evidence is inferred from proposals.

Even after approval, the exporter rechecks 500 unique blind IDs, exact text,
human/test exclusions, duplicate groups/direct-near edges and existing fail-closed
guards. Only then can it write identical id,text_annotation files for Codex,
Claude and Gemini with a shared guideline checksum. These gates were not met or
invoked here. I.3's 101 Facebook candidates span only 3 posts and cannot represent
Facebook generally; doubtful legacy quality must not be used to fill quota.
