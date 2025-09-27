"""핵심 헬퍼 모듈 테스트(KR). Core helper module tests (EN)."""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from core.decimal_format import format_2d
from core.errors import PipelineError
from core.logging import configure_logging
from core.timezone import dubai_now


def test_format_2d_should_round_and_pad() -> None:
    """소수를 두 자리로 반올림/패딩한다 · Rounds and pads decimals to 2 places."""

    assert format_2d(Decimal("12.345")) == "12.35"
    assert format_2d(5) == "5.00"
    assert format_2d("7.4") == "7.40"


def test_dubai_now_should_return_tz_aware_iso() -> None:
    """두바이 타임존 ISO8601 문자열을 돌려준다 · Returns Dubai timezone ISO string."""

    timestamp = dubai_now()
    assert timestamp.endswith("+04:00")
    # ISO8601 basic check
    assert "T" in timestamp


def test_configure_logging_should_install_json_handler(tmp_path: Path) -> None:
    """로깅 설정이 JSON 핸들러를 추가한다 · Logging config installs JSON handler."""

    log_path = tmp_path / "app.log"
    configure_logging(log_path, level="INFO")
    logger = logging.getLogger("core")
    logger.info("hello")
    contents = log_path.read_text(encoding="utf-8")
    assert "hello" in contents
    assert "timestamp" in contents


def test_pipeline_error_str() -> None:
    """파이프라인 오류는 메시지를 노출한다 · Pipeline error exposes message."""

    error = PipelineError("failed", stage="scan")
    assert "scan" in str(error)
