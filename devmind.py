"""Devmind CLI orchestrates project auto-organization.

KR: 프로젝트 파일을 스캔·분류·군집·이동·리포트·롤백한다.
EN: Scan, classify, cluster, organize, report, and rollback project files.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import html
import json
import math
import mimetypes
import os
import re
import shutil
import sqlite3
import sys
import textwrap
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, cast

import click

from logi import Field, LogiBaseModel, LogisticsMetadata

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback loader
    yaml = None

try:  # pragma: no cover - optional rich styling for CLI feedback
    from rich.console import Console
    from rich.table import Table

    console: Optional[Console] = Console()
except ModuleNotFoundError:  # pragma: no cover - degrade gracefully
    console = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


SAFE_DIR = Path(".cache")
DEFAULT_SCAN_EMIT = SAFE_DIR / "scan.json"
DEFAULT_SCORES_EMIT = SAFE_DIR / "scores.json"
DEFAULT_PROJECTS_EMIT = SAFE_DIR / "projects.json"
DEFAULT_JOURNAL = SAFE_DIR / "journal.jsonl"
DEFAULT_SAFE_MAP = SAFE_DIR / "safe_map.json"
CACHE_DB_PATH = SAFE_DIR / "scan_cache.sqlite3"

SCHEMA_FALLBACK = {
    "target_root": "C:/PROJECTS_STRUCT",
    "structure": [
        "src/core/",
        "src/utils/",
        "src/pipelines/",
        "scripts/",
        "tests/unit/",
        "tests/integration/",
        "docs/",
        "reports/",
        "configs/",
        "data/raw/",
        "data/interim/",
        "data/processed/",
        "notebooks/",
        "archive/",
        "tmp/",
    ],
    "conflict_policy": "version",
    "mode": "move",
}

DEFAULT_RULES_CONFIG: Dict[str, Any] = {
    "buckets": {
        "src": {
            "exts": [".py"],
            "name_keywords": ["core", "utils", "pipeline", "engine", "module"],
        },
        "scripts": {
            "code_hints": ['if __name__ == "__main__":'],
            "name_keywords": ["run", "install", "setup", "batch", "job"],
        },
        "tests": {
            "imports": ["pytest", "unittest"],
            "dir_keywords": ["test", "tests"],
        },
        "docs": {
            "exts": [".md", ".rst", ".txt"],
            "title_keywords": ["readme", "guide", "installation", "plan", "spec", "tdd"],
            "name_keywords": ["readme", "guide", "installation", "plan", "spec", "tdd"],
        },
        "reports": {
            "name_keywords": ["report", "summary", "analysis", "final", "complete"],
        },
        "configs": {
            "exts": [".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".json", ".txt"],
            "name_keywords": ["requirements", "config", "settings", "pyproject"],
        },
        "data": {
            "exts": [".csv", ".xlsx", ".xls", ".parquet"],
            "dir_keywords": ["data", "raw", "interim", "processed"],
        },
        "notebooks": {
            "exts": [".ipynb"],
        },
        "archive": {
            "name_keywords": ["old", "backup", "bak", "copy", r"v\d+"],
        },
    },
    "weights": {"name": 4, "dir": 3, "content": 2, "mimetype": 1},
}

BUCKET_FALLBACK_ORDER = (
    "src",
    "scripts",
    "tests",
    "docs",
    "reports",
    "configs",
    "data",
    "notebooks",
    "archive",
    "tmp",
)

BUCKET_TO_SUBDIR = {
    "src": Path("src/core"),
    "scripts": Path("scripts"),
    "tests": Path("tests/unit"),
    "docs": Path("docs"),
    "reports": Path("reports"),
    "configs": Path("configs"),
    "data": Path("data/raw"),
    "notebooks": Path("notebooks"),
    "archive": Path("archive"),
    "tmp": Path("tmp"),
}

DEFAULT_HINTS = [
    "hvdc",
    "warehouse",
    "ontology",
    "mcp",
    "cursor",
    "layoutapp",
    "ldg",
    "logi",
    "stow",
]

SKIP_LABEL_SEGMENTS = {
    "src",
    "source",
    "docs",
    "documents",
    "tests",
    "test",
    "data",
    "images",
    "image",
    "reports",
    "report",
    "configs",
    "config",
    "tmp",
    "temp",
    "archive",
    "notebooks",
    "scripts",
    "script",
    "misc",
    "project",
    "projects",
    "files",
}


def ensure_cache_dir() -> None:
    """KR: .cache 디렉토리를 만든다. EN: Ensure cache directory exists."""

    SAFE_DIR.mkdir(parents=True, exist_ok=True)


def parse_size_limit(limit: Optional[str]) -> Optional[int]:
    """KR: 문자열 용량 제한을 바이트로 변환한다. EN: Convert size token to bytes."""

    if not limit:
        return None
    token = limit.strip().upper()
    m = re.match(r"^(\d+)(B|KB|MB|GB)?$", token)
    if not m:
        raise click.BadParameter("--max-size expects numbers like 500MB or 1024KB")
    value = int(m.group(1))
    suffix = m.group(2) or "B"
    factor = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
    }[suffix]
    return value * factor


def sanitize_path(path: str) -> str:
    """KR: 민감 경로를 마스킹한다. EN: Mask sensitive absolute paths."""

    path = path.replace("/", "\\")
    return re.sub(r"[A-Za-z]:\\[^\\]+", "<PATH>", path)


def mask_sensitive_text(text: str) -> str:
    """KR: PII/시크릿을 마스킹한다. EN: Mask PII and secrets from samples."""

    patterns = [
        (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "<EMAIL>"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "<SSN>"),
        (r"\b\d{6,}\b", "<NUM>"),
        (r"(aws_secret_access_key|aws_access_key_id)\s*=\s*[^\s]+", r"\1=<REDACTED>"),
        (r"(?i)api[_-]?key\s*[:=]\s*[^\s]+", "API_KEY=<REDACTED>"),
        (r"[A-Za-z]:\\[^\n]+", "<PATH>"),
    ]
    masked = text
    for pat, repl in patterns:
        masked = re.sub(pat, repl, masked)
    return masked


def compute_blake7(path: Path) -> str:
    """KR: BLAKE3 7자 해시를 계산한다. EN: Compute seven-char BLAKE3 hash."""

    try:
        import blake3

        hasher = blake3.blake3()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return str(hasher.hexdigest()[:7])
    except ModuleNotFoundError:  # pragma: no cover - fallback path
        hasher = hashlib.blake2b(digest_size=16)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return str(hasher.hexdigest()[:7])


def sha256_string(value: str) -> str:
    """KR: 문자열 SHA256. EN: SHA256 hash of string."""

    digest = hashlib.sha256()
    digest.update(value.encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def infer_mimetype(path: Path) -> str:
    """KR: 마임타입 추론. EN: Infer mimetype for file."""

    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def dir_hint(path: Path) -> str:
    """KR: 상위 디렉토리 힌트를 만든다. EN: Build directory hint tokens."""

    parts = [segment.lower() for segment in path.parts[-3:]]
    return "/".join(parts)


def extract_imports(sample_text: str) -> List[str]:
    """KR: 파이썬 import 키워드를 추출. EN: Extract Python imports from text."""

    imports: List[str] = []
    for line in sample_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            token = re.split(r"\s+", stripped)[1]
            imports.append(token.replace(",", "").strip())
        if len(imports) >= 8:
            break
    return imports


def extract_python_docstring(path: Path) -> Optional[str]:
    """KR: 파이썬 파일 최상위 docstring 추출. EN: Extract python module docstring."""

    if path.suffix.lower() != ".py":
        return None
    try:
        import ast

        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        doc = ast.get_docstring(tree)
        if doc:
            doc = " ".join(doc.split())
        return doc
    except Exception:  # pragma: no cover - parsing failures degrade
        return None


def extract_markdown_headings(sample_text: str) -> List[str]:
    """KR: Markdown H1~H3 제목 추출. EN: Extract markdown headings (H1-H3)."""

    headings: List[str] = []
    for line in sample_text.splitlines():
        match = re.match(r"^(#{1,3})\s+(.*)$", line.strip())
        if match:
            headings.append(match.group(2).strip())
        if len(headings) >= 5:
            break
    return headings


def extract_json_keys(path: Path, limit_bytes: int = 512 * 1024) -> List[str]:
    """KR: JSON 루트 키 추출. EN: Extract JSON root keys."""

    if path.suffix.lower() != ".json":
        return []
    try:
        data = path.read_bytes()
        if len(data) > limit_bytes:
            return []
        obj = json.loads(data.decode("utf-8", errors="ignore"))
        if isinstance(obj, dict):
            return list(obj.keys())[:20]
    except Exception:  # pragma: no cover - invalid JSON
        return []
    return []


def extract_csv_header(path: Path) -> List[str]:
    """KR: CSV 헤더 추출. EN: Extract CSV header row."""

    if path.suffix.lower() not in {".csv", ".tsv"}:
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            row = next(reader)
            return row[:20]
    except Exception:  # pragma: no cover
        return []


def read_sample(path: Path, sample_bytes: int) -> str:
    """KR: 파일 샘플을 읽는다. EN: Read file sample text."""

    with path.open("rb") as handle:
        chunk = handle.read(sample_bytes)
    text = chunk.decode("utf-8", errors="ignore")
    return mask_sensitive_text(text)


class DocumentRecord(LogiBaseModel):
    """KR: 스캔 결과 레코드. EN: Representation of scanned file metadata."""

    path: str
    safe_id: str
    name: str
    ext: str
    size: int
    mtime: float
    mimetype: str
    dir_hint: str
    blake3: Optional[str] = None
    imports: List[str] = Field(default_factory=list)
    top_comment: Optional[str] = None
    md_headings: List[str] = Field(default_factory=list)
    json_root_keys: List[str] = Field(default_factory=list)
    csv_header: List[str] = Field(default_factory=list)
    sample: str = ""
    bucket: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        """KR: JSON 직렬화. EN: Convert model into JSON dictionary."""

        payload = self.model_dump()
        return payload


def record_from_entry(entry: Dict[str, Any]) -> DocumentRecord:
    """KR: dict→DocumentRecord 변환. EN: Convert dict to DocumentRecord."""

    return DocumentRecord.model_validate(entry)


class ScanCache:
    """KR: 스캔 캐시(SQLite). EN: SQLite-backed scan cache."""

    def __init__(self, db_path: Path) -> None:
        ensure_cache_dir()
        # SQLite 잠금 문제 해결: WAL 모드 + timeout + busy_timeout
        self.conn = sqlite3.connect(str(db_path), timeout=30.0)
        cur = self.conn.cursor()

        # WAL 모드 설정: 읽기(다수) + 쓰기(1) 동시 허용, 잠금 충돌 감소
        cur.execute("PRAGMA journal_mode=WAL;")

        # Busy 핸들러: 잠금 시 재시도 대기 (5초)
        cur.execute("PRAGMA busy_timeout=5000;")

        # fsync 강도 조절로 성능/안정 타협
        cur.execute("PRAGMA synchronous=NORMAL;")

        # 테이블 생성
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                safe_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def load(self, safe_id: str, mtime: float, size: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT payload FROM records WHERE safe_id = ? AND mtime = ? AND size = ?",
            (safe_id, mtime, size),
        )
        row = cur.fetchone()
        if row:
            try:
                return cast(Dict[str, Any], json.loads(row[0]))
            except json.JSONDecodeError:  # pragma: no cover
                return None
        return None

    def save(self, record: DocumentRecord) -> None:
        payload = json.dumps(record.to_json(), ensure_ascii=False)
        self.conn.execute(
            "REPLACE INTO records (safe_id, path, size, mtime, payload) VALUES (?,?,?,?,?)",
            (record.safe_id, record.path, record.size, record.mtime, payload),
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class RuleBucket(LogiBaseModel):
    """KR: 버킷 규칙. EN: Configuration for a single bucket."""

    name: str
    exts: List[str] = Field(default_factory=list)
    name_keywords: List[str] = Field(default_factory=list)
    dir_keywords: List[str] = Field(default_factory=list)
    title_keywords: List[str] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    code_hints: List[str] = Field(default_factory=list)
    mimetypes: List[str] = Field(default_factory=list)


class RuleWeights(LogiBaseModel):
    """KR: 가중치. EN: Weighting for rule scoring."""

    name: float = 4.0
    dir: float = 3.0
    content: float = 2.0
    mimetype: float = 1.0


class RuleEngine:
    """KR: 규칙 기반 버킷 분류기. EN: Rule-based bucket classifier."""

    def __init__(self, buckets: List[RuleBucket], weights: RuleWeights) -> None:
        self.buckets = buckets
        self.weights = weights

    @staticmethod
    def from_config(path: Optional[Path]) -> "RuleEngine":
        config_data: Dict[str, Any] = copy.deepcopy(DEFAULT_RULES_CONFIG)
        if path and path.exists() and yaml:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                buckets_override = loaded.get("buckets")
                weights_override = loaded.get("weights")
                if isinstance(buckets_override, dict):
                    buckets_data = cast(Dict[str, Any], config_data.setdefault("buckets", {}))
                    buckets_data.update(buckets_override)
                if isinstance(weights_override, dict):
                    weights_data = cast(Dict[str, Any], config_data.setdefault("weights", {}))
                    weights_data.update(weights_override)

        buckets_cfg = cast(Dict[str, Any], config_data.get("buckets", {}))
        buckets = [
            RuleBucket(
                name=name,
                exts=[e.lower() for e in data.get("exts", [])],
                name_keywords=[w.lower() for w in data.get("name_keywords", [])],
                dir_keywords=[w.lower() for w in data.get("dir_keywords", [])],
                title_keywords=[w.lower() for w in data.get("title_keywords", [])],
                imports=[w.lower() for w in data.get("imports", [])],
                code_hints=[w.lower() for w in data.get("code_hints", [])],
                mimetypes=[w.lower() for w in data.get("mimetypes", [])],
            )
            for name, data in buckets_cfg.items()
        ]

        weights_data = cast(Dict[str, Any], config_data.get("weights", {}))
        weights = RuleWeights(**weights_data)
        return RuleEngine(buckets, weights)

    def score_bucket(self, record: DocumentRecord, bucket: RuleBucket) -> float:
        name_lower = record.name.lower()
        path_lower = record.path.lower()
        sample_lower = record.sample.lower()
        score = 0.0

        if bucket.exts and record.ext.lower() in bucket.exts:
            score += self.weights.name

        if bucket.name_keywords:
            for keyword in bucket.name_keywords:
                if keyword in name_lower:
                    score += self.weights.name

        if bucket.dir_keywords:
            for keyword in bucket.dir_keywords:
                if keyword in path_lower or keyword in record.dir_hint:
                    score += self.weights.dir

        if bucket.title_keywords:
            joined = " ".join(record.md_headings).lower()
            for keyword in bucket.title_keywords:
                if keyword in joined:
                    score += self.weights.content

        if bucket.imports:
            imports_lower = [imp.lower() for imp in record.imports]
            for keyword in bucket.imports:
                if keyword in imports_lower:
                    score += self.weights.content

        if bucket.code_hints:
            for keyword in bucket.code_hints:
                if keyword in sample_lower:
                    score += self.weights.content

        if bucket.mimetypes:
            for mime in bucket.mimetypes:
                if mime in record.mimetype.lower():
                    score += self.weights.mimetype

        return score

    def classify(self, record: DocumentRecord) -> str:
        scores = []
        for bucket in self.buckets:
            score = self.score_bucket(record, bucket)
            scores.append((score, bucket.name))
        scores.sort(reverse=True)
        top_score, top_bucket = scores[0]
        if top_score <= 0:
            return "tmp"
        return top_bucket


# ---------------------------------------------------------------------------
# Cluster logic
# ---------------------------------------------------------------------------


def normalize_label(label: str) -> str:
    """KR: 프로젝트 라벨 정규화. EN: Normalize project labels."""

    cleaned = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return cleaned or "misc"


def split_path_segments(path: str) -> List[str]:
    """경로를 세그먼트로 분리한다. Split a filesystem-like path into segments."""

    tokens = re.split(r"[\\/]+", path)
    segments: List[str] = []
    for token in tokens:
        candidate = token.strip()
        if not candidate:
            continue
        if candidate.endswith(":"):
            continue
        if candidate in {"."}:
            continue
        segments.append(candidate)
    return segments


def longest_common_prefix(segments: List[List[str]]) -> List[str]:
    """공통 접두 세그먼트를 구한다. Return the longest common prefix across segment lists."""

    if not segments:
        return []
    prefix: List[str] = []
    for group in zip(*segments):
        first = group[0]
        if all(item == first for item in group[1:]):
            prefix.append(first)
        else:
            break
    return prefix


def derive_project_label(doc_ids: List[str], fallback: str) -> str:
    """프로젝트 라벨을 추론한다. Derive a project label from document paths."""

    segments = [split_path_segments(path) for path in doc_ids if path]
    usable = [seg for seg in segments if seg]
    if usable:
        prefix = longest_common_prefix(usable)
        for segment in reversed(prefix):
            normalized = normalize_label(segment)
            if normalized and normalized not in SKIP_LABEL_SEGMENTS:
                return normalized
        flattened = [normalize_label(part) for seq in usable for part in seq]
        counts = Counter(part for part in flattened if part and part not in SKIP_LABEL_SEGMENTS)
        if counts:
            return counts.most_common(1)[0][0]
    return normalize_label(fallback)


def simple_cluster(items: Sequence[Dict[str, Any]], hints: Sequence[str]) -> Dict[str, Any]:
    """KR: 모듈 없이 실행되는 단순 군집화. EN: Lightweight cluster fallback."""

    groups: Dict[str, List[str]] = defaultdict(list)
    for entry in items:
        path = entry.get("path")
        if not path:
            continue
        lower_path = path.lower()
        label_source: Optional[str] = None
        for hint in hints:
            if hint in lower_path:
                label_source = hint
                break
        if not label_source:
            parts = [part for part in Path(path).parts if part]
            if len(parts) >= 2:
                label_source = parts[-2]
            elif parts:
                label_source = parts[-1]
            else:
                label_source = "misc"
        label = normalize_label(label_source)
        groups[label].append(path)

    projects: List[Dict[str, Any]] = []
    for label, doc_ids in groups.items():
        bucket_counts = Counter(
            entry.get("bucket", "tmp") for entry in items if entry.get("path") in doc_ids
        )
        projects.append(
            {
                "project_id": label,
                "project_label": label,
                "doc_ids": doc_ids,
                "role_bucket_map": dict(bucket_counts),
                "confidence": 0.6,
                "reasons": ["fallback_directory"],
            }
        )
    return {"projects": projects}


def local_cluster(items: Sequence[Dict[str, Any]], hints: Sequence[str]) -> Dict[str, Any]:
    """KR: TF-IDF 로컬 군집화. EN: Local TF-IDF clustering."""

    try:
        from sklearn.cluster import DBSCAN, KMeans
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ModuleNotFoundError:
        return simple_cluster(items, hints)

    documents: List[str] = []
    paths: List[str] = []
    weights: List[str] = []

    for entry in items:
        path = entry.get("path")
        if not path:
            continue
        bucket = entry.get("bucket", "")
        sample = entry.get("sample", "")
        tokens = " ".join(
            [
                entry.get("name", ""),
                path,
                bucket,
                entry.get("dir_hint", ""),
                " ".join(entry.get("md_headings", [])),
                " ".join(entry.get("imports", [])),
                sample,
            ]
        )
        for hint in hints:
            if hint in tokens.lower():
                tokens += (" " + hint) * 3
        documents.append(tokens)
        paths.append(path)
        weights.append(bucket)

    if not documents:
        return {"projects": []}

    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(documents)

    n_docs = len(documents)
    if n_docs <= 2:
        labels = [0] * n_docs
    elif n_docs <= 20:
        clustering = DBSCAN(eps=0.8, min_samples=2, metric="cosine")
        labels = clustering.fit_predict(matrix)
        if (labels == -1).all():
            k = max(2, min(n_docs, int(math.sqrt(n_docs)) or 1))
            kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = kmeans.fit_predict(matrix)
    else:
        k = max(2, min(12, int(math.sqrt(n_docs))))
        kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42)
        labels = kmeans.fit_predict(matrix)

    groups: Dict[int, List[int]] = defaultdict(list)
    for idx, cluster_label in enumerate(labels):
        groups[int(cluster_label)].append(idx)

    cosine = cosine_similarity(matrix)
    projects: List[Dict[str, Any]] = []
    for group_id, indices in groups.items():
        doc_ids = [paths[i] for i in indices]
        submatrix = cosine[[i for i in indices]][:, [i for i in indices]]
        if submatrix.size:
            mean_scores = submatrix.mean(axis=1)
            representative_idx = indices[int(mean_scores.argmax())]
        else:
            representative_idx = indices[0]

        representative_text = documents[representative_idx].lower()
        candidate_keywords: List[str] = []
        for hint in hints:
            if hint in representative_text and hint not in candidate_keywords:
                candidate_keywords.append(hint)
        for bucket in BUCKET_FALLBACK_ORDER:
            if bucket in representative_text and bucket not in candidate_keywords:
                candidate_keywords.append(bucket)

        hint_seed = "_".join(candidate_keywords[:3])
        fallback_label = hint_seed or doc_ids[0]
        label = derive_project_label(doc_ids, fallback_label)
        confidence = 0.5
        if submatrix.size:
            confidence = float(submatrix.mean())
            confidence = max(0.5, min(0.95, confidence))

        bucket_counts = Counter(items[i].get("bucket", "tmp") for i in indices)
        reasons = ["tfidf_kmeans" if n_docs > 20 else "tfidf_dbscan", "path_prefix"]
        if hint_seed:
            reasons.append("hint_keywords")

        projects.append(
            {
                "project_id": label,
                "project_label": label,
                "doc_ids": doc_ids,
                "role_bucket_map": dict(bucket_counts),
                "confidence": confidence,
                "reasons": reasons,
            }
        )

    return {"projects": projects}


def gpt_cluster(
    items: Sequence[Dict[str, Any]], safe_map_path: str, model_env_var: str = "OPENAI_API_KEY"
) -> Dict[str, Any]:
    """KR: GPT 기반 프로젝트 군집화. EN: GPT-powered project clustering."""

    import urllib.request
    import urllib.parse

    api_key = os.environ.get(model_env_var)
    if not api_key:
        raise RuntimeError(f"Environment variable {model_env_var} not set")

    def build_gpt_payload(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        safe_map = json.load(open(safe_map_path, encoding="utf-8"))
        safe_items = []
        for it in items:
            if "path" not in it:
                continue
            safe_id = sha256_string(it["path"])
            safe_map[safe_id] = it["path"]
            safe_items.append(
                {
                    "safe_id": safe_id,
                    "name": it.get("name", ""),
                    "bucket": it.get("bucket", ""),
                    "hint": it.get("dir_hint", ""),
                }
            )
        json.dump(
            safe_map, open(safe_map_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2
        )
        return {"items": safe_items}

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Group files into projects. Return JSON with projects array containing project_id, project_label, doc_ids (safe_id list), role_bucket_map, confidence, reasons.",
            },
            {"role": "user", "content": json.dumps(build_gpt_payload(items), ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
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
        raw_seed = p.get("project_label") or p.get("project_id") or "misc"
        label = derive_project_label(paths, raw_seed)
        normalized_seed = normalize_label(raw_seed)
        reasons = list(p.get("reasons", []))
        if label != normalized_seed:
            reasons.append("path_prefix")
        reasons.append("mapped_via_safe_map")
        projects.append(
            {
                "project_id": label,
                "project_label": label,
                "doc_ids": paths,  # ← organize가 기대하는 "path" 리스트로 변환 완료
                "role_bucket_map": p.get("role_bucket_map", {}),
                "confidence": float(p.get("confidence", 0.7)),
                "reasons": reasons,
            }
        )
    return {"projects": projects}


# ---------------------------------------------------------------------------
# Organize helpers
# ---------------------------------------------------------------------------


def load_schema(schema_path: Optional[Path]) -> Dict[str, Any]:
    """KR: 스키마 로드. EN: Load schema configuration."""

    if schema_path and schema_path.exists() and yaml:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = {**SCHEMA_FALLBACK, **data}
            merged.setdefault("structure", SCHEMA_FALLBACK["structure"])
            return merged
    return dict(SCHEMA_FALLBACK)


def ensure_schema(base_dir: Path, schema: Dict[str, Any]) -> None:
    """KR: 프로젝트 표준 디렉토리 생성. EN: Ensure schema directories exist."""

    for relative in schema.get("structure", []):
        target = base_dir / relative
        target.mkdir(parents=True, exist_ok=True)


def resolve_bucket_directory(base_dir: Path, bucket: str) -> Path:
    """KR: 버킷에 맞는 디렉토리 선택. EN: Resolve destination directory for bucket."""

    if bucket in BUCKET_TO_SUBDIR:
        return base_dir / BUCKET_TO_SUBDIR[bucket]
    if bucket in BUCKET_FALLBACK_ORDER:
        return base_dir / BUCKET_TO_SUBDIR.get(bucket, Path("archive"))
    return base_dir / "archive"


def versioned_destination(dst_dir: Path, filename: str, hash7: str, conflict: str) -> Path:
    """KR: 중복 버전 이름 처리. EN: Build destination path with hash suffix."""

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    if stem.endswith(f"__{hash7}"):
        candidate = dst_dir / f"{stem}{suffix}"
    else:
        candidate = dst_dir / f"{stem}__{hash7}{suffix}"

    if conflict == "overwrite":
        return dst_dir / f"{stem}{suffix}"
    if conflict == "skip" and candidate.exists():
        return candidate
    counter = 1
    while candidate.exists() and conflict == "version":
        candidate = dst_dir / f"{stem}__{hash7}_{counter}{suffix}"
        counter += 1
    return candidate


def now_ms() -> int:
    """KR: 현재 타임스탬프(ms). EN: Current timestamp in milliseconds."""

    return int(time.time() * 1000)


def emit_console_table(title: str, rows: Sequence[Sequence[Any]]) -> None:  # pragma: no cover
    if not console:
        return
    table = Table(title=title)
    if rows:
        for idx in range(len(rows[0])):
            table.add_column(f"col{idx+1}")
        for row in rows:
            table.add_row(*[str(col) for col in row])
        console.print(table)


# ---------------------------------------------------------------------------
# Click CLI commands
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """KR: devmind CLI 루트. EN: Root command group."""


@cli.command()
@click.option("--paths", multiple=True, required=True, help="루트 경로 다중 지정")
@click.option("--sample-bytes", default=4096, show_default=True, type=int)
@click.option("--max-size", default=None, help="파일 최대 크기, 예: 500MB")
@click.option("--emit", default=str(DEFAULT_SCAN_EMIT), show_default=True)
@click.option("--safe-map", "safe_map_path", default=str(DEFAULT_SAFE_MAP), show_default=True)
@click.option("--cache-db", default=str(CACHE_DB_PATH), show_default=True)
def scan(
    paths: Sequence[str],
    sample_bytes: int,
    max_size: Optional[str],
    emit: str,
    safe_map_path: str,
    cache_db: str,
) -> None:
    """KR: 지정 경로를 스캔한다. EN: Scan given paths for metadata."""

    ensure_cache_dir()
    size_limit = parse_size_limit(max_size)
    items: List[Dict[str, Any]] = []
    safe_map: Dict[str, str] = {}

    with ScanCache(Path(cache_db)) as cache:
        for root in paths:
            root_path = Path(root)
            if not root_path.exists():
                items.append({"path": str(root_path), "error": "root_not_found"})
                continue
            for directory, _, files in os.walk(root):
                for filename in files:
                    source = Path(directory) / filename
                    try:
                        stat = source.stat()
                    except FileNotFoundError:
                        items.append({"path": str(source), "error": "stat_failed"})
                        continue
                    if size_limit and stat.st_size > size_limit:
                        items.append(
                            {
                                "path": str(source),
                                "name": filename,
                                "size": stat.st_size,
                                "error": "size_exceeded",
                            }
                        )
                        continue

                    safe_id = sha256_string(str(source))
                    cached = cache.load(safe_id, stat.st_mtime, stat.st_size)
                    if cached:
                        items.append(cached)
                        safe_map[safe_id] = str(source)
                        continue

                    try:
                        sample = read_sample(source, sample_bytes)
                        record = DocumentRecord(
                            path=str(source),
                            safe_id=safe_id,
                            name=filename,
                            ext=source.suffix.lower(),
                            size=stat.st_size,
                            mtime=float(stat.st_mtime),
                            blake3=compute_blake7(source),
                            mimetype=infer_mimetype(source),
                            dir_hint=dir_hint(source),
                            imports=extract_imports(sample),
                            top_comment=extract_python_docstring(source),
                            md_headings=extract_markdown_headings(sample),
                            json_root_keys=extract_json_keys(source),
                            csv_header=extract_csv_header(source),
                            sample=sample,
                        )
                        payload = record.to_json()
                        cache.save(record)
                        items.append(payload)
                        safe_map[safe_id] = str(source)
                    except Exception as err:  # pragma: no cover - defensive branch
                        items.append(
                            {
                                "path": str(source),
                                "name": filename,
                                "error": f"scan_failed:{err}",
                            }
                        )

    emit_path = Path(emit)
    emit_path.parent.mkdir(parents=True, exist_ok=True)
    emit_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    safe_map_output = Path(safe_map_path)
    safe_map_output.parent.mkdir(parents=True, exist_ok=True)
    safe_map_output.write_text(
        json.dumps(safe_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    click.echo(f"[scan] {len(items)} items -> {emit_path}")


@cli.command()
@click.option("--scan", "scan_path", default=str(DEFAULT_SCAN_EMIT), show_default=True)
@click.option("--emit", default=str(DEFAULT_SCORES_EMIT), show_default=True)
@click.option("--config", "config_path", default="rules.yml", show_default=True)
def rules(scan_path: str, emit: str, config_path: str) -> None:
    """KR: 규칙 기반 버킷 태깅. EN: Apply bucket rules to scanned data."""

    data = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    engine = RuleEngine.from_config(Path(config_path))
    results: List[Dict[str, Any]] = []

    for entry in data:
        if "error" in entry:
            entry["bucket"] = "archive"
            results.append(entry)
            continue
        record = record_from_entry(entry)
        bucket = engine.classify(record)
        entry["bucket"] = bucket
        results.append(entry)

    emit_path = Path(emit)
    emit_path.parent.mkdir(parents=True, exist_ok=True)
    emit_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(f"[rules] -> {emit_path}")


@cli.command()
@click.option("--scores", default=str(DEFAULT_SCORES_EMIT), show_default=True)
@click.option("--emit", default=str(DEFAULT_PROJECTS_EMIT), show_default=True)
@click.option(
    "--project-mode",
    type=click.Choice(["local", "gpt"], case_sensitive=False),
    default="local",
    show_default=True,
)
@click.option("--safe-map", "safe_map_path", default=str(DEFAULT_SAFE_MAP), show_default=True)
@click.option("--hints", default=",".join(DEFAULT_HINTS), show_default=True)
def cluster(scores: str, emit: str, project_mode: str, safe_map_path: str, hints: str) -> None:
    """KR: 프로젝트 군집화. EN: Cluster files into projects."""

    items = json.loads(Path(scores).read_text(encoding="utf-8"))
    hints_list = [token.strip() for token in hints.split(",") if token.strip()]
    if project_mode.lower() == "gpt":
        try:
            output = gpt_cluster(items, safe_map_path=safe_map_path, hints=hints_list)
        except Exception as exc:
            click.echo(f"[cluster] GPT mode failed ({exc}); fallback to local")
            output = local_cluster(items, hints_list)
    else:
        output = local_cluster(items, hints_list)

    emit_path = Path(emit)
    emit_path.parent.mkdir(parents=True, exist_ok=True)
    emit_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(
        f"[cluster/{project_mode}] {len(output.get('projects', []))} projects -> {emit_path}"
    )


@cli.command()
@click.option("--projects", default=str(DEFAULT_PROJECTS_EMIT), show_default=True)
@click.option("--scores", default=str(DEFAULT_SCORES_EMIT), show_default=True)
@click.option("--target", default="C:/PROJECTS_STRUCT", show_default=True)
@click.option("--mode", default="move", type=click.Choice(["move", "copy"]), show_default=True)
@click.option(
    "--conflict",
    default="version",
    type=click.Choice(["version", "skip", "overwrite"]),
    show_default=True,
)
@click.option("--journal", default=str(DEFAULT_JOURNAL), show_default=True)
@click.option("--schema", "schema_path", default="schema.yml", show_default=True)
def organize(
    projects: str,
    scores: str,
    target: str,
    mode: str,
    conflict: str,
    journal: str,
    schema_path: str,
) -> None:
    """KR: 프로젝트 구조에 맞춰 이동. EN: Organize files into project structure."""

    schema = load_schema(Path(schema_path))
    projects_data = json.loads(Path(projects).read_text(encoding="utf-8"))
    scores_data = json.loads(Path(scores).read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in scores_data if "path" in item}

    target_root = Path(target)
    target_root.mkdir(parents=True, exist_ok=True)

    journal_path = Path(journal)
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    total_moves = 0
    with journal_path.open("a", encoding="utf-8") as log:
        for project in projects_data.get("projects", []):
            label = project.get("project_label") or "misc"
            base_dir = target_root / label
            ensure_schema(base_dir, schema)
            for doc_path in project.get("doc_ids", []):
                source = Path(doc_path)
                if not source.exists():
                    log.write(
                        json.dumps(
                            {
                                "ts": now_ms(),
                                "code": "MISS",
                                "project": label,
                                "src": str(source),
                                "src_masked": sanitize_path(str(source)),
                            }
                        )
                        + "\n"
                    )
                    continue

                metadata = by_path.get(doc_path, {})
                bucket = metadata.get("bucket", "tmp")
                destination_dir = resolve_bucket_directory(base_dir, bucket)
                destination_dir.mkdir(parents=True, exist_ok=True)

                try:
                    hash7 = compute_blake7(source)
                    destination = versioned_destination(
                        destination_dir, source.name, hash7, conflict
                    )
                    if destination.exists() and conflict == "skip":
                        code = "SKIP"
                    else:
                        if mode == "copy":
                            shutil.copy2(source, destination)
                        else:
                            shutil.move(source, destination)
                        code = "OK"
                        total_moves += 1
                    log.write(
                        json.dumps(
                            {
                                "ts": now_ms(),
                                "code": code,
                                "project": label,
                                "bucket": bucket,
                                "src": str(source),
                                "dst": str(destination),
                                "src_masked": sanitize_path(str(source)),
                                "dst_masked": sanitize_path(str(destination)),
                                "hash": hash7,
                                "mode": mode,
                            }
                        )
                        + "\n"
                    )
                except Exception as exc:  # pragma: no cover - resilience branch
                    log.write(
                        json.dumps(
                            {
                                "ts": now_ms(),
                                "code": "ERR",
                                "project": label,
                                "bucket": bucket,
                                "src": str(source),
                                "error": str(exc),
                            }
                        )
                        + "\n"
                    )

    click.echo(f"[organize] moves={total_moves} -> {target_root} (journal: {journal_path})")


def summarise_journal(journal_path: Path) -> Dict[str, Any]:
    """KR: 저널을 요약한다. EN: Summarise journal entries for reporting."""

    summary: Dict[str, Any] = {
        "total": 0,
        "ok": 0,
        "errors": 0,
        "skipped": 0,
        "missing": 0,
        "projects": defaultdict(int),
        "buckets": defaultdict(int),
        "entries": [],
    }
    if not journal_path.exists():
        return summary
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        summary["entries"].append(entry)
        summary["total"] += 1
        code = entry.get("code")
        project = entry.get("project", "misc")
        bucket = entry.get("bucket", "tmp")
        summary["projects"][project] += 1
        summary["buckets"][bucket] += 1
        if code == "OK":
            summary["ok"] += 1
        elif code == "ERR":
            summary["errors"] += 1
        elif code == "SKIP":
            summary["skipped"] += 1
        elif code == "MISS":
            summary["missing"] += 1
    return summary


def build_report_cards(summary: Dict[str, Any]) -> str:
    """KR: HTML 카드 생성. EN: Build HTML cards for report."""

    cards = [
        (
            "총 이동 수 / Total Moves",
            f"{summary['ok']:,}",
        ),
        (
            "스킵 / Skipped",
            f"{summary['skipped']:,}",
        ),
        (
            "오류 / Errors",
            f"{summary['errors']:,}",
        ),
        (
            "누락 / Missing",
            f"{summary['missing']:,}",
        ),
    ]
    card_html = "".join(
        f"<div class='card'><h3>{html.escape(title)}</h3><p>{html.escape(value)}</p></div>"
        for title, value in cards
    )
    return card_html


def build_table(title: str, mapping: Dict[str, int]) -> str:
    """KR: HTML 표 생성. EN: Build HTML table snippet."""

    if not mapping:
        rows = "<tr><td>—</td><td>0</td></tr>"
    else:
        rows = "".join(
            f"<tr><td>{html.escape(key)}</td><td>{value}</td></tr>"
            for key, value in sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
        )
    return textwrap.dedent(
        f"""
        <section>
          <h2>{html.escape(title)}</h2>
          <table>
            <thead><tr><th>Label</th><th>Count</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        """
    )


@cli.command()
@click.option("--journal", default=str(DEFAULT_JOURNAL), show_default=True)
@click.option("--out", default="reports/projects_summary.html", show_default=True)
def report(journal: str, out: str) -> None:
    """KR: HTML/CSV/JSON 리포트를 생성한다. EN: Produce HTML/CSV/JSON reports."""

    summary = summarise_journal(Path(journal))
    reports_dir = Path(out).parent
    reports_dir.mkdir(parents=True, exist_ok=True)

    cards_html = build_report_cards(summary)
    project_table = build_table("프로젝트 분포 / Project Distribution", summary["projects"])
    bucket_table = build_table("버킷 분포 / Bucket Distribution", summary["buckets"])

    html_output = textwrap.dedent(
        f"""
        <!doctype html>
        <html lang="ko">
        <head>
          <meta charset="utf-8" />
          <title>Projects Summary</title>
          <style>
            body {{
              background:#0B1220;
              color:#E5E7EB;
              font-family:'Inter', system-ui;
              margin:0;
              padding:24px;
            }}
            h1 {{ text-align:center; color:#60A5FA; }}
            h2 {{
              color:#22D3EE;
              border-bottom:1px solid #1F2937;
              padding-bottom:8px;
            }}
            .cards {{
              display:grid;
              grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
              gap:16px;
              margin:24px auto;
              max-width:1000px;
            }}
            .card {{
              background:#111827;
              border:1px solid #1F2937;
              border-radius:12px;
              padding:16px;
              text-align:center;
            }}
            table {{
              width:100%;
              border-collapse:collapse;
              margin:24px 0;
              background:#111827;
              border-radius:12px;
              overflow:hidden;
            }}
            th, td {{
              padding:12px 16px;
              border-bottom:1px solid #1F2937;
              text-align:left;
            }}
            section {{ max-width:1000px; margin:0 auto 32px auto; }}
            footer {{
              text-align:center;
              color:#6B7280;
              margin-top:32px;
              font-family:'JetBrains Mono', monospace;
            }}
          </style>
        </head>
        <body>
          <h1>프로젝트 자동 정리 리포트 / Project Auto-Organize Report</h1>
          <div class="cards">{cards_html}</div>
          {project_table}
          {bucket_table}
          <footer>Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}</footer>
        </body>
        </html>
        """
    )

    html_path = Path(out)
    html_path.write_text(html_output, encoding="utf-8")

    json_summary = {
        "total": summary["total"],
        "ok": summary["ok"],
        "skipped": summary["skipped"],
        "errors": summary["errors"],
        "missing": summary["missing"],
        "projects": dict(summary["projects"]),
        "buckets": dict(summary["buckets"]),
    }
    (reports_dir / "projects_summary.json").write_text(
        json.dumps(json_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = reports_dir / "projects_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["project", "count"])
        for key, value in sorted(summary["projects"].items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([key, value])

    click.echo(
        f"[report] html={html_path} json={reports_dir / 'projects_summary.json'} csv={csv_path}"
    )


@cli.command()
@click.option("--journal", required=True)
def rollback(journal: str) -> None:
    """KR: 이동을 원위치. EN: Roll files back to original location."""

    journal_path = Path(journal)
    if not journal_path.exists():
        click.echo("[rollback] journal not found")
        sys.exit(1)

    entries = [
        json.loads(line)
        for line in journal_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    restored = 0
    for entry in reversed(entries):
        if entry.get("code") != "OK":
            continue
        src = Path(entry.get("src", ""))
        dst = Path(entry.get("dst", ""))
        if dst.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(dst, src)
            restored += 1
    click.echo(f"[rollback] restored={restored}")


@cli.command(name="logistics-validate")
@click.option(
    "--payload",
    type=click.Path(path_type=Path),
    required=True,
    help="물류 데이터 JSON 경로 (KR/EN)",
)
def logistics_validate(payload: Path) -> None:
    """KR: 물류 데이터 정합성 검증. EN: Validate logistics payload."""

    raw = payload.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    records_data = parsed if isinstance(parsed, list) else [parsed]
    summaries = [LogisticsMetadata(**record).summary() for record in records_data]
    click.echo(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
