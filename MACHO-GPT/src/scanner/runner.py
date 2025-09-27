"""
Streaming scanner runner
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import ScanStatistics, ScanOptions, FileRecord
from .walker import DirectoryWalker
from .textual import is_text_file, extract_text_hint


def stream_scan_paths(
    paths: List[str],
    emit_path: str,
    safe_map_path: str,
    batch_size: int = 1000,
    timeout: float = 30.0,
    include: List[str] = None,
    exclude: List[str] = None,
    max_depth: Optional[int] = None,
    overall_timeout: float = 300.0,
    per_batch_timeout: float = 30.0,
) -> ScanStatistics:
    """
    Stream scan paths to files

    Args:
        paths: List of paths to scan
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
    if include is None:
        include = []
    if exclude is None:
        exclude = []

    options = ScanOptions(
        include=include,
        exclude=exclude,
        max_depth=max_depth,
        batch_size=batch_size,
        timeout=timeout,
        overall_timeout=overall_timeout,
        per_batch_timeout=per_batch_timeout,
    )

    # Initialize statistics
    stats = ScanStatistics()

    # Process each path
    for path_str in paths:
        path = Path(path_str)
        if not path.exists():
            continue

        if path.is_file():
            # Process single file
            record = _process_file(path, options)
            if record:
                stats.add_file(record)
        elif path.is_dir():
            # Process directory
            walker = DirectoryWalker(options)
            for record in walker.walk(path):
                stats.add_file(record)

    # Emit results
    _emit_results(stats, emit_path, safe_map_path)

    return stats


def _process_file(path: Path, options: ScanOptions) -> Optional[FileRecord]:
    """Process a single file"""
    try:
        stat = path.stat()

        # Check if file should be included
        if not _should_include_file(path, options):
            return None

        # Extract text hint if it's a text file
        text_hint = None
        if is_text_file(path):
            text_hint = extract_text_hint(path, limit_bytes=4096)

        # Create file record
        record = FileRecord(
            path=str(path),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_text=is_text_file(path),
            text_hint=text_hint,
        )

        return record

    except Exception:
        return None


def _should_include_file(path: Path, options: ScanOptions) -> bool:
    """Check if file should be included based on patterns"""
    path_str = str(path)

    # Check exclude patterns
    for pattern in options.exclude:
        if pattern in path_str:
            return False

    # Check include patterns
    if options.include:
        for pattern in options.include:
            if pattern in path_str:
                return True
        return False

    return True


def _emit_results(stats: ScanStatistics, emit_path: str, safe_map_path: str):
    """Emit scan results to files"""
    # Emit scan results
    with open(emit_path, "w", encoding="utf-8") as f:
        json.dump(stats.files, f, ensure_ascii=False, indent=2)

    # Emit safe map
    with open(safe_map_path, "w", encoding="utf-8") as f:
        json.dump(stats.safe_map, f, ensure_ascii=False, indent=2)
