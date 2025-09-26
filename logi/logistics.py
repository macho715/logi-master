"""KR: 물류 검증 로직. EN: Logistics validation logic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Dict, Sequence

from logi import Field, LogiBaseModel

from .resources import hs_description_map, load_hs_map, load_incoterm_map, normalize_hs_code


class Currency(str, Enum):
    """KR: 통화 코드 Enum. EN: Currency code enumeration."""

    AED = "AED"
    USD = "USD"
    EUR = "EUR"
    SAR = "SAR"

    @classmethod
    def from_value(cls, value: str | "Currency") -> "Currency":
        """문자열에서 통화 Enum을 생성(KR). Build enum from string value (EN)."""

        if isinstance(value, Currency):
            return value
        try:
            text = value.strip().upper()
            return cls[text]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"unsupported currency: {value}") from exc


def validate_incoterm(value: str) -> str:
    """Incoterm 코드 유효성 검증(KR). Validate incoterm code (EN)."""

    code = value.strip().upper()
    if not code:
        raise ValueError("incoterm is required")
    incoterms = load_incoterm_map()
    if code not in incoterms:
        raise ValueError(f"unknown incoterm: {value}")
    return code


def validate_hs_code(value: str) -> str:
    """HS Code 유효성 검증(KR). Validate HS code (EN)."""

    code = normalize_hs_code(value)
    if not code:
        raise ValueError("hs_code is required")
    codes = load_hs_map()
    if code not in codes:
        raise ValueError(f"unknown hs_code: {value}")
    return code


def hs_description(code: str) -> str:
    """HS Code 영문 설명을 반환(KR). Return HS code English description (EN)."""

    normalized = validate_hs_code(code)
    descriptions = hs_description_map()
    return descriptions.get(normalized, "")


class LogisticsMetadata(LogiBaseModel):
    """KR: 물류 메타데이터 모델. EN: Logistics metadata model."""

    incoterm: str
    hs_code: str
    currency: Currency = Currency.AED
    declared_value: Decimal = Field(default_factory=lambda: Decimal("0.00"))

    def __init__(self, **data: Any) -> None:
        incoterm_value = data.get("incoterm", "")
        hs_value = data.get("hs_code", "")
        currency_value = data.get("currency", Currency.AED)
        declared = data.get("declared_value", Decimal("0"))

        data["incoterm"] = validate_incoterm(str(incoterm_value))
        data["hs_code"] = validate_hs_code(str(hs_value))
        data["currency"] = Currency.from_value(currency_value)

        if not isinstance(declared, Decimal):
            declared = Decimal(str(declared or "0"))
        data["declared_value"] = declared.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().__init__(**data)

    def formatted_declared_value(self) -> str:
        """KR: 통화 금액을 포맷팅. EN: Format declared value with currency."""

        return f"{self.currency.value} {self.declared_value:.2f}"

    def summary(self) -> Dict[str, str]:
        """KR: 보고용 요약 사전을 반환. EN: Return summary dictionary for reporting."""

        return {
            "incoterm": self.incoterm,
            "hs_code": self.hs_code,
            "currency": self.currency.value,
            "declared_value": f"{self.declared_value:.2f}",
        }


__all__: Sequence[str] = (
    "Currency",
    "LogisticsMetadata",
    "validate_incoterm",
    "validate_hs_code",
    "hs_description",
)
