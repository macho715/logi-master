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
