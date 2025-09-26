# devmind.py
import hashlib, json, os, re, shutil, sys, time, math
from pathlib import Path
from collections import defaultdict
import click

TARGET_ROOT = Path("C:/PROJECTS_STRUCT")

def blake7(p: Path) -> str:
    import blake3
    h = blake3.blake3()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()[:7]

def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def mask_path(s: str) -> str:
    return re.sub(r"[A-Za-z]:\\\\[^\\n]+", "<MASK>", s.replace("/", "\\\\"))

def now_ms() -> int:
    return int(time.time() * 1000)

def sha256_str(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8", errors="ignore"))
    return h.hexdigest()

# ---------- scan ----------
@click.group()
def cli():
    pass

@cli.command()
@click.option("--paths", multiple=True, required=True)
@click.option("--sample-bytes", default=4096, show_default=True)
@click.option("--emit", default=".cache/scan.json", show_default=True)
@click.option("--safe-map", "safe_map_path", default=".cache/safe_map.json", show_default=True)
def scan(paths, sample_bytes, emit, safe_map_path):
    items = []
    safe_map = {}  # {safe_id: path}
    for root in paths:
        for dp, _, files in os.walk(root):
            for fn in files:
                p = Path(dp) / fn
                try:
                    st = p.stat()
                    safe_id = sha256_str(str(p))
                    rec = {
                        "path": str(p),
                        "safe_id": safe_id,         # ★ 추가
                        "name": fn,
                        "ext": p.suffix.lower(),
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                    }
                    # 가벼운 내용 힌트 (텍스트만)
                    try:
                        with open(p, "rb") as f:
                            head = f.read(sample_bytes)
                        rec["hint"] = head.decode("utf-8", errors="ignore")
                    except Exception:
                        rec["hint"] = ""
                    items.append(rec)
                    safe_map[safe_id] = str(p)    # ★ 추가
                except Exception as e:
                    items.append({"path": str(p), "error": str(e)})
    Path(".cache").mkdir(exist_ok=True)
    with open(emit, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    
    with open(safe_map_path, "w", encoding="utf-8") as f:   # ★ 추가
        json.dump(safe_map, f, ensure_ascii=False, indent=2)
    
    click.echo(f"[scan] {len(items)} items -> {emit} ; safe_map -> {safe_map_path}")

# ---------- rules (아주 얕은 규칙) ----------
RULES = [
    ("src",      r"\.py$"),
    ("scripts",  r"\.ps1$|\.bat$|run_|setup|install"),
    ("tests",    r"(^|\\)tests?(\\|/)|\bpytest\b|\bunittest\b"),
    ("docs",     r"\.md$|README|GUIDE|INSTALLATION|PLAN|SPEC|TDD"),
    ("reports",  r"report|summary|analysis|final|complete"),
    ("configs",  r"\.ya?ml$|\.toml$|\.ini$|pyproject|requirements|\.env$|\.json$|\.cfg$"),
    ("data",     r"\.csv$|\.xlsx$|\.xls$|\.parquet$|(\\|/)data(\\|/)"),
    ("notebooks",r"\.ipynb$"),
    ("archive",  r"old|backup|_bak|_copy|v\d+"),
]

def bucket_of(name: str, path: str, hint: str) -> str:
    text = f"{name} {path} {hint}".lower()[:8000]
    for b, pat in RULES:
        if re.search(pat, text, re.I):
            return b
    return "tmp"

@cli.command()
@click.option("--scan", "scan_path", default=".cache/scan.json")
@click.option("--emit", default=".cache/scores.json")
def rules(scan_path, emit):
    items = json.load(open(scan_path, encoding="utf-8"))
    for it in items:
        if "error" in it: 
            it["bucket"] = "archive"
            continue
        it["bucket"] = bucket_of(it["name"], it["path"], it.get("hint",""))
    json.dump(items, open(emit,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    click.echo(f"[rules] -> {emit}")

# ---------- cluster (프로젝트 라벨러: 간단 버전) ----------
# 외부 GPT 없이도 루트 이름 힌트로 라벨링(임시). GPT 연결 시 교체.
def proj_label(path: str) -> str:
    p = path.replace("\\", "/").lower()
    for key in ["hvdc", "warehouse", "ontology", "mcp", "cursor", "layoutapp", "ldg", "logi", "stow"]:
        if key in p:
            return key
    # 상위 폴더명
    parts = Path(path).parts
    return (parts[1] if len(parts)>1 else "misc").lower()

def take_hint_tokens(it):
    name = it.get("name","")
    path = it.get("path","")
    hint = it.get("hint","")
    bucket = it.get("bucket","")
    return " ".join([name, path, hint, bucket])

DEFAULT_HINTS = ["hvdc","warehouse","ontology","mcp","cursor","layoutapp","ldg","logi","stow"]

def normalize_label(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "misc"

# ====== LOCAL 모드 구현 (TF-IDF + KMeans/DBSCAN) ======
def local_cluster(items, k: int | None = None, hints=DEFAULT_HINTS):
    """
    items: .cache/scores.json 로드 결과(list of dict with 'path','name','hint','bucket')
    return: {"projects":[{project_id, project_label, doc_ids, role_bucket_map, confidence, reasons}]}
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    docs = []
    paths = []
    for it in items:
        if "path" not in it: 
            continue
        txt = take_hint_tokens(it)
        # 힌트/버킷 가중치(단어 가중 부여)
        for h in hints:
            if h in txt.lower():
                txt += (" " + h) * 5
        if it.get("bucket") in ("docs","configs","scripts","src","tests","reports","data","notebooks"):
            txt += (" " + it["bucket"]) * 3
        docs.append(txt)
        paths.append(it["path"])

    if not docs:
        return {"projects":[]}

    # TF-IDF
    vect = TfidfVectorizer(max_features=20000, ngram_range=(1,2))
    X = vect.fit_transform(docs)

    n = len(docs)
    if k is None:
        # 간단한 k 추정: sqrt(n) 클러스터, 최소 2, 최대 12
        k = max(2, min(12, int(math.sqrt(n))))
    labels = None

    # 작은 데이터는 DBSCAN으로 노이즈 억제
    if n <= 20:
        db = DBSCAN(eps=0.8, min_samples=2, metric="cosine")
        labels = db.fit_predict(X)
        # 모두 -1이면 kmeans fallback
        if (labels == -1).all():
            km = KMeans(n_clusters=min(k, n), n_init="auto", random_state=42)
            labels = km.fit_predict(X)
    else:
        km = KMeans(n_clusters=min(k, n), n_init="auto", random_state=42)
        labels = km.fit_predict(X)

    # 라벨 → 문서 매핑
    groups = defaultdict(list)
    for p, lab in zip(paths, labels):
        groups[int(lab)].append(p)

    # 클러스터 라벨링(대표 키워드+경로 힌트 추출)
    projects = []
    csim = cosine_similarity(X)
    for gid, doc_ids in groups.items():
        if gid == -1:
            label = "misc_noise"
            conf = 0.45
            reasons = ["dbscan_noise"]
        else:
            # 대표 문서(index: 최대 평균 유사도)
            idxs = [paths.index(p) for p in doc_ids]
            sub = csim[np.ix_(idxs, idxs)]
            avg_sim = sub.mean(axis=1)
            rep_idx = idxs[int(np.argmax(avg_sim))]
            rep_text = docs[rep_idx].lower()

            # 대표 키워드 추출(힌트/버킷 우선)
            cand = []
            for h in hints:
                if h in rep_text:
                    cand.append(h)
            for b in ["src","scripts","tests","docs","reports","configs","data","notebooks"]:
                if b in rep_text:
                    cand.append(b)
            label = normalize_label("_".join(cand[:3]) or Path(doc_ids[0]).parent.name)
            conf = float(avg_sim.max()) if avg_sim.size else 0.6
            conf = max(0.5, min(0.95, conf))
            reasons = ["tfidf_kmeans" if n>20 else "tfidf_dbscan"]

        projects.append({
            "project_id": label,
            "project_label": label,
            "doc_ids": doc_ids,
            "role_bucket_map": {},
            "confidence": conf,
            "reasons": reasons
        })
    return {"projects": projects}

@cli.command()
@click.option("--scores", default=".cache/scores.json")
@click.option("--emit", default=".cache/projects.json")
@click.option("--project-mode", type=click.Choice(["local","gpt"]), default="local", show_default=True)
@click.option("--k", type=int, default=None, help="local 모드에서 클러스터 수 힌트(없으면 sqrt(n))")
@click.option("--safe-map", "safe_map_path", default=".cache/safe_map.json", show_default=True)
def cluster(scores, emit, project_mode, k, safe_map_path):
    items = json.load(open(scores, encoding="utf-8"))
    items = [x for x in items if "path" in x]

    if project_mode == "local":
        out = local_cluster(items, k=k, hints=DEFAULT_HINTS)
        json.dump(out, open(emit,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        click.echo(f"[cluster/local] {len(out.get('projects',[]))} projects -> {emit}")
        return

    # gpt 모드 (safe_map.json 방식)
    try:
        out = gpt_cluster(items, safe_map_path=safe_map_path)
        # 결과 없으면 local로 안전 대체
        if not out.get("projects"):
            out = local_cluster(items, k=k, hints=DEFAULT_HINTS)
        json.dump(out, open(emit,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        click.echo(f"[cluster/gpt] {len(out.get('projects',[]))} projects -> {emit}")
    except Exception as e:
        # 완전 안전장치: 실패 시 local로 대체
        click.echo(f"[cluster/gpt] error -> fallback to local: {e}")
        out = local_cluster(items, k=k, hints=DEFAULT_HINTS)
        json.dump(out, open(emit,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

# ====== GPT 모드 구현 (마스킹·메타만 전송) ======
def build_gpt_payload(items, max_snip=500):
    safe = []
    for it in items:
        safe_id = it.get("safe_id") or sha256_str(it.get("path",""))
        safe.append({
            "id": safe_id,                               # ★ 경로 대신 safe_id
            "name": it.get("name",""),
            "ext": it.get("ext",""),
            "size": it.get("size",0),
            "mime": "text/plain",
            "snippet": (it.get("hint","") or "")[:max_snip],
            "rule_tags": [it.get("bucket","tmp")],
            # 경로 정보는 마스킹된 힌트만(말단 2~3단)
            "path_hint": normalize_label("/".join(Path(it.get("path","")).parts[-3:]))
        })
    return safe

GPT_SYSTEM = """You cluster files by project for developer workspaces.
Return JSON for function call:
{"projects":[{"project_id": "...","project_label":"...","doc_ids":["<id>"],"role_bucket_map":{},"confidence":0.0,"reasons":["..."]}]}
- Use short snake_case labels.
- Max 12 clusters.
- No raw text beyond 15 words in reasons.
"""

def gpt_cluster(items, safe_map_path, model_env_var="OPENAI_API_KEY"):
    import os, json
    import urllib.request

    api_key = os.environ.get(model_env_var)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role":"system","content": GPT_SYSTEM},
            {"role":"user","content": json.dumps(build_gpt_payload(items), ensure_ascii=False)}
        ],
        "response_format": {"type":"json_object"},
        "temperature": 0.2
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))

    content = out["choices"][0]["message"]["content"]
    data = json.loads(content)  # {"projects":[{..., "doc_ids":[safe_id,...]}]}

    # ★ 여기서 safe_id → path 역매핑
    safe_map = json.load(open(safe_map_path, encoding="utf-8"))
    projects = []
    for p in data.get("projects", []):
        ids = p.get("doc_ids", [])
        paths = [safe_map.get(i) for i in ids if i in safe_map]  # 없는 id는 드롭
        if not paths:
            continue
        label = normalize_label(p.get("project_label") or p.get("project_id") or "misc")
        projects.append({
            "project_id": label,
            "project_label": label,
            "doc_ids": paths,              # ← organize가 기대하는 "path" 리스트로 변환 완료
            "role_bucket_map": p.get("role_bucket_map", {}),
            "confidence": float(p.get("confidence", 0.7)),
            "reasons": p.get("reasons", []) + ["mapped_via_safe_map"]
        })
    return {"projects": projects}

# ---------- organize (바로 이동 + 버전 보존) ----------
SCHEMA = [
    "src/core/","src/utils/","src/pipelines/","scripts/","tests/unit/","tests/integration/",
    "docs/","reports/","configs/","data/raw/","data/interim/","data/processed/","notebooks/","archive/","tmp/"
]

def ensure_schema(base: Path):
    for rel in SCHEMA:
        safe_mkdir(base / rel)

def versioned_name(dst_dir: Path, name: str, hash7: str) -> Path:
    stem = Path(name).stem
    ext  = Path(name).suffix
    cand = dst_dir / f"{stem}__{hash7}{ext}"
    # 이름이 이미 __hash7 라면 그대로
    return cand

@cli.command()
@click.option("--projects", default=".cache/projects.json")
@click.option("--scores", default=".cache/scores.json")
@click.option("--target", default="C:/PROJECTS_STRUCT")
@click.option("--mode", default="move", type=click.Choice(["move","copy"]))
@click.option("--conflict", default="version", type=click.Choice(["version","skip","overwrite"]))
@click.option("--journal", default=".cache/journal.jsonl")
def organize(projects, scores, target, mode, conflict, journal):
    TARGET_ROOT = Path(target)
    safe_mkdir(TARGET_ROOT)
    data = json.load(open(scores, encoding="utf-8"))
    by_path = {x["path"]: x for x in data if "path" in x}
    proj = json.load(open(projects, encoding="utf-8"))["projects"]
    with open(journal, "a", encoding="utf-8") as log:
        for p in proj:
            base = TARGET_ROOT / p["project_label"]
            ensure_schema(base)
            for path in p["doc_ids"]:
                src = Path(path)
                if not src.exists(): 
                    log.write(json.dumps({"ts":now_ms(),"code":"MISS","src":str(src)})+"\n")
                    continue
                meta = by_path.get(path, {})
                bucket = meta.get("bucket", "tmp")
                dst_dir = base / bucket
                safe_mkdir(dst_dir)
                try:
                    h7 = blake7(src)
                    dst = versioned_name(dst_dir, src.name, h7)
                    if conflict == "skip" and dst.exists():
                        code="SKIP"
                    else:
                        if mode=="copy":
                            shutil.copy2(src, dst)
                        else:
                            shutil.move(src, dst)
                        code="OK"
                    log.write(json.dumps({
                        "ts": now_ms(), "code": code, 
                        "src": str(src), "dst": str(dst),
                        "hash": h7
                    })+"\n")
                except Exception as e:
                    log.write(json.dumps({
                        "ts": now_ms(), "code":"ERR", "src": str(src),
                        "reason": str(e)
                    })+"\n")
    click.echo(f"[organize] done -> {target} (journal: {journal})")

# ---------- report (아주 간단) ----------
@cli.command()
@click.option("--journal", default=".cache/journal.jsonl")
@click.option("--out", default="reports/projects_summary.html")
def report(journal, out):
    Path("reports").mkdir(exist_ok=True)
    moves, errs = 0, 0
    by_proj = {}
    if Path(journal).exists():
        for line in open(journal, encoding="utf-8"):
            j = json.loads(line)
            code = j.get("code")
            if code == "OK": moves += 1
            if code in ("ERR","MISS"): errs += 1
            proj = Path(j.get("dst","/misc")).parts
            key = proj[1] if len(proj)>1 else "misc"
            by_proj[key] = by_proj.get(key, 0) + 1
    rows = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>" for k,v in sorted(by_proj.items()))
    html = f"""
<!doctype html><meta charset="utf-8">
<title>Project Organize Report</title>
<style>
 body{{background:#0B1220;color:#E5E7EB;font-family:Inter,system-ui}}
 table{{border-collapse:collapse;width:70%;margin:40px auto;background:#111827}}
 th,td{{padding:12px;border-bottom:1px solid #374151}}
 h1{{text-align:center}}
 .card{{max-width:900px;margin:20px auto;padding:16px;background:#111827;border:1px solid #374151;border-radius:12px}}
 .ok{{color:#22D3EE}} .err{{color:#F87171}}
</style>
<h1>Projects Summary</h1>
<div class="card">
  <p>Moved: <b class="ok">{moves}</b> &nbsp; Errors/Missing: <b class="err">{errs}</b></p>
</div>
<table>
  <thead><tr><th>Project</th><th>Files</th></tr></thead>
  <tbody>{rows or "<tr><td>—</td><td>0</td></tr>"}</tbody>
</table>
"""
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    open(out, "w", encoding="utf-8").write(html)
    click.echo(f"[report] -> {out}")

# ---------- rollback ----------
@cli.command()
@click.option("--journal", required=True)
def rollback(journal):
    if not Path(journal).exists():
        click.echo("[rollback] journal not found")
        sys.exit(1)
    lines = [json.loads(x) for x in open(journal, encoding="utf-8")]
    # 최신 역순
    for j in reversed(lines):
        if j.get("code")!="OK": 
            continue
        src, dst = j["src"], j["dst"]
        if Path(dst).exists():
            Path(Path(src).parent).mkdir(parents=True, exist_ok=True)
            shutil.move(dst, src)
    click.echo("[rollback] completed")

if __name__ == "__main__":
    cli()
