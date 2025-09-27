"""디렉터리 순회 도우미./Directory walking helpers."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Callable, Iterator

from .models import ScanOptions

ErrorReporter = Callable[[Path, OSError], None]


class DirectoryWalker:
    """옵션에 맞게 파일을 순회합니다./Walk files according to options."""

    def __init__(self, options: ScanOptions, report_error: ErrorReporter) -> None:
        self._options = options
        self._report_error = report_error
        self._include = tuple(options.include)
        self._exclude = tuple(options.exclude)

    def iter_files(self) -> Iterator[Path]:
        """파일 경로를 생성합니다./Yield file paths."""

        for root in self._options.roots:
            yield from self._walk_root(root)

    def _walk_root(self, root: Path) -> Iterator[Path]:
        if not root.exists():
            self._report_error(root, FileNotFoundError(f"missing root: {root}"))
            return
        stack: list[tuple[Path, int]] = [(root, 0)]
        follow = self._options.follow_symlinks
        max_depth = self._options.max_depth
        while stack:
            current, depth = stack.pop()
            try:
                with os.scandir(current) as iterator:
                    for entry in iterator:
                        entry_path = Path(entry.path)
                        try:
                            relative = entry_path.relative_to(root)
                        except ValueError:
                            relative = entry_path
                        rel_posix = relative.as_posix()
                        is_dir = entry.is_dir(follow_symlinks=follow)
                        if self._is_excluded(rel_posix, is_dir):
                            continue
                        if is_dir:
                            if max_depth is not None and depth + 1 > max_depth:
                                continue
                            stack.append((entry_path, depth + 1))
                            continue
                        if not entry.is_file(follow_symlinks=follow):
                            continue
                        if self._include and not self._match_include(rel_posix):
                            continue
                        yield entry_path
            except OSError as exc:
                self._report_error(current, exc)

    def _match_include(self, rel: str) -> bool:
        return any(fnmatch.fnmatchcase(rel, pattern) for pattern in self._include)

    def _is_excluded(self, rel: str, is_dir: bool) -> bool:
        if not self._exclude:
            return False
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in self._exclude):
            return True
        if is_dir:
            rel_dir = f"{rel}/"
            return any(fnmatch.fnmatchcase(rel_dir, pattern) for pattern in self._exclude)
        return False
