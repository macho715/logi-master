"""정리 결과 보고서를 생성합니다./Generate organization reports."""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Union, cast

from utils import ensure_directory


@dataclass(slots=True)
class ReportSummary:
    """리포트 요약 지표입니다./Report summary metrics."""

    total_operations: int
    by_code: dict[str, int]
    last_updated: float


def load_journal(path: Path) -> list[dict[str, object]]:
    """저널 JSONL을 로드합니다./Load journal JSONL."""

    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, object]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def summarize(entries: Iterable[dict[str, object]]) -> ReportSummary:
    """저널 항목을 요약합니다./Summarize journal entries."""

    items = list(entries)
    codes = [str(item.get("code", "UNKNOWN")) for item in items]
    counts = Counter(codes)
    timestamps: list[int] = []
    for item in items:
        raw_value = item.get("ts", 0)
        try:
            numeric = int(cast(Union[int, float, str], raw_value))
        except (TypeError, ValueError):
            numeric = 0
        timestamps.append(numeric)
    last = (max(timestamps) if timestamps else 0) / 1000.0
    return ReportSummary(total_operations=len(items), by_code=dict(counts), last_updated=last)


def emit_csv(entries: Iterable[dict[str, object]], path: Path) -> None:
    """저널을 CSV로 내보냅니다./Export journal to CSV."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ts", "code", "src", "dst"])
        writer.writeheader()
        for item in entries:
            writer.writerow(
                {
                    "ts": item.get("ts"),
                    "code": item.get("code"),
                    "src": item.get("src"),
                    "dst": item.get("dst"),
                }
            )


def emit_json(summary: ReportSummary, path: Path) -> None:
    """요약 정보를 JSON으로 저장합니다./Save summary as JSON."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "total_operations": summary.total_operations,
                "by_code": summary.by_code,
                "last_updated": summary.last_updated,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def emit_html(entries: Iterable[dict[str, object]], summary: ReportSummary, path: Path) -> None:
    """HTML 리포트를 생성합니다./Generate HTML report."""

    ensure_directory(path.parent)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(summary.last_updated))
    row_template = "<tr><td>{ts}</td><td>{code}</td><td>{src}</td><td>{dst}</td></tr>"
    table_rows = "\n".join(
        row_template.format(
            ts=item.get("ts"),
            code=item.get("code"),
            src=item.get("src"),
            dst=item.get("dst", ""),
        )
        for item in entries
    )
    html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>Project Autosort Report</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; margin: 24px; background: #0f172a; color: #e2e8f0; }}
    .card {{ background: #1e293b; padding: 16px 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 10px 25px rgba(15,23,42,0.3); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ padding: 8px 12px; border-bottom: 1px solid #334155; text-align: left; }}
    th {{ color: #38bdf8; }}
  </style>
</head>
<body>
  <h1>Project Autosort Summary</h1>
  <div class="grid">
    <div class="card">
      <h2>총 작업 수</h2>
      <p style="font-size: 28px; font-weight: 600;">{summary.total_operations}</p>
    </div>
    <div class="card">
      <h2>마지막 업데이트</h2>
      <p>{timestamp}</p>
    </div>
    <div class="card">
      <h2>작업별 건수</h2>
      <ul>
        {''.join(f"<li>{code}: {count}</li>" for code, count in summary.by_code.items())}
      </ul>
    </div>
  </div>
  <div class="card">
    <h2>저널 로그</h2>
    <table>
      <thead>
        <tr><th>Timestamp</th><th>Code</th><th>Source</th><th>Destination</th></tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>
</body>
</html>
    """
    with path.open("w", encoding="utf-8") as handle:
        handle.write(html)


def generate_html_report(journal_path: Path, output_path: Path) -> None:
    """저널에서 HTML 리포트를 생성합니다./Generate HTML report from journal."""

    entries = load_journal(journal_path)
    summary = summarize(entries)
    emit_html(entries, summary, output_path)


__all__ = [
    "ReportSummary",
    "emit_csv",
    "emit_html",
    "emit_json",
    "generate_html_report",
    "load_journal",
    "summarize",
]
