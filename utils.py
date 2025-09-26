"""공통 유틸리티를 제공합니다./Provide shared utilities."""

from __future__ import annotations

import hashlib
import importlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, cast

_blake3_module: Any | None
try:  # pragma: no cover - optional dependency
    _blake3_module = importlib.import_module("blake3")
except ModuleNotFoundError:  # pragma: no cover
    _blake3_module = None

blake3 = cast(Any, _blake3_module)


@dataclass(slots=True)
class JournalRecord:
    """정리 작업 로그 항목을 표현합니다./Represent a journal entry."""

    timestamp_ms: int
    code: str
    source: str
    destination: str | None = None
    details: dict[str, Any] | None = None

    def to_json(self) -> str:
        """로그 레코드를 JSON 문자열로 변환합니다./Convert record to JSON string."""

        payload: dict[str, Any] = {
            "ts": self.timestamp_ms,
            "code": self.code,
            "src": self.source,
        }
        if self.destination is not None:
            payload["dst"] = self.destination
        if self.details:
            payload.update(self.details)
        return json.dumps(payload, ensure_ascii=False)


def now_ms() -> int:
    """현재 시간을 ms 단위로 반환합니다./Return current time in ms."""

    return int(time.time() * 1000)


def ensure_directory(path: Path) -> None:
    """폴더가 없으면 생성합니다./Create directory if missing."""

    path.mkdir(parents=True, exist_ok=True)


def sha256_text(text: str) -> str:
    """문자열의 SHA-256 해시를 계산합니다./Compute SHA-256 for text."""

    digest = hashlib.sha256()
    digest.update(text.encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def blake3_path_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """파일 콘텐츠 기반 blake3 해시를 반환합니다./Return blake3 hash of file."""

    if blake3 is None:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()[:7]
    hasher = blake3.blake3()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return str(hasher.hexdigest())[:7]


def read_json(path: Path) -> Any:
    """JSON 파일을 읽어 반환합니다./Read and return JSON file."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    """JSON 파일을 저장합니다./Persist payload to JSON file."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def append_journal(path: Path, records: Iterable[JournalRecord]) -> None:
    """저널 파일에 레코드를 추가합니다./Append records to journal file."""

    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")
