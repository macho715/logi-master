"""로깅 설정 유틸리티(KR). Logging configuration utilities (EN)."""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

from .timezone import dubai_now


class JsonFormatter(logging.Formatter):
    """JSON 포맷터 구현 · Implement JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """레코드를 JSON 문자열로 직렬화 · Serialize record into JSON string."""

        payload: Dict[str, Any] = {
            "timestamp": dubai_now(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_file: Path, level: str = "INFO") -> None:
    """JSON 파일 로거를 설정한다 · Configure JSON file logger."""

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "core.logging.JsonFormatter",
                }
            },
            "handlers": {
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "json",
                    "filename": str(log_file),
                    "encoding": "utf-8",
                }
            },
            "loggers": {
                "core": {
                    "level": level.upper(),
                    "handlers": ["file"],
                    "propagate": False,
                }
            },
        }
    )


__all__ = ["configure_logging", "JsonFormatter"]
