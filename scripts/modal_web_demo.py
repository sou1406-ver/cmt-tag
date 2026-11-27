"""Fine-tune demo BERTs and serve predictions through an authenticated Modal function."""

from functools import lru_cache
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import re
from time import perf_counter

import modal


app = modal.App("cmt-tag-bert-demo")
volume = modal.Volume.from_name("cmt-tag-web-bert", create_if_missing=True)
mount = "/checkpoints"
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", extra_index_url="https://download.pytorch.org/whl/cu128")
         .pip_install("transformers==4.57.1", "sentencepiece==0.2.1", "protobuf==6.33.5"))
labels = ("POS", "NEG", "NEU")
MAX_INFERENCE_ROWS = 32
config = dict(seed=20261123, epochs=4, batch_size=16, max_length=128,
              learning_rate=2e-5, weight_decay=0.01, warmup=0.1)


def file_hash(path):
    from hashlib import file_digest

    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def model_key(name, train_sha, seed=config["seed"]):
    if name not in {"phobert", "visobert"} or not re.fullmatch(r"[0-9a-f]{64}", train_sha):
        raise ValueError("Invalid demo checkpoint identity")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Invalid training seed")
    settings = {**config, "seed": seed}
    digest = sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:12]
    return f"{name}-{train_sha[:16]}-{digest}"


def pack(examples, padding, device):
    import torch

    width = ceil(max(map(len, examples)) / 8) * 8
    ids = torch.tensor([row + [padding] * (width - len(row)) for row in examples], device=device)
    mask = torch.tensor([[1] * len(row) + [0] * (width - len(row)) for row in examples], device=device)
    return dict(input_ids=ids, attention_mask=mask)


@app.function(image=image, gpu="L4", cpu=2, memory=6144, timeout=900, retries=0,
              volumes={mount: volume})
def train_demo(name, proof, training_sha, token_rows, label_ids, pad, seed=config["seed"]):
    import tempfile

    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForSequenceClassification, get_linear_schedule_with_warmup, set_seed

    start = perf_counter()
    key = model_key(name, training_sha, seed)
    settings = {**config, "seed": seed}
    destination = Path(mount) / key
    metadata = destination / "run.json"
    if metadata.is_file():
        previous = json.loads(metadata.read_text(encoding="utf-8"))
        if (previous["revision"] != proof["revision"] or previous["train_sha256"] != training_sha
                or previous["config"] != settings or previous["train_size"] != len(token_rows)):
            raise ValueError("Existing checkpoint does not match the requested snapshot")
        if file_hash(destination / "model.safetensors") != previous["weights_sha256"]:
            raise ValueError("Existing checkpoint hash is invalid")
        return {**previous, "reused": True}

    if len(token_rows) != len(label_ids) or set(label_ids) != set(range(len(labels))):
        raise ValueError("Invalid training payload")
    if any(not 0 < len(row) <= config["max_length"] for row in token_rows):
        raise ValueError("Invalid token row")
    snapshot = Path(snapshot_download(proof["repository"], revision=proof["revision"],
                                      allow_patterns=list(proof["files"]), token=False))
    for filename, expected in proof["files"].items():
        if file_hash(snapshot / filename) != expected:
            raise ValueError(f"Pretrained checkpoint hash differs: {filename}")

    torch.set_num_threads(2)
    set_seed(seed)
    device = torch.device("cuda")
    model = AutoModelForSequenceClassification.from_pretrained(
        snapshot, local_files_only=True, trust_remote_code=False, num_labels=len(labels),
        id2label=dict(enumerate(labels)), label2id={name: i for i, name in enumerate(labels)},
    ).to(device)
    targets = torch.tensor(label_ids, device=device)
    counts = torch.bincount(targets, minlength=len(labels))
    weights = len(label_ids) / (len(labels) * counts)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"],
                                  weight_decay=config["weight_decay"])
    steps = ceil(len(token_rows) / config["batch_size"]) * config["epochs"]
    scheduler = get_linear_schedule_with_warmup(optimizer, int(steps * config["warmup"]), steps)
    shuffle = torch.Generator().manual_seed(seed)
    losses = []
    trained_at = perf_counter()
    model.train()
    for epoch in range(config["epochs"]):
        total = 0.0
        order = torch.randperm(len(token_rows), generator=shuffle).tolist()
        for i in range(0, len(order), config["batch_size"]):
            indices = order[i:i + config["batch_size"]]
            batch = pack([token_rows[index] for index in indices], pad, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=torch.cuda.is_bf16_supported()):
                logits = model(**batch).logits
                loss = torch.nn.functional.cross_entropy(logits, targets[indices], weight=weights)
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total += loss.item() * len(indices)
        losses.append(total / len(order))
        print(f"{name} seed {seed} epoch {epoch + 1}/{config['epochs']} loss={losses[-1]:.4f}", flush=True)
    with tempfile.TemporaryDirectory(dir=mount) as stage:
        prepared = Path(stage) / key
        model.save_pretrained(prepared, safe_serialization=True)
        result = dict(model=name, checkpoint=key, revision=proof["revision"], train_sha256=training_sha,
                      train_size=len(token_rows), gpu=torch.cuda.get_device_name(0), loss=losses,
                      training_seconds=round(perf_counter() - trained_at, 2),
                      worker_seconds=round(perf_counter() - start, 2),
                      weights_sha256=file_hash(prepared / "model.safetensors"), config=settings)
        (prepared / "run.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        prepared.rename(destination)
    volume.commit()
    return result


@lru_cache(maxsize=1)
def load_checkpoint(key):
    from shutil import copyfile
    from tempfile import TemporaryDirectory

    import torch
    from transformers import AutoModelForSequenceClassification

    folder = Path(mount) / key
    if not folder.is_dir():
        volume.reload()
    metadata = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    if metadata["checkpoint"] != key:
        raise ValueError("Demo checkpoint failed verification")
    torch.set_num_threads(2)
    # Safetensors can keep weights memory-mapped while the model is cached.
    # Load from local scratch so another checkpoint can refresh the mounted volume.
    with TemporaryDirectory() as scratch:
        local = Path(scratch)
        for name in ("config.json", "model.safetensors"):
            copyfile(folder / name, local / name)
        if file_hash(local / "model.safetensors") != metadata["weights_sha256"]:
            raise ValueError("Demo checkpoint failed verification")
        model = AutoModelForSequenceClassification.from_pretrained(
            local, local_files_only=True, trust_remote_code=False, use_safetensors=True
        ).eval()
    return model, metadata


@app.function(image=image, cpu=2, memory=4096, timeout=90, scaledown_window=15,
              min_containers=0, max_containers=1, volumes={mount: volume})
def predict(key, ids):
    import torch

    if not re.fullmatch(r"(phobert|visobert)-[0-9a-f]{16}-[0-9a-f]{12}", key):
        raise ValueError("Invalid checkpoint")
    if not isinstance(ids, list) or not ids:
        raise ValueError("Invalid inference tokens")
    batched = isinstance(ids[0], list)
    rows = ids if batched else [ids]
    if len(rows) > MAX_INFERENCE_ROWS:
        raise ValueError("Too many inference rows")
    model, metadata = load_checkpoint(key)
    if any(not isinstance(row, list) or not 0 < len(row) <= config["max_length"]
           or any(type(token) is not int or not 0 <= token < model.config.vocab_size for token in row)
           for row in rows):
        raise ValueError("Invalid inference tokens")
    with torch.inference_mode():
        probabilities = model(**pack(rows, model.config.pad_token_id, "cpu")).logits.softmax(dim=1).tolist()
    results = [dict(label=labels[max(range(len(scores)), key=scores.__getitem__)],
                    scores=dict(zip(labels, scores, strict=True)), train_sha256=metadata["train_sha256"])
               for scores in probabilities]
    return results if batched else results[0]


@app.local_entrypoint()
def run(gpu: str = "L4"):
    from src.web_bert import BERT_NAMES, RECEIPT, BertTokenizer, load_proof
    from src.web_demo import DEFAULT_TRAIN_DIR, read_train

    if gpu not in {"L4", "A10"}:
        raise ValueError("GPU must be L4 or A10")
    worker = train_demo if gpu == "L4" else train_demo.with_options(gpu=gpu)
    texts, targets, dataset = read_train(DEFAULT_TRAIN_DIR)
    target_ids = [labels.index(label) for label in targets]
    inputs = []
    for name in BERT_NAMES:
        proof = load_proof(name)
        tokenizer = BertTokenizer(name, proof)
        tokens = tokenizer.encode(texts)
        public_proof = {key: proof[key] for key in ("repository", "revision", "files")}
        inputs.append((name, public_proof, tokens, tokenizer.pad))
    handles = []
    for name, proof, tokens, pad in inputs:
        call = worker.spawn(name, proof, dataset["train_sha256"], tokens, target_ids, pad)
        handles.append((name, call))
        print(f"Submitted {name}: {call.object_id}", flush=True)
    results = []
    prepared = RECEIPT.with_name("bert_modal_trained.json")
    prepared.parent.mkdir(parents=True, exist_ok=True)
    for name, call in handles:
        result = call.get()
        results.append({**result, "call_id": call.object_id})
        prepared.write_text(json.dumps({"app": app.name, "models": results}, indent=2), encoding="utf-8")
        print(f"Finished {name}: {result['worker_seconds']} s", flush=True)
