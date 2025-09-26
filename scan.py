"""파일 시스템 스캔 단계를 제공합니다./Provide file scanning stage."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from utils import ensure_directory, sha256_text, write_json


@dataclass(slots=True)
class FileRecord:
    """단일 파일의 메타데이터입니다./Metadata for a single file."""

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
        """저장을 위한 딕셔너리를 반환합니다./Return dict payload for storage."""

        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None and v != ""}


def _is_textual(path: Path) -> bool:
    """텍스트 파일 여부를 추정합니다./Heuristically detect text file."""

    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("text"):
        return True
    return path.suffix.lower() in {
        ".md",
        ".txt",
        ".py",
        ".json",
        ".yml",
        ".yaml",
        ".cfg",
        ".ini",
        ".toml",
        ".csv",
    }


def scan_paths(
    paths: Sequence[Path], sample_bytes: int = 4096
) -> tuple[list[FileRecord], dict[str, str]]:
    """경로 목록을 스캔합니다./Scan provided paths recursively."""

    records: list[FileRecord] = []
    safe_map: dict[str, str] = {}
    for root in paths:
        for child in root.rglob("*"):
            if not child.is_file():
                continue
            try:
                stat = child.stat()
                safe_id = sha256_text(str(child))
                hint = ""
                if _is_textual(child):
                    try:
                        with child.open("rb") as handle:
                            hint = handle.read(sample_bytes).decode("utf-8", errors="ignore")
                    except OSError:
                        hint = ""
                record = FileRecord(
                    path=str(child),
                    safe_id=safe_id,
                    name=child.name,
                    ext=child.suffix.lower(),
                    size=stat.st_size,
                    mtime=int(stat.st_mtime),
                    hint=hint,
                )
                records.append(record)
                safe_map[safe_id] = str(child)
            except OSError as exc:
                records.append(
                    FileRecord(
                        path=str(child),
                        safe_id=sha256_text(str(child)),
                        name=child.name,
                        ext=child.suffix.lower(),
                        size=0,
                        mtime=0,
                        error=str(exc),
                    )
                )
    return records, safe_map


def emit_scan(
    records: Iterable[FileRecord], safe_map: dict[str, str], out_path: Path, safe_map_path: Path
) -> None:
    """스캔 결과를 파일로 저장합니다./Persist scan results to disk."""

    ensure_directory(out_path.parent)
    write_json(out_path, [record.to_payload() for record in records])
    write_json(safe_map_path, safe_map)


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


__all__ = ["FileRecord", "emit_scan", "load_records", "scan_paths"]
