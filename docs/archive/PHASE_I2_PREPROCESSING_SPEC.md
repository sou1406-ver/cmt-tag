# Phase I.2 raw-to-plain specification

The authoritative source is `outputs/phase_i/v5/unified_corpus.local.jsonl`.
Every clean view is reconstructed from its immutable `text_raw`, never from the
Phase I.1 clean output. Record IDs, provenance, human decisions and test guards
remain intact. No shared `text_model` is created: future char-SVM/ViSoBERT input
can use plain text, while PhoBERT segmentation belongs to its own model adapter.

`plain_text_v1` first identifies URL, email, inline/fenced code, mention and
hashtag spans. Their contents remain exact. Outside them it applies NFC,
invalid-control removal, complete HTML entity decoding to fixed point, reviewed
emoji restoration, explicit lexical compound restoration and whitespace collapse.
It preserves punctuation, emoji repetition, case, negation and ambiguous
teencode. Long text is never truncated or split into labeled examples.

Emoji mapping uses the six explicit CLDR-based aliases from Phase I.1.
Colon-wrapped known aliases are restored. Bare known aliases require a complete
token match plus a Vietnamese lexical/diacritic context signal in the comment.
Embedded identifiers and protected spans are not rewritten. Unknown aliases or
bare aliases lacking context are preserved and flagged. This is a rule-based
serialization hypothesis, not proof of the source encoder. Review the real
before/after cases for literal alias discussion or code not enclosed in backticks.

The versioned `configs/plain_text_lexicon_v1.json` contains the user's four
confirmed examples plus an explicitly listed set of Vietnamese compounds
reviewed for lexical spacing. Only complete token matches are converted, keeping
letter case. No global underscore replacement occurs. This table is a lexical
proposal and does not identify the original tokenizer or prove every occurrence
is segmentation. IDs containing digits remain protected; unclassified names,
usernames and technical forms remain unresolved. Unknown token format puts a row
in REVIEW and outside the annotation pool.

`transform_events` records rule, before/after spans, raw-segment offsets and
within-stage offsets where applicable. Technical events may cover a complete
unprotected segment; stage offsets should not be interpreted as original raw
character positions after preceding transformations. The events and raw text
make the transformation inspectable without overwriting either source text or
human label provenance.

Domain/context, structural repetition and quality rules from Phase I.1 run on
the new clean text. These are unvalidated proposals, not semantic gold labels.
Long reviews are routed for review rather than deleted. Exact and direct-near
duplicates are recomputed. Human/test/planned-test exact groups and direct
neighbors are excluded from the new pool. Original master giant components are
not discarded wholesale. New near-pair ID counts can include representative
changes and should not all be interpreted as new semantic duplicates.

## Reproduce and review

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/prepare_phase_i2.py
```

Output `outputs/phase_i2/v2/` is immutable and local. A separate bundled
artifact-tool authoring run creates `outputs/phase_i2/workbook_v1/quality_review_200.xlsx`
from `workbook_input.local.json`; its input hash is verified against v2.
Only `text_annotation` appears on Review. The Raw & Changes sheet contains raw,
clean and transform evidence; Instructions explains decisions. Freeze header,
table filters, wrapping and a KEEP/REVIEW/EXCLUDE dropdown are enabled. Human
decision and note cells start empty. Very long rows have capped display height;
select the text cell and expand the formula bar (Ctrl+Shift+U) or use F2 to read
the complete retained value. No cell exceeded the Excel 32,767-character limit.

Fill only the last two Review columns. Import the complete quality review into
a new output, without modifying sentiment decisions or releasing annotation:

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/import_quality_review.py --input outputs/phase_i2/workbook_v1/quality_review_200.xlsx --output outputs/phase_i2/human_quality_import_01
```

Importer joins by ID and validates all 200 rows, original text, proposals and
raw/transform evidence. Missing/invalid decisions or edited source cells fail
before output. Future official Codex/Claude/Gemini export uses `release_inputs`:
it requires an explicit reviewer approval receipt bound to the exact pilot
checksum. It emits identical `id,text_annotation` files with one guideline
checksum. This function was not invoked; no prediction or consensus exists.
