"""Local tokenizer and authenticated Modal client for the web demo."""

import json
from math import isclose, isfinite
from pathlib import Path
import sys

from src.dataset.common import ROOT, sha


APP_NAME = "cmt-tag-bert-demo"
BERT_NAMES = {"phobert": "PhoBERT", "visobert": "ViSoBERT"}
PROOFS = ROOT / "data" / "local_models" / "v2_fresh_checkpoints"
RECEIPT = ROOT / "data" / "web_demo" / "bert_modal.json"
MAX_LENGTH = 128
PREDICTION_BATCH_SIZE = 32


class RemotePredictionError(RuntimeError):
    pass


def load_proof(name):
    if name not in BERT_NAMES:
        raise ValueError("Mô hình BERT không hợp lệ.")
    return json.loads((PROOFS / f"{name}.json").read_text(encoding="utf-8"))


class BertTokenizer:
    def __init__(self, name, proof):
        from transformers import AutoTokenizer

        self.name = name
        repository = "models--" + proof["repository"].replace("/", "--")
        packaged = PROOFS / repository / "snapshots" / proof["revision"]
        local = packaged if packaged.is_dir() else Path(proof["path"])
        tokenizer_files = {file: digest for file, digest in proof["files"].items()
                           if not file.endswith((".bin", ".safetensors"))}
        if not tokenizer_files or any(sha(local / file) != digest for file, digest in tokenizer_files.items()):
            raise ValueError(f"Tokenizer {name} lệch checkpoint đã ghim.")
        self.tokenizer = AutoTokenizer.from_pretrained(
            local, local_files_only=True, use_fast=name != "phobert", trust_remote_code=False
        )
        self.pad = self.tokenizer.pad_token_id

    def encode(self, texts):
        if self.name == "phobert":
            from pyvi import ViTokenizer

            texts = [ViTokenizer.tokenize(text) for text in texts]
        return self.tokenizer(texts, truncation=True, max_length=MAX_LENGTH,
                              return_attention_mask=False, return_token_type_ids=False)["input_ids"]


class ModalBert:
    def __init__(self, entry, train_sha256):
        local_client = ROOT / "data" / "local_models" / "modal_client"
        if (local_client / "modal").is_dir() and str(local_client) not in sys.path:
            sys.path.append(str(local_client))
        import modal

        self.name = entry["model"]
        proof = load_proof(self.name)
        if (entry["revision"] != proof["revision"] or entry["train_sha256"] != train_sha256
                or entry["train_size"] < 1):
            raise ValueError("Checkpoint demo BERT lệch snapshot V2.")
        self.tokenizer = BertTokenizer(self.name, proof)
        self.remote = modal.Function.from_name(APP_NAME, "predict")
        self.checkpoint = entry["checkpoint"]
        self.train_sha256 = train_sha256

    def predict(self, text):
        encoded, = self.tokenizer.encode([text])
        return self.validate_prediction(self.run_remote(encoded))

    def predict_batch(self, texts):
        encoded = self.tokenizer.encode(list(texts))
        predictions = []
        for start in range(0, len(encoded), PREDICTION_BATCH_SIZE):
            batch = encoded[start:start + PREDICTION_BATCH_SIZE]
            results = self.run_remote(batch)
            if not isinstance(results, list) or len(results) != len(batch):
                raise RemotePredictionError("Modal trả sai số lượng kết quả BERT.")
            predictions.extend(self.validate_prediction(result) for result in results)
        return predictions

    def run_remote(self, encoded):
        try:
            return self.remote.remote(self.checkpoint, encoded)
        except Exception as exc:
            raise RemotePredictionError("Modal chưa trả kết quả. M có thể thử lại hoặc chọn baseline.") from exc

    def validate_prediction(self, result):
        if not isinstance(result, dict):
            raise RemotePredictionError("Modal trả kết quả BERT không hợp lệ.")
        if result.get("train_sha256") != self.train_sha256:
            raise RemotePredictionError("Checkpoint Modal lệch snapshot train của demo.")
        scores = result.get("scores")
        if (not isinstance(scores, dict) or set(scores) != {"POS", "NEG", "NEU"}
                or any(type(p) not in (int, float) or not isfinite(p) or not 0 <= p <= 1 for p in scores.values())
                or not isclose(sum(scores.values()), 1, abs_tol=1e-5)
                or result.get("label") != max(scores, key=scores.__getitem__)):
            raise RemotePredictionError("Modal trả kết quả BERT không hợp lệ.")
        return result


def enable():
    """Probe both deployed models with a synthetic sentence, then enable them for the local web app."""
    from src.web_demo import DEFAULT_TRAIN_DIR, read_train

    source = RECEIPT.with_name("bert_modal_trained.json")
    registry = json.loads(source.read_text(encoding="utf-8"))
    _, _, train = read_train(DEFAULT_TRAIN_DIR)
    if registry["app"] != APP_NAME or {entry["model"] for entry in registry["models"]} != BERT_NAMES.keys():
        raise ValueError("Training receipt does not contain both BERT models")
    for entry in registry["models"]:
        model = ModalBert(entry, train["train_sha256"])
        result = model.predict("Phim hay, dien vien dien rat tot.")
        print(f"Modal {entry['model']}: {result['label']}", flush=True)
    updated = RECEIPT.with_suffix(".tmp")
    updated.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    updated.replace(RECEIPT)


if __name__ == "__main__":
    enable()
