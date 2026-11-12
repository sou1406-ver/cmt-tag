# Phase I unified dataset dictionary

The complete corpus and all comment-bearing artifacts are local-only under
`outputs/phase_i/v1/`. They are ignored by Git. `text_raw` is copied without
mutation from the frozen Phase G master. The human-decision ledger is separate
from AI predictions; a legacy `overall` value is retained only as
`legacy_overall` with status `UNVERIFIED_SOURCE_LABEL` and is never interpreted
as a human sentiment label.

| Field | Meaning |
| --- | --- |
| `record_id` | Stable Phase G master identity. |
| `original_id` | Source internal ID(s), when present; otherwise `record_id`. |
| `source_dataset` | `facebook`, `legacy_29k_unverified`, or `unknown_source`. |
| `platform` | Verified platform from master metadata, else `unknown`. |
| `source_file`, `source_row` | Master source provenance. `metadata_provenance` retains all source observations. |
| `movie_id`, `post_id`, `comment_id`, `parent_comment_id`, `post_url` | Populated only from verified source metadata. |
| `text_raw` | Unchanged source text. |
| `text_clean` | Deterministic Phase I basic cleaning view. |
| `text_annotation` | Default blind annotation view; currently identical to `text_clean`. |
| `quality_status` | `KEEP`, `REVIEW`, or `EXCLUDE`; this is not a sentiment label. |
| `quality_reasons`, `flags` | Rule IDs and review cues. Length/context flags do not assign sentiment. |
| `duplicate_group_id` | Exact normalized text group. Near-duplicate edges are recorded in aggregate diagnostics and pilot selection constraints. |
| `master_group_id` | Original transitive Phase G group, retained for audit only; not used to discard a whole giant component. |
| `human_decisions` | Provenance-backed human decisions, including `REVIEW`/`EXCLUDE`. |
| `human_label` | Only a valid human `POS`/`NEG`/`NEU` decision; never populated from `overall`. |
| `human_label_source`, `label_status` | Human provenance/status, legacy unverified status, or `UNLABELED`. These rows are development data, not an independent gold test. |
| `legacy_overall`, `legacy_overall_status` | Original legacy label retained for audit; always explicitly unverified. |
| `test_reserved` | True only for confirmed reservation/quarantine IDs. Planned but exposure-unknown source posts are separately held out of the pilot. |
| `exposure_status` | Preserved Phase G exposure finding; unknown does not mean unused. |
| `preprocessing_version` | `phase_i_basic_v1`. |

The three local blind input files have exactly `id,text_annotation`. They do not
include labels, source/platform metadata, movie/post identity, model outputs or
quality annotations.
