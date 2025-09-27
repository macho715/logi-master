"""파이프라인 설정 모델(KR). Pipeline configuration models (EN)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import yaml

from logi import Field, LogiBaseModel


class PipelinePaths(LogiBaseModel):
    """핵심 경로 구성을 보관 · Store core filesystem paths."""

    base_dir: Path = Field(default_factory=Path.cwd)
    cache_dir: Path = Field(default_factory=lambda: Path(".cache"))
    reports_dir: Path = Field(default_factory=lambda: Path("reports"))
    target_dir: Path = Field(default_factory=lambda: Path("PROJECTS_STRUCT"))

    def ensure(self) -> None:
        """필수 디렉터리를 생성 · Ensure required directories exist."""

        for path in (self.cache_dir, self.reports_dir, self.target_dir):
            Path(path).mkdir(parents=True, exist_ok=True)


class PipelineConfig(LogiBaseModel):
    """파이프라인 설정 전체를 표현 · Represent complete pipeline settings."""

    paths: PipelinePaths = Field(default_factory=PipelinePaths)
    default_roots: Tuple[str, ...] = Field(
        default_factory=lambda: (
            r"C:/MACHO GPT/MACHO-GPT/test_data",
            r"C:/MACHO GPT/MACHO-GPT",
        )
    )
    safe_map: Path = Field(default_factory=lambda: Path(".cache/safe_map.json"))
    schema_path: Path = Field(default_factory=lambda: Path("schema.yml"))

    @classmethod
    def from_file(cls, config_file: Path) -> "PipelineConfig":
        """설정 파일에서 로드 · Load settings from config file."""

        data = (
            yaml.safe_load(config_file.read_text(encoding="utf-8"))
            if config_file.exists()
            else {}
        )
        if not isinstance(data, dict):
            raise ValueError("configuration file must contain a mapping")
        return cls.model_validate(data)

    def to_dict(self) -> Dict[str, Any]:
        """사전을 반환 · Return dictionary representation."""

        return dict(self.model_dump())

    def resolve_sources(self, paths: Iterable[str | Path]) -> Tuple[Path, ...]:
        """소스 경로를 정규화 · Normalise source directories."""

        resolved = tuple(Path(p).expanduser().resolve() for p in paths)
        for directory in resolved:
            directory.mkdir(parents=True, exist_ok=True)
        return resolved


__all__ = ["PipelineConfig", "PipelinePaths"]
