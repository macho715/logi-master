"""스트리밍 스캐너 동작을 검증합니다./Validate streaming scanner behaviour."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List

import pytest

from tests.fixtures.virtual_fs import bulk_create_files, create_virtual_tree

if TYPE_CHECKING:
    from src.scanner import FileRecord, ProgressEvent, ScanOptions


@pytest.fixture()
def sample_tree(tmp_path: Path) -> Path:
    """테스트용 트리를 생성합니다./Build sample tree for tests."""

    files = {
        "keep/a.txt": "alpha",
        "keep/b.py": "print('hi')",
        "keep/deep/c.log": "ignored",
        "ignore/.git/config": "user",
        "ignore/note.md": "note",
    }
    create_virtual_tree(tmp_path, files)
    return tmp_path


@pytest.fixture()
def large_tree(tmp_path: Path) -> Path:
    """대량 파일 트리를 생성합니다./Create large file tree for stress."""

    target = tmp_path / "bulk"
    list(bulk_create_files(target, 120))
    return target


def _collect_records(options: ScanOptions, **kwargs: object) -> List[FileRecord]:
    """스캔 결과를 리스트로 모읍니다./Collect scan batches into list."""

    from src.scanner import ScanBatch, scan_batches

    batches = list(scan_batches(options, **kwargs))
    records: List[FileRecord] = []
    for batch in batches:
        assert isinstance(batch, ScanBatch)
        records.extend(batch.records)
    return records


def test_scan_batches_filters_and_depth(sample_tree: Path) -> None:
    """포함/제외/깊이 옵션을 확인합니다./Check include/exclude/depth options."""

    from src.scanner import ScanOptions

    options = ScanOptions(
        roots=[sample_tree],
        include=("*.py", "*.txt"),
        exclude=("**/.git/**", "*.md"),
        max_depth=2,
        batch_size=2,
    )
    records = _collect_records(options)
    paths = {Path(record.path).relative_to(sample_tree) for record in records}
    assert Path("keep/b.py") in paths
    assert Path("keep/a.txt") in paths
    assert Path("ignore/note.md") not in paths
    assert Path("keep/deep/c.log") not in paths


def test_progress_callback_invoked(sample_tree: Path) -> None:
    """진행률 콜백이 호출되는지 확인합니다./Ensure progress callback receives updates."""

    from src.scanner import ProgressEvent, ScanOptions, scan_batches

    events: list[ProgressEvent] = []

    def progress(event: ProgressEvent) -> None:
        events.append(event)

    options = ScanOptions(roots=[sample_tree], batch_size=1, throttle_interval=0.0)
    list(scan_batches(options, progress_callback=progress))
    assert events, "progress callback should receive at least one event"
    max_processed = max(event.stats.processed for event in events)
    assert events[-1].stats.processed == max_processed
    assert events[-1].stats.discovered >= events[-1].stats.processed
    assert events[-1].stats.eta_seconds is None or events[-1].stats.eta_seconds >= 0.0


def test_cancellation_stops_scan(sample_tree: Path) -> None:
    """취소 토큰이 작동하는지 확인합니다./Ensure cancellation token stops scan."""

    from src.scanner import (
        CancellationToken,
        ScanCancelledError,
        ScanOptions,
        scan_batches,
    )

    token = CancellationToken()

    def progress(event: ProgressEvent) -> None:
        if event.stats.processed >= 1:
            token.cancel()

    options = ScanOptions(roots=[sample_tree], batch_size=1, throttle_interval=0.0)
    with pytest.raises(ScanCancelledError):
        for _ in scan_batches(options, cancellation_token=token, progress_callback=progress):
            pass


def test_overall_timeout_raises(sample_tree: Path) -> None:
    """전체 타임아웃 초과 시 예외가 발생해야 합니다./Overall timeout should raise."""

    from src.scanner import ScanOptions, ScanTimeoutError, scan_batches

    options = ScanOptions(roots=[sample_tree], overall_timeout=0.0)
    with pytest.raises(ScanTimeoutError):
        list(scan_batches(options))


def test_stream_writer_produces_json(sample_tree: Path, tmp_path: Path) -> None:
    """스트리밍 기록이 올바른 JSON을 만드는지 확인합니다./Ensure streaming writer outputs valid JSON."""

    from src.scanner import ScanOptions, run_scan_to_files

    out = tmp_path / "scan.json"
    safe_map = tmp_path / "safe.json"

    stats = run_scan_to_files(
        ScanOptions(roots=[sample_tree], batch_size=2, throttle_interval=0.0),
        output_path=out,
        safe_map_path=safe_map,
    )
    assert stats.processed > 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    mapping = json.loads(safe_map.read_text(encoding="utf-8"))
    assert set(mapping.values()) == {str(p) for p in {Path(r["path"]) for r in payload}}


def test_large_tree_batches_limit_memory(large_tree: Path) -> None:
    """배치가 메모리 상한을 유지하는지 확인합니다./Ensure batches limit memory footprint."""

    from src.scanner import ScanOptions, scan_batches

    options = ScanOptions(roots=[large_tree], batch_size=10, throttle_interval=0.0)
    for batch in scan_batches(options):
        assert len(batch.records) <= 10
        assert batch.stats.processed >= len(batch.records)
