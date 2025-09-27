"""파이프라인 예외 정의(KR). Pipeline exception definitions (EN)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PipelineError(Exception):
    """파이프라인 단계 오류를 표현 · Represent pipeline stage failure."""

    message: str
    stage: str | None = None

    def __str__(self) -> str:
        """사람 친화적 메시지를 생성 · Build human friendly message."""

        if self.stage:
            return f"[{self.stage}] {self.message}"
        return self.message


__all__ = ["PipelineError"]
