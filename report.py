"""리포트 생성을 제공합니다./Provide report generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from utils import JournalRecord, read_json, write_json


@dataclass(slots=True)
class Summary:
    """리포트 요약을 표현합니다./Represent report summary."""

    total_files: int
    total_projects: int
    success_count: int
    error_count: int
    total_size: int


def load_journal(journal_path: Path) -> list[JournalRecord]:
    """저널을 로드합니다./Load journal entries."""

    if not journal_path.exists():
        return []

    entries = []
    with journal_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                entries.append(
                    JournalRecord(
                        timestamp_ms=data.get("ts", 0),
                        code=data.get("code", ""),
                        source=data.get("src", ""),
                        destination=data.get("dst"),
                        details=data.get("details"),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue

    return entries


def summarize(entries: list[JournalRecord]) -> Summary:
    """저널을 요약합니다./Summarize journal entries."""

    total_files = len([e for e in entries if e.code in ["MOVE", "COPY"]])
    success_count = len([e for e in entries if e.code in ["MOVE", "COPY"]])
    error_count = len([e for e in entries if e.code == "ERROR"])

    # 프로젝트 수 계산 (간단한 추정)
    projects = set()
    for entry in entries:
        if entry.details and "project" in entry.details:
            projects.add(entry.details["project"])

    return Summary(
        total_files=total_files,
        total_projects=len(projects),
        success_count=success_count,
        error_count=error_count,
        total_size=0,  # 실제로는 파일 크기 합계 계산
    )


def emit_html(entries: list[JournalRecord], summary: Summary, out_path: Path) -> None:
    """HTML 리포트를 생성합니다./Generate HTML report."""

    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>MACHO-GPT Project Summary</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .entry {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ccc; }}
        .success {{ border-left-color: #4CAF50; }}
        .error {{ border-left-color: #f44336; }}
        .move {{ border-left-color: #2196F3; }}
        .copy {{ border-left-color: #FF9800; }}
    </style>
</head>
<body>
    <h1>MACHO-GPT Project Summary</h1>

    <div class="summary">
        <h2>Summary</h2>
        <p>Total Files: {summary.total_files}</p>
        <p>Total Projects: {summary.total_projects}</p>
        <p>Success: {summary.success_count}</p>
        <p>Errors: {summary.error_count}</p>
    </div>

    <h2>Journal Entries</h2>
    <div class="entries">
"""

    for entry in entries:
        css_class = entry.code.lower()
        html_content += f"""
        <div class="entry {css_class}">
            <strong>{entry.code}</strong> - {entry.source}
            {f' → {entry.destination}' if entry.destination else ''}
            {f'<br><small>{entry.details}</small>' if entry.details else ''}
        </div>
"""

    html_content += """
    </div>
</body>
</html>
"""

    with out_path.open("w", encoding="utf-8") as f:
        f.write(html_content)


def emit_csv(entries: list[JournalRecord], out_path: Path) -> None:
    """CSV 리포트를 생성합니다./Generate CSV report."""

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        f.write("timestamp,code,source,destination,details\n")
        for entry in entries:
            f.write(
                f"{entry.timestamp_ms},{entry.code},{entry.source},{entry.destination or ''},{entry.details or ''}\n"
            )


def emit_json(summary: Summary, out_path: Path) -> None:
    """JSON 리포트를 생성합니다./Generate JSON report."""

    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "total_files": summary.total_files,
        "total_projects": summary.total_projects,
        "success_count": summary.success_count,
        "error_count": summary.error_count,
        "total_size": summary.total_size,
    }

    write_json(out_path, payload)


__all__ = ["Summary", "load_journal", "summarize", "emit_html", "emit_csv", "emit_json"]
