"""스트리밍 스캔 실행기./Streaming scan runner."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Iterator

from utils import sha256_text

from ..utils.json_stream import JsonArrayWriter
from ..utils.safe_map import SafeMapWriter
from .exceptions import ScanCancelledError, ScanTimeoutError
from .models import (
    CancellationToken,
    FileRecord,
    ProgressCallback,
    ScanBatch,
    ScanError,
    ScanOptions,
    ScanStatistics,
)
from .state import ScanState
from .textual import is_textual_file, read_text_hint
from .walker import DirectoryWalker

__all__ = ["scan_batches", "run_scan_to_files"]


def _ensure_limits(
    state: ScanState,
    options: ScanOptions,
    cancellation_token: CancellationToken | None,
    now: float,
) -> None:
    """취소/타임아웃을 검사합니다./Check cancellation and timeout constraints."""

    if cancellation_token is not None and cancellation_token.is_cancelled():
        raise ScanCancelledError("scan cancelled")
    if options.overall_timeout is not None and now - state.start_time >= options.overall_timeout:
        raise ScanTimeoutError("overall timeout exceeded")
    if (
        options.per_batch_timeout is not None
        and state.batch_elapsed(now) >= options.per_batch_timeout
    ):
        raise ScanTimeoutError("per-batch timeout exceeded")


def scan_batches(
    options: ScanOptions,
    *,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> Iterator[ScanBatch]:
    """옵션에 맞춰 배치로 스캔합니다./Scan directories yielding batches."""

    state = ScanState(options=options, progress_callback=progress_callback)
    walker = DirectoryWalker(options, _make_error_handler(state))
    batch: list[FileRecord] = []
    errors: list[ScanError] = []
    for path in walker.iter_files():
        if state.pending_errors:
            errors.extend(state.pending_errors)
            state.pending_errors.clear()
        now = time.perf_counter()
        _ensure_limits(state, options, cancellation_token, now)
        state.current_path = str(path)
        state.discovered += 1
        try:
            stat_result = path.stat()
            hint = read_text_hint(path, options.sample_bytes) if is_textual_file(path) else ""
            record = FileRecord(
                path=str(path),
                safe_id=sha256_text(str(path)),
                name=path.name,
                ext=path.suffix.lower(),
                size=int(stat_result.st_size),
                mtime=int(stat_result.st_mtime),
                hint=hint,
            )
            batch.append(record)
            state.processed += 1
        except OSError as exc:
            errors.append(ScanError(path=str(path), message=str(exc)))
            state.skipped += 1
            state.errors += 1
        now = time.perf_counter()
        _ensure_limits(state, options, cancellation_token, now)
        if state.should_emit_progress(now):
            state.emit_progress(now)
        if len(batch) >= options.batch_size:
            stats = state.snapshot(now)
            yield ScanBatch(records=batch, stats=stats, errors=errors)
            batch = []
            errors = []
            state.mark_batch_emitted(time.perf_counter())
            if options.throttle_interval > 0.0:
                time.sleep(options.throttle_interval)
    if state.pending_errors:
        errors.extend(state.pending_errors)
        state.pending_errors.clear()
    final_now = time.perf_counter()
    if batch or errors:
        stats = state.snapshot(final_now)
        yield ScanBatch(records=batch, stats=stats, errors=errors)
    if state.progress_callback is not None:
        state.current_path = None
        state.emit_progress(final_now)


def _make_error_handler(state: ScanState) -> Callable[[Path, OSError], None]:
    """오류 리스너를 생성합니다./Create error reporter closure."""

    def _handle(path: Path, error: OSError) -> None:
        state.skipped += 1
        state.errors += 1
        state.pending_errors.append(ScanError(path=str(path), message=str(error)))
        state.current_path = str(path)
        if state.progress_callback is not None:
            state.emit_progress(time.perf_counter())

    return _handle


def run_scan_to_files(
    options: ScanOptions,
    *,
    output_path: Path,
    safe_map_path: Path,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> ScanStatistics:
    """스캔을 실행하고 파일로 기록./Run scan and persist to files."""

    last_stats: ScanStatistics | None = None
    total_errors = 0
    with JsonArrayWriter(output_path) as writer, SafeMapWriter(safe_map_path) as safe_writer:
        for batch in scan_batches(
            options,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        ):
            for record in batch.records:
                writer.write(record.to_payload())
                safe_writer.append(record.safe_id, record.path)
            total_errors += len(batch.errors)
            last_stats = ScanStatistics(
                processed=batch.stats.processed,
                discovered=batch.stats.discovered,
                skipped=batch.stats.skipped,
                errors=total_errors,
                duration_seconds=batch.stats.elapsed_seconds,
            )
    if last_stats is None:
        last_stats = ScanStatistics(
            processed=0,
            discovered=0,
            skipped=0,
            errors=0,
            duration_seconds=0.0,
        )
    return last_stats
