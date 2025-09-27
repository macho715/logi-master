"""대규모 테스트용 가상 파일 시스템 도우미./Virtual filesystem helpers for large tests."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def create_virtual_tree(base: Path, files: dict[str, str]) -> list[Path]:
    """상대 경로 맵으로 파일을 생성합니다./Create files from relative path mapping."""

    created: list[Path] = []
    for relative, content in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


def bulk_create_files(
    base: Path, count: int, prefix: str = "file", extension: str = ".txt"
) -> Iterable[Path]:
    """대량 파일을 생성합니다./Generate many files for stress tests."""

    for index in range(count):
        path = base / f"{prefix}_{index:05d}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"sample-{index}", encoding="utf-8")
        yield path
