"""스트리밍 스캔 벤치마크 및 메모리 측정./Benchmark streaming scan with memory profile."""

from __future__ import annotations

import argparse
import tracemalloc
from pathlib import Path
from time import perf_counter

from src.scanner import ProgressEvent, ScanOptions, ScanStatistics, run_scan_to_files


def _format_float(value: float) -> str:
    """소수점 둘째 자리까지 포맷./Format float to two decimals."""

    return f"{value:.2f}"


def _print_progress(event: ProgressEvent) -> None:
    """진행 상황을 로그합니다./Log progress updates."""

    eta = "∞" if event.stats.eta_seconds is None else _format_float(event.stats.eta_seconds)
    path = event.current_path or "-"
    print(
        f"processed={event.stats.processed} "
        f"discovered={event.stats.discovered} "
        f"skipped={event.stats.skipped} "
        f"elapsed={_format_float(event.stats.elapsed_seconds)}s "
        f"eta={eta}s path={path}",
        flush=True,
    )


def run_benchmark(roots: list[Path], out_dir: Path) -> ScanStatistics:
    """벤치마크 스캔을 실행합니다./Execute benchmark scan."""

    options = ScanOptions(roots=roots, batch_size=256, throttle_interval=0.2)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "scan_results.json"
    safe_map_path = out_dir / "safe_map.json"
    tracemalloc.start()
    started = perf_counter()
    stats = run_scan_to_files(
        options,
        output_path=output_path,
        safe_map_path=safe_map_path,
        progress_callback=_print_progress,
    )
    elapsed = perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        "SUMMARY",
        f"duration={_format_float(elapsed)}s",
        f"processed={stats.processed}",
        f"skipped={stats.skipped}",
        f"peak_mb={_format_float(peak / (1024 * 1024))}",
        sep=" ",
    )
    return stats


def main() -> None:
    """CLI 진입점./CLI entry point."""

    parser = argparse.ArgumentParser(description="Stream scan benchmark")
    parser.add_argument("roots", nargs="+", type=Path, help="directories to scan")
    parser.add_argument("--out", type=Path, default=Path(".cache"), help="output directory")
    args = parser.parse_args()
    run_benchmark([root.resolve() for root in args.roots], args.out.resolve())


if __name__ == "__main__":
    main()
