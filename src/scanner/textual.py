"""텍스트 파일 판별 및 힌트 추출./Text detection and hint extraction."""

from __future__ import annotations

import mimetypes
from pathlib import Path

_TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".toml",
    ".csv",
    ".rs",
    ".ts",
    ".js",
    ".java",
}


def is_textual_file(path: Path) -> bool:
    """텍스트 파일인지 판정합니다./Return True if file is textual."""

    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("text"):
        return True
    return path.suffix.lower() in _TEXT_EXTENSIONS


def read_text_hint(path: Path, sample_bytes: int) -> str:
    """텍스트 힌트를 추출합니다./Read textual hint from file."""

    with path.open("rb") as handle:
        chunk = handle.read(sample_bytes)
    return chunk.decode("utf-8", errors="ignore")
