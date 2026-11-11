"""One real pretrained forward/backward/evaluation step on synthetic text."""
import json
import platform
from pathlib import Path

from src.dataset.common import ROOT, load
from src.transformer import LABELS
from src.transformer.models import load_classifier, load_segmenter, prepare_phobert, prepare_visobert
from src.transformer.training import encode_batch, validate_logits


def run_smoke(model_key, output, config_path="configs/phase_h/training.json", local_only=False):
    import torch
    training = load(ROOT / config_path)
    import os
    os.environ.setdefault("HF_HOME", str((ROOT / training["local_model_cache"]).resolve()))
    model_id = training["models"][model_key]["id"]
    revision = training["models"][model_key]["revision"]
    segmenter = load_segmenter(ROOT / training["phobert_segmenter_dir"]) if model_key == "phobert_v2" else None
    tokenizer, model = load_classifier(model_id, revision, local_files_only=local_only)
    text = "Bộ phim có nhịp kể chậm nhưng diễn xuất thuyết phục."  # synthetic smoke fixture
    model_text = prepare_phobert(text, segmenter) if segmenter else prepare_visobert(text)
    encoded = encode_batch(tokenizer, [model_text], ["POS"], int(training["max_length"]))
    encoded = {k: (torch.tensor(v, dtype=torch.long) if isinstance(v, list) else v) for k, v in encoded.items()}
    model.train(); result = model(**encoded)
    validate_logits(result.logits, 1)
    result.loss.backward()
    model.eval()
    with torch.no_grad():
        evaluated = model(**{k: v for k, v in encoded.items() if k != "labels"})
    validate_logits(evaluated.logits, 1)
    payload = {"status": "PASS", "model": model_key, "model_id": model_id,
        "resolved_revision": getattr(model.config, "_commit_hash", None), "synthetic_fixture_only": True,
        "label_order": list(LABELS), "logits_shape": list(evaluated.logits.shape),
        "training_loss_finite": bool(torch.isfinite(result.loss)), "python": platform.python_version(),
        "torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
        "parameters": sum(p.numel() for p in model.parameters()),
        "tokenizer": tokenizer.__class__.__name__,
        "phobert_segmenter": ({"java_version": segmenter.java_version,
            "assets_sha256": segmenter.asset_sha256} if model_key == "phobert_v2" else None)}
    if payload["resolved_revision"] != revision:
        raise ValueError("Loaded checkpoint revision differs from the pinned model config")
    output = Path(output)
    output = (ROOT / output).resolve() if not output.is_absolute() else output.resolve()
    if not output.is_relative_to((ROOT / "outputs/phase_h").resolve()):
        raise ValueError("Phase H smoke output must stay under gitignored outputs/phase_h")
    output.mkdir(parents=True, exist_ok=False)
    with (output / "smoke.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return payload
