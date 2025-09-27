"""JSON 스트리밍 유틸리티./JSON streaming utilities."""

from __future__ import annotations

import json
from pathlib import Path

from types import TracebackType
from typing import Optional, Type

from utils import ensure_directory


class JsonArrayWriter:
    """JSON 배열을 스트리밍으로 작성./Stream-write JSON arrays."""

    def __init__(self, path: Path) -> None:
        ensure_directory(path.parent)
        self._handle = path.open("w", encoding="utf-8")
        self._handle.write("[\n")
        self._first = True

    def write(self, payload: dict[str, object]) -> None:
        """단일 항목을 추가합니다./Append a JSON object."""

        if not self._first:
            self._handle.write(",\n")
        json.dump(payload, self._handle, ensure_ascii=False)
        self._first = False

    def close(self) -> None:
        """스트림을 종료합니다./Close the underlying stream."""

        self._handle.write("\n]\n")
        self._handle.close()

    def __enter__(self) -> "JsonArrayWriter":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()
