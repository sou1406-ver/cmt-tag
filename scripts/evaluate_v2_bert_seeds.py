"""Score additional BERT checkpoints on T2 and aggregate across three seeds."""

import argparse
from json import JSONDecodeError
from pathlib import Path
from statistics import mean, stdev
from time import monotonic, sleep

from scripts.evaluate_v2_t2 import read_t2_input, score_predictions
from scripts.prepare_v2_final import FINAL
from scripts.train_v2_bert_seeds import EXTRA_RUNS, SEEDS
from scripts.train_v2_final import MODELS
from src.dataset.common import load, read_jsonl, save, seal, sha, staged, verify, write_jsonl
from src.web_bert import APP_NAME, BERT_NAMES, ModalBert
from src.web_demo import MODEL_NAMES, T2_RESULTS_DIR, T2_THREE_SEED_RESULTS_DIR


def evaluate(output, wait_seconds):
    if output.exists():
        raise FileExistsError("Use the sealed three-seed evaluation already on disk")
    dataset, test_sha, rows = read_t2_input(FINAL)
    train_sha = dataset["train_sha256"]
    original_report = verify(T2_RESULTS_DIR)
    original_predictions = read_jsonl(T2_RESULTS_DIR / "predictions.local.jsonl")
    original_receipt = MODELS / "bert_modal_trained.json"
    anchors = {entry["model"]: entry for entry in load(original_receipt)["models"]}
    if (original_report["kind"] != "V2_FINAL_T2_EVALUATION"
            or original_report["train_sha256"] != train_sha or original_report["test_sha256"] != test_sha
            or original_report["train_size"] != dataset["train_size"]
            or original_report["test_size"] != len(rows) or original_report["test_groups"] != dataset["test_groups"]
            or original_report["bert_receipt_sha256"] != sha(original_receipt)
            or original_report["baselines_manifest_sha256"] != sha(MODELS / "baselines" / "manifest.json")
            or original_report["bert_seeds"] != dict.fromkeys(BERT_NAMES, SEEDS[0])
            or anchors.keys() != BERT_NAMES.keys()
            or [(row["id"], row["label"]) for row in rows]
               != [(row["id"], row["gold"]) for row in original_predictions]):
        raise ValueError("The existing one-seed scores do not match the frozen T2 inputs and checkpoints")

    texts = [row["text"] for row in rows]
    targets = [row["label"] for row in rows]
    per_seed = {name: {SEEDS[0]: original_report["scores"][name]} for name in BERT_NAMES}
    predictions = {name: {SEEDS[0]: [row["predicted"][name] for row in original_predictions]} for name in BERT_NAMES}
    pending = [(name, seed) for name in BERT_NAMES for seed in SEEDS[1:]]
    deadline = monotonic() + wait_seconds
    while pending:
        for name, seed in pending[:]:
            entry_path = EXTRA_RUNS / f"{name}_{seed}.json"
            if not entry_path.is_file():
                continue
            anchor = anchors[name]
            try:
                entry = load(entry_path)
            except JSONDecodeError:
                continue
            if (entry["model"] != name or entry["revision"] != anchor["revision"]
                    or entry["train_sha256"] != train_sha or entry["train_size"] != dataset["train_size"]
                    or entry["config"] != {**anchor["config"], "seed": seed}):
                raise ValueError(f"Checkpoint mismatch for {name} seed {seed}")
            cached = EXTRA_RUNS / "t2" / f"{name}_{seed}"
            source = dict(test_sha256=test_sha, checkpoint_receipt_sha256=sha(entry_path))
            cache_exists = cached.exists()
            if cache_exists:
                saved = verify(cached)
                if any(saved[key] != value for key, value in source.items()):
                    raise ValueError(f"Saved predictions mismatch for {name} seed {seed}")
                labels = load(cached / "labels.local.json")
            else:
                # Send token IDs for inference, with labels and comment IDs kept local.
                labels = [result["label"] for result in ModalBert(entry, train_sha).predict_batch(texts)]
            scores = score_predictions(targets, labels)
            if not cache_exists:
                with staged(cached) as folder:
                    save(folder / "labels.local.json", labels)
                    seal(folder, source)
            predictions[name][seed] = labels
            per_seed[name][seed] = scores
            pending.remove((name, seed))
            print(f"{name} seed {seed}: Macro-F1 {scores['macro_f1']:.4f}, Accuracy {scores['accuracy']:.4f}", flush=True)
        if pending:
            if monotonic() >= deadline:
                raise TimeoutError(f"Training checkpoints are still pending: {pending}")
            sleep(3)

    additional_receipt = EXTRA_RUNS / "bert_modal_trained.json"
    additional = load(additional_receipt)
    if (additional["app"] != APP_NAME or additional["original_receipt_sha256"] != sha(original_receipt)
            or additional["models"] != [load(EXTRA_RUNS / f"{name}_{seed}.json")
                                        for name in BERT_NAMES for seed in SEEDS[1:]]):
        raise ValueError("Additional BERT registry does not match the evaluated checkpoints")
    scores = {name: original_report["scores"][name] for name in MODEL_NAMES}
    deviations = {}
    for name, runs in per_seed.items():
        metrics = {metric: [runs[seed][metric] for seed in SEEDS] for metric in ("macro_f1", "accuracy")}
        scores[name] = {metric: mean(values) for metric, values in metrics.items()}
        deviations[name] = {metric: stdev(values) for metric, values in metrics.items()}
        print(f"{name} mean: {scores[name]}, sample SD: {deviations[name]}", flush=True)

    with staged(output) as folder:
        write_jsonl(folder / "predictions.local.jsonl", (
            {"id": row["id"], "gold": row["label"],
             "baselines": {name: original_predictions[i]["predicted"][name] for name in MODEL_NAMES},
             "bert_by_seed": {name: {seed: labels[i] for seed, labels in runs.items()}
                              for name, runs in predictions.items()}}
            for i, row in enumerate(rows)
        ))
        seal(folder, dict(kind="V2_FINAL_T2_THREE_SEED_EVALUATION", train_sha256=train_sha,
                          train_size=dataset["train_size"], test_sha256=test_sha,
                          test_size=len(rows), test_groups=dataset["test_groups"], scores=scores,
                          bert_std=deviations, bert_seeds=SEEDS, scores_by_seed=per_seed,
                          bert_receipt_sha256=sha(original_receipt), additional_receipt_sha256=sha(additional_receipt),
                          source_evaluation_sha256=sha(T2_RESULTS_DIR / "manifest.json"),
                          std_definition="sample_n_minus_1"))
    verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=T2_THREE_SEED_RESULTS_DIR)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    evaluate(args.output, args.wait_seconds)
