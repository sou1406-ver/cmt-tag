"""One current guide; recognize immutable task provenance from Git history."""
from pathlib import Path

from src.data.importers import digest

GUIDELINE = Path(__file__).resolve().parents[2] / 'docs/guidelines/MOVIE_SENTIMENT.md'
GUIDELINE_VERSION = 'V2.1'
# Original bytes remain at 89ec79a:docs/guidelines/MOVIE_SENTIMENT_V2_0.md.
LEGACY_VERSION = 'V2.0'
LEGACY_SHA256 = 'b094bcffc28f5099b6aa0278f95eaf4ee35cba1ee4f3965afa7009d26bd43844'


def validate_guideline(version, sha256):
    known = {GUIDELINE_VERSION: digest(GUIDELINE.read_bytes()), LEGACY_VERSION: LEGACY_SHA256}
    if version not in known or known[version] != sha256:
        raise ValueError('Guideline version/hash mismatch')
    return version, sha256
