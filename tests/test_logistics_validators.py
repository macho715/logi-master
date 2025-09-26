"""KR: 물류 검증 테스트. EN: Logistics validation tests."""

from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from logi.logistics import (
    Currency,
    LogisticsMetadata,
    hs_description,
    validate_hs_code,
    validate_incoterm,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, str]:
    """샘플 물류 데이터를 불러온다(KR). Load sample logistics payload (EN)."""

    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return cast(dict[str, str], payload)


def test_validate_incoterm_success() -> None:
    """Incoterm 코드가 대문자로 정규화되는지 확인."""

    assert validate_incoterm("fob") == "FOB"


def test_validate_incoterm_failure() -> None:
    """알 수 없는 Incoterm은 예외를 발생시켜야 한다."""

    with pytest.raises(ValueError):
        validate_incoterm("zzz")


def test_validate_hs_code_success() -> None:
    """HS Code가 표준 데이터셋에서 조회되는지 검증."""

    normalized = validate_hs_code("8517.70")
    assert normalized == "851770"
    assert "telephone" in hs_description(normalized).lower()


def test_validate_hs_code_failure() -> None:
    """존재하지 않는 HS Code는 오류를 발생시켜야 한다."""

    with pytest.raises(ValueError):
        validate_hs_code("0000.00")


def test_logistics_metadata_rounds_value() -> None:
    """선언 금액이 두 자리 소수로 반올림되는지 확인."""

    record = LogisticsMetadata(
        incoterm="cif",
        hs_code="851770",
        declared_value=Decimal("1250.504"),
    )
    assert record.currency is Currency.AED
    assert record.declared_value == Decimal("1250.50")
    assert record.formatted_declared_value() == "AED 1250.50"


def test_logistics_cli_validation(tmp_workspace: Path) -> None:
    """CLI에서 물류 검증 커맨드가 성공적으로 실행되는지 확인."""

    payload = load_fixture("shipment_valid.json")
    workspace_payload = tmp_workspace / "shipment.json"
    workspace_payload.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "logistics-validate",
            "--payload",
            "shipment.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary[0]["incoterm"] == "CIF"
    assert summary[0]["hs_code"] == "851770"
    assert summary[0]["currency"] == "AED"
    assert summary[0]["declared_value"] == "1250.50"
