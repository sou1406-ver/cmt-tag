"""Fit and score four V2 baselines on the same three seeds as the BERT runs."""

from statistics import mean, stdev

import sklearn

from scripts.evaluate_v2_t2 import read_t2_input, score_predictions
from scripts.prepare_v2_final import FINAL
from scripts.train_v2_bert_seeds import SEEDS
from scripts.train_v2_final import MODELS
from src.dataset.common import read_jsonl, seal, sha, staged, verify, write_jsonl
from src.models.core import v2_baseline_model
from src.web_bert import BERT_NAMES
from src.web_demo import MODEL_NAMES, T2_ALL_MODELS_RESULTS_DIR, T2_THREE_SEED_RESULTS_DIR, read_train


def evaluate():
    output = T2_ALL_MODELS_RESULTS_DIR
    if output.exists():
        raise FileExistsError("Use the sealed all-model evaluation already on disk")
    train_texts, train_labels, dataset = read_train(FINAL)
    _, test_sha, test = read_t2_input(FINAL)
    bert_report = verify(T2_THREE_SEED_RESULTS_DIR)
    bert_predictions = read_jsonl(T2_THREE_SEED_RESULTS_DIR / "predictions.local.jsonl")
    receipt_sha = sha(MODELS / "bert_modal_trained.json")
    if (bert_report["kind"] != "V2_FINAL_T2_THREE_SEED_EVALUATION"
            or bert_report["std_definition"] != "sample_n_minus_1"
            or bert_report["bert_seeds"] != list(SEEDS)
            or bert_report["train_sha256"] != dataset["train_sha256"]
            or bert_report["train_size"] != len(train_texts)
            or bert_report["test_sha256"] != test_sha or bert_report["test_size"] != len(test)
            or bert_report["test_groups"] != dataset["test_groups"]
            or bert_report["bert_receipt_sha256"] != receipt_sha
            or [(row["id"], row["label"]) for row in test]
               != [(row["id"], row["gold"]) for row in bert_predictions]):
        raise ValueError("The completed BERT evaluation does not match this train and T2 snapshot")

    texts = [row["text"] for row in test]
    targets = [row["label"] for row in test]
    predictions = {}
    scores = {name: bert_report["scores"][name] for name in BERT_NAMES}
    deviations = {name: bert_report["bert_std"][name] for name in BERT_NAMES}
    by_seed = dict(bert_report["scores_by_seed"])
    for name in MODEL_NAMES:
        runs = {}
        predictions[name] = {}
        for seed in SEEDS:
            model = v2_baseline_model(name)
            if "model__random_state" in model.get_params():
                model.set_params(model__random_state=seed)
            labels = model.fit(train_texts, train_labels).predict(texts).tolist()
            predictions[name][seed] = labels
            runs[seed] = score_predictions(targets, labels)
            print(f"{name} seed {seed}: {runs[seed]}", flush=True)
        by_seed[name] = runs
        values = {metric: [runs[seed][metric] for seed in SEEDS] for metric in ("macro_f1", "accuracy")}
        scores[name] = {metric: mean(points) for metric, points in values.items()}
        deviations[name] = {metric: stdev(points) for metric, points in values.items()}
        print(f"{name} mean: {scores[name]}, sample SD: {deviations[name]}", flush=True)

    with staged(output) as folder:
        write_jsonl(folder / "predictions.local.jsonl", (
            {"id": row["id"], "gold": row["label"],
             "predicted_by_seed": {**bert_predictions[i]["bert_by_seed"],
                                   **{name: {seed: labels[i] for seed, labels in runs.items()}
                                      for name, runs in predictions.items()}}}
            for i, row in enumerate(test)
        ))
        seal(folder, dict(kind="V2_FINAL_T2_ALL_MODELS_THREE_SEED_EVALUATION",
                          train_sha256=dataset["train_sha256"], train_size=len(train_texts),
                          test_sha256=test_sha, test_size=len(test), test_groups=dataset["test_groups"],
                          seeds=SEEDS, scores=scores, std=deviations, scores_by_seed=by_seed,
                          std_definition="sample_n_minus_1", bert_receipt_sha256=receipt_sha,
                          bert_evaluation_sha256=sha(T2_THREE_SEED_RESULTS_DIR / "manifest.json"),
                          baseline_sklearn_version=sklearn.__version__))
    verify(output)


if __name__ == "__main__":
    evaluate()
