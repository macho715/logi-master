"""KR: 프로젝트 엔티티 기반 모델. EN: Base model for project entities."""

from __future__ import annotations

from typing import Any, Dict, Sequence

try:  # pragma: no cover - prefer real pydantic when available
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import Field as _PydanticField
    from pydantic.config import ConfigDict
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback
    _PydanticBaseModel = None
    _PydanticField = None


if _PydanticBaseModel is not None and _PydanticField is not None:

    class LogiBaseModel(_PydanticBaseModel):
        """Pydantic v2 기반 공통 모델."""

        model_config = ConfigDict(extra="ignore", validate_assignment=True)

    Field = _PydanticField
else:

    class _FieldInfo:
        __slots__ = ("default", "default_factory")

        def __init__(self, *, default: Any = None, default_factory: Any | None = None) -> None:
            self.default = default
            self.default_factory = default_factory

    def Field(*, default: Any = None, default_factory: Any | None = None) -> _FieldInfo:
        """Fallback Field 구현(KR). Provide Field-like helper (EN)."""

        return _FieldInfo(default=default, default_factory=default_factory)

    class LogiBaseModel:  # type: ignore[override]
        """간소화된 BaseModel 대체(KR). Simplified BaseModel replacement (EN)."""

        model_config: Dict[str, Any] = {"extra": "ignore", "validate_assignment": True}

        def __init__(self, **data: Any) -> None:
            annotations = getattr(self, "__annotations__", {})
            for name in annotations:
                if name in data:
                    setattr(self, name, data[name])
                    continue
                descriptor = getattr(type(self), name, None)
                if isinstance(descriptor, _FieldInfo):
                    if descriptor.default_factory is not None:
                        setattr(self, name, descriptor.default_factory())
                    else:
                        setattr(self, name, descriptor.default)
                else:
                    setattr(self, name, descriptor)
            for key, value in data.items():
                if key not in annotations:
                    setattr(self, key, value)

        @classmethod
        def model_validate(cls, data: Dict[str, Any]) -> "LogiBaseModel":
            return cls(**data)

        def model_dump(self) -> Dict[str, Any]:
            annotations = getattr(self, "__annotations__", {})
            payload: Dict[str, Any] = {}
            for name in annotations:
                payload[name] = getattr(self, name, None)
            for name, value in self.__dict__.items():
                if name not in payload:
                    payload[name] = value
            return payload


__all__: Sequence[str] = ("LogiBaseModel", "Field")
