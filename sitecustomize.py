"""KR: 테스트 환경용 커스텀 설정. EN: Custom runtime setup for tests."""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType, SimpleNamespace


def _install_psutil_fallback() -> None:
    """psutil이 없을 때 최소 기능을 제공한다(KR). Provide psutil shim when missing (EN)."""

    try:
        importlib.import_module("psutil")
        return
    except ModuleNotFoundError:
        pass

    _resource_module: ModuleType | None
    try:
        import resource as _resource_module
    except ModuleNotFoundError:  # pragma: no cover - Windows fallback
        _resource_module = None

    def _rss_bytes(pid: int) -> int:
        if _resource_module is not None:
            try:
                usage = _resource_module.getrusage(_resource_module.RUSAGE_SELF)
                rss_kb = getattr(usage, "ru_maxrss", 0)
                if rss_kb == 0:
                    return 0
                # Linux returns KB, macOS returns bytes
                return int(rss_kb * 1024 if rss_kb < 10_000_000 else rss_kb)
            except Exception:  # pragma: no cover - defensive branch
                pass
        try:
            import tracemalloc

            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, _ = tracemalloc.get_traced_memory()
            return int(current)
        except Exception:  # pragma: no cover - defensive branch
            return 0

    class _Process:
        def __init__(self, pid: int | None = None) -> None:
            self.pid = os.getpid() if pid is None else pid

        def memory_info(self) -> SimpleNamespace:
            return SimpleNamespace(rss=_rss_bytes(self.pid))

    class _PsutilModule(ModuleType):
        Process = _Process
        __all__ = ["Process"]

    shim = _PsutilModule("psutil")
    shim.__doc__ = "Fallback psutil shim provided by sitecustomize"
    sys.modules.setdefault("psutil", shim)


_install_psutil_fallback()
