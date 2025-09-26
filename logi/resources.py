"""KR: 물류 리소스 로더. EN: Logistics resource loader."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, Sequence

try:  # pragma: no cover - optional dependency branch
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"


def _ensure_resource(path: Path) -> Path:
    """리소스 경로를 확인한다(KR). Ensure resource path exists (EN)."""

    if not path.exists():
        raise FileNotFoundError(f"resource missing: {path}")
    return path


@lru_cache(maxsize=1)
def load_incoterm_map() -> Dict[str, Dict[str, str]]:
    """Incoterm 코드→메타데이터 매핑을 반환(KR). Return incoterm metadata map (EN)."""

    path = _ensure_resource(RESOURCE_DIR / "incoterm.yaml")
    if not yaml:
        raise RuntimeError("pyyaml is required to parse incoterm.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    records = raw.get("incoterms", []) if isinstance(raw, dict) else []
    data: Dict[str, Dict[str, str]] = {}
    for entry in records:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code", "")).upper().strip()
        if not code:
            continue
        data[code] = {
            "name_en": str(entry.get("name_en", "")).strip(),
            "name_ko": str(entry.get("name_ko", "")).strip(),
        }
    return data


@lru_cache(maxsize=1)
def load_hs_map() -> Dict[str, Dict[str, str]]:
    """HS Code→설명 매핑을 반환(KR). Return HS code description map (EN)."""

    path = _ensure_resource(RESOURCE_DIR / "hs2022.csv")
    data: Dict[str, Dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            code = normalize_hs_code(row.get("hs_code", ""))
            if not code:
                continue
            data[code] = {
                "description_en": str(row.get("description_en", "")).strip(),
                "description_ko": str(row.get("description_ko", "")).strip(),
            }
    return data


def normalize_hs_code(value: str) -> str:
    """HS Code 문자열을 정규화한다(KR). Normalize HS code string (EN)."""

    digits = "".join(ch for ch in value if ch.isdigit())
    return digits.zfill(6) if digits else ""


def hs_description_map() -> Dict[str, str]:
    """HS Code→영문 설명 매핑을 제공(KR). Provide HS code to English description (EN)."""

    return {code: meta.get("description_en", "") for code, meta in load_hs_map().items()}


__all__: Sequence[str] = (
    "load_incoterm_map",
    "load_hs_map",
    "normalize_hs_code",
    "hs_description_map",
)
