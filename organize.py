"""파일 정리 및 롤백 유틸리티를 제공합니다./Provide organization and rollback utilities."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence, cast

import yaml

from scan import FileRecord
from utils import (
    JournalRecord,
    append_journal,
    blake3_path_hash,
    ensure_directory,
    now_ms,
)

DEFAULT_SCHEMA_PATHS: tuple[str, ...] = (
    "src/",
    "docs/",
    "data/",
    "tests/",
    "images/",
    "misc/",
)


@dataclass(slots=True)
class OrganizeConfig:
    """정리 동작 구성을 보관합니다./Hold configuration for organization."""

    target_root: Path
    mode: Literal["move", "copy"]
    conflict: Literal["version", "skip", "overwrite"]
    schema_paths: Sequence[str]


def load_schema_config(path: Path | None) -> OrganizeConfig:
    """스키마 설정을 로드합니다./Load schema configuration."""

    schema_paths: Sequence[str] = DEFAULT_SCHEMA_PATHS
    target_root = Path("C:/PROJECTS_STRUCT")
    mode: Literal["move", "copy"] = "move"
    conflict: Literal["version", "skip", "overwrite"] = "version"
    if path and path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("structure"), list) and data["structure"]:
                schema_paths = [str(item) for item in data["structure"]]
            if data.get("target_root"):
                target_root = Path(str(data["target_root"]))
            if data.get("mode") in {"move", "copy"}:
                mode = data["mode"]
            if data.get("conflict_policy") in {"version", "skip", "overwrite"}:
                conflict = data["conflict_policy"]
    return OrganizeConfig(
        target_root=target_root, mode=mode, conflict=conflict, schema_paths=schema_paths
    )


def ensure_schema(base: Path, schema_paths: Sequence[str]) -> None:
    """프로젝트 하위 스키마를 생성합니다./Create project sub-directories."""

    for relative in schema_paths:
        ensure_directory((base / relative).resolve())


def _versioned_name(dst_dir: Path, name: str, suffix: str) -> Path:
    """버전 충돌 이름을 생성합니다./Build versioned filename."""

    stem = Path(name).stem
    ext = Path(name).suffix
    candidate = dst_dir / f"{stem}__{suffix}{ext}"
    counter = 1
    while candidate.exists():
        candidate = dst_dir / f"{stem}__{suffix}_{counter}{ext}"
        counter += 1
    return candidate


def organize_files(
    records: Sequence[FileRecord],
    safe_map: dict[str, str],
    config: OrganizeConfig,
    journal_path: Path,
) -> None:
    """파일들을 직접 정리합니다./Organize files directly."""
    
    # 단순한 프로젝트 구조로 파일들을 정리
    # 모든 파일을 하나의 프로젝트로 처리
    projects = {
        "projects": [{
            "project_label": "unified_project",
            "doc_ids": [record.path for record in records]
        }]
    }
    
    organize_projects(projects, records, config, journal_path)


def organize_projects(
    projects: dict[str, object],
    scored_records: Sequence[FileRecord],
    config: OrganizeConfig,
    journal_path: Path,
) -> None:
    """프로젝트별 파일을 정리합니다./Organize files by project."""

    ensure_directory(config.target_root)
    by_path = {record.path: record for record in scored_records}
    journal_entries: list[JournalRecord] = []
    raw_projects = projects.get("projects", [])
    project_entries: list[dict[str, object]] = []
    if isinstance(raw_projects, Sequence):
        for item in raw_projects:
            if isinstance(item, dict):
                project_entries.append(cast(dict[str, object], item))
    for project in project_entries:
        label = project.get("project_label") or project.get("project_id") or "misc"
        label = str(label)
        base = config.target_root / label
        ensure_directory(base)
        ensure_schema(base, config.schema_paths)
        raw_doc_ids = project.get("doc_ids", [])
        doc_ids = [str(p) for p in raw_doc_ids] if isinstance(raw_doc_ids, Sequence) else []
        for path_str in doc_ids:
            src = Path(path_str)
            if not src.exists():
                journal_entries.append(
                    JournalRecord(timestamp_ms=now_ms(), code="MISS", source=str(src))
                )
                continue
            record = by_path.get(str(src))
            bucket = record.bucket if record and record.bucket else "misc"
            dst_dir = base / bucket
            ensure_directory(dst_dir)
            dst_path = dst_dir / src.name
            if dst_path.exists():
                if config.conflict == "skip":
                    journal_entries.append(
                        JournalRecord(
                            timestamp_ms=now_ms(),
                            code="SKIP",
                            source=str(src),
                            details={"reason": "exists"},
                        )
                    )
                    continue
                if config.conflict == "version":
                    hash_suffix = blake3_path_hash(src)
                    dst_path = _versioned_name(dst_dir, src.name, hash_suffix)
            try:
                if config.mode == "move":
                    final_path = Path(shutil.move(str(src), str(dst_path)))
                    journal_entries.append(
                        JournalRecord(
                            timestamp_ms=now_ms(),
                            code="MOVE",
                            source=str(src),
                            destination=str(final_path),
                        )
                    )
                else:
                    final_path = Path(shutil.copy2(str(src), str(dst_path)))
                    journal_entries.append(
                        JournalRecord(
                            timestamp_ms=now_ms(),
                            code="COPY",
                            source=str(src),
                            destination=str(final_path),
                        )
                    )
            except shutil.Error as exc:
                journal_entries.append(
                    JournalRecord(
                        timestamp_ms=now_ms(),
                        code="ERROR",
                        source=str(src),
                        destination=str(dst_path),
                        details={"message": str(exc)},
                    )
                )
    append_journal(journal_path, journal_entries)


def rollback(journal_path: Path) -> None:
    """저널을 기반으로 원복합니다./Rollback using journal entries."""

    if not journal_path.exists():
        return
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("code") not in {"MOVE", "COPY"}:
            continue
        src = Path(data["src"])
        dst = Path(data.get("dst", ""))
        if not dst.exists():
            continue
        ensure_directory(src.parent)
        shutil.move(str(dst), str(src))


__all__ = ["OrganizeConfig", "ensure_schema", "load_schema_config", "organize_files", "organize_projects", "rollback"]
