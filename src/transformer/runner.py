"""Phase H fixed-fold fine-tuning; all comments and checkpoints stay local."""
from collections import Counter
import importlib.metadata
import json
import os
import platform
import random
import time
from pathlib import Path

import numpy as np

from src.dataset.common import ROOT, load, sha
from src.transformer import LABELS
from src.transformer.data import fold_training_rows, load_phase_h_data
from src.transformer.models import load_classifier, load_segmenter, prepare_phobert, prepare_visobert
from src.transformer.training import encode_batch, set_seed, validate_logits


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _checksum_tree(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in sorted(path.rglob("*")) if p.is_file()}


def _predict(model, tokenizer, texts, labels, max_length, batch_size, torch, device):
    model.eval()
    predictions, truncation, loss_sum = [], 0, 0.0
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            full = tokenizer(batch, padding=False, truncation=False)
            truncation += sum(len(ids) > max_length for ids in full["input_ids"])
            encoded = tokenizer(batch, padding=True, truncation=True, max_length=max_length,
                                return_tensors="pt")
            if encoded["input_ids"].shape != encoded["attention_mask"].shape:
                raise ValueError("Tokenizer padding/attention mask mismatch")
            encoded = {k: v.to(device) for k, v in encoded.items()}
            encoded["labels"] = torch.tensor([LABELS.index(label) for label in labels[start:start + len(batch)]],
                                             dtype=torch.long, device=device)
            output = model(**encoded)
            logits = output.logits
            loss_sum += float(output.loss.cpu()) * len(batch)
            validate_logits(logits, len(batch))
            predictions.extend(logits.argmax(dim=-1).cpu().tolist())
    return [LABELS[i] for i in predictions], truncation, loss_sum / max(len(texts), 1)


def _scores(truth, predicted):
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    report = classification_report(truth, predicted, labels=list(LABELS), output_dict=True, zero_division=0)
    return {"accuracy": float(accuracy_score(truth, predicted)),
            "macro_f1": float(report["macro avg"]["f1-score"]),
            "per_class": {label: {k: float(report[label][k]) for k in ("precision", "recall", "f1-score", "support")}
                          for label in LABELS},
            "confusion_matrix_rows_true_labels": confusion_matrix(truth, predicted, labels=list(LABELS)).tolist()}


def compare_oof_to_svm(current_rows, reference_rows, model_key, dataset_name, trial):
    from sklearn.metrics import f1_score
    current = {r["id"]: r for r in current_rows
               if r["model"] == model_key and r["dataset"] == dataset_name}
    reference = {r["id"]: r for r in reference_rows if r["experiment"] == trial}
    if not current or set(current) != set(reference):
        return None
    ids = sorted(current)
    truth = [current[i]["human_label"] for i in ids]
    transformer = [current[i]["prediction"] for i in ids]
    svm = [reference[i]["predicted_label"] for i in ids]
    return {"model": model_key, "dataset": dataset_name, "svm_reference_trial": trial, "support": len(ids),
        "svm_macro_f1": float(f1_score(truth, svm, labels=list(LABELS), average="macro")),
        "transformer_macro_f1": float(f1_score(truth, transformer, labels=list(LABELS), average="macro")),
        "transformer_corrected_svm_errors": sum(svm[i] != truth[i] and transformer[i] == truth[i] for i in range(len(ids))),
        "transformer_regressed_svm_correct": sum(svm[i] == truth[i] and transformer[i] != truth[i] for i in range(len(ids)))}


def _fit_fold(model_id, model_key, train_rows, valid_rows, training_cfg, output, fold_no,
              local_only=False, segmenter=None):
    import torch
    from transformers import get_linear_schedule_with_warmup

    seed = int(training_cfg["seed"] + fold_no)
    set_seed(seed, torch)
    model_revision = training_cfg["models"][model_key]["revision"]
    tokenizer, model = load_classifier(model_id, model_revision, local_files_only=local_only)
    prepare = prepare_phobert if model_key == "phobert_v2" else prepare_visobert
    def text(row):
        if model_key != "phobert_v2":
            return prepare(row["text_view"])
        return prepare(row["text_view"], segmenter, legacy_source=row["source_dataset"] == "legacy_human")
    x_train = [text(r) for r in train_rows]
    y_train = [r["label"] for r in train_rows]
    x_valid = [text(r) for r in valid_rows]
    y_valid = [r["label"] for r in valid_rows]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    batch_size = int(training_cfg["batch_size"])
    accumulation = int(training_cfg["gradient_accumulation_steps"])
    effective_steps = (len(x_train) + batch_size * accumulation - 1) // (batch_size * accumulation)
    total_steps = effective_steps * int(training_cfg["epochs"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(training_cfg["learning_rate"]),
                                  weight_decay=float(training_cfg["weight_decay"]))
    scheduler = get_linear_schedule_with_warmup(optimizer, 0, total_steps)
    use_amp = device.type == "cuda" and training_cfg.get("mixed_precision") == "auto"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    epochs = []
    started = time.perf_counter()
    for epoch in range(int(training_cfg["epochs"])):
        model.train(); order = list(range(len(x_train))); random.Random(seed + epoch).shuffle(order)
        optimizer.zero_grad(set_to_none=True); epoch_loss = 0.0; batches = 0
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            batch_text = [x_train[i] for i in indices]; batch_labels = [y_train[i] for i in indices]
            encoded = encode_batch(tokenizer, batch_text, batch_labels, int(training_cfg["max_length"]))
            encoded = {k: (torch.tensor(v, dtype=torch.long) if isinstance(v, list) else v).to(device)
                       for k, v in encoded.items()}
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                result = model(**encoded)
                loss = result.loss / accumulation
            scaler.scale(loss).backward(); epoch_loss += float(loss.detach().cpu()) * accumulation; batches += 1
            final_batch = start + batch_size >= len(order)
            if (batches % accumulation == 0) or final_batch:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(training_cfg["max_grad_norm"]))
                scaler.step(optimizer); scaler.update(); scheduler.step(); optimizer.zero_grad(set_to_none=True)
        preds, truncated, validation_loss = _predict(model, tokenizer, x_valid, y_valid, int(training_cfg["max_length"]),
                                    batch_size, torch, device)
        val_metrics = _scores(y_valid, preds)
        epochs.append({"epoch": epoch + 1, "mean_train_loss": epoch_loss / max(batches, 1),
                       "validation_loss": validation_loss, "validation_metrics": val_metrics,
                       "validation_truncated_rows": truncated})
    elapsed = time.perf_counter() - started
    final_pred = preds
    fold_dir = output / model_key / ("fb_plus_legacy" if any(r["source_dataset"] == "legacy_human" for r in train_rows) else "fb_only") / f"fold_{fold_no}"
    if fold_dir.exists():
        raise FileExistsError(f"Refusing to overwrite checkpoint: {fold_dir}")
    fold_dir.mkdir(parents=True)
    model.save_pretrained(fold_dir / "checkpoint", safe_serialization=True)
    tokenizer.save_pretrained(fold_dir / "checkpoint")
    provenance = {"model_id": model_id, "resolved_revision": getattr(model.config, "_commit_hash", None),
        "model_type": getattr(model.config, "model_type", None), "label_order": list(LABELS),
        "training_rows": len(train_rows), "validation_rows": len(valid_rows), "train_label_counts": dict(Counter(y_train)),
        "validation_label_counts": dict(Counter(y_valid)), "training_mode": "fixed_epochs_final_checkpoint",
        "epochs": int(training_cfg["epochs"]), "seed": seed, "max_length": int(training_cfg["max_length"]),
        "truncated_validation_rows_final_epoch": epochs[-1]["validation_truncated_rows"],
        "device": str(device), "mixed_precision": bool(use_amp),
        "peak_cuda_memory_bytes": torch.cuda.max_memory_allocated(device) if device.type == "cuda" else None,
        "parameters": sum(p.numel() for p in model.parameters()), "elapsed_seconds": elapsed,
        "epoch_log": epochs, "tokenizer_class": tokenizer.__class__.__name__,
        "torch_version": torch.__version__,
        "phobert_segmenter": ({"java_version": segmenter.java_version,
            "assets_sha256": segmenter.asset_sha256} if model_key == "phobert_v2" else None)}
    if provenance["resolved_revision"] != model_revision:
        raise ValueError("Loaded checkpoint revision differs from the pinned model config")
    _write_json(fold_dir / "run.json", provenance)
    _write_json(fold_dir / "checkpoint_sha256.json", _checksum_tree(fold_dir / "checkpoint"))
    return final_pred, provenance


def run_phase_h(config_path="configs/phase_h/training.json", data_config="configs/phase_h/data.json",
                output=None, model_filter=None, fold_filter=None, local_only=False):
    import torch
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory
    else:
        gpu, vram = None, None
    training_cfg = load(ROOT / config_path)
    os.environ.setdefault("HF_HOME", str((ROOT / training_cfg["local_model_cache"]).resolve()))
    data_cfg, rows, fb, legacy, folds = load_phase_h_data(data_config)
    output = Path(output or (ROOT / training_cfg["output_root"] / "run_01")).resolve()
    if not output.is_relative_to((ROOT / "outputs/phase_h").resolve()):
        raise ValueError("Phase H data/checkpoints must stay under gitignored outputs/phase_h")
    if output.exists():
        raise FileExistsError("Phase H run output exists; choose a new output directory")
    output.mkdir(parents=True)
    segmenter = None
    selected_models = list(training_cfg["models"])
    if model_filter:
        if model_filter not in selected_models:
            raise ValueError("Unknown model configuration")
        selected_models = [model_filter]
    if "phobert_v2" in selected_models:
        segmenter = load_segmenter(ROOT / training_cfg["phobert_segmenter_dir"])
    results, all_oof = [], []
    for model_key in selected_models:
        for augmented in (False, True):
            dataset_key = "fb_plus_legacy" if augmented else "fb_only"
            for fold in folds:
                fold_no = int(fold["fold"])
                if fold_filter is not None and fold_no != fold_filter:
                    continue
                train_rows, valid_rows = fold_training_rows(fb, legacy, fold, augmented)
                prediction, run_info = _fit_fold(training_cfg["models"][model_key]["id"], model_key,
                    train_rows, valid_rows, training_cfg, output, fold_no,
                    local_only=local_only, segmenter=segmenter)
                truth = [r["label"] for r in valid_rows]
                metrics = _scores(truth, prediction)
                results.append({"model": model_key, "dataset": dataset_key, "fold": fold_no,
                                "metrics": metrics, "run": run_info})
                all_oof.extend({"id": r["id"], "fold": fold_no, "model": model_key,
                                "dataset": dataset_key, "human_label": r["label"], "prediction": p}
                               for r, p in zip(valid_rows, prediction))
    complete = len(results) == 12
    if complete:
        for model_key in selected_models:
            for dataset_name in ("fb_only", "fb_plus_legacy"):
                subset = [r for r in all_oof if r["model"] == model_key and r["dataset"] == dataset_name]
                if len(subset) != data_cfg["facebook_rows"] or len({r["id"] for r in subset}) != data_cfg["facebook_rows"]:
                    raise ValueError("Completed configuration must have exactly 346 unique Facebook OOF IDs")
    environment = {"python": platform.python_version(), "torch": torch.__version__}
    for package in ("transformers", "tokenizers", "sentencepiece", "accelerate", "protobuf",
                    "scikit-learn", "numpy", "py_vncorenlp"):
        try:
            environment[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            environment[package] = None
    _write_json(output / "results.json", {"status": "PARTIAL" if not complete else "COMPLETE_DEVELOPMENT_CV",
        "independent_test": False, "direct_leakage_gate": "PASS", "parent_thread_gate": "PASS",
        "legacy_provenance": data_cfg["legacy_identity_provenance"], "gpu_name": gpu, "gpu_vram_bytes": vram,
        "results": results, "oof_row_count": len(all_oof), "models_completed": sorted({r["model"] for r in results}),
        "configs_sha256": {config_path: sha(ROOT / config_path), data_config: sha(ROOT / data_config)},
        "environment": environment})
    with (output / "metrics.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        import csv
        fields = ["model", "dataset", "fold", "accuracy", "macro_f1"]
        for label in LABELS:
            fields.extend([f"{label}_precision", f"{label}_recall", f"{label}_f1", f"{label}_support"])
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in results:
            row = {k: item[k] for k in ("model", "dataset", "fold")}
            row.update(accuracy=item["metrics"]["accuracy"], macro_f1=item["metrics"]["macro_f1"])
            for label in LABELS:
                cls = item["metrics"]["per_class"][label]
                row.update({f"{label}_precision": cls["precision"], f"{label}_recall": cls["recall"],
                            f"{label}_f1": cls["f1-score"], f"{label}_support": cls["support"]})
            writer.writerow(row)
    with (output / "oof_predictions.local.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in all_oof:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    reference_path = ROOT / "outputs/phase_g31/ablation/oof_predictions.csv"
    if reference_path.is_file():
        import csv
        with reference_path.open(encoding="utf-8-sig", newline="") as stream:
            reference_rows = list(csv.DictReader(stream))
        reference = {(row["experiment"], row["id"]): row
                     for row in reference_rows}
        comparisons = []
        for model_key in selected_models:
            for augmented, trial in ((False, "A"), (True, "B")):
                dataset_name = "fb_plus_legacy" if augmented else "fb_only"
                item = compare_oof_to_svm(all_oof, list(reference.values()), model_key, dataset_name, trial)
                if item:
                    comparisons.append(item)
        _write_json(output / "svm_comparison.json", comparisons)
    return output
