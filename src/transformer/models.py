"""Model-specific text preparation and lazy Hugging Face loading."""
from pathlib import Path
import subprocess

from src.dataset.common import sha


def prepare_phobert(text, segmenter, legacy_source=False):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("PhoBERT input must be nonempty text")
    # Treat legacy underscores as candidate syllable separators and rerun the
    # configured segmenter, never as proof of valid pretrained-model tokenization.
    segment_input = text.replace("_", " ") if legacy_source else text
    return segmenter.word_segment(segment_input)


def prepare_visobert(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ViSoBERT input must be nonempty text")
    # Preserve the original text_view verbatim for the model tokenizer.
    return text


def load_segmenter(model_dir):
    """Load the official local VnCoreNLP RDRSegmenter; no implicit downloads."""
    from py_vncorenlp import VnCoreNLP
    model_dir = Path(model_dir).resolve()
    if not (model_dir.is_dir() and (model_dir / "VnCoreNLP-1.2.jar").is_file()
            and (model_dir / "models").is_dir()):
        raise FileNotFoundError("Install local VnCoreNLP-1.2.jar and models under the configured directory")
    java = subprocess.run(["java", "-version"], check=True, capture_output=True, text=True, timeout=10)
    java_line = (java.stderr or java.stdout).splitlines()[0]
    segmenter = VnCoreNLP(annotators=["wseg"], save_dir=str(model_dir))

    class Adapter:
        java_version = java_line
        asset_sha256 = {p.relative_to(model_dir).as_posix(): sha(p)
                        for p in sorted(model_dir.rglob("*")) if p.is_file()}

        def word_segment(self, text):
            segmented = segmenter.word_segment(text)
            return " ".join(segmented) if isinstance(segmented, list) else str(segmented)

    return Adapter()


def load_classifier(model_id, revision, num_labels=3, local_files_only=False):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Model revision must be a pinned full commit SHA")
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=local_files_only)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, revision=revision, num_labels=num_labels, local_files_only=local_files_only,
        label2id={"POS": 0, "NEG": 1, "NEU": 2}, id2label={0: "POS", 1: "NEG", 2: "NEU"},
        ignore_mismatched_sizes=True,
    )
    return tokenizer, model
