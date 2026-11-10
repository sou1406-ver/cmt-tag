"""Immutable guideline files, pinned to the hashes used by annotation tasks."""
from pathlib import Path

from src.data.importers import digest

DIRECTORY = Path(__file__).resolve().parents[2] / 'docs/guidelines'
GUIDELINE = DIRECTORY / 'MOVIE_SENTIMENT_V2_1.md'
GUIDELINE_VERSION = 'V2.1'
GUIDELINE_SHA256 = '7d0a308a6c64f36308cd980b4e05b4b7fb7eb76b3d80d5f172b96f7c2619ee9a'
LEGACY_VERSION = 'V2.0'
LEGACY_SHA256 = 'b094bcffc28f5099b6aa0278f95eaf4ee35cba1ee4f3965afa7009d26bd43844'


def validate_guideline(version, sha256):
    known = {GUIDELINE_VERSION: (GUIDELINE, GUIDELINE_SHA256),
             LEGACY_VERSION: (DIRECTORY/'MOVIE_SENTIMENT_V2_0.md', LEGACY_SHA256)}
    if version not in known or known[version][1] != sha256:
        raise ValueError('Guideline version/hash mismatch')
    path, expected = known[version]
    if digest(path.read_bytes()) != expected:
        raise ValueError('Immutable guideline file changed; create a new version')
    return version, sha256
