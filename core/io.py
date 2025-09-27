"""입출력 헬퍼(KR). Input/output helpers (EN)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List


def read_json(path: Path) -> list[dict[str, Any]]:
    """JSON 배열 파일을 읽는다 · Read JSON array file."""

    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [dict(item) for item in data]
    raise ValueError(f"expected list payload: {path}")


def write_json(path: Path, payload: Iterable[dict[str, Any]]) -> None:
    """JSON 배열을 저장한다 · Persist JSON array payload."""

    path.parent.mkdir(parents=True, exist_ok=True)
    data: List[dict[str, Any]] = [dict(item) for item in payload]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    """JSON 오브젝트를 기록한다 · Write JSON object payload."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_object(path: Path) -> dict[str, Any]:
    """JSON 오브젝트를 읽는다 · Read JSON object payload."""

    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return dict(data)
    raise ValueError(f"expected object payload: {path}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSONL 파일을 읽는다 · Read JSONL log file."""

    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """JSONL 엔트리를 추가한다 · Append JSONL entry."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


__all__ = [
    "read_json",
    "write_json",
    "write_json_object",
    "read_json_object",
    "read_jsonl",
    "append_jsonl",
]
