"""파일 시스템 스캔 단계를 제공합니다./Provide file scanning stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, Sequence

from src.scanner import (
    CancellationToken,
    FileRecord,
    ProgressEvent,
    ScanOptions,
    ScanStatistics,
    run_scan_to_files,
    scan_batches,
)
from src.utils.json_stream import JsonArrayWriter
from src.utils.safe_map import SafeMapWriter
from utils import ensure_directory, sha256_text


def scan_paths(
    paths: Sequence[Path],
    *,
    sample_bytes: int = 4096,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    max_depth: int | None = None,
    batch_size: int = 128,
    throttle_interval: float = 0.2,
    overall_timeout: float | None = None,
    per_batch_timeout: float | None = None,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
    cancellation_token: CancellationToken | None = None,
) -> tuple[list[FileRecord], dict[str, str]]:
    """경로 목록을 스캔합니다./Scan provided paths recursively."""

    options = ScanOptions(
        roots=[Path(path) for path in paths],
        include=tuple(include or ()),
        exclude=tuple(exclude or ()),
        max_depth=max_depth,
        batch_size=batch_size,
        sample_bytes=sample_bytes,
        throttle_interval=throttle_interval,
        overall_timeout=overall_timeout,
        per_batch_timeout=per_batch_timeout,
    )
    records: list[FileRecord] = []
    safe_map: dict[str, str] = {}
    for batch in scan_batches(
        options,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    ):
        for record in batch.records:
            records.append(record)
            safe_map[record.safe_id] = record.path
        for error in batch.errors:
            error_path = Path(error.path)
            records.append(
                FileRecord(
                    path=error.path,
                    safe_id=sha256_text(error.path),
                    name=error_path.name,
                    ext=error_path.suffix.lower(),
                    size=0,
                    mtime=0,
                    error=error.message,
                )
            )
    return records, safe_map


def emit_scan(
    records: Iterable[FileRecord], safe_map: dict[str, str], out_path: Path, safe_map_path: Path
) -> None:
    """스캔 결과를 파일로 저장합니다./Persist scan results to disk."""

    ensure_directory(out_path.parent)
    with JsonArrayWriter(out_path) as writer:
        for record in records:
            writer.write(record.to_payload())
    with SafeMapWriter(safe_map_path) as writer:
        for safe_id, path in safe_map.items():
            writer.append(safe_id, path)


def load_records(path: Path) -> list[FileRecord]:
    """스캔 결과를 로드합니다./Load scan records from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[FileRecord] = []
    for item in payload:
        records.append(
            FileRecord(
                path=item.get("path", ""),
                safe_id=item.get("safe_id", ""),
                name=item.get("name", ""),
                ext=item.get("ext", ""),
                size=int(item.get("size", 0)),
                mtime=int(item.get("mtime", 0)),
                hint=item.get("hint", ""),
                bucket=item.get("bucket"),
                error=item.get("error"),
            )
        )
    return records


def stream_paths_to_files(
    paths: Sequence[Path],
    *,
    output_path: Path,
    safe_map_path: Path,
    sample_bytes: int = 4096,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    max_depth: int | None = None,
    batch_size: int = 128,
    throttle_interval: float = 0.2,
    overall_timeout: float | None = None,
    per_batch_timeout: float | None = None,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
    cancellation_token: CancellationToken | None = None,
) -> ScanStatistics:
    """경로를 직접 파일로 기록합니다./Stream scan results directly to files."""

    options = ScanOptions(
        roots=[Path(path) for path in paths],
        include=tuple(include or ()),
        exclude=tuple(exclude or ()),
        max_depth=max_depth,
        batch_size=batch_size,
        sample_bytes=sample_bytes,
        throttle_interval=throttle_interval,
        overall_timeout=overall_timeout,
        per_batch_timeout=per_batch_timeout,
    )
    return run_scan_to_files(
        options,
        output_path=output_path,
        safe_map_path=safe_map_path,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )


__all__ = [
    "FileRecord",
    "emit_scan",
    "load_records",
    "scan_paths",
    "stream_paths_to_files",
]
