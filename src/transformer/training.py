"""Deterministic, fixed-epoch sequence classification training primitives."""
import random

import numpy as np

from src.transformer import LABELS


LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}


def set_seed(seed, torch):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def encode_batch(tokenizer, texts, labels, max_length):
    if len(texts) != len(labels) or not texts:
        raise ValueError("Text/label batch must be nonempty and aligned")
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=max_length,
                        return_tensors="pt")
    if "input_ids" not in encoded or "attention_mask" not in encoded:
        raise ValueError("Tokenizer must return input_ids and attention_mask")
    if encoded["input_ids"].shape != encoded["attention_mask"].shape:
        raise ValueError("Padding mask shape mismatch")
    encoded["labels"] = [LABEL_TO_ID[label] for label in labels]
    return encoded


def validate_logits(logits, batch_size):
    if len(logits.shape) != 2 or logits.shape[0] != batch_size or logits.shape[1] != 3:
        raise ValueError("Sequence classifier must produce one three-class row per input")
