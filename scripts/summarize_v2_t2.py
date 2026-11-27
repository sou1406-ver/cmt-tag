"""Derive macro precision, recall and confusion matrices from saved T2 predictions."""

from statistics import mean, stdev

from sklearn.metrics import confusion_matrix, precision_score, recall_score

from scripts.evaluate_v2_t2 import read_t2_input, score_predictions
from scripts.prepare_v2_final import FINAL
from src.dataset.common import read_jsonl, seal, sha, staged, verify
from src.models.core import LABELS
from src.web_bert import BERT_NAMES
from src.web_demo import MODEL_NAMES, T2_ALL_MODELS_RESULTS_DIR, T2_DETAILED_RESULTS_DIR


def summarize():
    source = T2_ALL_MODELS_RESULTS_DIR
    report = verify(source)
    rows = read_jsonl(source / "predictions.local.jsonl")
    dataset, test_sha, test = read_t2_input(FINAL)
    if (report["kind"] != "V2_FINAL_T2_ALL_MODELS_THREE_SEED_EVALUATION"
            or report["std_definition"] != "sample_n_minus_1"
            or report["train_sha256"] != dataset["train_sha256"] or report["test_sha256"] != test_sha
            or report["train_size"] != dataset["train_size"] or report["test_size"] != dataset["test_size"]
            or report["test_groups"] != dataset["test_groups"]
            or [(row["id"], row["gold"]) for row in rows] != [(row["id"], row["label"]) for row in test]):
        raise ValueError("The saved predictions do not match the final train and T2 snapshots")

    seeds = [str(seed) for seed in report["seeds"]]
    targets = [row["gold"] for row in rows]
    scores, deviations, per_run, matrices = {}, {}, {}, {}
    for model in (*MODEL_NAMES, *BERT_NAMES):
        per_run[model], matrices[model] = {}, {}
        for seed in seeds:
            predicted = [row["predicted_by_seed"][model][seed] for row in rows]
            metrics = score_predictions(targets, predicted)
            if metrics != report["scores_by_seed"][model][seed]:
                raise ValueError(f"Accuracy or Macro-F1 mismatch for {model} seed {seed}")
            per_run[model][seed] = dict(
                **metrics,
                macro_precision=float(precision_score(targets, predicted, labels=LABELS, average="macro", zero_division=0)),
                macro_recall=float(recall_score(targets, predicted, labels=LABELS, average="macro", zero_division=0)),
            )
            matrices[model][seed] = confusion_matrix(targets, predicted, labels=LABELS).tolist()
        values = {metric: [run[metric] for run in per_run[model].values()] for metric in per_run[model][seeds[0]]}
        scores[model] = {metric: mean(points) for metric, points in values.items()}
        deviations[model] = {metric: stdev(points) for metric, points in values.items()}
        rendered = [f"{scores[model][metric]:.4f} ± {deviations[model][metric]:.4f}"
                    for metric in ("accuracy", "macro_precision", "macro_recall", "macro_f1")]
        print("| " + " | ".join([MODEL_NAMES.get(model) or BERT_NAMES[model], *rendered]) + " |", flush=True)

    with staged(T2_DETAILED_RESULTS_DIR) as folder:
        seal(folder, dict(kind="V2_FINAL_T2_DETAILED_EVALUATION",
                          **{key: report[key] for key in ("train_sha256", "train_size", "test_sha256", "test_size",
                                                         "test_groups", "seeds", "std_definition", "bert_receipt_sha256")},
                          source_evaluation_sha256=sha(source / "manifest.json"), scores=scores,
                          std=deviations, scores_by_seed=per_run, labels=LABELS, confusion_matrices=matrices))
    print("ViSoBERT seed 20261123", matrices["visobert"]["20261123"])


if __name__ == "__main__":
    summarize()
