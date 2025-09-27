"""scan.py 모듈 래퍼를 검증합니다./Validate scan module wrappers."""

from __future__ import annotations

from pathlib import Path

from scan import emit_scan, load_records, scan_paths, stream_paths_to_files
from src.scanner import ProgressEvent


def test_emit_and_load_records(tmp_path: Path) -> None:
    """스트리밍 저장과 로드를 확인합니다./Ensure emit and load work with streaming writers."""

    roots = [tmp_path / "src"]
    roots[0].mkdir(parents=True, exist_ok=True)
    (roots[0] / "a.txt").write_text("alpha", encoding="utf-8")
    (roots[0] / "b.py").write_text("print('b')", encoding="utf-8")
    records, safe_map = scan_paths(roots, batch_size=1, throttle_interval=0.0)
    out_path = tmp_path / "scan.json"
    safe_path = tmp_path / "safe.json"
    emit_scan(records, safe_map, out_path, safe_path)
    reloaded = load_records(out_path)
    assert len(reloaded) == len(records)
    loaded_paths = {item.path for item in reloaded}
    assert loaded_paths == {str(path) for path in roots[0].iterdir()}


def test_stream_paths_to_files_supports_progress(tmp_path: Path) -> None:
    """경로 스트리밍이 진행률 콜백을 지원합니다./Ensure stream_paths_to_files triggers progress callback."""

    base = tmp_path / "data"
    (base / "keep").mkdir(parents=True)
    (base / "keep" / "one.log").write_text("one", encoding="utf-8")
    (base / "skip.md").write_text("skip", encoding="utf-8")
    events: list[ProgressEvent] = []

    def progress(event: ProgressEvent) -> None:
        events.append(event)

    stats = stream_paths_to_files(
        [base],
        output_path=tmp_path / "stream.json",
        safe_map_path=tmp_path / "stream_safe.json",
        include=("**/*.log",),
        exclude=("*.md",),
        throttle_interval=0.0,
        progress_callback=progress,
    )
    assert stats.processed == 1
    assert events, "progress callback should fire"
    payload = load_records(tmp_path / "stream.json")
    assert len(payload) == 1
    assert payload[0].path.endswith("one.log")
