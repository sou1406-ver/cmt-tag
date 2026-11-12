# Phase I.1 preprocessing and quality review

Status: PENDING_HUMAN_QUALITY_APPROVAL. Do not send the Phase I or I.1 pilot to
AI annotators before the quality audit has been reviewed. The frozen Phase I
v5 artifact remains available for comparison. No sentiment annotation, API,
crawl or training runs in this workflow.

The new view starts with the Phase I technical cleaning. It preserves raw text,
human decisions, negation, teencode, underscores, long reviews and emoji.
Six explicit colon-wrapped emoji aliases are mapped to Unicode using a reviewed
subset of [Unicode CLDR English annotation names](https://github.com/unicode-org/cldr/blob/main/common/annotations/en.xml).
The mapping is versioned in `src/preprocessing/emoji_aliases.py`. URLs, backtick
code and aliases embedded in identifiers are protected. Unknown aliases and bare
names are left intact; known bare alias names receive a review flag. Repeated
emoji are retained. No teencode or underscore replacement is enabled.

Repetition diagnostics use exact token blocks of widths 10–30, 50 and 100,
plus up to eight periods inferred from recurring 10-token anchors (maximum 512
tokens). Coverage >=0.4 with >=3 repeats raises review risk; >=0.65 with >=8
repeats and >=100 total tokens raises EXCLUDE_CANDIDATE. Compression, unique
token ratio and repeated sentence counts are diagnostics, not independent
exclusion rules. A candidate is held in quality REVIEW; no source row is deleted.
Emoji emphasis and stretched letters alone cannot trigger this rule.

Domain states are unvalidated proposals: film-related lexical cues and verified
film-post metadata support IN_DOMAIN_LIKELY; short replies without parent text
need CONTEXT_NEEDED; multiple advertising cues suggest OFF_TOPIC_LIKELY;
insufficient evidence produces UNCERTAIN. Missing the word “phim” does not
establish off-topic status. No religious, political or script blacklist is used.
Script mixture is measured separately and is not an exclusion criterion.
Provenance alone cannot establish that a specific comment discusses film; this
is a known limitation to inspect in the human audit.

Quality KEEP requires technical validity, likely film context and no serious
review signal. Ambiguous domain, missing context, replacement characters,
symbol-only comments, suspected repetitions, bare aliases or >1,000 characters
route to REVIEW. Empty text is the only unconditional EXCLUDE rule added here.
These proposals never overwrite human sentiment or human EXCLUDE/REVIEW.

## Human quality audit

Open `outputs/phase_i1/v2/quality_review_200.csv`. Fill only
`human_quality_decision` with KEEP, REVIEW or EXCLUDE. Judge whether the whole
comment can be interpreted for film sentiment, whether formatting lost meaning,
and whether repetition is meaningful emphasis or structural spam. Read the
complete raw and clean text. Do not infer a sentiment label for this task.
Unknown context should remain REVIEW. The audit deliberately oversamples risk
strata; its raw class proportions are not population estimates. Filter precision
and recall are not calculated until real decisions exist, and any estimates must
account for this sampling design.

Coordinator evidence, full source metadata, raw/clean examples and all proposals
are local only. Some previously human-labeled rows may appear in the quality
audit for inspection; they are excluded from the new unlabeled pilot. The new
500-row candidate uses a fixed seeded shuffle with no fixed source quotas and
inherits Phase I exclusions, fresh exact/direct-near duplicate checks, and the
existing fail-closed test guard. Only KEEP candidates enter it. No official
Codex/Claude/Gemini input files are issued in I.1.

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/audit_phase_i1.py
```

Existing output paths are immutable; choose a new output directory to rebuild.
