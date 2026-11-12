# Consolidation plan and audit record

Baseline: `33b60e5`, working tree clean before inventory. This is structural
maintenance, not a research phase. The follow-up request prioritizes synthesis
over relocating files. No dataset, labels, algorithms, approvals or results change.

## Audit completed before implementation

Local inventory and evidence: `outputs/repository_audit/before/`.
308 tracked files; 1,716 project-local files outside environments/profiles/cache/
reparse trees; 16 root files; 42 Markdown files directly under docs; 69 source
files; 51 scripts. Secrets/profile contents were not read. Every tracked file
has a role/reason, import callers and SHA-256. Local metadata inventory includes
unclassified artifacts; UNKNOWN means keep, never delete. Metadata scans covered
246 small manifests/contracts/config snapshots, finding 91 checksum-pinned files.
239 current/historical data/workbook/result files were snapshotted for preservation.

AST import edges, path literals and exact function-body comparisons are recorded
locally. There are no identical multi-line function bodies under the AST criterion;
the real repetition is schema-specific ID validation and CLI/parser boilerplate.
Do not describe lexical similarity or shared version components as exact copies.

## Decisions before edits

| Scope | Decision | Evidence and risk |
| --- | --- | --- |
| Raw, human workbooks, outputs, checkpoints, frozen plans/results | KEEP | Existing SHA/manifest references; no move/delete/regeneration |
| Guidelines V2.0/V2.1 and all configs/rule resources | KEEP | Source/approval hashes, fixed paths; functional indexes replace physical config moves |
| plain_text.py, plain_text_v3.py, final_normalization.py | KEEP + shared facade in existing package initializer | Version components are intentionally composed and checksum-pinned; no algorithm merge |
| Quality rules/readiness, historical phase builders | KEEP | Checksummed implementations and source contracts; moving would invalidate rule/experiment evidence |
| XLSX parsing and stable ID validation | MERGE into existing dataset/common.py | Standard-library utilities with unchanged results/errors; old reader re-export remains compatible |
| Current quality prepare/import/evaluate/freeze/export CLI | MERGE in existing quality_review.py | Same implementations/defaults; four old scripts become compatibility adapters |
| Crawler, annotation and baseline module CLIs | KEEP | Already canonical; new umbrella package would add unnecessary routing |
| Historical workbook builders/schemas | KEEP, mark historical | Different fields/meaning, some pinned; no speculative generic workbook framework |
| Reports/specs no longer current and not runtime-addressed | ARCHIVE | Synthesize first; preserve narrative/numbers, adjust Markdown destinations only |
| Runtime report/prompt paths | KEEP | phase_i.py reads annotation protocol; phase_i3.py records G.2 evidence path; crawler errors name its guide |
| Requirements | MERGE environment entrypoints, WRAP old names | Compare recursive expansion before/after; keep all package pins/options and lock contents |
| Root README/docs index | REPLACE navigation | Three synthesis documents become recommended reading, archived reports remain evidence |
| Unknown/legacy scripts and tracked research data | KEEP | Lack of import does not establish obsolescence; no private data copied into new docs |

## Target, migration and rollback

Use existing functional source packages. Shared I/O/XLSX integrity lives in
dataset/common.py; current human-quality workflow in quality_review.py; versioned
text engines keep their original paths behind preprocessing.preprocess().
Canonical environments live under requirements/, with old root names as thin
`-r` adapters. Active/experiment/frozen config roles are documented by exact paths,
without copying resources. Docs have three primary syntheses, environment guide,
reference, guidelines, architecture and archive; only technically required older
paths remain at root. No empty directories or new packaging dependency.

Low risk: navigation, synthesized docs, environment include adapters, pure helper
extraction and CLI delegation. Medium risk: report path/link changes; audit every
Markdown destination and retain runtime-addressed reports. Deferred high risk:
moving checksum-bound phase engines/configs/data, rewriting model pipelines or
merging environment versions. Phase E uses NumPy 2.5.4/sklearn 1.9.1; H uses
NumPy 2.3.4/sklearn 1.7.2. They remain isolated, with no upgrades/install.

Rollback is the inverse structural commit (ordinary revert after checking user
changes), not reset/clean/history rewrite. Pre-change hashes and inventory support
path-by-path verification; old script/requirement paths remain executable.
No local artifact is removed to make rollback easier.

## Reproducibility boundary

Existing artifacts remain byte-identical. Same-input normalization is checked
against all 39,842 saved proposals. Pure reader/validator fixture comparisons
and real completed/blank workbook validations cover the helper extraction.
Frozen results are checked by hash, never retrained. Phase B deliberately hashes
all src/scripts Python into a new data_version: structural code changes therefore
change the provenance ID of a future rebuild, even with identical text/split
behavior. Do not claim byte-identical new build manifests or old data_version.

## File-proliferation policy

Before adding a file, find the existing owner, call sites, schema and config.
Prefer extending that owner or an existing subcommand. A new file needs an
independent responsibility, a declared replacement/compatibility decision and
an index update. Preserve schema-specific semantics and historical recipe
versions; do not create phase_k.py/preprocessing_v4.py by default. Update
PROJECT_EVOLUTION, CURRENT_PIPELINE or EXPERIMENT_RESULTS instead of another
phase report. Requirements changes belong to the relevant environment and must
not silently upgrade a research lock. Each workflow has one recommended entry
point and guide, with old paths explicitly identified as compatibility/reproduction.

## Verification and final counts

| Metric and scope | Before | After |
| --- | ---: | ---: |
| Tracked project files | 308 | 324 |
| ACTIVE/SHARED classified files, including guides/config/runtime aliases | 119 | 136 |
| Root files | 16 | 16 |
| Markdown documents directly under docs/ | 42 | 11 |
| Reports in archive | 0 | 32 |
| Schema/dictionary moved into reference | 0 | 2 |
| CLI parsers for current quality workflow | 4 | 1 |
| Canonical recommended module CLIs (crawler, annotation, baseline, quality) | 3 + four quality-script parsers | 4 module CLIs |
| Unpinned review-ID validation implementations consolidated | 4 | 1 shared helper |
| Root requirement compatibility paths | 9 original declarations/includes | 9 thin includes |
| Broken Markdown destinations / requirements includes | 0 / 0 | 0 / 0 |
| Full regression suite | 334 tests, 333 pass/1 skip | 341 tests, 340 pass/1 skip |

The added 16 files are six requested/single-purpose synthesis/architecture/setup
documents, nine canonical environment/lock manifests and one structural regression
test. No phase module, umbrella package, dependency, raw data or AI input was added.
ACTIVE/SHARED counts rise because new navigation/environment owners and backward
compatible paths are counted; this is not a claim of more runtime capabilities.
The file census is a maintained-source inventory, not a count of venv/cache/profile
contents. The pre-change local inventory contains 1,716 project files with those
surfaces excluded; raw inventories stay local because they contain user paths.

**Completed consolidation:** four unpinned validators share the same ID/literal
integrity primitives; old XLSX reader re-exports the canonical common reader.
The remaining historical I.4 validator keeps its own loop because phase_i4.py is
checksum-pinned. Thus across those five validators, integrity implementations
go from five to two, not to one globally. Evaluator logic moved once into the
existing quality owner; four scripts delegate rather than duplicate parsing.
There was no exact AST function-body duplicate to delete. Underthesea's non-lock
pin now has one segmentation owner; all nine old requirements recursively expand
to exactly the same packages/options, and the full classical lock is byte-identical.
The root-file count does not fall: nine old requirement names remain deliberately
for compatibility. One setup guide replaces phase-specific setup navigation.

**Verified:** 91 checksum-pinned tracked files and 239 protected local data/
workbook/result files unchanged; guidelines/config/rules remain exact. All 39,842
raw-derived normalization results **including events/flags** match the saved
I.4.1 proposals. Human counts remain 650/532. Existing real format/normalization/
domain/holdout workbooks validate after the helper extraction. 68 src modules
import successfully; no missing optional import was observed. Archived narrative
and numbers compare equal after stripping link/path destinations; only navigation
destinations changed. Local evidence is in outputs/repository_audit/after/.

**Deferred:** do not merge the three plain-text engines or rewrite phase_i*/
quality_readiness/repetition/semantic_quality code: these are real version/hash
contracts, not interchangeable duplicates. Do not relocate configs, model assets,
human annotations, unknown files or output trees. Historical workbook schemas
and builders retain different meanings and reproduction duties. E/H dependency
versions remain isolated. Unknown legacy provenance, pending quality approvals,
the incomplete independent test and limited Facebook coverage are research/data
blockers, not cleanup errors. No freeze, pilot release, live crawl, AI call or
research fitting occurred. Tests may execute synthetic fixtures only.
