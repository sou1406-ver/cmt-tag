# Phase H — PhoBERT-v2 and ViSoBERT development fine-tuning

**Status: PARTIAL.** The experiment pipeline is implemented; ViSoBERT passed a
synthetic smoke and a fixed-config fold-0 pilot. Aggregate pilot metrics are
reported below, not as completed CV results. No raw comments, human labels,
checkpoints or per-comment predictions are tracked in Git.

## Fixed protocol

`src/transformer/` reads the sealed 532-row human dataset and unchanged three
Facebook folds. It verifies the G.3.1 direct-isolation manifest and reruns the
G.3.2 parent/reply audit against exact source rows before any fit. Each fold
uses only its frozen Facebook train IDs for H1/H3; H2/H4 append the 186 human
legacy POS/NEG/NEU rows to that training partition. Validation is always the
corresponding Facebook fold. No legacy row is validation, and no reserved
test/quarantine row is loaded. Legacy provenance is still unavailable at
post level, so augmented results remain exploratory.

The adapter checks allowed labels, source, frozen IDs/groups, exact text,
comment/post identities, and parent/thread boundaries. It does not use legacy
`overall`, edit labels, or rewrite `text_raw`. Per-fold checkpoints are
initialized independently from pretrained weights and never reused across
folds. The final fixed epoch is reported; there is no checkpoint selection
from validation scores. The fixed config records seed, optimizer, max length,
epochs, class weighting (none), accumulation/clipping and precision policy.
Dynamic batch padding, attention masks, truncation counts, train/validation
metrics and runtime are recorded.

## Model-specific inputs

- PhoBERT-v2: `text_view` is passed to a local VnCoreNLP RDR word segmenter at
  runtime. Existing underscores are not proof of segmentation. The segmenter
  needs Java and local VnCoreNLP assets; it does not mutate source text.
- ViSoBERT: its tokenizer receives `text_view` verbatim, without PhoBERT
  segmentation or custom social-text rewriting.
- Both heads use output order POS, NEG, NEU. Run metadata records resolved
  upstream revision, model/tokenizer identifiers, label order and local
  checkpoint SHA-256 values.

The pinned upstream revisions are PhoBERT-v2
`86cd7fd4c148980922ac11a2cf5e257f2ba639e1` and ViSoBERT
`196a62afad9cbe4f52a54aabad828b13f0eec59a`; updates require an explicit
config change.

The PhoBERT-v2 card requires word-segmented input, reports maximum length 256,
and displays AGPL-3.0. The ViSoBERT card identifies an XLM-R model and says it
is available for research purposes. Review terms before uses beyond this
research. [PhoBERT-v2 model card](https://huggingface.co/vinai/phobert-base-v2),
[ViSoBERT model card](https://huggingface.co/uitnlp/visobert).

## Inspected environment and run status

The inspected Python is 3.12.14. `.venv-phase-e` has no PyTorch, Transformers,
SentencePiece, Accelerate or `py_vncorenlp`; Java is not on PATH, so the
PhoBERT segmenter cannot run here. No usable NVIDIA runtime/device could be
verified. Disk had about 20 GiB free on C: and G: when inspected. ViSoBERT's
public checkpoint was downloaded only to the ignored local cache. A synthetic
CPU smoke completed one forward/loss/backward and evaluation step: 97,568,259
parameters, output `[1, 3]`, finite loss, resolved revision
`196a62afad9cbe4f52a54aabad828b13f0eec59a`, PyTorch `2.14.1+cpu`, CUDA
unavailable. This validates software execution only; it is not a sentiment
result. PhoBERT smoke remains blocked by missing Java and local RDR assets;
the full 12-fit run remains unrun.

The full test command subsequently passed after installing the repo-pinned
Selenium version into the existing test venv. A single-fold ViSoBERT pilot
also completed both fixed 3-epoch configurations on CPU (fold 0, validation
n=152 each). It is not complete CV:

| Pilot configuration | Macro-F1 | Accuracy | POS F1 | NEG F1 | NEU F1 | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ViSoBERT, FB train | 0.3895 | 0.4408 | 0.3200 | 0.5380 | 0.3103 | 171.2 |
| ViSoBERT, FB + legacy train | 0.5191 | 0.5461 | 0.5968 | 0.5913 | 0.3692 | 497.9 |

The frozen SVM fold-0 references are approximately 0.5739 (A) and 0.5391 (B).
On the same 152 IDs, ViSoBERT FB-only corrected 13 SVM errors and regressed
35 SVM-correct rows; the augmented pilot corrected 22 and regressed 22. These
are pilot observations with one fold and no uncertainty estimate; do not infer
that legacy improves general performance from them. Fold label support was
POS/NEG/NEU = 58/47/47. All model outputs, weights and ID-level predictions
are local under `outputs/phase_h/pilot_visobert_fold0/` and are gitignored.

The first full-suite invocation in the restricted runner had ACL errors on
gitignored `outputs/phase_g/`; after rerunning with authorized local-data read
access, the requested suite passed **260 tests (1 skipped)**. The current
status is **PARTIAL**: ViSoBERT smoke and one fold's two training configurations
passed, but full CV requires substantially more CPU time and PhoBERT also needs
Java/RDR assets.

## Reproduction

Install the matching CPU/CUDA PyTorch wheel from the official selector, then
`requirements-phase-h.txt`. For PhoBERT, install Java and official local
VnCoreNLP RDRSegmenter files in the configured directory and record their
versions and checksums. Weights, cache, data and run outputs are local and
gitignored.

```powershell
python -m venv .venv-phase-h
.\.venv-phase-h\Scripts\python.exe -m pip install -r requirements-phase-h-torch-cpu.txt
.\.venv-phase-h\Scripts\python.exe -m pip install -r requirements-phase-h.txt
.\.venv-phase-h\Scripts\python.exe scripts/run_phase_h.py --smoke --model visobert --output outputs/phase_h/smoke_visobert_01
.\.venv-phase-h\Scripts\python.exe scripts/run_phase_h.py --smoke --model phobert_v2 --output outputs/phase_h/smoke_phobert_01
.\.venv-phase-h\Scripts\python.exe scripts/run_phase_h.py --output outputs/phase_h/run_01
```

The full run is four configurations × three fresh fold fits. Start with the
synthetic smoke modes, then one pilot fold. Outputs include per-fold logs,
OOF predictions and checkpoints; an existing run directory is never
overwritten.

## Comparison reference and limits

G.3.1 char-SVM OOF references remain Facebook-only Macro-F1 **0.580159** and
Facebook+legacy **0.542666**. The fold-0 pilot comparison above aligns exact
Facebook IDs against frozen SVM predictions. These are development CV values,
not independent gold test results. The pilot does not establish which model
is best across folds.
The independent 180-row test reservation and quarantine remain untouched.
