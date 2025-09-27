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

## 파일 스캔 파이프라인 (File Scan Pipeline)

- `python devmind.py scan --paths <dir>` 명령은 **스트리밍 배치 스캐너**를 사용해 최대 2만+ 파일을 5초 이내로 메타 스캔합니다.
- `--include`, `--exclude`, `--max-depth` 옵션으로 글롭 기반 필터링과 최대 탐색 깊이를 지정할 수 있습니다.
- 전체/배치 타임아웃과 취소 토큰을 지원하여 장시간 블로킹 없이 안전하게 중단할 수 있습니다.
- 진행률 콜백은 0.20초 주기로 `processed/discovered/skipped/ETA`를 갱신하며 UI 백프레셔를 제공합니다.
- I/O 예외는 로깅 후 스킵되며, 긴 경로·락 파일·WinError 2 케이스를 자동으로 건너뜁니다.
- 출력 JSON과 safe-map은 스트리밍으로 기록되어 피크 메모리 사용량을 500MB 이하로 유지합니다.
