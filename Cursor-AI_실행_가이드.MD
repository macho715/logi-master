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


