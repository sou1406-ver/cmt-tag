"""Train two additional seeds for each final V2 BERT using the same input."""

from scripts.prepare_v2_final import FINAL
from scripts.train_v2_final import MODELS
from src.dataset.common import load, save, sha
from src.models.core import LABELS
from src.web_bert import APP_NAME, BERT_NAMES, BertTokenizer, load_proof
from src.web_demo import read_train


SEEDS = (20261123, 20261124, 20261125)
EXTRA_RUNS = MODELS / "extra_seeds"


def train():
    import modal

    texts, targets, dataset = read_train(FINAL)
    train_sha = dataset["train_sha256"]
    original_path = MODELS / "bert_modal_trained.json"
    original = load(original_path)
    anchors = {entry["model"]: entry for entry in original["models"]}
    if (original["app"] != APP_NAME or anchors.keys() != BERT_NAMES.keys()
            or any(entry["train_sha256"] != train_sha or entry["train_size"] != len(texts)
                   or entry["config"]["seed"] != SEEDS[0] for entry in anchors.values())):
        raise ValueError("Original BERT checkpoints do not match the final V2 training input")

    EXTRA_RUNS.mkdir(exist_ok=True)
    worker = modal.Function.from_name(APP_NAME, "train_demo")
    label_ids = [LABELS.index(label) for label in targets]
    calls = {}
    for name in BERT_NAMES:
        proof = load_proof(name)
        if anchors[name]["revision"] != proof["revision"]:
            raise ValueError(f"Pinned pretrained weights changed for {name}")
        token_rows = None
        for seed in SEEDS[1:]:
            path = EXTRA_RUNS / f"{name}_{seed}.call.json"
            if not path.exists():
                if token_rows is None:
                    tokenizer = BertTokenizer(name, proof)
                    token_rows = tokenizer.encode(texts)
                public_proof = {key: proof[key] for key in ("repository", "revision", "files")}
                call = worker.spawn(name, public_proof, train_sha, token_rows, label_ids, tokenizer.pad, seed)
                save(path, dict(call_id=call.object_id, train_sha256=train_sha))
                print(f"Submitted {name} seed {seed}: {call.object_id}", flush=True)
            recorded = load(path)
            if recorded["train_sha256"] != train_sha:
                raise ValueError("A saved Modal call belongs to another train snapshot")
            calls[name, seed] = recorded["call_id"]

    entries = []
    for (name, seed), call_id in calls.items():
        path = EXTRA_RUNS / f"{name}_{seed}.json"
        entry = (load(path) if path.exists() else
                 {**modal.FunctionCall.from_id(call_id).get(), "call_id": call_id})
        anchor = anchors[name]
        if (entry["model"] != name or entry["revision"] != anchor["revision"]
                or entry["train_sha256"] != train_sha or entry["train_size"] != len(texts)
                or entry["config"] != {**anchor["config"], "seed": seed}
                or entry["checkpoint"] == anchor["checkpoint"] or entry["call_id"] != call_id):
            raise ValueError(f"Unexpected checkpoint for {name} seed {seed}")
        if not path.exists():
            save(path, entry)
        entries.append(entry)
        print(f"Finished {name} seed {seed}: {entry['training_seconds']}s on {entry['gpu']}", flush=True)

    if len({entry["checkpoint"] for entry in entries}) != len(calls):
        raise ValueError("Additional seeds must have distinct checkpoints")
    receipt = EXTRA_RUNS / "bert_modal_trained.json"
    registry = dict(app=APP_NAME, original_receipt_sha256=sha(original_path), models=entries)
    if not receipt.exists():
        save(receipt, registry)
    elif load(receipt) != registry:
        raise ValueError("Additional BERT receipt differs from the completed checkpoints")


if __name__ == "__main__":
    train()
