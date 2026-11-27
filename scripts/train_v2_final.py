"""Train the V2 consensus baselines and both BERTs on one pinned train set."""

import argparse
from collections import Counter
from pathlib import Path
from time import perf_counter

import joblib

from scripts.prepare_v2_final import FINAL
from src.dataset.common import ROOT, load, save, seal, sha, staged, verify
from src.models.core import LABELS, v2_baseline_model
from src.web_bert import APP_NAME, BERT_NAMES, BertTokenizer, ModalBert, load_proof
from src.web_demo import MODEL_NAMES, read_train


MODELS = ROOT / "outputs/07_Mo_hinh_cuoi_V2"
SMOKE = ["Phim hay, diễn viên diễn rất tốt.", "Kịch bản lê thê, kết phim hụt hẫng.", "Phim chiếu lúc 7 giờ."]


def run_baselines(output, texts, targets, train_sha256):
    if output.exists():
        if verify(output)["train_sha256"] != train_sha256:
            raise ValueError("Baseline output points to another train set")
        return
    with staged(output) as work:
        runs = {}
        for name in MODEL_NAMES:
            started = perf_counter()
            estimator = v2_baseline_model(name).fit(texts, targets)
            took = round(perf_counter() - started, 2)
            filename = f"{name}.joblib"
            joblib.dump(estimator, work / filename, compress=3)
            predictions = joblib.load(work / filename).predict(SMOKE).tolist()
            if set(predictions) - set(LABELS):
                raise ValueError(f"Baseline {name} returned invalid labels")
            runs[name] = dict(fit_seconds=took, smoke_predictions=predictions, file=filename)
            print(f"Baseline {name}: {took}s", flush=True)
        seal(work, dict(kind="V2_BASELINES", train_sha256=train_sha256, train_size=len(texts), runs=runs))


def run(train_dir, output):
    import modal

    texts, targets, dataset = read_train(train_dir)
    train_sha256 = dataset["train_sha256"]
    output.mkdir(parents=True, exist_ok=True)
    submission_path = output / "modal_calls.json"
    if submission_path.exists():
        submission = load(submission_path)
        if submission["train_sha256"] != train_sha256 or submission["app"] != APP_NAME:
            raise ValueError("Existing Modal calls belong to another train set")
    else:
        submission = dict(app=APP_NAME, train_sha256=train_sha256, calls={})
        save(submission_path, submission)

    worker = modal.Function.from_name(APP_NAME, "train_demo")
    label_ids = [LABELS.index(target) for target in targets]
    proofs = {name: load_proof(name) for name in BERT_NAMES}
    for name, proof in proofs.items():
        if name in submission["calls"]:
            continue
        tokenizer = BertTokenizer(name, proof)
        tokens = tokenizer.encode(texts)
        public_proof = {key: proof[key] for key in ("repository", "revision", "files")}
        call = worker.spawn(name, public_proof, train_sha256, tokens, label_ids, tokenizer.pad)
        submission["calls"][name] = call.object_id
        updated = submission_path.with_suffix(".tmp")
        save(updated, submission)
        updated.replace(submission_path)
        print(f"Submitted {name}: {call.object_id}", flush=True)

    run_baselines(output / "baselines", texts, targets, train_sha256)
    entries = []
    for name, call_id in submission["calls"].items():
        path = output / f"{name}.json"
        entry = (load(path) if path.exists() else
                 {**modal.FunctionCall.from_id(call_id).get(), "call_id": call_id})
        if (entry["model"] != name or entry["revision"] != proofs[name]["revision"]
                or entry["train_sha256"] != train_sha256 or entry["train_size"] != len(texts)):
            raise ValueError(f"Modal returned an unexpected checkpoint for {name}")
        if not path.exists():
            save(path, entry)
        print(f"Finished {name}: {entry['training_seconds']}s on {entry['gpu']}", flush=True)
        entries.append(entry)

    for entry in entries:
        client = ModalBert(entry, train_sha256)
        predicted = [item["label"] for item in client.predict_batch(SMOKE)]
        print(f"Prediction verified {entry['model']}: {predicted}", flush=True)
    receipt = output / "bert_modal_trained.json"
    registry = dict(app=APP_NAME, models=entries)
    if receipt.exists():
        if load(receipt) != registry:
            raise ValueError("BERT receipt differs from completed checkpoints")
    else:
        save(receipt, registry)
    print(f"Trained on {len(texts)} comments: {dict(Counter(targets))}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", type=Path, default=FINAL)
    parser.add_argument("--output", type=Path, default=MODELS)
    args = parser.parse_args()
    run(args.train_dir, args.output)
