"""스캐너 데이터 모델 정의./Define scanner data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

ProgressCallback = Callable[["ProgressEvent"], None]


@dataclass(slots=True)
class ScanOptions:
    """스캔 동작 설정./Configuration for scanning behaviour."""

    roots: Sequence[Path]
    include: Sequence[str] = ()
    exclude: Sequence[str] = ()
    max_depth: int | None = None
    batch_size: int = 128
    sample_bytes: int = 4096
    throttle_interval: float = 0.2
    overall_timeout: float | None = None
    per_batch_timeout: float | None = None
    follow_symlinks: bool = False


@dataclass(slots=True)
class CancellationToken:
    """외부 취소 신호를 전달합니다./Carry cancellation signals."""

    _cancelled: bool = field(default=False, init=False)

    def cancel(self) -> None:
        """취소 상태로 설정합니다./Mark token as cancelled."""

        self._cancelled = True

    def is_cancelled(self) -> bool:
        """취소 여부를 반환합니다./Return cancellation flag."""

        return self._cancelled


@dataclass(slots=True)
class FileRecord:
    """스캔된 단일 파일 메타./Metadata for a scanned file."""

    path: str
    safe_id: str
    name: str
    ext: str
    size: int
    mtime: int
    hint: str = ""
    bucket: str | None = None
    error: str | None = None

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화용 딕트를 생성./Return dict for JSON serialisation."""

        payload = {
            "path": self.path,
            "safe_id": self.safe_id,
            "name": self.name,
            "ext": self.ext,
            "size": self.size,
            "mtime": self.mtime,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.bucket:
            payload["bucket"] = self.bucket
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(slots=True)
class ScanError:
    """스캔 중 발생한 오류 정보를 표현./Represent an error during scanning."""

    path: str
    message: str


@dataclass(slots=True)
class ProgressStats:
    """스캔 진행 통계./Scan progress statistics."""

    processed: int
    discovered: int
    skipped: int
    elapsed_seconds: float
    eta_seconds: float | None


@dataclass(slots=True)
class ProgressEvent:
    """진행 콜백 이벤트./Event payload for progress callback."""

    stats: ProgressStats
    current_path: str | None


@dataclass(slots=True)
class ScanBatch:
    """배치 결과와 통계를 포함./Contain batch results and stats."""

    records: list[FileRecord]
    stats: ProgressStats
    errors: list[ScanError]


@dataclass(slots=True)
class ScanStatistics:
    """전체 스캔 요약 통계./Overall scan statistics."""

    processed: int
    discovered: int
    skipped: int
    errors: int
    duration_seconds: float
