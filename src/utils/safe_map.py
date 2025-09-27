"""세이프맵 스트리밍 저장소./Streaming safe-map writer."""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from utils import ensure_directory


class SafeMapWriter:
    """safe_id→경로 매핑을 스트리밍으로 저장./Stream safe_id to path mapping."""

    def __init__(self, path: Path) -> None:
        ensure_directory(path.parent)
        self._handle = path.open("w", encoding="utf-8")
        self._handle.write("{\n")
        self._first = True

    def append(self, safe_id: str, path: str) -> None:
        """새 항목을 기록합니다./Write a new mapping entry."""

        if not self._first:
            self._handle.write(",\n")
        json.dump(safe_id, self._handle, ensure_ascii=False)
        self._handle.write(": ")
        json.dump(path, self._handle, ensure_ascii=False)
        self._first = False

    def close(self) -> None:
        """스트림을 종료합니다./Close the writer stream."""

        self._handle.write("\n}\n")
        self._handle.close()

    def __enter__(self) -> "SafeMapWriter":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()
