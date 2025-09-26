"""규칙 분류와 클러스터링 단계를 제공합니다./Provide rule tagging and clustering."""

from __future__ import annotations

import importlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import yaml
from yaml import YAMLError

from scan import FileRecord
from utils import write_json

try:  # pragma: no cover - optional dependency
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_OK = True
except ModuleNotFoundError:  # pragma: no cover
    SKLEARN_OK = False

DEFAULT_RULES: tuple[tuple[str, str], ...] = (
    ("src", r"\.py$"),
    ("scripts", r"\.ps1$|\.bat$|run_|setup|install"),
    ("tests", r"(^|\\\\)tests?(\\\\|/)|\bpytest\b|\bunittest\b"),
    ("docs", r"\.md$|readme|guide|installation|plan|spec|tdd"),
    ("reports", r"report|summary|analysis|final|complete"),
    ("configs", r"\.ya?ml$|\.toml$|\.ini$|pyproject|requirements|\.env$|\.json$|\.cfg$"),
    ("data", r"\.csv$|\.xlsx$|\.xls$|\.parquet$|(\\\\|/)data(\\\\|/)"),
    ("notebooks", r"\.ipynb$"),
    ("archive", r"old|backup|_bak|_copy|v\d+"),
)

DEFAULT_HINTS: tuple[str, ...] = (
    "hvdc",
    "warehouse",
    "ontology",
    "mcp",
    "cursor",
    "layoutapp",
    "ldg",
    "logi",
    "stow",
)


def _sanitize_rules_yaml(raw_text: str) -> str:
    """패턴 문자열의 이스케이프를 보정합니다./Normalize pattern escapes."""

    def _replacer(match: re.Match[str]) -> str:
        prefix = match.group(1)
        body = match.group(2)
        sanitized = body.replace("'", "''")
        return f"{prefix}'{sanitized}'"

    return re.sub(r"(\bpattern\s*:\s*)\"([^\"]*)\"", _replacer, raw_text)


def load_rules_config(path: Path | None) -> list[tuple[str, str]]:
    """규칙 설정을 로드합니다./Load rule configuration."""

    if path and path.exists():
        raw_text = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(raw_text)
        except YAMLError:
            data = yaml.safe_load(_sanitize_rules_yaml(raw_text))
        rules = data.get("rules", []) if isinstance(data, dict) else []
        loaded: list[tuple[str, str]] = []
        for item in rules:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            pattern = str(item.get("pattern", "")).strip()
            if name and pattern:
                loaded.append((name, pattern))
        if loaded:
            return loaded
    return list(DEFAULT_RULES)


def apply_rules(
    records: Sequence[FileRecord], rules: Sequence[tuple[str, str]]
) -> list[FileRecord]:
    """규칙 기반 버킷을 할당합니다./Assign rule buckets to records."""

    compiled = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in rules]
    tagged: list[FileRecord] = []
    for record in records:
        if record.error:
            record.bucket = "archive"
            tagged.append(record)
            continue
        text = f"{record.name} {record.path} {record.hint}".lower()[:8000]
        name_hint = f"{record.name} {record.hint}".lower()
        path_lower = record.path.lower()
        record.bucket = "tmp"
        for name, matcher in compiled:
            if matcher.search(text):
                if (
                    name == "tests"
                    and "pytest-of-" in path_lower
                    and "pytest" not in name_hint
                    and "unittest" not in name_hint
                ):
                    continue
                record.bucket = name
                break
        tagged.append(record)
    return tagged


def _normalize_label(label: str) -> str:
    """라벨을 스네이크케이스로 정규화합니다./Normalize label to snake_case."""

    token = label.lower().strip()
    token = re.sub(r"[^a-z0-9]+", "_", token)
    return token.strip("_") or "misc"


def _collect_tokens(record: FileRecord, hints: Sequence[str]) -> str:
    """클러스터링용 토큰을 수집합니다./Collect text tokens for clustering."""

    text = " ".join([record.name, record.path, record.hint, record.bucket or ""]).strip()
    lowered = text.lower()
    for hint in hints:
        if hint in lowered:
            text += (" " + hint) * 5
    if record.bucket in {
        "docs",
        "configs",
        "scripts",
        "src",
        "tests",
        "reports",
        "data",
        "notebooks",
    }:
        text += (" " + record.bucket) * 3
    return text


def cluster_local(
    records: Sequence[FileRecord], hints: Sequence[str] | None = None
) -> dict[str, object]:
    """로컬 클러스터링을 수행합니다./Perform local clustering."""

    hints = hints or list(DEFAULT_HINTS)
    docs: list[str] = []
    paths: list[str] = []
    for record in records:
        if record.error:
            continue
        docs.append(_collect_tokens(record, hints))
        paths.append(record.path)
    if not docs:
        return {"projects": []}
    if not SKLEARN_OK:
        groups: dict[str, list[str]] = defaultdict(list)
        for path in paths:
            label = _normalize_label(
                Path(path).parts[1] if len(Path(path).parts) > 1 else Path(path).stem
            )
            groups[label].append(path)
        fallback_projects = [
            {
                "project_id": name,
                "project_label": name,
                "doc_ids": paths,
                "role_bucket_map": {},
                "confidence": 0.60,
                "reasons": ["fallback_no_sklearn"],
            }
            for name, paths in groups.items()
        ]
        return {"projects": fallback_projects}
    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(docs)
    count = len(docs)
    target_k = max(2, min(12, int(math.sqrt(count))))
    labels = None
    if count <= 20:
        model = DBSCAN(eps=0.8, min_samples=2, metric="cosine")
        labels = model.fit_predict(matrix)
        if (labels == -1).all():
            km = KMeans(n_clusters=min(target_k, count), n_init="auto", random_state=42)
            labels = km.fit_predict(matrix)
    else:
        km = KMeans(n_clusters=min(target_k, count), n_init="auto", random_state=42)
        labels = km.fit_predict(matrix)
    label_list = [int(value) for value in labels.tolist()]
    groups_int: dict[int, list[str]] = defaultdict(list)
    for path, raw_label in zip(paths, label_list):
        groups_int[int(raw_label)].append(path)
    similarity = cosine_similarity(matrix)
    projects_local: list[dict[str, object]] = []
    for cluster_id, doc_ids in groups_int.items():
        if cluster_id == -1:
            projects_local.append(
                {
                    "project_id": "misc_noise",
                    "project_label": "misc_noise",
                    "doc_ids": doc_ids,
                    "role_bucket_map": {},
                    "confidence": 0.45,
                    "reasons": ["dbscan_noise"],
                }
            )
            continue
        idx = label_list.index(cluster_id)
        similar_indices = similarity[idx].argsort()[::-1][:3]
        keywords = set()
        for i in similar_indices:
            tokens = docs[i].split()
            for token in tokens:
                if len(token) > 4 and token.isalpha():
                    keywords.add(token)
        label_token = _normalize_label(" ".join(sorted(keywords))[:40] or Path(doc_ids[0]).stem)
        projects_local.append(
            {
                "project_id": label_token,
                "project_label": label_token,
                "doc_ids": doc_ids,
                "role_bucket_map": {},
                "confidence": 0.72,
                "reasons": ["tfidf_cluster"],
            }
        )
    return {"projects": projects_local}


def _build_safe_payload(
    records: Sequence[FileRecord], max_snippet: int = 500
) -> list[dict[str, object]]:
    """GPT 호출용 페이로드를 만듭니다./Create payload for GPT call."""

    payload: list[dict[str, object]] = []
    for record in records:
        if record.error:
            continue
        payload.append(
            {
                "id": record.safe_id,
                "name": record.name,
                "ext": record.ext,
                "size": record.size,
                "mime": "text/plain",
                "snippet": (record.hint or "")[:max_snippet],
                "rule_tags": [record.bucket or "tmp"],
                "path_hint": _normalize_label("/".join(Path(record.path).parts[-3:])),
            }
        )
    return payload


GPT_SYSTEM_PROMPT = (
    "You are a project clustering assistant for developer workspaces.\n"
    "Group files into ≤12 coherent project clusters with snake_case labels.\n"
    'Output JSON: {"projects":[{project_id, project_label, doc_ids[], '
    "role_bucket_map, confidence, reasons[]}]}."
)


def cluster_hybrid(
    records: Sequence[FileRecord], safe_map: dict[str, str], api_key: str
) -> dict[str, object]:
    """GPT 보조 클러스터링을 수행합니다./Run GPT-assisted clustering."""

    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for hybrid mode")
    payload = _build_safe_payload(records)
    if not payload:
        return {"projects": []}
    requests = importlib.import_module("requests")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": GPT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"records": payload}, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    projects = []
    for project in parsed.get("projects", []):
        doc_ids = project.get("doc_ids", [])
        resolved = [safe_map.get(doc_id, doc_id) for doc_id in doc_ids]
        project["doc_ids"] = resolved
        projects.append(project)
    return {"projects": projects}


def emit_scores(records: Iterable[FileRecord], out_path: Path) -> None:
    """규칙 결과를 저장합니다./Persist rule scoring output."""

    write_json(out_path, [record.to_payload() for record in records])


def emit_projects(projects: dict[str, object], out_path: Path) -> None:
    """클러스터링 결과를 저장합니다./Persist project clusters."""

    write_json(out_path, projects)


__all__ = [
    "apply_rules",
    "cluster_local",
    "cluster_hybrid",
    "emit_projects",
    "emit_scores",
    "load_rules_config",
]
