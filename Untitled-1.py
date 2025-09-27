"""Project Autosort CLI 엔트리포인트./Project Autosort CLI entrypoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

import click

from classify import (
    apply_rules,
    cluster_hybrid,
    cluster_local,
    emit_projects,
    emit_scores,
    load_rules_config,
)
from organize import load_schema_config, organize_projects, rollback
from report import emit_csv, emit_html, emit_json, load_journal, summarize
from scan import emit_scan, load_records, scan_paths


@click.group()
def cli() -> None:
    """Autosort 명령 그룹입니다./Autosort command group."""


def run_scan(paths: Sequence[Path], sample_bytes: int, emit: Path, safe_map_path: Path) -> None:
    """스캔 단계를 실행합니다./Execute scan stage."""
    
    records, safe_map = scan_paths(paths, sample_bytes=sample_bytes)
    emit_scan(records, safe_map, emit, safe_map_path)
    click.echo(f"[scan] {len(records)} items saved to {emit}")


@cli.command("scan")
@click.option("--paths", multiple=True, required=True, type=click.Path(path_type=Path))
@click.option("--sample-bytes", default=4096, show_default=True, type=int)
@click.option(
    "--emit", default=Path(".cache/scan.json"), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--safe-map",
    "safe_map_path",
    default=Path(".cache/safe_map.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
def scan_command(paths: Sequence[Path], sample_bytes: int, emit: Path, safe_map_path: Path) -> None:
    """선택한 경로를 스캔합니다./Scan selected directories."""
    
    run_scan(paths, sample_bytes, emit, safe_map_path)


def run_rules(scan_path: Path, emit: Path, rules_config: Path) -> None:
    """규칙 단계를 실행합니다./Execute rule tagging stage."""
    
    records = load_records(scan_path)
    rule_defs = load_rules_config(rules_config if rules_config.exists() else None)
    tagged = apply_rules(records, rule_defs)
    emit_scores(tagged, emit)
    click.echo(f"[rules] saved to {emit}")


@cli.command("rules")
@click.option(
    "--scan", "scan_path", default=Path(".cache/scan.json"), type=click.Path(path_type=Path)
)
@click.option("--emit", default=Path(".cache/scores.json"), type=click.Path(path_type=Path))
@click.option("--rules-config", default=Path("rules.yml"), type=click.Path(path_type=Path))
def rules_command(scan_path: Path, emit: Path, rules_config: Path) -> None:
    """규칙 기반 버킷을 계산합니다./Assign rule buckets."""
    
    run_rules(scan_path, emit, rules_config)


def run_cluster(scores: Path, emit: Path, mode: str, safe_map_path: Path, api_key: str) -> None:
    """클러스터 단계를 실행합니다./Execute clustering stage."""
    
    records = load_records(scores)
    if mode == "local":
        projects = cluster_local(records)
    else:
        safe_map = (
            json.loads(safe_map_path.read_text(encoding="utf-8")) if safe_map_path.exists() else {}
        )
        projects = cluster_hybrid(records, safe_map, api_key)
    emit_projects(projects, emit)
    click.echo(f"[cluster:{mode}] saved to {emit}")


@cli.command("cluster")
@click.option("--scores", default=Path(".cache/scores.json"), type=click.Path(path_type=Path))
@click.option("--emit", default=Path(".cache/projects.json"), type=click.Path(path_type=Path))
@click.option("--mode", type=click.Choice(["local", "hybrid"]), default="local", show_default=True)
@click.option(
    "--project-mode",
    default=None,
    type=click.Choice(["local", "gpt"]),
    help="[Legacy] alias for --mode",
)
@click.option(
    "--safe-map",
    "safe_map_path",
    default=Path(".cache/safe_map.json"),
    type=click.Path(path_type=Path),
)
@click.option("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), envvar="OPENAI_API_KEY")
def cluster_command(
    scores: Path,
    emit: Path,
    mode: str,
    project_mode: str | None,
    safe_map_path: Path,
    api_key: str,
) -> None:
    """프로젝트 클러스터를 생성합니다./Cluster files into projects."""
    
    effective_mode = mode
    if project_mode:
        effective_mode = "hybrid" if project_mode == "gpt" else project_mode
    run_cluster(scores, emit, effective_mode, safe_map_path, api_key)


def run_organize(
    projects: Path,
    scores: Path,
    target: Path | None,
    transfer_mode: str | None,
    conflict: str | None,
    journal: Path,
    schema: Path,
) -> None:
    """정리 단계를 실행합니다./Execute organization stage."""
    
    records = load_records(scores)
    project_payload = json.loads(projects.read_text(encoding="utf-8"))
    config = load_schema_config(schema if schema.exists() else None)
    if target:
        config.target_root = target
    if transfer_mode:
        config.mode = transfer_mode  # type: ignore[assignment]
    if conflict:
        config.conflict = conflict  # type: ignore[assignment]
    organize_projects(project_payload, records, config, journal)
    click.echo(f"[organize] completed into {config.target_root}")


@cli.command("organize")
@click.option("--projects", default=Path(".cache/projects.json"), type=click.Path(path_type=Path))
@click.option("--scores", default=Path(".cache/scores.json"), type=click.Path(path_type=Path))
@click.option("--target", default=None, type=click.Path(path_type=Path))
@click.option("--mode", "transfer_mode", default=None, type=click.Choice(["move", "copy"]))
@click.option("--conflict", default=None, type=click.Choice(["version", "skip", "overwrite"]))
@click.option("--journal", default=Path(".cache/journal.jsonl"), type=click.Path(path_type=Path))
@click.option("--schema", default=Path("schema.yml"), type=click.Path(path_type=Path))
def organize_command(
    projects: Path,
    scores: Path,
    target: Path | None,
    transfer_mode: str | None,
    conflict: str | None,
    journal: Path,
    schema: Path,
) -> None:
    """프로젝트 구조로 파일을 정리합니다./Organize files into schema."""
    
    run_organize(projects, scores, target, transfer_mode, conflict, journal, schema)


def run_report(journal: Path, html_out: Path, csv_out: Path, json_out: Path) -> None:
    """리포트 단계를 실행합니다./Execute reporting stage."""
    
    entries = load_journal(journal)
    summary = summarize(entries)
    emit_html(entries, summary, html_out)
    emit_csv(entries, csv_out)
    emit_json(summary, json_out)
    click.echo(f"[report] HTML: {html_out}")


@cli.command("report")
@click.option("--journal", default=Path(".cache/journal.jsonl"), type=click.Path(path_type=Path))
@click.option(
    "--html",
    "html_out",
    default=Path("reports/projects_summary.html"),
    type=click.Path(path_type=Path),
)
@click.option(
    "--csv",
    "csv_out",
    default=Path("reports/projects_summary.csv"),
    type=click.Path(path_type=Path),
)
@click.option(
    "--json",
    "json_out",
    default=Path("reports/projects_summary.json"),
    type=click.Path(path_type=Path),
)
def report_command(journal: Path, html_out: Path, csv_out: Path, json_out: Path) -> None:
    """정리 결과 리포트를 생성합니다./Produce summary reports."""
    
    run_report(journal, html_out, csv_out, json_out)


def run_rollback(journal: Path) -> None:
    """롤백 단계를 실행합니다./Execute rollback stage."""
    
    rollback(journal)
    click.echo("[rollback] completed")


@cli.command("rollback")
@click.option("--journal", default=Path(".cache/journal.jsonl"), type=click.Path(path_type=Path))
def rollback_command(journal: Path) -> None:
    """저널을 사용해 롤백합니다./Rollback using journal."""
    
    run_rollback(journal)


@cli.command("full-pipeline")
@click.option("--paths", multiple=True, required=True, type=click.Path(path_type=Path))
@click.option("--mode", type=click.Choice(["local", "hybrid"]), default="local", show_default=True)
@click.option("--schema", default=Path("schema.yml"), type=click.Path(path_type=Path))
@click.option("--rules-config", default=Path("rules.yml"), type=click.Path(path_type=Path))
@click.option("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), envvar="OPENAI_API_KEY")
def full_pipeline(
    paths: Sequence[Path], mode: str, schema: Path, rules_config: Path, api_key: str
) -> None:
    """전체 파이프라인을 실행합니다./Run complete pipeline."""
    
    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    scan_path = cache_dir / "scan.json"
    safe_map_path = cache_dir / "safe_map.json"
    scores_path = cache_dir / "scores.json"
    projects_path = cache_dir / "projects.json"
    journal_path = cache_dir / "journal.jsonl"

    run_scan(paths=paths, sample_bytes=4096, emit=scan_path, safe_map_path=safe_map_path)
    run_rules(scan_path=scan_path, emit=scores_path, rules_config=rules_config)
    run_cluster(
        scores=scores_path,
        emit=projects_path,
        mode=mode,
        safe_map_path=safe_map_path,
        api_key=api_key,
    )
    run_organize(
        projects=projects_path,
        scores=scores_path,
        target=None,
        transfer_mode=None,
        conflict=None,
        journal=journal_path,
        schema=schema,
    )
    run_report(
        journal=journal_path,
        html_out=Path("reports/projects_summary.html"),
        csv_out=Path("reports/projects_summary.csv"),
        json_out=Path("reports/projects_summary.json"),
    )


if __name__ == "__main__":
    cli()