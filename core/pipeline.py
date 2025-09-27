"""파이프라인 핵심 단계 구현(KR). Core pipeline stage implementations (EN)."""

from __future__ import annotations

import html
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, cast

from .errors import PipelineError
from .io import append_jsonl, read_jsonl, write_json, write_json_object
from .timezone import dubai_now
from scan import scan_paths as stream_scan_paths

BUCKET_RULES: Dict[str, Sequence[str]] = {
    "docs": (".md", ".rst", ".txt"),
    "tests": ("test", "_test.py"),
    "scripts": (".sh", ".ps1", ".bat"),
    "src": (".py", ".rs", ".go", ".java"),
    "reports": ("report", "summary"),
    "configs": (".yml", ".yaml", ".toml", ".json", "config"),
    "data": (".csv", ".xlsx"),
}


def scan_paths(sources: Iterable[Path], emit: Path, safe_map_path: Path) -> list[dict[str, Any]]:
    """소스 경로를 스캔한다 · Scan source directories."""

    file_records, safe_map = stream_scan_paths(tuple(sources))
    payload: list[dict[str, Any]] = []
    for record in file_records:
        parent = Path(record.path).parent.name if record.path else ""
        row: dict[str, Any] = {
            **record.to_payload(),
            "parent": parent,
        }
        payload.append(row)
    write_json(emit, payload)
    write_json_object(safe_map_path, safe_map)
    return payload


def _match_bucket(record: dict[str, Any]) -> str:
    """레코드에 적합한 버킷을 찾는다 · Find best bucket for record."""

    name = record.get("name", "").lower()
    ext = record.get("ext", "").lower()
    for bucket, patterns in BUCKET_RULES.items():
        for pattern in patterns:
            if pattern.startswith(".") and ext == pattern:
                return bucket
            if pattern in name:
                return bucket
    return "misc"


def apply_rules(scan_records: list[dict[str, Any]], emit: Path) -> list[dict[str, Any]]:
    """스캔 레코드에 규칙을 적용한다 · Apply rules to scan records."""

    enriched: list[dict[str, Any]] = []
    for record in scan_records:
        bucket = _match_bucket(record)
        enriched_record = {
            **record,
            "bucket": bucket,
            "score": 1.0 if bucket != "misc" else 0.5,
        }
        enriched.append(enriched_record)
    write_json(emit, enriched)
    return enriched


def cluster_projects(
    scored_records: list[dict[str, Any]], emit: Path, mode: str = "local"
) -> dict[str, Any]:
    """레코드를 프로젝트 단위로 묶는다 · Cluster records into projects."""

    clusters: Dict[str, List[dict[str, Any]]] = defaultdict(list)
    for record in scored_records:
        bucket = record.get("bucket", "misc")
        project_name = f"{mode}_{bucket}"
        clusters[project_name].append(record)
    projects: list[dict[str, Any]] = []
    for name, files in clusters.items():
        doc_ids = [str(record.get("safe_id")) for record in files if record.get("safe_id")]
        projects.append({"project": name, "mode": mode, "files": files, "doc_ids": doc_ids})
    payload = {"mode": mode, "projects": projects}
    write_json_object(emit, payload)
    return payload


def _resolve_destination(
    target_dir: Path, record: dict[str, Any], conflict_policy: str
) -> Path | None:
    """대상 파일 경로를 계산 · Compute destination file path."""

    bucket = record.get("bucket", "misc")
    base_dir = target_dir / bucket
    base_dir.mkdir(parents=True, exist_ok=True)
    destination = base_dir / record["name"]
    if conflict_policy == "version":
        safe_id = str(
            record.get("safe_id")
            or hashlib.sha256(str(record.get("path", "")).encode("utf-8")).hexdigest()
        )[:7]
        return cast(Path, base_dir / f"{destination.stem}__{safe_id}{destination.suffix}")
    if conflict_policy == "skip" and destination.exists():
        return None
    return cast(Path, destination)


def organize_projects(
    projects: list[dict[str, Any]],
    target_dir: Path,
    journal_path: Path,
    mode: str = "move",
    conflict_policy: str = "version",
) -> dict[str, Any]:
    """프로젝트 파일을 재배치한다 · Reorganize project files."""

    summary: Dict[str, Any] = {"projects": len(projects), "files": 0}
    for project in projects:
        files = project.get("files", [])
        for record in files:
            source = Path(record["path"])
            if not source.exists():
                raise PipelineError(f"missing source file: {source}", stage="organize")
            destination = _resolve_destination(target_dir, record, conflict_policy)
            if destination is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if mode == "copy":
                shutil.copy2(source, destination)
            else:
                if destination.exists() and conflict_policy == "overwrite":
                    destination.unlink()
                shutil.move(source, destination)
            summary["files"] += 1
            append_jsonl(
                journal_path,
                {
                    "timestamp": dubai_now(),
                    "action": "organize",
                    "project": project.get("project"),
                    "source": str(source),
                    "destination": str(destination),
                },
            )
    return summary


def generate_report(journal_path: Path, out_path: Path) -> None:
    """조직화 리포트를 생성한다 · Generate organisation report."""

    entries = read_jsonl(journal_path)
    html_rows = []
    for entry in entries[-20:]:
        timestamp = html.escape(entry.get("timestamp", ""))
        project = html.escape(entry.get("project", ""))
        source = html.escape(entry.get("source", ""))
        destination = html.escape(entry.get("destination", ""))
        html_rows.append(
            f"<tr><td>{timestamp}</td>"
            f"<td>{project}</td>"
            f"<td>{source}</td>"
            f"<td>{destination}</td></tr>"
        )
    document = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'/>
<title>Project Autosort Report</title>
<style>
body {{ font-family: Arial, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #222; color: #fff; }}
</style>
</head>
<body>
<h1>Project Autosort Summary</h1>
<p>Generated at {dubai_now()}</p>
<table>
<thead><tr><th>Timestamp</th><th>Project</th><th>Source</th><th>Destination</th></tr></thead>
<tbody>{''.join(html_rows)}</tbody>
</table>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")


__all__ = [
    "apply_rules",
    "cluster_projects",
    "generate_report",
    "organize_projects",
    "scan_paths",
]
