"""규칙 기반 분류 및 클러스터링을 제공합니다./Provide rule-based classification and clustering."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from scan import FileRecord
from utils import write_json


@dataclass(slots=True)
class RuleDef:
    """규칙 정의를 표현합니다./Represent a rule definition."""

    name: str
    pattern: str
    bucket: str
    weight: float = 1.0
    flags: int = 0

    def matches(self, record: FileRecord) -> bool:
        """레코드가 규칙에 매치되는지 확인합니다./Check if record matches rule."""

        text = f"{record.name} {record.ext} {record.hint}".lower()
        try:
            return bool(re.search(self.pattern, text, self.flags))
        except re.error:
            return False


@dataclass(slots=True)
class Project:
    """프로젝트 그룹을 표현합니다./Represent a project group."""

    name: str
    files: list[str]
    confidence: float
    description: str = ""


def load_rules_config(config_path: Path | None) -> list[RuleDef]:
    """규칙 설정을 로드합니다./Load rules configuration."""

    if config_path is None or not config_path.exists():
        return []

    import yaml

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules = []
    for rule_data in data.get("rules", []):
        rules.append(
            RuleDef(
                name=rule_data["name"],
                pattern=rule_data["pattern"],
                bucket=rule_data["bucket"],
                weight=rule_data.get("weight", 1.0),
                flags=rule_data.get("flags", 0),
            )
        )

    return rules


def apply_rules(records: list[FileRecord], rules: list[RuleDef]) -> list[FileRecord]:
    """규칙을 적용하여 버킷을 할당합니다./Apply rules to assign buckets."""

    for record in records:
        if record.error:
            continue
        best_bucket = None
        best_weight = 0.0
        for rule in rules:
            if rule.matches(record):
                if rule.weight > best_weight:
                    best_weight = rule.weight
                    best_bucket = rule.bucket
        if best_bucket:
            record.bucket = best_bucket
    return records


def cluster_local(records: list[FileRecord]) -> list[Project]:
    """로컬 클러스터링을 수행합니다./Perform local clustering."""

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    import numpy as np

    # 텍스트 데이터 준비
    texts = []
    for record in records:
        if record.error:
            continue
        text = f"{record.name} {record.ext} {record.hint}".lower()
        texts.append(text)

    if not texts:
        return []

    # TF-IDF 벡터화
    vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts)

    # K-means 클러스터링
    n_clusters = min(5, len(texts))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(tfidf_matrix)

    # 프로젝트 생성
    projects = []
    for i in range(n_clusters):
        cluster_files = [
            records[j].path
            for j in range(len(records))
            if j < len(cluster_labels) and cluster_labels[j] == i and not records[j].error
        ]
        if cluster_files:
            projects.append(
                Project(
                    name=f"project_{i+1}",
                    files=cluster_files,
                    confidence=0.8,
                    description=f"Cluster {i+1} with {len(cluster_files)} files",
                )
            )

    return projects


def cluster_hybrid(
    records: list[FileRecord], safe_map: dict[str, str], api_key: str
) -> list[Project]:
    """하이브리드 클러스터링을 수행합니다./Perform hybrid clustering."""

    if not api_key:
        return cluster_local(records)

    # 간단한 구현 - 실제로는 OpenAI API를 호출
    projects = []
    bucket_groups = {}

    for record in records:
        if record.error or not record.bucket:
            continue
        if record.bucket not in bucket_groups:
            bucket_groups[record.bucket] = []
        bucket_groups[record.bucket].append(record.path)

    for bucket, files in bucket_groups.items():
        if files:
            projects.append(
                Project(
                    name=bucket,
                    files=files,
                    confidence=0.9,
                    description=f"Rule-based bucket: {bucket}",
                )
            )

    return projects


def emit_scores(records: list[FileRecord], out_path: Path) -> None:
    """점수 결과를 저장합니다./Persist scoring results."""

    payload = [record.to_payload() for record in records]
    write_json(out_path, payload)


def emit_projects(projects: list[Project], out_path: Path) -> None:
    """프로젝트 결과를 저장합니다./Persist project results."""

    payload = []
    for project in projects:
        payload.append(
            {
                "name": project.name,
                "files": project.files,
                "confidence": project.confidence,
                "description": project.description,
            }
        )
    write_json(out_path, payload)


__all__ = [
    "RuleDef",
    "Project",
    "apply_rules",
    "cluster_local",
    "cluster_hybrid",
    "emit_scores",
    "emit_projects",
    "load_rules_config",
]
