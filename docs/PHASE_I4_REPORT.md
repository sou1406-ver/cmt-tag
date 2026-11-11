# Phase I.4 readiness and human quality review

**PENDING_HUMAN_REVIEW — not approved for AI annotation.** The I.3 format workbook
has 200/200 blank decisions and 200/200 blank notes on disk. Its IDs, raw/I.2/I.3
text and evidence were validated against the frozen coordinator. Status is
PENDING_HUMAN_FORMAT_REVIEW; acceptance rate, transformation accuracy and error
breakdowns remain unavailable. No human decision was supplied by the software.

## Corpus state

| Measure | Count/status |
| --- | --- |
| Raw records preserved | 39,842 |
| Technically readable KEEP proposals | 39,842 |
| Plain/protected format proposals | 34,499 |
| Records with unresolved format | 5,343 |
| Existing heuristic annotation candidates | 10,787 |
| Frozen I.3 quality proposals KEEP / REVIEW / EXCLUDE | 20,305 / 19,537 / 0 (unvalidated) |
| Existing human decisions / sentiment labels | 650 / 532 |
| New preprocessing rules/versions | 0 |
| Human-validated domain/spam judgments in this phase | 0 |
| Quality precision/recall or transformation accuracy | Not available |
| New final pilot / official AI input export | Not issued |

Technical readability is not proof of film relevance, preserved meaning or
eligibility for final annotation. The 1,917 earlier REVIEW-to-KEEP proposals and
26,561 recovered token occurrences remain unvalidated. Known limitations include
unknown original legacy provenance/processing, ambiguous names/identifiers and
emoji aliases, missing parent context, heuristic domain decisions and only three
identity-backed Facebook posts in the old candidate frame.

## New semantic audit

A single workbook contains 200 unique IDs: 100 Facebook and 100 legacy records.
It has 50 random KEEP and 150 stratified REVIEW representatives; both existing
repetition-risk cases are included. Sampling uses 25 disjoint strata in a
35,660-representative non-test frame. Every stratum records its frame count,
sample count and n_h/N_h probability. The proposal distribution is 72 IN_DOMAIN,
97 UNCERTAIN, 30 CONTEXT_REQUIRED and 1 OFF_TOPIC; **all are unvalidated proposals**,
not true dataset labels or prevalence estimates.

Metadata alone is not treated as evidence that a comment itself discusses film.
Existing repetition scores are reused unchanged; no named topic is added as a
spam rule. Format, technical quality, proposed domain, proposed spam and pending
annotation eligibility are separate. No legacy overall or sentiment decision is
used as a domain target or selection criterion. The workbook never shows those
labels. IN_DOMAIN does not require praise/criticism; OFF_TOPIC does not become NEU.

The main Review sheet shows one complete text_annotation and blank human domain/
note fields. Raw & Evidence holds full raw/clean text, source uncertainty and
rule evidence. Instructions explains off-topic, neutral film comments, missing
context, structural spam, valid long reviews and emoji emphasis. Explicit spam
notes use [SPAM]/[NOT_SPAM]/[SPAM_UNSURE]; blank notes are not spam ground truth.

The targeted sample is disjoint from the I.3 format-review IDs, their exact
groups/direct-near links and all reserved/planned-test sources/links. Forty
additional quality-rule holdout IDs are reserved separately, with no human labels
or extra workbook. Review/holdout IDs, exact groups, detected direct-near links
and available Facebook post IDs are separated. Post independence cannot be proved
where identity metadata is missing, including legacy and Facebook archives; this
is not an independent sentiment gold test.

## Tooling and gates

The format validator reports counts now and can report source/rule/confidence
breakdowns once real completed review exists. The domain importer checks the
sealed coordinator hash, exact coverage, full text/proposals/evidence and valid
domain choices. It rejects incomplete cells before writing imports or metrics.
The actual blank workbook was tested and rejected; no import/metrics directory
was created. Future confusion/precision/recall reports describe this reviewed
sample, with abstentions and undefined metrics made explicit; they are not natural
corpus error rates. No rule fixes or semantic improvement are claimed now.

Readiness is TECHNICALLY_PREPARED with release state PENDING_HUMAN_REVIEW. The
release guard requires complete real format/domain/quality-holdout imports,
matching checksums, disjoint review/holdout IDs, explicit human issue resolution
and corpus/candidate approval. The guarded future exporter also repeats blind
schema, human/test and exact/direct-near checks. No gate was automatically passed,
no final pilot was sampled and no Codex/Claude/Gemini input or prediction was issued.

## Local handoff

- Format workbook still needing decisions:
  `outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx`.
- New domain/spam workbook:
  `outputs/phase_i4/workbook_v2/semantic_quality_review_200.xlsx`.
- Sealed semantic coordinator and sampling probabilities:
  `outputs/phase_i4/v5/workbook_input.local.json`,
  `semantic_review_coordinator.local.jsonl`, `sampling_manifest.local.json`.
- Current blockers and null-metric evidence:
  `outputs/phase_i4/v5/format_validation_summary.json`, `corpus_readiness.json`.
- Unlabeled quality-rule holdout reservation:
  `outputs/phase_i4/v5/quality_holdout_reservation.local.json`.

Read [quality protocol and import instructions](PHASE_I4_QUALITY_PROTOCOL.md).
All comment text, row IDs, workbook/coordinator, decisions and predictions remain
local/Git ignored. Old corpus, human, master, reservations, frozen results and
checkpoint snapshots are hash-protected. The workbook has been checked for exact
200-ID/full-text/evidence roundtrip and blank human fields, and opens in Excel
read-only with 3 sheets, 201 Review rows, a filter table, frozen header and exact
domain dropdown. All three sheet previews were visually inspected.

Full regression result: **302 tests ran, OK, 1 skipped**. Additional real-data
checks verified source/old-artifact hashes, 200 full-text/ID/evidence rows, blank
human fields, stratum probabilities, disjoint quality holdout and rejection of
the actual blank workbook without creating metrics/import outputs. Evidence is
local in `outputs/phase_i4/verification_v1/checks.json`. Tests do not validate
semantic quality; that remains blocked on genuine human decisions.
