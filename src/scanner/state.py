"""스캔 상태 추적기./Track scan progress state."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import (
    ProgressCallback,
    ProgressEvent,
    ProgressStats,
    ScanError,
    ScanOptions,
    ScanStatistics,
)


@dataclass(slots=True)
class ScanState:
    """스캔 진행 상황을 저장합니다./Store ongoing scan statistics."""

    options: ScanOptions
    progress_callback: ProgressCallback | None
    start_time: float = field(default_factory=time.perf_counter)
    last_callback_time: float = field(default_factory=time.perf_counter)
    last_batch_time: float = field(default_factory=time.perf_counter)
    processed: int = 0
    discovered: int = 0
    skipped: int = 0
    errors: int = 0
    current_path: str | None = None
    pending_errors: list[ScanError] = field(default_factory=list)

    def snapshot(self, now: float) -> ProgressStats:
        """현재 통계를 계산합니다./Build a snapshot of current stats."""

        elapsed = max(now - self.start_time, 0.0)
        remaining = max(self.discovered - self.processed, 0)
        eta: float | None = None
        if self.processed > 0 and remaining > 0:
            rate = elapsed / float(self.processed)
            eta = round(max(rate * remaining, 0.0), 2)
        elif self.processed > 0 and remaining == 0:
            eta = 0.0
        return ProgressStats(
            processed=self.processed,
            discovered=self.discovered,
            skipped=self.skipped,
            elapsed_seconds=round(elapsed, 2),
            eta_seconds=eta,
        )

    def should_emit_progress(self, now: float) -> bool:
        """콜백 호출 여부를 결정합니다./Decide if progress callback should run."""

        if self.progress_callback is None:
            return False
        interval = self.options.throttle_interval
        if interval <= 0.0:
            return True
        return now - self.last_callback_time >= interval

    def emit_progress(self, now: float) -> None:
        """진행률 콜백을 실행합니다./Invoke the progress callback."""

        if self.progress_callback is None:
            self.last_callback_time = now
            return
        event = ProgressEvent(stats=self.snapshot(now), current_path=self.current_path)
        self.progress_callback(event)
        self.last_callback_time = now

    def mark_batch_emitted(self, now: float) -> None:
        """배치가 방출된 시간을 기록합니다./Record last batch emission time."""

        self.last_batch_time = now

    def batch_elapsed(self, now: float) -> float:
        """배치 경과 시간을 반환./Return elapsed time for current batch."""

        return now - self.last_batch_time

    def final_statistics(self, now: float) -> ScanStatistics:
        """최종 통계를 생성합니다./Produce final aggregate statistics."""

        snapshot = self.snapshot(now)
        return ScanStatistics(
            processed=snapshot.processed,
            discovered=snapshot.discovered,
            skipped=snapshot.skipped,
            errors=self.errors,
            duration_seconds=snapshot.elapsed_seconds,
        )
