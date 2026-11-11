# Phase I.3 format recovery and source sampling specification

Status: **PENDING_HUMAN_FORMAT_APPROVAL**. No transformation accuracy, AI
annotation, consensus, source-label validity or independent-test result is claimed.

## Sources and recovery evidence

The entire 38,833-occurrence I.2 unresolved inventory is audited locally, with
frequency, unique-token counts, source, length, shape and model-roundtrip outcome.
The local top-200 table is an audit aid, never a public corpus. Resource building
excludes reserved/planned-test source records and never reads sentiment labels
or legacy `overall`. The observed underscores support a segmentation-like format
hypothesis, but the original preprocessing provenance is unknown. Phase G.2
documents an externally supplied legacy CSV without a verified source or label
method. No tokenizer/library or uniform processing of all legacy rows was proved.

`plain_text_v3` reconstructs each view from immutable raw text. It uses the I.2
technical/explicit-compound normalization as a deterministic pipeline component,
not as an input artifact. Possible uppercase/name-shaped underscore tokens are
masked before that component, preserving them for inspection. Protected URL,
email, mention, hashtag, code and digit-containing identifiers remain intact.
Technical HTML decoding only accepts complete entities; fragmented encodings are
not guessed.

For other lowercase accented Vietnamese-shaped compounds, the installed offline
`underthesea==8.3.0` segmenter checks whether spacing the token and segmenting it
back yields the exact original compound. This is supporting lexical evidence,
not evidence that underthesea created the legacy data. Only whole-token matches
with successful shape and exact roundtrip are restored automatically. Model files
are hashed in the local provenance artifact; no package/model download, LLM call
or training occurs. The dependency already existed in Phase E and is explicitly
declared in `requirements-phase-i3.txt`. See the [official project](https://github.com/undertheseanlp/underthesea)
for the library; the recorded local version, not the latest branch, is used.

Confidence categories are categorical evidence statements, not calibrated scores:

- RESTORED_VERIFIED_SOURCE: requires an explicit format attestation bound to both
  source namespace and exact input checksum. No real source currently has one.
- RESTORED_HIGH_CONFIDENCE: reviewed lexical/emoji/technical rule or exact offline
  roundtrip plus shape gates. Requires human validation of semantic preservation.
- PROTECTED_IDENTIFIER: preserve protected structures and identifier-like forms.
- AMBIGUOUS_NEEDS_REVIEW: preserve possible names or ambiguous alias discussion.
- UNKNOWN_PRESERVED: preserve insufficiently supported forms.

The small CLDR-name mapping is extended with eight explicit common emoji names.
Only complete aliases are converted, with colon syntax or Vietnamese context.
Remaining punctuation, Unicode emoji, emoticons, negation and ambiguous teencode
are retained. Literal alias discussion and lowercase proper names remain risks;
the name-shape guard is not a general named-entity recognizer.

Each transform has source/result spans, rule, evidence, confidence category and
an offset where available. Explicit raw offsets belong to name-mask evidence.
Other offsets are labeled as masked-input or transformation-stage offsets; they
must not be interpreted as byte/character positions in original raw text.

## Independent decision layers

`format_status`, `technical_quality_status`, `domain_status`,
`repetition_status` and `annotation_eligibility` are separate. Unknown underscores
do not turn a record into spam or EXCLUDE. They can keep annotation eligibility
pending while domain/technical proposals remain KEEP. Structural repetition and
domain/context signals are recomputed on I.3 clean text and remain unvalidated.
No comment is shortened, split, or assigned a sentiment by these rules.

Exact/direct-near duplicates are recomputed. Human/test/planned-test exact groups
and direct neighbors remain outside the pilot. Old development-post and identity
guards remain active. Facebook archives without comment/post/URL metadata are
additionally held because post-level leakage cannot be checked. This is a
provenance hold, not an assertion of poor text quality. No transitive giant master
component is removed wholesale.

The Facebook funnel reports both independent rule counts and sequential removal,
plus a complete pairwise overlap matrix. Source-stratified pilot selection targets
up to 200 valid Facebook records, draws across shuffled post lists, then fills
remaining slots with eligible legacy records. It never introduces a filtered
record to meet quota. All records must pass exact/direct-near checks and existing
fail-closed test guards. This deliberately oversamples Facebook relative to the
eligible pool and is not a natural-distribution sample or independent test.

## Reproduce and validate

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/prepare_phase_i3.py
```

The immutable local output is `outputs/phase_i3/v3/`. It includes the corpus,
raw/I.2/I.3 comparison, complete token table, local roundtrip resource, model/source
provenance, Facebook funnel, duplicate pairs, pilot preview and coordinator.
The separate workbook is under `outputs/phase_i3/workbook_v3/`.

In `plain_text_validation_200.xlsx`, fill only `format_decision` and `human_note`
in Validation: ACCEPT means the transformation preserves content, REJECT means
it introduces a formatting/content error, UNSURE means insufficient evidence.
This is not sentiment/domain labeling. Raw I2 I3 contains full comparison text
and evidence, split across cells if needed to avoid Excel limits. Long main cells
retain full text; expand the formula bar or use F2 to inspect them.

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/import_format_validation.py --input outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx --output outputs/phase_i3/human_format_import_01
```

Importer requires all 200 decisions, unchanged IDs/text/evidence and saves a new
artifact. It does not alter sentiment, apply rejected changes automatically or
release AI inputs. Precision/accuracy needs genuine human review and a sampling
design appropriate to the estimate; this targeted sample is not population-random.

Final targeted format coordinator: `outputs/phase_i3/validation_v1/workbook_input.local.json`. Recreate it after the corpus build with `python scripts/prepare_format_validation_sample.py`; then run the bundled artifact-tool workbook builder on that input.
