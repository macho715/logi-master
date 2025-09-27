"""
Streaming file scanner for MACHO-GPT
"""

import json
from pathlib import Path
from typing import Iterator, Dict, Any, List, Optional
from .src.scanner.runner import stream_scan_paths
from .src.scanner.models import ScanStatistics


def stream_paths_to_files(
    paths: tuple[Path, ...],
    emit_path: Path,
    safe_map_path: Path,
    batch_size: int = 1000,
    timeout: float = 30.0,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    overall_timeout: float = 300.0,
    per_batch_timeout: float = 30.0,
) -> ScanStatistics:
    """
    Stream scan paths to files and return statistics

    Args:
        paths: Tuple of paths to scan
        emit_path: Path to emit scan results
        safe_map_path: Path to emit safe map
        batch_size: Batch size for processing
        timeout: Timeout for individual operations
        include: Include patterns
        exclude: Exclude patterns
        max_depth: Maximum directory depth
        overall_timeout: Overall timeout for the entire scan
        per_batch_timeout: Timeout per batch

    Returns:
        ScanStatistics object with scan results
    """
    # Convert paths to strings for the scanner
    path_strings = [str(p) for p in paths]

    # Call the streaming scanner
    stats = stream_scan_paths(
        paths=path_strings,
        emit_path=str(emit_path),
        safe_map_path=str(safe_map_path),
        batch_size=batch_size,
        timeout=timeout,
        include=include or [],
        exclude=exclude or [],
        max_depth=max_depth,
        overall_timeout=overall_timeout,
        per_batch_timeout=per_batch_timeout,
    )

    return stats
