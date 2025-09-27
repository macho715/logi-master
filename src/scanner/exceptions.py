"""스캐너 전용 예외를 정의합니다./Define scanner specific exceptions."""

from __future__ import annotations


class ScanErrorBase(RuntimeError):
    """스캔 중 발생한 오류 기본 클래스./Base class for scan errors."""


class ScanCancelledError(ScanErrorBase):
    """취소 토큰으로 스캔이 중단됨./Scan stopped by cancellation token."""


class ScanTimeoutError(ScanErrorBase):
    """시간 제한을 초과함./Raised when a time limit is exceeded."""
