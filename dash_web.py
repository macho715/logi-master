from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title='Project Autosort Dashboard',
    layout='wide',
    initial_sidebar_state='expanded',
)


BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = BASE_DIR / '.cache'
REPORTS_DIR = BASE_DIR / 'reports'
SCHEMA_PATH = BASE_DIR / 'schema.yml'
DEFAULT_ROOTS = (
    r'C:\HVDC PJT',
    r'C:\cursor-mcp',
)
DEFAULT_TARGET = os.environ.get('DEV_SORT_TARGET', r'C:\PROJECTS_STRUCT')

CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


PIPELINE_ORDER = (
    'scan',
    'rules',
    'cluster_local',
    'organize',
    'report',
)
HYBRID_PIPELINE_ORDER = (
    'scan',
    'rules',
    'cluster_gpt',
    'organize',
    'report',
)


@dataclass
class PipelineConfig:
    """파이프라인 실행 설정을 보관한다. Store configuration for pipeline execution."""

    base_dir: Path
    cache_dir: Path
    reports_dir: Path
    schema_path: Path
    default_roots: tuple[str, ...]
    default_target: str


@dataclass
class SidebarFilters:
    """사이드바 필터 상태를 표현한다. Represent sidebar filter selections."""

    query: str
    extensions: tuple[str, ...]
    min_size: int | None
    max_size: int | None
    project: str | None


@dataclass
class SidebarState:
    """사이드바 입력 값을 담는다. Hold sidebar interaction values."""

    mode: str
    run_clicked: bool
    clear_cache: bool
    root_paths: tuple[str, ...]
    target_path: str
    filters: SidebarFilters


@dataclass
class PipelineData:
    """파이프라인 산출물을 적재한다. Load persisted pipeline artifacts."""

    scan_records: list[dict[str, Any]]
    scored_records: list[dict[str, Any]]
    projects: dict[str, Any] | None
    journal_entries: list[dict[str, Any]]


@dataclass
class ProgressPanel:
    """진행률과 로그 위젯을 캡슐화한다. Encapsulate progress and log widgets."""

    status: Any
    progress: Any
    log_placeholder: Any
    log_buffer: list[str] = field(default_factory=list)


def ensure_json(path: Path) -> list[dict[str, Any]]:
    """JSON 파일을 안전하게 읽는다. Safely read a JSON file."""

    if not path.exists():
        return []
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    return []


def ensure_json_object(path: Path) -> dict[str, Any] | None:
    """JSON 오브젝트를 읽어온다. Read a JSON object from disk."""

    if not path.exists():
        return None
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        return data
    return None


def ensure_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """JSONL 로그를 적재한다. Load JSONL log entries."""

    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(payload)
    if limit is not None:
        return entries[-limit:]
    return entries


def load_pipeline_data(config: PipelineConfig) -> PipelineData:
    """파이프라인 산출 데이터를 모두 불러온다. Load all pipeline artifacts."""

    scan_path = config.cache_dir / 'scan.json'
    scores_path = config.cache_dir / 'scores.json'
    projects_path = config.cache_dir / 'projects.json'
    journal_path = config.cache_dir / 'journal.jsonl'
    return PipelineData(
        scan_records=ensure_json(scan_path),
        scored_records=ensure_json(scores_path),
        projects=ensure_json_object(projects_path),
        journal_entries=ensure_jsonl(journal_path, limit=500),
    )


def get_unique_extensions(records: list[dict[str, Any]]) -> tuple[str, ...]:
    """확장자 목록을 반환한다. Return unique extensions."""

    extensions = {rec.get('ext', '').lower() for rec in records if rec.get('ext')}
    ordered = sorted(ext for ext in extensions if ext)
    return tuple(ordered)


def render_sidebar(config: PipelineConfig, data: PipelineData) -> SidebarState:
    """사이드바 UI를 렌더링한다. Render the sidebar UI."""

    with st.sidebar:
        st.title('Project Autosort')
        st.caption('로컬 정리 파이프라인을 실행하고 모니터링합니다. Run and monitor the local organisation pipeline.')

        mode = st.toggle('Hybrid GPT 모드 · Hybrid GPT mode', value=False)
        resolved_mode = 'HYBRID' if mode else 'LOCAL'

        root_default = '\n'.join(config.default_roots)
        root_text = st.text_area(
            '대상 루트 경로들 · Root directories',
            value=root_default,
            help='각 줄에 하나씩 경로를 입력하세요. Enter one path per line.',
        )
        root_paths = tuple(line.strip() for line in root_text.splitlines() if line.strip())

        target_path = st.text_input(
            '타깃 루트 · Target root',
            value=config.default_target,
            help='정리된 프로젝트가 배치될 위치입니다. Destination for organised projects.',
        )

        extensions = get_unique_extensions(data.scored_records or data.scan_records)
        selected_ext = st.multiselect(
            '확장자 필터 · Extension filter',
            options=extensions,
            help='표시할 확장자를 선택합니다. Select extensions to display.',
        )

        min_size, max_size = _render_size_filter(data.scan_records)

        project_options = _collect_project_labels(data.projects)
        project_choice = None
        if project_options:
            project_choice = st.selectbox(
                '프로젝트 선택 · Select project',
                options=('전체 · All',) + project_options,
            )
            if project_choice == '전체 · All':
                project_choice = None

        query = st.text_input(
            '검색어 · Search keyword',
            help='파일명, 경로 또는 해시를 검색합니다. Search by name, path, or hash.',
        )

        st.divider()
        run_clicked = st.button('🚀 파이프라인 실행 · Run pipeline', type='primary', width='stretch')
        clear_cache = st.button('🧹 캐시 삭제 · Clear cache', width='stretch')
        report_path = REPORTS_DIR / 'projects_summary.html'
        st.link_button(
            '📄 최신 리포트 열기 · Open latest report',
            report_path.as_posix(),
            disabled=not report_path.exists(),
            width='stretch',
        )

        filters = SidebarFilters(
            query=query.strip(),
            extensions=tuple(selected_ext),
            min_size=min_size,
            max_size=max_size,
            project=project_choice,
        )
        return SidebarState(
            mode=resolved_mode,
            run_clicked=run_clicked,
            clear_cache=clear_cache,
            root_paths=root_paths or config.default_roots,
            target_path=target_path or config.default_target,
            filters=filters,
        )


def _render_size_filter(records: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    """사이즈 필터를 생성한다. Render the size filter widget."""

    if not records:
        return None, None
    sizes = [rec.get('size', 0) for rec in records if isinstance(rec.get('size'), int)]
    if not sizes:
        return None, None
    min_size = min(sizes)
    max_size = max(sizes)
    step = max(1, (max_size - min_size) // 100 or 1)
    selected = st.slider(
        '파일 크기 범위 · File size range (bytes)',
        value=(min_size, max_size),
        min_value=min_size,
        max_value=max_size,
        step=step,
    )
    return selected


def _collect_project_labels(projects: dict[str, Any] | None) -> tuple[str, ...]:
    """프로젝트 라벨을 수집한다. Collect project labels."""

    if not projects:
        return tuple()
    labels = [proj.get('project_label', '') for proj in projects.get('projects', [])]
    return tuple(sorted({label for label in labels if label}))


def render_main_layout(data: PipelineData, sidebar: SidebarState) -> ProgressPanel:
    """메인 레이아웃을 그린다. Render the main dashboard layout."""

    status_col, summary_col = st.columns([0.35, 0.65])
    with status_col:
        st.subheader('진행률 · Progress')
        status = st.status('대기중 · Idle', expanded=True)
        progress = st.progress(0, text='0%')
    with summary_col:
        st.subheader('요약 지표 · Summary KPIs')
        render_summary_cards(data)

    st.divider()
    charts_col, search_col = st.columns([0.55, 0.45])
    with charts_col:
        st.subheader('분류 시각화 · Classification insights')
        render_charts(data)
    with search_col:
        st.subheader('파일 탐색 · File explorer')
        render_file_table(data, sidebar.filters)

    st.divider()
    st.subheader('작업 로그 · Activity log')
    render_log_viewer(data.journal_entries)

    st.subheader('실시간 로그 · Live log')
    log_placeholder = st.empty()
    return ProgressPanel(status=status, progress=progress, log_placeholder=log_placeholder)


def render_summary_cards(data: PipelineData) -> None:
    """요약 지표 카드를 출력한다. Render summary metric cards."""

    totals = _compute_totals(data)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('총 파일 수 · Total files', f"{totals['total_files']}")
    col2.metric('중복 파일 · Duplicates', f"{totals['duplicate_files']}")
    col3.metric('최근 실행 · Last run', totals['last_run'])
    col4.metric('총 용량(MB) · Total size (MB)', f"{totals['total_size_mb']:.2f}")


def _compute_totals(data: PipelineData) -> dict[str, Any]:
    """요약 통계를 계산한다. Compute summary statistics."""

    files = [rec for rec in data.scan_records if 'path' in rec]
    total_files = len(files)
    total_size_mb = sum(rec.get('size', 0) for rec in files) / (1024 * 1024) if files else 0
    duplicates = sum(1 for rec in data.journal_entries if rec.get('conflict') == 'version')
    last_run = 'N/A'
    if data.journal_entries:
        last_ts = max(entry.get('timestamp', 0) for entry in data.journal_entries)
        if last_ts:
            last_run = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_ts))
    return {
        'total_files': total_files,
        'duplicate_files': duplicates,
        'last_run': last_run,
        'total_size_mb': total_size_mb,
    }


def render_charts(data: PipelineData) -> None:
    """시각화를 표시한다. Display visual charts."""

    bucket_df = _bucket_distribution(data.scored_records or data.scan_records)
    if bucket_df is not None and not bucket_df.empty:
        pie = alt.Chart(bucket_df).mark_arc().encode(
            theta='count:Q',
            color='bucket:N',
            tooltip=['bucket', 'count'],
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        st.info('버킷 데이터가 없습니다. No bucket data available.')

    history_df = _pipeline_history(data.journal_entries)
    if history_df is not None and not history_df.empty:
        bar = alt.Chart(history_df).mark_bar().encode(
            x='run_id:N',
            y='files:Q',
            tooltip=['run_id', 'files'],
        )
        st.altair_chart(bar, use_container_width=True)
    else:
        st.info('실행 히스토리가 없습니다. No execution history available.')

    timeline_df = _timeline_growth(data.journal_entries)
    if timeline_df is not None and not timeline_df.empty:
        line = alt.Chart(timeline_df).mark_line(point=True).encode(
            x='timestamp:T',
            y='cumulative:Q',
            tooltip=['timestamp:T', 'cumulative:Q'],
        )
        st.altair_chart(line, use_container_width=True)
    else:
        st.info('시간 경과 추이를 계산할 수 없습니다. No timeline data available.')


def _bucket_distribution(records: list[dict[str, Any]]) -> pd.DataFrame | None:
    """버킷 분포를 만든다. Build bucket distribution dataframe."""

    if not records:
        return None
    buckets = [rec.get('bucket') or 'unassigned' for rec in records]
    df = pd.DataFrame({'bucket': buckets})
    if df.empty:
        return None
    return df.groupby('bucket', as_index=False).size().rename(columns={'size': 'count'})


def _pipeline_history(entries: list[dict[str, Any]]) -> pd.DataFrame | None:
    """실행 이력을 요약한다. Summarise pipeline runs."""

    if not entries:
        return None
    rows: list[dict[str, Any]] = []
    for entry in entries:
        run_id = entry.get('run_id') or entry.get('session') or 'unknown'
        files = entry.get('files_processed') or entry.get('files', 0)
        if isinstance(files, int):
            rows.append({'run_id': run_id, 'files': files})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    grouped = df.groupby('run_id', as_index=False)['files'].sum()
    return grouped.tail(10)


def _timeline_growth(entries: list[dict[str, Any]]) -> pd.DataFrame | None:
    """시간 경과 누적치를 만든다. Build cumulative timeline dataframe."""

    if not entries:
        return None
    rows: list[dict[str, Any]] = []
    for entry in entries:
        timestamp = entry.get('timestamp')
        if not isinstance(timestamp, (int, float)):
            continue
        files = entry.get('files_processed') or entry.get('files', 1)
        if not isinstance(files, int):
            files = 1
        # ms vs s 구분
        ts_value = float(timestamp)
        if ts_value > 10**12:
            ts_value /= 1000
        rows.append({'timestamp': pd.to_datetime(ts_value, unit='s'), 'files': max(files, 0)})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values('timestamp')
    df['cumulative'] = df['files'].cumsum()
    return df


def render_file_table(data: PipelineData, filters: SidebarFilters) -> None:
    """필터된 파일 목록을 보여준다. Display filtered file list."""

    records = data.scored_records or data.scan_records
    if not records:
        st.info('표시할 파일이 없습니다. No files to display.')
        return
    df = pd.DataFrame(records)
    if 'path' in df.columns:
        df = df[df['path'].notna()]
    if filters.extensions and 'ext' in df.columns:
        df = df[df['ext'].isin(filters.extensions)]
    if filters.min_size is not None and filters.max_size is not None:
        df = df[(df['size'] >= filters.min_size) & (df['size'] <= filters.max_size)]
    if filters.project:
        if 'project_label' in df.columns:
            df = df[df['project_label'] == filters.project]
        else:
            df = df.iloc[0:0]
    if filters.query:
        path_series = df['path'] if 'path' in df.columns else pd.Series('', index=df.index)
        name_series = df['name'] if 'name' in df.columns else pd.Series('', index=df.index)
        mask = path_series.str.contains(filters.query, case=False, na=False) | name_series.str.contains(
            filters.query, case=False, na=False
        )
        df = df[mask]
    columns = ['name', 'ext', 'size', 'bucket', 'path']
    available = [col for col in columns if col in df.columns]
    st.dataframe(df[available].head(200), width='stretch')


def render_log_viewer(entries: list[dict[str, Any]]) -> None:
    """최근 로그를 보여준다. Display recent logs."""

    if not entries:
        st.info('로그가 없습니다. No log entries available.')
        return
    tail = entries[-20:]
    formatted = '\n'.join(json.dumps(entry, ensure_ascii=False, indent=2) for entry in tail)
    st.code(formatted, language='json')
    if any(_is_error(entry) for entry in tail):
        st.error('오류 로그가 감지되었습니다. Errors detected in recent logs.')


def _is_error(entry: dict[str, Any]) -> bool:
    """로그에서 오류 여부를 판단한다. Determine whether log entry signals an error."""

    level = str(entry.get('level', '')).lower()
    status = str(entry.get('status', '')).lower()
    return 'error' in level or status == 'error'


def build_commands(config: PipelineConfig, sidebar: SidebarState) -> dict[str, str]:
    """파이프라인 명령을 생성한다. Build pipeline command strings."""

    root_args = ' '.join(f'--paths "{path}"' for path in sidebar.root_paths)
    safe_map = (config.cache_dir / 'safe_map.json').as_posix()
    schema_suffix = ''
    if config.schema_path.exists():
        schema_suffix = f' --schema "{config.schema_path.as_posix()}"'
    commands = {
        'scan': (
            f'python devmind.py scan {root_args} '
            f'--emit "{config.cache_dir / "scan.json"}" --safe-map "{safe_map}"'
        ),
        'rules': (
            f'python devmind.py rules --scan "{config.cache_dir / "scan.json"}" '
            f'--emit "{config.cache_dir / "scores.json"}"'
        ),
        'cluster_local': (
            f'python devmind.py cluster --scores "{config.cache_dir / "scores.json"}" '
            f'--emit "{config.cache_dir / "projects.json"}" --project-mode local'
        ),
        'cluster_gpt': (
            f'python devmind.py cluster --scores "{config.cache_dir / "scores.json"}" '
            f'--emit "{config.cache_dir / "projects.json"}" --project-mode gpt --safe-map "{safe_map}"'
        ),
        'organize': (
            f'python devmind.py organize --projects "{config.cache_dir / "projects.json"}" '
            f'--scores "{config.cache_dir / "scores.json"}" --target "{sidebar.target_path}" '
            f'--mode move --conflict version --journal "{config.cache_dir / "journal.jsonl"}"{schema_suffix}'
        ),
        'report': (
            f'python devmind.py report --journal "{config.cache_dir / "journal.jsonl"}" '
            f'--out "{config.reports_dir / "projects_summary.html"}"'
        ),
    }
    return commands


def run_pipeline(commands: dict[str, str], sidebar: SidebarState, panel: ProgressPanel) -> None:
    """파이프라인을 실행한다. Execute the selected pipeline."""

    steps = HYBRID_PIPELINE_ORDER if sidebar.mode == 'HYBRID' else PIPELINE_ORDER
    queue: Queue[Any] = Queue()

    def worker() -> None:
        for step in steps:
            queue.put({'type': 'stage', 'value': step})
            cmd = commands[step]
            rc, tail = _run_subprocess(cmd, queue)
            queue.put({'type': 'result', 'step': step, 'returncode': rc, 'tail': tail})
            if rc != 0:
                break
        queue.put({'type': 'done'})

    threading.Thread(target=worker, daemon=True).start()

    total = len(steps)
    completed = 0
    with panel.status as status:
        status.update(label=f'실행 중 · Running ({sidebar.mode})', state='running')
        while True:
            try:
                event = queue.get(timeout=0.1)
            except Empty:
                continue
            if event['type'] == 'log':
                _append_log(panel, event['message'])
            elif event['type'] == 'stage':
                status.write(f"🚀 {event['value']}")
            elif event['type'] == 'result':
                completed += 1
                progress_value = int(completed / total * 100)
                panel.progress.progress(progress_value, text=f'{progress_value}%')
                if event['returncode'] == 0:
                    status.write(f"✅ {event['step']} 완료 · completed")
                else:
                    status.write(f"❌ {event['step']} 실패 · failed (rc={event['returncode']})")
                    panel.log_placeholder.code('\n'.join(event['tail'][-25:]), language='bash')
                    status.update(label='실패 · Failed', state='error')
                    st.error('파이프라인이 실패했습니다. The pipeline execution failed.')
                    st.toast('Pipeline failed', icon='❌')
                    return
            elif event['type'] == 'done':
                panel.progress.progress(100, text='100%')
                status.update(label='완료 · Completed', state='complete')
                st.toast('Pipeline completed', icon='✅')
                return


def _run_subprocess(cmd: str, queue: Queue[Any]) -> tuple[int, list[str]]:
    """서브프로세스를 실행한다. Run subprocess and stream logs."""

    env = dict(os.environ)
    env.setdefault('PYTHONUNBUFFERED', '1')
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        cwd=BASE_DIR,
        env=env,
        bufsize=1,
    )
    tail: list[str] = []
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip('\n')
        if not line:
            continue
        tail.append(line)
        if len(tail) > 200:
            tail.pop(0)
        queue.put({'type': 'log', 'message': line})
    process.wait()
    return process.returncode, tail


def _append_log(panel: ProgressPanel, line: str) -> None:
    """로그 위젯을 갱신한다. Append a line to the live log widget."""

    panel.log_buffer.append(line)
    if len(panel.log_buffer) > 400:
        panel.log_buffer[:] = panel.log_buffer[-400:]
    panel.log_placeholder.code('\n'.join(panel.log_buffer), language='bash')


def clear_cache_directory() -> None:
    """캐시 디렉터리를 비운다. Clear cache directory contents."""

    for child in CACHE_DIR.glob('*'):
        try:
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
        except OSError as exc:
            st.warning(f'삭제 실패 · Failed to remove {child}: {exc}')


def main() -> None:
    """대시보드 진입점을 구성한다. Configure dashboard entry point."""

    config = PipelineConfig(
        base_dir=BASE_DIR,
        cache_dir=CACHE_DIR,
        reports_dir=REPORTS_DIR,
        schema_path=SCHEMA_PATH,
        default_roots=DEFAULT_ROOTS,
        default_target=DEFAULT_TARGET,
    )
    data = load_pipeline_data(config)
    sidebar = render_sidebar(config, data)
    if sidebar.clear_cache:
        clear_cache_directory()
        st.experimental_rerun()
    panel = render_main_layout(data, sidebar)
    if sidebar.run_clicked:
        commands = build_commands(config, sidebar)
        run_pipeline(commands, sidebar, panel)


if __name__ == '__main__':
    main()
