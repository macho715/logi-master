# 물류 검증 가이드 (Logistics Validation Guide)

## 개요

`devmind.py logistics-validate` 명령은 Incoterm/HS Code/AED 통화 규칙을 기반으로 물류 데이터를 검증하고 요약합니다.

## 사용법

```bash
python devmind.py logistics-validate --payload shipment.json
```

- `incoterm`: `/resources/incoterm.yaml`에 정의된 2020 Incoterm 코드만 허용됩니다.
- `hs_code`: `resources/hs2022.csv`에 수록된 HS Code만 허용되며 자동으로 숫자만 남겨 6자리로 정규화합니다.
- `currency`: 기본값은 AED이며 Enum(`AED`, `USD`, `EUR`, `SAR`) 중 하나만 허용됩니다.
- `declared_value`: 항상 소수점 두 자리로 반올림되어 보고됩니다.

## 출력

명령은 각 레코드별 요약(JSON 배열)을 반환하며, 리포트/저널 등 다른 파이프라인 단계에서 재사용할 수 있습니다.
