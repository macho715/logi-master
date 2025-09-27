"""Streamlit 대시보드 리팩터링./Refactored Streamlit dashboard."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Sequence

import altair as alt
import pandas as pd  # type: ignore[import-untyped]
import streamlit as st

from organize import load_schema_config
from report import load_journal, summarize
from scan import load_records

BASE = Path(__file__).parent.resolve()
CACHE = BASE / ".cache"
REPORTS = BASE / "reports"
CACHE.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)
SCHEMA_PATH = BASE / "schema.yml"
RULES_PATH = BASE / "rules.yml"

PIPELINE_STEPS = ["scan", "rules", "cluster", "organize", "report"]


def build_step_command(step: str, roots: Sequence[str], mode: str) -> list[str]:
    """각 파이프라인 단계의 명령을 생성합니다./Build command for pipeline step."""

    base_cmd = ["python", "autosort.py"]
    if step == "scan":
        cmd = base_cmd + ["scan"]
        for root in roots:
            cmd += ["--paths", root]
        cmd += ["--emit", str(CACHE / "scan.json"), "--safe-map", str(CACHE / "safe_map.json")]
        return cmd
    if step == "rules":
        return base_cmd + [
            "rules",
            "--scan",
            str(CACHE / "scan.json"),
            "--emit",
            str(CACHE / "scores.json"),
            "--rules-config",
            str(RULES_PATH),
        ]
    if step == "cluster":
        cluster_mode = "hybrid" if mode == "HYBRID" else "local"
        cmd = base_cmd + [
            "cluster",
            "--scores",
            str(CACHE / "scores.json"),
            "--emit",
            str(CACHE / "projects.json"),
            "--mode",
            cluster_mode,
            "--safe-map",
            str(CACHE / "safe_map.json"),
        ]
        if cluster_mode == "hybrid":
            cmd += ["--api-key", os.environ.get("OPENAI_API_KEY", "")]
        return cmd
    if step == "organize":
        return base_cmd + [
            "organize",
            "--projects",
            str(CACHE / "projects.json"),
            "--scores",
            str(CACHE / "scores.json"),
            "--journal",
            str(CACHE / "journal.jsonl"),
            "--schema",
            str(SCHEMA_PATH),
        ]
    if step == "report":
        return base_cmd + [
            "report",
            "--journal",
            str(CACHE / "journal.jsonl"),
            "--html",
            str(REPORTS / "projects_summary.html"),
            "--csv",
            str(REPORTS / "projects_summary.csv"),
            "--json",
            str(REPORTS / "projects_summary.json"),
        ]
    raise ValueError(f"Unknown step: {step}")


def run_subprocess(cmd: Sequence[str], output_queue: "queue.Queue[object]") -> int:
    """서브프로세스를 실행하고 로그를 큐에 전달합니다./Run subprocess and stream logs."""

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(BASE), env=env
    )
    assert process.stdout is not None
    for line in process.stdout:
        output_queue.put(line.rstrip())
    process.wait()
    return process.returncode


def stream_pipeline(
    roots: Sequence[str],
    mode: str,
    status_box: Any,
    progress_bar: Any,
    log_placeholder: Any,
) -> None:
    """파이프라인을 스트리밍 실행합니다./Stream pipeline execution."""

    q: "queue.Queue[object]" = queue.Queue()
    total = len(PIPELINE_STEPS)
    completed = 0

    def worker() -> None:
        for step in PIPELINE_STEPS:
            q.put(("stage", step))
            rc = run_subprocess(build_step_command(step, roots, mode), q)
            q.put(("result", step, rc))
            if rc != 0:
                q.put(("failed", step, rc))
                return
        q.put(("done", ""))

    threading.Thread(target=worker, daemon=True).start()

    collected: list[str] = []
    with status_box as box:
        box.update(label="Running pipeline", state="running")
        while True:
            try:
                item = q.get(timeout=0.05)
            except queue.Empty:
                continue
            if isinstance(item, tuple):
                tag = item[0]
                if tag == "stage":
                    box.write(f"🚀 {item[1]} started")
                elif tag == "result":
                    _, step, rc = item
                    if rc == 0:
                        completed += 1
                        progress_bar.progress(int(completed / total * 100))
                        box.write(f"✅ {step} completed")
                elif tag == "failed":
                    _, step, rc = item
                    box.update(label="Pipeline failed", state="error")
                    box.write(f"❌ {step} failed (rc={rc})")
                    st.error("파이프라인이 실패했습니다. 로그를 확인하세요.")
                    break
                elif tag == "done":
                    progress_bar.progress(100)
                    box.update(label="Pipeline finished", state="complete")
                    st.toast("Pipeline completed", icon="✅")
                    break
            else:
                collected.append(str(item))
                if len(collected) > 800:
                    collected[:] = collected[-800:]
                log_placeholder.code("\n".join(collected), language="bash")
            time.sleep(0.01)


def load_scores_dataframe(scores_path: Path) -> pd.DataFrame:
    """스코어 파일을 데이터프레임으로 로드합니다./Load scores as DataFrame."""

    if not scores_path.exists():
        return pd.DataFrame(columns=["path", "bucket", "size", "ext"])
    records = load_records(scores_path)
    rows = [
        {
            "path": rec.path,
            "bucket": rec.bucket or "misc",
            "size": rec.size,
            "ext": rec.ext,
            "name": rec.name,
        }
        for rec in records
        if not rec.error
    ]
    return pd.DataFrame(rows)


def render_summary(df: pd.DataFrame, journal: list[dict[str, object]], mode: str) -> None:
    """상단 요약 카드를 렌더링합니다./Render KPI summary cards."""

    summary = summarize(journal)
    cols = st.columns(4)
    total_files = len(df)
    duplicate_count = int(df["name"].duplicated().sum()) if not df.empty else 0
    total_size = df["size"].sum() if not df.empty else 0
    cols[0].metric("총 파일 수 Total files", f"{total_files}")
    cols[1].metric("중복 파일 수 Duplicate files", f"{duplicate_count}")
    cols[2].metric("총 용량(바이트) Total size", f"{total_size:,}")
    cols[3].metric("최근 모드 Last mode", mode)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(summary.last_updated))
    st.info(f"마지막 작업 {timestamp} · 총 작업 {summary.total_operations}개")


def render_charts(df: pd.DataFrame, journal: list[dict[str, object]]) -> None:
    """시각화 섹션을 렌더링합니다./Render visualization section."""

    if df.empty:
        st.warning("시각화를 위해 먼저 파이프라인을 실행하세요./Run the pipeline to see charts.")
        return
    col1, col2 = st.columns(2)
    bucket_counts = df.groupby("bucket")["path"].count().reset_index(name="count")
    pie = (
        alt.Chart(bucket_counts)
        .mark_arc()
        .encode(theta="count", color="bucket", tooltip=["bucket", "count"])
    )
    col1.altair_chart(pie, use_container_width=True)

    if journal:
        journal_df = pd.DataFrame(journal)
        bar = journal_df.groupby("code")["ts"].count().reset_index(name="count")
        col2.altair_chart(
            alt.Chart(bar).mark_bar().encode(x="code", y="count", tooltip=["code", "count"]),
            use_container_width=True,
        )
        journal_df["ts_dt"] = pd.to_datetime(journal_df["ts"], unit="ms")
        line = journal_df.sort_values("ts_dt").assign(total=lambda d: range(1, len(d) + 1))
        st.altair_chart(
            alt.Chart(line)
            .mark_line()
            .encode(x="ts_dt:T", y="total:Q", tooltip=["ts_dt", "total"]),
            use_container_width=True,
        )


def render_file_browser(df: pd.DataFrame, filters: dict[str, str]) -> None:
    """검색과 필터 UI를 렌더링합니다./Render search and filtering UI."""

    st.subheader("파일 검색 Search files")
    search = filters.get("search", "").lower()
    bucket = filters.get("bucket", "")
    ext = filters.get("ext", "")
    filtered = df
    if search:
        filtered = filtered[filtered["path"].str.lower().str.contains(search)]
    if bucket:
        filtered = filtered[filtered["bucket"] == bucket]
    if ext:
        filtered = filtered[filtered["ext"] == ext]
    st.dataframe(filtered.sort_values("bucket"), use_container_width=True, height=320)


def render_logs(journal: list[dict[str, object]]) -> None:
    """저널 로그 뷰어를 렌더링합니다./Render journal log viewer."""

    st.subheader("최근 로그 Recent logs")
    if not journal:
        st.write("로그가 없습니다./No logs yet.")
        return
    tail = journal[-20:]
    text = "\n".join(json.dumps(item, ensure_ascii=False) for item in tail)
    st.code(text, language="json")


def sidebar_controls(df: pd.DataFrame) -> tuple[list[str], str, bool]:
    """사이드바 제어 UI를 구성합니다./Build sidebar controls."""

    with st.sidebar:
        st.header("Controls")
        mode = st.radio(
            "모드 Mode", ["LOCAL", "HYBRID"], help="LOCAL: 규칙 기반 · HYBRID: GPT 보조"
        )
        root_input = st.text_area(
            "루트 경로 Roots", "\n".join(str(p) for p in [BASE / "sample_data"]), height=120
        )
        roots = [line.strip() for line in root_input.splitlines() if line.strip()]
        st.caption("한 줄에 하나씩 폴더 경로를 입력하세요./One path per line.")
        run_btn = st.button("▶ Run Pipeline", type="primary", use_container_width=True)
        st.link_button(
            "📄 최신 리포트 열기 Open report",
            (REPORTS / "projects_summary.html").as_posix(),
            disabled=not (REPORTS / "projects_summary.html").exists(),
            use_container_width=True,
        )
        st.divider()
        st.caption("필터 Filters")
        search = st.text_input("검색 Search")
        bucket_options = (
            sorted({row for row in df["bucket"].dropna().unique()}) if not df.empty else []
        )
        schema_options = {
            Path(p).parts[0].rstrip("/") for p in load_schema_config(SCHEMA_PATH).schema_paths
        }
        merged_options = sorted(set(bucket_options) | schema_options)
        bucket = st.selectbox("버킷 Bucket", options=[""] + merged_options)
        ext = st.text_input("확장자 Extension", help="예: .py")
    st.session_state["filters"] = {"search": search, "bucket": bucket, "ext": ext}
    return roots, mode, run_btn


def main() -> None:
    """대시보드 메인 엔트리./Main entry for dashboard."""

    st.set_page_config(
        page_title="Project Autosort", layout="wide", initial_sidebar_state="expanded"
    )
    scores_df = load_scores_dataframe(CACHE / "scores.json")
    journal_entries = load_journal(CACHE / "journal.jsonl")
    roots, mode, trigger = sidebar_controls(scores_df)

    st.title("Project Autosort Dashboard")
    status_col, log_col = st.columns([0.4, 0.6])
    with status_col:
        status_box = st.status("대기 중 Idle", expanded=True)
        progress = st.progress(0)
    with log_col:
        live_log = st.empty()

    if trigger:
        if not roots:
            st.error("최소 한 개의 루트 경로가 필요합니다./At least one root path is required.")
        else:
            stream_pipeline(roots, mode, status_box, progress, live_log)
            scores_df = load_scores_dataframe(CACHE / "scores.json")
            journal_entries = load_journal(CACHE / "journal.jsonl")

    render_summary(scores_df, journal_entries, mode)
    render_charts(scores_df, journal_entries)
    render_file_browser(scores_df, st.session_state.get("filters", {}))
    render_logs(journal_entries)


if __name__ == "__main__":
    main()
