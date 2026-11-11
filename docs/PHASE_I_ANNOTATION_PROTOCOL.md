# Phase I multi-AI annotation protocol

## Purpose and data boundary

The 500-row pilot is for development and annotation-process validation. It is
not an independent test set. The 346 Facebook sentiment labels and 186 legacy
sentiment labels are human single-annotator development decisions. The remaining
human `REVIEW` and `EXCLUDE` decisions are retained outside the three-class
label field. The legacy `overall` column is unverified and is never copied into
the human label field.

Claude, Gemini and (if a real, authorized inference runtime becomes available)
Codex receive the same two-column input with the V2.1 guideline. No model sees
the master source, source/movie/post metadata, human decisions or any other
model's predictions. No external API is called by the Phase I preparation
commands.

## Output schema

Each annotator returns one UTF-8 CSV with exactly:

`id,status,label,review_reason,reason`

- `LABELED`: `label` is one of `POS`, `NEG`, `NEU`; `review_reason` is empty.
- `REVIEW`: blank `label`; `review_reason` is one of `REV_MIXED`,
  `REV_SARCASM`, `REV_TARGET`, `REV_CONTEXT`, `REV_OTHER`.
- `EXCLUDE`: blank `label`; `review_reason` is one of
  `EXC_EMPTY_OR_UI`, `EXC_IRRELEVANT`, `EXC_NON_TEXT`,
  `EXC_PERSONAL_EVENT`, `EXC_SPAM`.
- `reason` is a short explanation. Do not add confidence scores or alter IDs.

Keep predictions in three separate files named
`codex_predictions.csv`, `claude_predictions.csv`, and
`gemini_predictions.csv`. Each requires a neighboring metadata file such as
`claude_metadata.json` with annotator, provider, model ID/version, V2.1
guideline checksum, prompt checksum, timestamp and `label_source=automatic`.
Do not create predictions from keyword rules or legacy labels.

## Import and consensus

Validate each file independently against the exact pilot ID set:

```powershell
python scripts/validate_phase_i_predictions.py --predictions-dir <local-results-folder>
```

Consensus is unavailable unless all three valid prediction files and metadata
sidecars exist:

```powershell
python scripts/validate_phase_i_predictions.py --predictions-dir <local-results-folder> --consensus
```

Consensus output is a silver candidate only. 3/3 sentiment agreement becomes
`SILVER_3_OF_3`; 2/3 requires human review; 1/1/1 is disagreement. Any `REVIEW`
or `EXCLUDE` output routes the row to human review. No consensus is `HUMAN_GOLD`.
