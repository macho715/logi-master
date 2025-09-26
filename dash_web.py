import os, pathlib, queue, subprocess, threading, time
from typing import Callable, Tuple
import streamlit as st

# ── Page setup (wide) ────────────────────────────────────────────────────────
st.set_page_config(page_title="Project Autosort", layout="wide", initial_sidebar_state="expanded")  # wide + sidebar :contentReference[oaicite:1]{index=1}

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = pathlib.Path(__file__).parent.resolve()
CACHE = BASE / ".cache"; CACHE.mkdir(parents=True, exist_ok=True)
REPORTS = BASE / "reports"; REPORTS.mkdir(parents=True, exist_ok=True)
TARGET = os.environ.get("DEV_SORT_TARGET", r"C:\PROJECTS_STRUCT")
SCHEMA = BASE / "schema.yml"

# ── Commands (devmind 6-step) ────────────────────────────────────────────────
CMD = {
    "scan":   f'python devmind.py scan --paths "C:\\HVDC PJT" --paths "C:\\cursor-mcp" --emit "{(CACHE/"scan.json").as_posix()}" --safe-map "{(CACHE/"safe_map.json").as_posix()}"',
    "rules":  f'python devmind.py rules --scan "{(CACHE/"scan.json").as_posix()}" --emit "{(CACHE/"scores.json").as_posix()}"',
    "cluster_local": f'python devmind.py cluster --scores "{(CACHE/"scores.json").as_posix()}" --emit "{(CACHE/"projects.json").as_posix()}" --project-mode local',
    "cluster_gpt":   f'python devmind.py cluster --scores "{(CACHE/"scores.json").as_posix()}" --emit "{(CACHE/"projects.json").as_posix()}" --project-mode gpt --safe-map "{(CACHE/"safe_map.json").as_posix()}"',
    "organize": (
        f'python devmind.py organize --projects "{(CACHE/"projects.json").as_posix()}" '
        f'--scores "{(CACHE/"scores.json").as_posix()}" --target "{TARGET}" --mode move --conflict version '
        f'--journal "{(CACHE/"journal.jsonl").as_posix()}" ' + (f'--schema "{SCHEMA.as_posix()}" ' if SCHEMA.exists() else "")
    ),
    "report": f'python devmind.py report --journal "{(CACHE/"journal.jsonl").as_posix()}" --out "{(REPORTS/"projects_summary.html").as_posix()}"',
}
STEPS_LOCAL = ["scan","rules","cluster_local","organize","report"]
STEPS_GPT   = ["scan","rules","cluster_gpt","organize","report"]

# ── Subprocess helpers ───────────────────────────────────────────────────────
def run_step(cmd: str, on_line: Callable[[str], None]) -> Tuple[int, list[str]]:
    env = dict(os.environ); env.setdefault("PYTHONUNBUFFERED","1")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, shell=True, bufsize=1, cwd=str(BASE), env=env)
    tail: list[str] = []
    assert p.stdout is not None
    for raw in p.stdout:
        line = (raw.rstrip()[:700]) if raw else ""
        if line:
            on_line(line)
            tail.append(line)
            if len(tail) > 100: tail.pop(0)
    p.wait()
    return p.returncode, tail

def run_pipeline(mode: str, on_stage, on_line):
    steps = STEPS_LOCAL if mode=="local" else STEPS_GPT
    for step in steps:
        on_stage(step)
        rc, tail = run_step(CMD[step], on_line)
        yield step, rc, tail
        if rc != 0:
            break

# ── Sidebar (Left controls) ─────────────────────────────────────────────────
with st.sidebar:  # 공식 사이드바 영역 사용 (좌측 고정) :contentReference[oaicite:2]{index=2}
    st.markdown("### Controls")
    st.caption("Choose mode and run the 6-step pipeline.")
    mode = st.radio("Mode", ["LOCAL", "GPT"], horizontal=True, help="LOCAL: TF-IDF/KMeans · GPT: safe_id만 전송")
    if mode == "GPT" and not os.environ.get("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY not set · GPT 단계는 local로 폴백될 수 있습니다.")
    run_btn = st.button("▶ Run", type="primary", use_container_width=True)
    st.divider()
    report_path = REPORTS / "projects_summary.html"
    st.link_button("📄 Open Report", report_path.as_posix(), disabled=not report_path.exists(),
                   use_container_width=True, help="최신 리포트를 새 탭으로 엽니다.")  # link_button :contentReference[oaicite:3]{index=3}
    clear_btn = st.button("🧹 Clear Cache (.cache)", use_container_width=True)

    if clear_btn:
        try:
            for p in CACHE.glob("*"):
                if p.is_file(): p.unlink()
            st.success("Cleared .cache/")
        except Exception as e:
            st.error(f"Failed to clear cache: {e}")

# ── Main area (Right: status + logs) ────────────────────────────────────────
left, right = st.columns([0.35, 0.65])  # 상태/진행 + 로그 넓게 분할 :contentReference[oaicite:4]{index=4}

with left:
    st.markdown("### Pipeline Status")
    status_box = st.status("Idle", expanded=True)  # status 위젯(장시간 작업용) :contentReference[oaicite:5]{index=5}
    bar = st.progress(0)                           # 단계 기반 진행 바 :contentReference[oaicite:6]{index=6}

with right:
    st.markdown("### Live Log")
    log = st.empty()

# ── Runner ──────────────────────────────────────────────────────────────────
def stream(mode: str):
    steps = STEPS_LOCAL if mode=="LOCAL" else STEPS_GPT
    total = len(steps); done = 0
    lines: list[str] = []
    q: "queue.Queue" = queue.Queue()

    def on_stage(step: str): q.put(f"🚀 {step}")
    def on_line(line: str): q.put(line)

    def worker():
        for step, rc, tail in run_pipeline(mode.lower(), on_stage, on_line):
            q.put(("step", step, rc, tail))
        q.put(("end", None, None, None))

    threading.Thread(target=worker, daemon=True).start()

    with status_box as s:
        s.update(label=f"Running ({mode})", state="running")
        while True:
            drained = False
            while not q.empty():
                drained = True
                item = q.get()
                if isinstance(item, tuple):
                    tag, step, rc, tail = item
                    if tag == "step":
                        done += 1
                        bar.progress(int(done/total*100))
                        if rc == 0:
                            s.write(f"✅ **{step}** completed")
                        else:
                            s.write(f"❌ **{step}** failed (rc={rc})")
                            st.error("Last lines:\n" + "\n".join(tail[-25:]))
                            s.update(label="Failed", state="error")
                            st.toast("Pipeline failed", icon="❌")
                            return
                    elif tag == "end":
                        s.update(label="Completed", state="complete")
                        st.toast("Pipeline completed", icon="✅")
                        return
                else:
                    lines.append(str(item))
                    if len(lines) > 800: lines[:] = lines[-800:]
                    log.code("\n".join(lines), language="bash")
            if not drained:
                time.sleep(0.04)

# ── Actions ─────────────────────────────────────────────────────────────────
if run_btn:
    stream(mode)

# ── Minimal shortcuts (L/G/R) ───────────────────────────────────────────────
st.markdown("""
<script>
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key==='l'||e.key==='L'){const b=[...document.querySelectorAll('button')].find(x=>x.innerText.includes('Run')); if(b){const r=[...document.querySelectorAll('div[data-baseweb=radio]')]; if(r.length){b.click();}}}
  if (e.key==='g'||e.key==='G'){const b=[...document.querySelectorAll('button')].find(x=>x.innerText.includes('Run')); if(b){b.click();}}
  if (e.key==='r'||e.key==='R'){const a=[...document.querySelectorAll('a')].find(x=>x.innerText.includes('Open Report')); if(a){a.click();}}
});
</script>
""", unsafe_allow_html=True)