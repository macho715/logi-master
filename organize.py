"""파일 정리 및 롤백을 제공합니다./Provide file organization and rollback."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scan import FileRecord
from utils import JournalRecord, append_journal, blake3_path_hash, now_ms


@dataclass(slots=True)
class SchemaConfig:
    """스키마 설정을 표현합니다./Represent schema configuration."""

    target_root: Path
    mode: str = "move"
    conflict: str = "version"
    preserve_structure: bool = True


def load_schema_config(config_path: Path | None) -> SchemaConfig:
    """스키마 설정을 로드합니다./Load schema configuration."""

    if config_path is None or not config_path.exists():
        return SchemaConfig(target_root=Path("C:/PROJECTS_STRUCT"))

    import yaml

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return SchemaConfig(
        target_root=Path(data.get("target_root", "C:/PROJECTS_STRUCT")),
        mode=data.get("mode", "move"),
        conflict=data.get("conflict", "version"),
        preserve_structure=data.get("preserve_structure", True),
    )


def organize_projects(
    projects: list[dict[str, Any]],
    records: list[FileRecord],
    config: SchemaConfig,
    journal_path: Path,
) -> None:
    """프로젝트를 정리합니다./Organize projects according to schema."""

    journal_records = []

    # 타겟 디렉토리 생성
    config.target_root.mkdir(parents=True, exist_ok=True)

    # 파일 매핑 생성
    file_map = {record.path: record for record in records}

    for project in projects:
        project_name = project["name"]
        project_dir = config.target_root / project_name
        project_dir.mkdir(exist_ok=True)

        for file_path in project["files"]:
            if file_path not in file_map:
                continue

            record = file_map[file_path]
            if record.error:
                continue

            source_path = Path(record.path)
            if not source_path.exists():
                continue

            # 대상 경로 결정
            if config.preserve_structure:
                relative_path = source_path.relative_to(source_path.anchor)
                dest_path = project_dir / relative_path
            else:
                dest_path = project_dir / source_path.name

            # 충돌 처리
            if dest_path.exists():
                if config.conflict == "version":
                    stem = dest_path.stem
                    suffix = dest_path.suffix
                    counter = 1
                    while dest_path.exists():
                        dest_path = dest_path.parent / f"{stem}_{counter}{suffix}"
                        counter += 1
                elif config.conflict == "skip":
                    continue
                elif config.conflict == "overwrite":
                    pass  # 덮어쓰기

            # 디렉토리 생성
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 파일 이동/복사
            try:
                if config.mode == "move":
                    shutil.move(str(source_path), str(dest_path))
                    journal_records.append(
                        JournalRecord(
                            timestamp_ms=now_ms(),
                            code="MOVE",
                            source=str(source_path),
                            destination=str(dest_path),
                            details={"project": project_name},
                        )
                    )
                else:  # copy
                    shutil.copy2(str(source_path), str(dest_path))
                    journal_records.append(
                        JournalRecord(
                            timestamp_ms=now_ms(),
                            code="COPY",
                            source=str(source_path),
                            destination=str(dest_path),
                            details={"project": project_name},
                        )
                    )
            except Exception as e:
                journal_records.append(
                    JournalRecord(
                        timestamp_ms=now_ms(),
                        code="ERROR",
                        source=str(source_path),
                        destination=str(dest_path),
                        details={"error": str(e), "project": project_name},
                    )
                )

    # 저널 저장
    if journal_records:
        append_journal(journal_path, journal_records)


def rollback(journal_path: Path) -> None:
    """저널을 사용해 롤백합니다./Rollback using journal."""

    if not journal_path.exists():
        return

    with journal_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("code") == "MOVE" and entry.get("dst"):
                    # MOVE 작업을 되돌리기
                    source = Path(entry["dst"])
                    dest = Path(entry["src"])
                    if source.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source), str(dest))
                elif entry.get("code") == "COPY" and entry.get("dst"):
                    # COPY 작업은 파일 삭제
                    source = Path(entry["dst"])
                    if source.exists():
                        source.unlink()
            except (json.JSONDecodeError, KeyError, OSError):
                continue


__all__ = ["SchemaConfig", "load_schema_config", "organize_projects", "rollback"]
