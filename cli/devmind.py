'''DevMind CLI 진입점(KR). DevMind CLI entrypoint (EN).'''

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import click

from core import (
    PipelineConfig,
    apply_rules,
    cluster_projects,
    configure_logging,
    format_2d,
    generate_report,
    organize_projects,
    scan_paths,
)
from core.errors import PipelineError
from core.io import read_json, read_json_object, read_jsonl
from core.timezone import dubai_now
from logi.logistics import LogisticsMetadata

DEFAULT_SCAN = Path('.cache/scan.json')
DEFAULT_SCORES = Path('.cache/scores.json')
DEFAULT_PROJECTS = Path('.cache/projects.json')
DEFAULT_JOURNAL = Path('.cache/journal.jsonl')
DEFAULT_LOG = Path('.cache/devmind.log')


def _resolve_step_list(steps: str | None) -> Sequence[str]:
    '''실행할 스텝 리스트를 구한다 · Resolve pipeline step list.'''

    if not steps:
        return ('scan', 'rules', 'cluster', 'organize', 'report')
    return tuple(step.strip().lower() for step in steps.split(',') if step.strip())


@click.group()
@click.option(
    '--config-file',
    type=click.Path(path_type=Path),
    default=None,
    help='구성 파일 경로 · Config file path',
)
@click.option('--verbose', is_flag=True, help='상세 로그 · Verbose logs')
@click.option('--quiet', is_flag=True, help='간략 로그 · Quiet logs')
@click.option(
    '--log-file',
    type=click.Path(path_type=Path),
    default=DEFAULT_LOG,
    help='로그 파일 경로 · Log file path',
)
@click.pass_context
def cli(
    ctx: click.Context, config_file: Path | None, verbose: bool, quiet: bool, log_file: Path
) -> None:
    '''프로젝트 자동 정리 CLI · Project autosort CLI.'''

    level = 'INFO'
    if verbose:
        level = 'DEBUG'
    if quiet:
        level = 'WARNING'
    configure_logging(log_file, level=level)
    config = PipelineConfig.from_file(config_file) if config_file else PipelineConfig()
    config.paths.ensure()
    ctx.obj = {'config': config, 'log_file': log_file}


@cli.command()
@click.option(
    '--paths',
    'paths',
    type=click.Path(path_type=Path),
    multiple=True,
    help='스캔 경로 · Paths to scan',
)
@click.option(
    '--emit',
    type=click.Path(path_type=Path),
    default=DEFAULT_SCAN,
    help='스캔 결과 저장 경로 · Output path',
)
@click.option(
    '--safe-map',
    type=click.Path(path_type=Path),
    default=Path('.cache/safe_map.json'),
    help='세이프 맵 경로 · Safe map path',
)
@click.pass_context
def scan(ctx: click.Context, paths: Sequence[Path], emit: Path, safe_map: Path) -> None:
    '''소스 파일을 스캔한다 · Scan source files.'''

    config: PipelineConfig = ctx.obj['config']
    sources: Iterable[Path]
    if paths:
        sources = tuple(paths)
    else:
        sources = config.resolve_sources(config.default_roots)
    records = scan_paths(sources, emit, safe_map)
    click.echo(
        json.dumps(
            {
                'stage': 'scan',
                'records': len(records),
                'items': len(records),
                'timestamp': dubai_now(),
            },
            ensure_ascii=False,
        )
    )


@cli.command()
@click.option(
    '--scan',
    'scan_path',
    type=click.Path(path_type=Path),
    default=DEFAULT_SCAN,
    help='스캔 결과 입력 · Scan input path',
)
@click.option(
    '--emit',
    type=click.Path(path_type=Path),
    default=DEFAULT_SCORES,
    help='규칙 결과 저장 · Rules output path',
)
@click.pass_context
def rules(ctx: click.Context, scan_path: Path, emit: Path) -> None:
    '''규칙 엔진을 적용한다 · Apply rules engine.'''

    if not scan_path.exists():
        raise click.ClickException(f'scan payload missing: {scan_path}')
    scan_records = read_json(scan_path)
    enriched = apply_rules(scan_records, emit)
    click.echo(json.dumps({'records': len(enriched), 'timestamp': dubai_now()}, ensure_ascii=False))


@cli.command()
@click.option(
    '--scores',
    type=click.Path(path_type=Path),
    default=DEFAULT_SCORES,
    help='규칙 결과 경로 · Scores path',
)
@click.option(
    '--emit',
    type=click.Path(path_type=Path),
    default=DEFAULT_PROJECTS,
    help='프로젝트 출력 경로 · Projects output path',
)
@click.option(
    '--project-mode',
    type=click.Choice(['local', 'gpt']),
    default='local',
    help='프로젝트 모드 · Project mode',
)
@click.option(
    '--safe-map',
    type=click.Path(path_type=Path),
    default=Path('.cache/safe_map.json'),
    help='세이프 맵 경로 · Safe map path',
)
@click.pass_context
def cluster(
    ctx: click.Context, scores: Path, emit: Path, project_mode: str, safe_map: Path
) -> None:
    '''프로젝트를 군집화한다 · Cluster projects.'''

    if not scores.exists():
        raise click.ClickException(f'scores payload missing: {scores}')
    del safe_map  # retained for CLI compatibility
    scored = read_json(scores)
    payload = cluster_projects(scored, emit=emit, mode=project_mode)
    project_count = len(payload.get('projects', []))
    click.echo(json.dumps({'projects': project_count, 'mode': project_mode}, ensure_ascii=False))


@cli.command()
@click.option(
    '--projects',
    type=click.Path(path_type=Path),
    default=DEFAULT_PROJECTS,
    help='프로젝트 입력 경로 · Projects input path',
)
@click.option(
    '--scores',
    type=click.Path(path_type=Path),
    default=DEFAULT_SCORES,
    help='규칙 결과 경로 · Scores path',
)
@click.option(
    '--target',
    type=click.Path(path_type=Path),
    default=Path('PROJECTS_STRUCT'),
    help='타깃 디렉터리 · Target directory',
)
@click.option(
    '--mode', type=click.Choice(['move', 'copy']), default='move', help='이동 모드 · Move mode'
)
@click.option(
    '--conflict',
    type=click.Choice(['version', 'overwrite', 'skip']),
    default='version',
    help='충돌 정책 · Conflict policy',
)
@click.option(
    '--journal',
    type=click.Path(path_type=Path),
    default=DEFAULT_JOURNAL,
    help='저널 경로 · Journal path',
)
@click.option(
    '--schema',
    type=click.Path(path_type=Path),
    default=None,
    help='스키마 파일 경로 · Schema file path',
)
@click.pass_context
def organize(
    ctx: click.Context,
    projects: Path,
    scores: Path,
    target: Path,
    mode: str,
    conflict: str,
    journal: Path,
    schema: Path | None,
) -> None:
    '''파일을 대상 구조로 이동한다 · Move files to target structure.'''

    del scores  # legacy parameter retained for compatibility
    if not projects.exists():
        raise click.ClickException(f'project payload missing: {projects}')
    try:
        payload_obj = read_json_object(projects)
        project_items = payload_obj.get('projects', [])
        if not project_items:
            raise KeyError
    except Exception:
        project_items = read_json(projects)
    if schema:
        schema_data = json.loads(schema.read_text(encoding='utf-8'))
        target = Path(schema_data.get('target_root', target))
        for sub in schema_data.get('structure', []):
            (target / sub).mkdir(parents=True, exist_ok=True)
    result = organize_projects(
        project_items, target_dir=target, journal_path=journal, mode=mode, conflict_policy=conflict
    )
    result['conflict'] = conflict
    payload = {
        'stage': 'organize',
        'moves': result['files'],
        'moved': result['files'],
        'projects': result['projects'],
        'conflict': conflict,
    }
    if schema:
        payload['schema'] = str(schema)
    click.echo(json.dumps(payload, ensure_ascii=False))


@cli.command()
@click.option(
    '--journal',
    type=click.Path(path_type=Path),
    default=DEFAULT_JOURNAL,
    help='저널 입력 경로 · Journal input path',
)
@click.option(
    '--out',
    type=click.Path(path_type=Path),
    default=Path('reports/pipeline.html'),
    help='리포트 경로 · Report output path',
)
@click.pass_context
def report(ctx: click.Context, journal: Path, out: Path) -> None:
    '''리포트를 생성한다 · Generate report.'''

    if not journal.exists():
        raise click.ClickException(f'journal payload missing: {journal}')
    generate_report(journal, out)
    click.echo(json.dumps({'report': str(out), 'timestamp': dubai_now()}, ensure_ascii=False))


@cli.command('logistics-validate')
@click.option(
    '--payload',
    type=click.Path(path_type=Path),
    required=True,
    help='로지스틱스 JSON 경로 · Logistics JSON path',
)
def logistics_validate(payload: Path) -> None:
    '''물류 페이로드를 검증한다 · Validate logistics payload.'''

    data = json.loads(payload.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise click.ClickException('payload must be JSON object or array')
    summaries: List[dict[str, str]] = []
    for entry in items:
        meta = LogisticsMetadata(**entry)
        summary = meta.summary()
        summary['declared_value'] = format_2d(summary['declared_value'])
        summaries.append(summary)
    click.echo(json.dumps(summaries, ensure_ascii=False))


@cli.command('run')
@click.option(
    '--mode',
    type=click.Choice(['local', 'gpt']),
    default='local',
    help='실행 모드 · Execution mode',
)
@click.option('--steps', type=str, default=None, help='실행 스텝 · Steps to execute')
@click.option('--dry-run', is_flag=True, help='드라이런 실행 · Dry-run execution')
@click.option('--resume', is_flag=True, help='중단 지점 재개 · Resume pipeline')
@click.option('--fail-fast', is_flag=True, help='에러 즉시 중단 · Fail fast on errors')
@click.pass_context
def run_pipeline(
    ctx: click.Context,
    mode: str,
    steps: str | None,
    dry_run: bool,
    resume: bool,
    fail_fast: bool,
) -> None:
    '''선택 스텝 파이프라인을 실행한다 · Run selected pipeline steps.'''

    config: PipelineConfig = ctx.obj['config']
    step_list = _resolve_step_list(steps)
    results: list[dict[str, str]] = []

    def _record(step: str, message: str) -> None:
        results.append({'step': step, 'message': message, 'timestamp': dubai_now()})

    try:
        if dry_run:
            for step in step_list:
                _record(step, 'dry-run')
            click.echo(json.dumps(results, ensure_ascii=False))
            return

        if 'scan' in step_list:
            sources = config.resolve_sources(config.default_roots)
            scan_paths(sources, DEFAULT_SCAN, Path('.cache/safe_map.json'))
            _record('scan', 'completed')

        if 'rules' in step_list:
            enriched = apply_rules(read_json(DEFAULT_SCAN), DEFAULT_SCORES)
            _record('rules', f'{len(enriched)} records')

        if 'cluster' in step_list:
            payload = cluster_projects(read_json(DEFAULT_SCORES), emit=DEFAULT_PROJECTS, mode=mode)
            project_items = payload.get('projects', [])
            _record('cluster', f'{len(project_items)} projects')

        if 'organize' in step_list:
            project_items = read_json_object(DEFAULT_PROJECTS).get('projects', [])
            if not project_items:
                project_items = read_json(DEFAULT_PROJECTS)
            organize_projects(
                project_items,
                target_dir=config.paths.target_dir,
                journal_path=DEFAULT_JOURNAL,
                conflict_policy='version',
            )
            _record('organize', 'files moved')

        if 'report' in step_list:
            if not Path(DEFAULT_JOURNAL).exists():
                raise PipelineError('journal missing for report', stage='report')
            generate_report(DEFAULT_JOURNAL, config.paths.reports_dir / 'pipeline.html')
            _record('report', 'generated')
    except Exception as exc:  # pragma: no cover - top level guard
        if fail_fast:
            raise
        _record('error', str(exc))
    click.echo(json.dumps(results, ensure_ascii=False))


@cli.command()
@click.option(
    '--journal', type=click.Path(path_type=Path), required=True, help='저널 경로 · Journal path'
)
@click.pass_context
def rollback(ctx: click.Context, journal: Path) -> None:
    '''조직화 작업을 되돌린다 · Roll back organization actions.'''

    if not journal.exists():
        raise click.ClickException(f'journal not found: {journal}')
    entries = read_jsonl(journal)
    restored = 0
    for entry in reversed(entries):
        source = Path(entry.get('source', ''))
        destination = Path(entry.get('destination', ''))
        if destination.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(destination, source)
            restored += 1
    click.echo(json.dumps({'stage': 'rollback', 'restored': restored}, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    '''CLI 진입점을 실행한다 · Execute CLI entry point.'''

    argv = argv or sys.argv[1:]
    try:
        cli.main(args=list(argv), prog_name='devmind')
    except PipelineError as exc:
        click.echo(json.dumps({'error': str(exc)}), err=True)
        return 1
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
