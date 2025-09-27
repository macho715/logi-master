#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Project Autosort — One-File Edition
- scan → rules → cluster(--project-mode local|gpt) → organize(move, version) → report → (rollback)
- 중복 파일은 모두 보존: name__{blake7}.ext
- GPT 모드: safe_id(sha256(path)) + 메타만 전송 → safe_map.json로 로컬 역매핑 (경로/원문 비전송)
Usage (PowerShell):
  python proj_autosort.py run --paths "C:\HVDC PJT" --paths "C:\cursor-mcp" --target "C:\PROJECTS_STRUCT" --project-mode local
  python proj_autosort.py run --paths "C:\HVDC PJT" --paths "C:\cursor-mcp" --target "C:\PROJECTS_STRUCT" --project-mode gpt --openai-key sk-xxxx
  python proj_autosort.py rollback --journal .cache\journal.jsonl
"""

import os, re, sys, json, time, hashlib, shutil, mimetypes, math
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# ---------- small deps (optional) ----------
try:
    import blake3  # pip install blake3
except Exception:
    blake3 = None
# local clustering (optional). If missing and project-mode=local, we fallback to naive path grouping
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


# ========= Utilities =========
def now_ms() -> int:
    return int(time.time() * 1000)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def sha256_str(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def blake7_of_file(p: Path) -> str:
    if blake3 is None:
        # fallback (sha256 7자리)
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for ch in iter(lambda: f.read(1024 * 1024), b""):
                h.update(ch)
        return h.hexdigest()[:7]
    h = blake3.blake3()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1024 * 1024), b""):
            h.update(ch)
    return h.hexdigest()[:7]

def normalize_label(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "misc"

DEFAULT_HINTS = ["hvdc", "warehouse", "ontology", "mcp", "cursor", "layoutapp", "ldg", "logi", "stow"]

# ========= 1) scan =========
def scan_paths(roots: List[str], sample_bytes: int = 4096) -> List[Dict[str, Any]]:
    items = []
    for root in roots:
        for dp, _, files in os.walk(root):
            for fn in files:
                p = Path(dp) / fn
                try:
                    st = p.stat()
                    rec = {
                        "path": str(p),
                        "safe_id": sha256_str(str(p)),  # 경로 기반 safe id (세션 내 안정)
                        "name": fn,
                        "ext": p.suffix.lower(),
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                    }
                    # lightweight snippet only for text-like
                    mime, _ = mimetypes.guess_type(p.name)
                    if mime and (mime.startswith("text") or any(p.suffix.lower().endswith(x) for x in (".md",".txt",".py",".json",".yml",".yaml",".cfg",".ini",".toml",".csv"))):
                        try:
                            with open(p, "rb") as f:
                                head = f.read(sample_bytes)
                            rec["hint"] = head.decode("utf-8", errors="ignore")
                        except Exception:
                            rec["hint"] = ""
                    else:
                        rec["hint"] = ""
                    items.append(rec)
                except Exception as e:
                    items.append({"path": str(p), "error": str(e)})
    return items

# ========= 2) rules (shallow bucket tags) =========
RULES = [
    ("src",       r"\.py$"),
    ("scripts",   r"\.ps1$|\.bat$|run_|setup|install"),
    ("tests",     r"(^|\\)tests?(\\|/)|\bpytest\b|\bunittest\b"),
    ("docs",      r"\.md$|README|GUIDE|INSTALLATION|PLAN|SPEC|TDD"),
    ("reports",   r"report|summary|analysis|final|complete"),
    ("configs",   r"\.ya?ml$|\.toml$|\.ini$|pyproject|requirements|\.env$|\.json$|\.cfg$"),
    ("data",      r"\.csv$|\.xlsx$|\.xls$|\.parquet$|(\\|/)data(\\|/)"),
    ("notebooks", r"\.ipynb$"),
    ("archive",   r"old|backup|_bak|_copy|v\d+"),
]

def apply_rules(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def bucket_of(name: str, path: str, hint: str) -> str:
        text = f"{name} {path} {hint}".lower()[:8000]
        for b, pat in RULES:
            if re.search(pat, text, re.I):
                return b
        return "tmp"
    out = []
    for it in items:
        if "error" in it:
            it["bucket"] = "archive"
        else:
            it["bucket"] = bucket_of(it["name"], it["path"], it.get("hint", ""))
        out.append(it)
    return out

# ========= 3) cluster (local | gpt) =========
def payload_safe(items: List[Dict[str, Any]], max_snip=500) -> List[Dict[str, Any]]:
    safe = []
    for it in items:
        safe.append({
            "id": it.get("safe_id") or sha256_str(it.get("path","")),
            "name": it.get("name",""),
            "ext": it.get("ext",""),
            "size": it.get("size",0),
            "mime": "text/plain",
            "snippet": (it.get("hint","") or "")[:max_snip],
            "rule_tags": [it.get("bucket","tmp")],
            "path_hint": normalize_label("/".join(Path(it.get("path","")).parts[-3:]))
        })
    return safe

SYSTEM_PROMPT = """You are a project clustering assistant for developer workspaces.
Goal: Group files into ≤12 coherent “project” clusters with short snake_case labels.

INPUT: SAFE records (no raw paths).
{id: safe_id, name, ext, size, mime, snippet<=500, rule_tags[], path_hint}

RULES
- Output JSON only: {"projects":[{project_id, project_label, doc_ids[], role_bucket_map, confidence, reasons[]}]}.
- project_label: short snake_case.
- ≤12 clusters; prefer 5–10 when uncertain.
- reasons: ≤15 words; no raw quotes from snippet.
- doc_ids are SAFE ids from input.
- If unsure, cluster by path_hint + rule_tags; outliers → misc_noise.
- Confidence 0.50–0.95.
"""

def cluster_local(items: List[Dict[str, Any]], hints=DEFAULT_HINTS) -> Dict[str, Any]:
    # If sklearn missing, fallback to naive grouping by top-level dir name
    if not SKLEARN_OK or len(items) < 3:
        groups: Dict[str, List[str]] = {}
        for it in items:
            p = Path(it["path"])
            label = normalize_label((p.parts[1] if len(p.parts)>1 else p.name) or "misc")
            groups.setdefault(label, []).append(it["path"])
        return {"projects":[{"project_id":k,"project_label":k,"doc_ids":v,"role_bucket_map":{},"confidence":0.65,"reasons":["naive_path"]} for k,v in groups.items()]}

    docs, paths = [], []
    for it in items:
        txt = " ".join([it.get("name",""), it.get("path",""), it.get("hint",""), it.get("bucket","")])
        for h in hints:
            if h in txt.lower():
                txt += (" " + h) * 5
        if it.get("bucket") in ("docs","configs","scripts","src","tests","reports","data","notebooks"):
            txt += (" " + it["bucket"]) * 3
        docs.append(txt)
        paths.append(it["path"])

    vect = TfidfVectorizer(max_features=20000, ngram_range=(1,2))
    X = vect.fit_transform(docs)
    n = len(docs)
    k = max(2, min(12, int(math.sqrt(n))))

    if n <= 20:
        db = DBSCAN(eps=0.8, min_samples=2, metric="cosine")
        labels = db.fit_predict(X)
        if (labels == -1).all():
            km = KMeans(n_clusters=min(k, n), n_init="auto", random_state=42)
            labels = km.fit_predict(X)
    else:
        km = KMeans(n_clusters=min(k, n), n_init="auto", random_state=42)
        labels = km.fit_predict(X)

    from collections import defaultdict
    groups = defaultdict(list)
    for pth, lab in zip(paths, labels):
        groups[int(lab)].append(pth)

    # representative-based label + confidence
    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        csim = cosine_similarity(X)
        projects = []
        for gid, doc_ids in groups.items():
            if gid == -1:
                projects.append({"project_id":"misc_noise","project_label":"misc_noise","doc_ids":doc_ids,"role_bucket_map":{},"confidence":0.55,"reasons":["dbscan_noise"]})
                continue
            idxs = [paths.index(p) for p in doc_ids]
            sub = csim[np.ix_(idxs, idxs)]
            avg_sim = sub.mean(axis=1) if sub.size else 0.6
            rep_idx = idxs[int(np.argmax(avg_sim))] if sub.size else idxs[0]
            rep_txt = docs[rep_idx].lower()
            cand = []
            for h in hints:
                if h in rep_txt: cand.append(h)
            for b in ["src","scripts","tests","docs","reports","configs","data","notebooks"]:
                if b in rep_txt: cand.append(b)
            label = normalize_label("_".join(cand[:3]) or Path(doc_ids[0]).parent.name)
            conf = float(avg_sim.max()) if sub.size else 0.65
            conf = max(0.5, min(0.95, conf))
            projects.append({"project_id":label,"project_label":label,"doc_ids":doc_ids,"role_bucket_map":{},"confidence":conf,"reasons":["tfidf_cluster"]})
        return {"projects": projects}
    except Exception:
        # safe fallback
        return {"projects":[{"project_id":normalize_label(Path(v[0]).parent.name),"project_label":normalize_label(Path(v[0]).parent.name),"doc_ids":v,"role_bucket_map":{},"confidence":0.65,"reasons":["fallback"]} for v in groups.values()]}

def call_openai_chat(api_key: str, safe_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    # pure stdlib call
    import urllib.request
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role":"system","content": SYSTEM_PROMPT},
            {"role":"user","content": json.dumps(safe_records, ensure_ascii=False)}
        ],
        "response_format": {"type":"json_object"},
        "temperature": 0.2
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    content = out["choices"][0]["message"]["content"]
    return json.loads(content)

def cluster_gpt(items: List[Dict[str, Any]], safe_map: Dict[str,str], api_key: str) -> Dict[str, Any]:
    safe_records = payload_safe(items)
    data = call_openai_chat(api_key, safe_records)  # {"projects":[{..., "doc_ids":[safe_id,...]}]}
    projects = []
    for p in data.get("projects", []):
        ids = p.get("doc_ids", [])
        paths = [safe_map.get(i) for i in ids if i in safe_map]
        if not paths:
            continue
        label = normalize_label(p.get("project_label") or p.get("project_id") or "misc")
        projects.append({
            "project_id": label,
            "project_label": label,
            "doc_ids": paths,
            "role_bucket_map": p.get("role_bucket_map", {}),
            "confidence": float(p.get("confidence", 0.7)),
            "reasons": (p.get("reasons", []) + ["mapped_via_safe_map"])[:5]
        })
    return {"projects": projects}

# ========= 4) organize (move + version) =========
DEFAULT_SCHEMA = [
    "src/core/","src/utils/","src/pipelines/","scripts/","tests/unit/","tests/integration/",
    "docs/","reports/","configs/","data/raw/","data/interim/","data/processed/","notebooks/","archive/","tmp/"
]

def ensure_schema(base: Path, schema_dirs: List[str]):
    for rel in schema_dirs:
        ensure_dir(base / rel)

def versioned_dst(dst_dir: Path, name: str, hash7: str) -> Path:
    stem = Path(name).stem
    ext  = Path(name).suffix
    return dst_dir / f"{stem}__{hash7}{ext}"

def organize(projects: Dict[str, Any], scores_items: List[Dict[str, Any]], target_root: str, mode: str, conflict: str, journal_path: str, schema_dirs: List[str]):
    ensure_dir(Path(target_root))
    by_path = {x["path"]: x for x in scores_items if "path" in x}
    with open(journal_path, "a", encoding="utf-8") as log:
        for p in projects.get("projects", []):
            base = Path(target_root) / p["project_label"]
            ensure_schema(base, schema_dirs)
            for src_path in p.get("doc_ids", []):
                src = Path(src_path)
                if not src.exists():
                    log.write(json.dumps({"ts":now_ms(),"code":"MISS","src":str(src)})+"\n")
                    continue
                meta = by_path.get(src_path, {})
                bucket = meta.get("bucket", "tmp")
                dst_dir = base / bucket
                ensure_dir(dst_dir)
                try:
                    h7 = blake7_of_file(src)
                    dst = versioned_dst(dst_dir, src.name, h7)
                    if conflict == "skip" and dst.exists():
                        code="SKIP"
                    else:
                        if mode == "copy":
                            shutil.copy2(src, dst)
                        else:
                            shutil.move(src, dst)
                        code="OK"
                    log.write(json.dumps({"ts":now_ms(),"code":code,"src":str(src),"dst":str(dst),"hash":h7})+"\n")
                except Exception as e:
                    log.write(json.dumps({"ts":now_ms(),"code":"ERR","src":str(src),"reason":str(e)})+"\n")

# ========= 5) report =========
def write_report(journal_path: str, out_html: str):
    ensure_dir(Path(out_html).parent)
    moves, errs = 0, 0
    by_proj = {}
    if Path(journal_path).exists():
        for line in open(journal_path, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            code = j.get("code")
            if code == "OK": moves += 1
            if code in ("ERR","MISS"): errs += 1
            dst = j.get("dst","")
            parts = Path(dst).parts
            key = parts[1] if len(parts)>1 else "misc"
            by_proj[key] = by_proj.get(key, 0) + 1
    rows = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>" for k,v in sorted(by_proj.items()))
    html = f"""<!doctype html><meta charset="utf-8">
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
    open(out_html, "w", encoding="utf-8").write(html)
    return out_html

# ========= 6) rollback =========
def rollback(journal_path: str):
    if not Path(journal_path).exists():
        print("[rollback] journal not found")
        return
    lines = [json.loads(x) for x in open(journal_path, encoding="utf-8") if x.strip()]
    for j in reversed(lines):
        if j.get("code") != "OK":
            continue
        src, dst = j["src"], j["dst"]
        if Path(dst).exists():
            ensure_dir(Path(src).parent)
            shutil.move(dst, src)
    print("[rollback] completed")

# ========= CLI =========
def main():
    ap = argparse.ArgumentParser(description="Project Autosort — One-File Edition")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_run = sub.add_parser("run", help="scan → rules → cluster → organize → report")
    ap_run.add_argument("--paths", action="append", required=True, help="scan roots (multi)")
    ap_run.add_argument("--target", required=True, help="destination root")
    ap_run.add_argument("--project-mode", choices=["local","gpt"], default="local")
    ap_run.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY",""), help="OpenAI API key (for gpt mode)")
    ap_run.add_argument("--sample-bytes", type=int, default=4096)
    ap_run.add_argument("--mode", choices=["move","copy"], default="move")
    ap_run.add_argument("--conflict", choices=["version","skip","overwrite"], default="version")
    ap_run.add_argument("--cache-dir", default=".cache")
    ap_run.add_argument("--report", default="reports/projects_summary.html")

    ap_rb = sub.add_parser("rollback", help="rollback using journal")
    ap_rb.add_argument("--journal", required=True)

    args = ap.parse_args()

    if args.cmd == "run":
        cache = Path(args.cache_dir); ensure_dir(cache)
        ensure_dir(Path(args.report).parent)

        # 1) scan
        items = scan_paths(args.paths, sample_bytes=args.sample_bytes)
        scan_json = cache / "scan.json"
        json.dump(items, open(scan_json,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

        # safe_map (safe_id -> path)
        safe_map = {it.get("safe_id"): it.get("path") for it in items if "safe_id" in it}
        json.dump(safe_map, open(cache/"safe_map.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)

        # 2) rules
        items2 = apply_rules(items)
        scores_json = cache / "scores.json"
        json.dump(items2, open(scores_json,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

        # 3) cluster
        if args.project_mode == "gpt":
            if not args.openai_key:
                print("[cluster/gpt] OPENAI KEY missing → fallback to local")
                projects = cluster_local(items2)
            else:
                try:
                    projects = cluster_gpt(items2, safe_map, args.openai_key)
                    if not projects.get("projects"):
                        print("[cluster/gpt] empty → fallback to local")
                        projects = cluster_local(items2)
                except Exception as e:
                    print(f"[cluster/gpt] error → local fallback: {e}")
                    projects = cluster_local(items2)
        else:
            projects = cluster_local(items2)

        projects_json = cache / "projects.json"
        json.dump(projects, open(projects_json,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

        # 4) organize
        journal = str(cache / "journal.jsonl")
        organize(projects, items2, args.target, args.mode, args.conflict, journal, DEFAULT_SCHEMA)

        # 5) report
        out_html = write_report(journal, args.report)
        print(f"[DONE] report -> {out_html}")

    elif args.cmd == "rollback":
        rollback(args.journal)

if __name__ == "__main__":
    main()
proj_autosort.py