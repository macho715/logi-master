# PLAN.md

## 프로젝트: Project Autosort (C:\HVDC PJT + C:\cursor-mcp → 표준 스키마 자동 정리)

### 목표

* 두 루트를 스캔하여 **프로젝트 단위 군집(local|gpt)** 후, `{TARGET}/{project}/…` 표준 스키마로 **즉시 이동(move)**.
* **중복 파일 전부 보존**: `__{hash7}` 서픽스로 버전 부여.
* **완전 추적/복구**: JSONL 저널 + HTML 리포트 + `rollback`.

### 원칙

* **TDD (Red → Green → Refactor)**: 최소 테스트 1개씩 쪼개 진행.
* **Tidy First**: 구조 변경과 행위 변경을 분리(커밋 단위도 분리).
* **보안**: 외부 전송은 메타/샘플/안전ID만. 경로/PII 마스킹.

### 아키텍처

1. `scan`

   * 메타 추출: `path, name, ext, size, mtime, hint(≤4KB)`
   * `safe_id=sha256(path)` 생성 → `.cache/safe_map.json` 저장
2. `rules`

   * 경량 규칙으로 1차 버킷(`src, scripts, tests, …`) 태깅
3. `cluster --project-mode local|gpt`

   * **local**: TF-IDF(+힌트 가중) → KMeans/DBSCAN → 라벨링
   * **gpt**: `safe_id` 기반 메타만 전송 → `doc_ids(safe_id)` 수신 → **safe_map 역매핑으로 path 복원**
4. `organize`

   * 표준 스키마 생성 → **move** 수행, 충돌=**version**
   * `journal.jsonl`에 전 과정 기록
5. `report`

   * HTML 대시보드(다크 테마), 분포/에러/요약
6. `rollback`

   * 저널 역연산으로 원위치

### 표준 스키마

```
src/core/  src/utils/  src/pipelines/
scripts/
tests/unit/  tests/integration/
docs/  reports/  configs/
data/raw/  data/interim/  data/processed/
notebooks/
archive/  tmp/
```

### TDD 계획 (스프린트 단위)

* **S1 (기본 흐름)**

  * [RED] scan이 기본 메타를 수집한다
  * [GREEN] rules가 주요 버킷을 지정한다
  * [GREEN] cluster(local)가 최소 2개 이상으로 그룹 나눈다
* **S2 (조직 + 버전 보존)**

  * [RED] organize가 중복 이름 파일을 2개 모두 보존한다
  * [GREEN] `__{hash7}` 적용 확인
* **S3 (롤백/리포트)**

  * [RED] rollback이 이동 파일을 되돌린다
  * [GREEN] report가 HTML 생성한다
* **S4 (gpt + safe_map)**

  * [RED] gpt 모드에서 `safe_id→path` 역매핑이 정확하다(모킹)
  * [GREEN] 실패 시 local fallback
* **Refactor**

  * 규칙 외부화(rules.yml), 스키마 외부화(schema.yml), 병렬화

### Done 기준

* `pytest -q` 전부 통과
* `python devmind.py …` E2E 동작, `C:\PROJECTS_STRUCT`에 구조 생성
* 리포트 생성 + 롤백 정상 동작
* Cursor Agent **원클릭 운영**

---

# README.md

## Project Autosort

**두 루트**: `C:\HVDC PJT`, `C:\cursor-mcp`
**타깃**: `C:\PROJECTS_STRUCT`
**정책**: **바로 이동(move)** · **중복 전부 보존(해시 서픽스)** · **완전 추적/복구**

### 1) 설치

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows
pip install click blake3 scikit-learn
pip install pytest              # 개발 시
```

### 2) 빠른 실행 (local 모드)

```powershell
python devmind.py scan --paths "C:\HVDC PJT" --paths "C:\cursor-mcp" --emit .cache\scan.json --safe-map .cache\safe_map.json
python devmind.py rules --scan .cache\scan.json --emit .cache\scores.json
python devmind.py cluster --scores .cache\scores.json --emit .cache\projects.json --project-mode local
python devmind.py organize --projects .cache\projects.json --scores .cache\scores.json --target "C:\PROJECTS_STRUCT" --mode move --conflict version --journal .cache\journal.jsonl
python devmind.py report --journal .cache\journal.jsonl --out reports\projects_summary.html
```

### 3) GPT 모드 (정확 매핑: safe_map.json)

```powershell
$env:OPENAI_API_KEY="sk-***"
python devmind.py cluster --scores .cache\scores.json --emit .cache\projects.json --project-mode gpt --safe-map .cache\safe_map.json
```

> 외부 전송 데이터: `safe_id, name, ext, size, snippet(≤500), rule_tags, path_hint(마스킹)`만. **실경로/원문** 비전송.

### 4) 롤백

```powershell
python devmind.py rollback --journal .cache\journal.jsonl
```

### 5) 표준 스키마 & 충돌 정책

* 스키마는 자동 생성.
* 충돌 정책: `version`(기본) → `name__{hash7}.ext`로 모두 보존.

### 6) 테스트 (TDD)

```bash
pytest -q
```

* 포함 테스트: 규칙 버킷, 버전 보존, 롤백, (gpt 모드 모킹 가능)

### 7) 설정 외부화 (선택)

* `rules.yml`, `schema.yml`로 규칙/스키마 조정.
* Cursor Agent로 **원클릭 실행** 가능(아래 가이드 참고).

### 8) 보안/운영

* `safe_map.json`은 로컬 전용(반출 금지).
* 장기 운용 시 콘텐츠 해시(blake3) 기반 stable id로 확장 권장.
* 대규모(10k+) 처리 시 해시/IO 병렬화 옵션 검토.

---

# Cursor-AI_실행_가이드.md

## 목적

Cursor에서 **한 번 클릭**으로 전체 파이프라인 실행. 사용자 입력 없이 자동 실행 → HTML 리포트 오픈.

## 준비

1. 워크스페이스 루트에 파일 배치:

```
devmind.py
tests/...
.cursor/agents.json
rules.yml (선택)
schema.yml (선택)
```

2. Python venv + 의존성 설치 완료.

## Agent JSON

`.cursor/agents.json`

```json
{
  "version": 1,
  "agents": [
    {
      "name": "프로젝트_자동정리_바로이동",
      "description": "C:\\\\HVDC PJT 와 C:\\\\cursor-mcp 를 프로젝트 단위로 묶어 표준 스키마로 즉시 이동하고 리포트까지 생성",
      "workingDirectory": "${workspaceRoot}",
      "env": { "PYTHONUTF8": "1" },
      "steps": [
        { "run": "python devmind.py scan --paths \"C:\\\\HVDC PJT\" --paths \"C:\\\\cursor-mcp\" --emit .cache/scan.json --safe-map .cache/safe_map.json" },
        { "run": "python devmind.py rules --scan .cache/scan.json --emit .cache/scores.json" },
        { "run": "python devmind.py cluster --scores .cache/scores.json --emit .cache/projects.json --project-mode local" },
        { "run": "python devmind.py organize --projects .cache/projects.json --scores .cache/scores.json --target \"C:\\\\PROJECTS_STRUCT\" --mode move --conflict version --journal .cache/journal.jsonl" },
        { "run": "python devmind.py report --journal .cache/journal.jsonl --out reports/projects_summary.html" },
        { "openFile": "reports/projects_summary.html" }
      ],
      "timeout": 0
    }
  ]
}
```

### GPT 모드로 돌리고 싶으면

```json
{ "run": "python devmind.py cluster --scores .cache/scores.json --emit .cache/projects.json --project-mode gpt --safe-map .cache/safe_map.json" }
```

* 환경변수: `OPENAI_API_KEY`를 Cursor에서 주입하거나 OS에 설정.

## 실행

* Cursor 좌측 **Agents** 패널 → `프로젝트_자동정리_바로이동` 클릭 → Run
* 완료되면 `reports/projects_summary.html` 자동 오픈

## 운영 팁

* 첫 실행 전 **백업 권장**(move 정책).
* 문제 발생 시 `rollback --journal`로 원복.
* `rules.yml`/`schema.yml` 수정으로 도메인 최적화 가능.
* GPT 비용 절약: 첫 군집만 gpt, 이후엔 local 유지(캐시 전략).

---

필요하면 **병렬 해시/IO**와 **sentence-transformers + FAISS**(완전 로컬 임베딩) 옵션까지 확장한 버전도 바로 붙여줄 수 있어. 지금 문서 세트로는 운영엔 충분하고, TDD 루틴/에이전트까지 포함돼서 장기 유지보수도 수월할 거야.
