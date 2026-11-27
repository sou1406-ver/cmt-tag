"""Score the six frozen V2 models against the sealed T2 test set."""

import argparse
from collections import Counter
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, f1_score

from scripts.prepare_v2_final import FINAL, SNAPSHOT_KIND
from scripts.train_v2_final import MODELS
from src.dataset.common import ROOT, load, read_jsonl, seal, sha, staged, verify, write_jsonl
from src.models.core import LABELS
from src.web_bert import APP_NAME, BERT_NAMES, ModalBert
from src.web_demo import MODEL_NAMES, T2_RESULTS_DIR, read_train


def read_t2_input(train_dir):
    train_manifest = verify(train_dir)
    if train_manifest["kind"] != SNAPSHOT_KIND:
        raise ValueError("T2 evaluation requires the final consensus train set")
    _, _, dataset = read_train(train_dir)
    test_manifest_path = ROOT / train_manifest["test_manifest"]
    if sha(test_manifest_path) != train_manifest["inputs_sha256"][train_manifest["test_manifest"]]:
        raise ValueError("The frozen T2 manifest differs from the train snapshot reference")
    test_manifest = load(test_manifest_path)
    test_path = test_manifest_path.with_name("T2.local.jsonl")
    test_sha = sha(test_path)
    if test_sha != test_manifest["output_sha256"][test_path.name]:
        raise ValueError("T2 checksum mismatch")

    rows = read_jsonl(test_path)
    train = read_jsonl(train_dir / "train.local.jsonl")
    if (len(rows) != dataset["test_size"] or len({row["id"] for row in rows}) != len(rows)
            or Counter(row["origin"] for row in rows) != dataset["test_groups"]
            or {row["label"] for row in rows} != set(LABELS)
            or {row["id"] for row in rows} & {row["id"] for row in train}
            or {row["post_id"] for row in rows} & {row["post_id"] for row in train}
            or any(not row["text"].strip() for row in rows)):
        raise ValueError("T2 roster or train/test isolation failed validation")
    return dataset, test_sha, rows


def score_predictions(targets, labels):
    if len(labels) != len(targets) or set(labels) - set(LABELS):
        raise ValueError("Invalid T2 predictions")
    return dict(macro_f1=float(f1_score(targets, labels, labels=LABELS, average="macro", zero_division=0)),
                accuracy=float(accuracy_score(targets, labels)))


def evaluate(train_dir, models_dir, output):
    if output.exists():
        raise FileExistsError("Evaluation already exists. Use the sealed results.")
    dataset, test_sha, rows = read_t2_input(train_dir)
    train_sha = dataset["train_sha256"]
    baselines_dir = models_dir / "baselines"
    baseline_manifest = verify(baselines_dir)
    if (baseline_manifest["train_sha256"] != train_sha
            or baseline_manifest["train_size"] != dataset["train_size"]
            or baseline_manifest["runs"].keys() != MODEL_NAMES.keys()):
        raise ValueError("Baseline artifacts do not match the final train snapshot")
    bert_receipt = models_dir / "bert_modal_trained.json"
    registry = load(bert_receipt)
    entries = {entry["model"]: entry for entry in registry["models"]}
    if (registry["app"] != APP_NAME or entries.keys() != BERT_NAMES.keys()
            or len(entries) != len(registry["models"])
            or any(entry["train_sha256"] != train_sha or entry["train_size"] != dataset["train_size"]
                   for entry in entries.values())):
        raise ValueError("BERT checkpoints do not match the final train snapshot")

    texts = [row["text"] for row in rows]
    targets = [row["label"] for row in rows]
    predictions = {}
    scores = {}
    for name in (*MODEL_NAMES, *BERT_NAMES):
        if name in MODEL_NAMES:
            artifact = baseline_manifest["runs"][name]["file"]
            if artifact not in baseline_manifest["output_sha256"]:
                raise ValueError(f"Unsealed baseline artifact: {name}")
            labels = joblib.load(baselines_dir / artifact).predict(texts).tolist()
        else:
            # Modal receives token IDs only. T2 labels and comment IDs stay local.
            labels = [prediction["label"] for prediction in ModalBert(entries[name], train_sha).predict_batch(texts)]
        predictions[name] = labels
        scores[name] = score_predictions(targets, labels)
        print(f"{name}: Macro-F1 {scores[name]['macro_f1']:.4f}, Accuracy {scores[name]['accuracy']:.4f} (n={len(labels)})", flush=True)

    with staged(output) as folder:
        write_jsonl(folder / "predictions.local.jsonl", (
            {"id": row["id"], "gold": row["label"],
             "predicted": {name: labels[i] for name, labels in predictions.items()}}
            for i, row in enumerate(rows)
        ))
        seal(folder, dict(kind="V2_FINAL_T2_EVALUATION", train_sha256=train_sha,
                          train_size=dataset["train_size"], test_sha256=test_sha,
                          test_size=len(rows), test_groups=dataset["test_groups"], scores=scores,
                          bert_seeds={name: entry["config"]["seed"] for name, entry in entries.items()},
                          baselines_manifest_sha256=sha(baselines_dir / "manifest.json"),
                          bert_receipt_sha256=sha(bert_receipt)))
    verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", type=Path, default=FINAL)
    parser.add_argument("--models-dir", type=Path, default=MODELS)
    parser.add_argument("--output", type=Path, default=T2_RESULTS_DIR)
    args = parser.parse_args()
    evaluate(args.train_dir, args.models_dir, args.output)
