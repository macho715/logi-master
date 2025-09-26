# AGENTS.md

## MACHO-GPT 프로젝트 설정 및 개발 가이드

### 🚀 빠른 시작

#### 의존성 설치
```bash
# Python 의존성 설치
pip install -r requirements.txt

# 또는 Makefile 사용
make install
```

#### 개발 서버 시작
```bash
# Streamlit 웹 인터페이스
streamlit run dash_web.py

# 또는 CLI 직접 실행
python devmind.py --help
```

#### 테스트 실행
```bash
# 전체 테스트 실행
make test

# 빠른 테스트 (병렬)
make test-fast

# 특정 테스트만
pytest tests/test_performance.py -v
```

### 🔧 개발 도구

#### 코드 품질 검사
```bash
# 린팅
make lint

# 포맷팅
make format

# 보안 스캔
make security

# 품질 게이트 전체 검사
make quality
```

#### 자동화된 파이프라인
```bash
# 전체 CI/CD 파이프라인 시뮬레이션
make ci

# 성능 테스트
make performance

# 통합 테스트
make integration
```

### 📋 코드 스타일 가이드

#### Python 스타일
- **타입 힌트 필수**: 모든 함수에 타입 어노테이션 사용
- **함수형 패턴 우선**: map, filter, reduce 등 함수형 스타일 선호
- **PEP 8 준수**: Black 포맷터 사용
- **단일 따옴표**: 문자열은 작은따옴표 사용
- **세미콜론 금지**: Python에서는 세미콜론 사용하지 않음

#### 예시 코드
```python
from typing import List, Dict, Optional
from pathlib import Path

def process_files(file_paths: List[Path]) -> Dict[str, int]:
    """파일을 처리하고 결과를 반환"""
    return {
        'processed': len(file_paths),
        'success': sum(1 for p in file_paths if p.exists())
    }

# 함수형 스타일 예시
def filter_python_files(files: List[Path]) -> List[Path]:
    return list(filter(lambda f: f.suffix == '.py', files))
```

#### 테스트 스타일
```python
def test_should_process_files_correctly(tmp_workspace: Path) -> None:
    """파일 처리가 올바르게 작동하는지 테스트"""
    # Given: 테스트 데이터 준비
    test_files = [tmp_workspace / 'test1.py', tmp_workspace / 'test2.txt']
    
    # When: 함수 실행
    result = process_files(test_files)
    
    # Then: 결과 검증
    assert result['processed'] == 2
    assert result['success'] >= 0
```

### 🏗️ 프로젝트 구조

```
MACHO-GPT/
├── .github/workflows/     # CI/CD 설정
├── scripts/              # 자동화 스크립트
├── tests/                # 테스트 파일들
├── .cache/              # 캐시 파일들 (gitignore)
├── reports/             # 생성된 리포트들
├── devmind.py           # 메인 CLI 도구
├── dash_web.py          # Streamlit 웹 인터페이스
├── quality_gates.py     # 품질 게이트 검사
├── Makefile            # 개발 명령어 모음
├── requirements.txt    # Python 의존성
└── .gitignore         # Git 무시 파일
```

### 🧪 테스트 전략

#### 테스트 유형
1. **단위 테스트**: 개별 함수/클래스 테스트
2. **통합 테스트**: 전체 파이프라인 테스트
3. **성능 테스트**: 실행시간 및 메모리 사용량
4. **보안 테스트**: 취약점 및 의존성 검사

#### 테스트 실행 명령어
```bash
# 모든 테스트
pytest

# 커버리지 포함
pytest --cov=. --cov-report=html

# 병렬 실행
pytest -n auto

# 특정 테스트 파일
pytest tests/test_performance.py

# 마커별 실행
pytest -m "not slow"
```

### 🔒 보안 가이드

#### API 키 관리
- **환경변수 사용**: 하드코딩 금지
- **GitHub Secrets**: CI/CD에서 안전하게 관리
- **로컬 설정**: `.env` 파일 사용 (gitignore에 포함)

#### 보안 검사
```bash
# 의존성 취약점 검사
safety check

# 코드 보안 스캔
bandit -r .

# 전체 보안 검사
make security
```

### 📊 품질 기준

| 항목 | 기준 | 도구 |
|------|------|------|
| **테스트 커버리지** | ≥80% | pytest-cov |
| **코드 품질** | flake8 통과 | flake8, mypy, black |
| **보안** | 취약점 0개 | bandit, safety |
| **성능** | <60초, <500MB | pytest-benchmark |
| **테스트 수** | ≥15개 | pytest |

### 🚀 CI/CD 파이프라인

#### GitHub Actions 워크플로우
- **다중 Python 버전**: 3.11, 3.12, 3.13
- **단계별 검증**: 테스트 → 보안 → 성능 → 통합
- **자동 배포**: main 브랜치 푸시 시 실행
- **정기 테스트**: 매일 오전 2시 자동 실행

#### 로컬 CI 시뮬레이션
```bash
# 전체 파이프라인 실행
make ci

# 단계별 실행
make lint && make test && make security
```

### 🛠️ 개발 워크플로우

#### 새 기능 개발
1. **브랜치 생성**: `git checkout -b feature/new-feature`
2. **테스트 작성**: TDD 방식으로 테스트 먼저 작성
3. **구현**: 최소한의 코드로 테스트 통과
4. **리팩터링**: 코드 품질 개선
5. **커밋**: 의미있는 커밋 메시지 작성
6. **푸시**: 원격 저장소에 푸시
7. **PR 생성**: GitHub에서 Pull Request 생성

#### 커밋 메시지 규칙
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅
refactor: 코드 리팩터링
test: 테스트 추가/수정
chore: 빌드/설정 변경
```

### 📝 문서화

#### 코드 문서화
- **독스트링 필수**: 모든 함수/클래스에 독스트링 작성
- **타입 힌트**: 매개변수와 반환값 타입 명시
- **예시 코드**: 복잡한 함수는 사용 예시 포함

#### README 업데이트
- **설치 방법**: 의존성 설치 및 설정
- **사용법**: 기본 명령어 및 옵션
- **예시**: 실제 사용 시나리오
- **기여 가이드**: 개발자 참여 방법

### 🔧 문제 해결

#### 일반적인 문제
1. **의존성 충돌**: `pip install --upgrade -r requirements.txt`
2. **테스트 실패**: `make clean && make test`
3. **메모리 부족**: `make clean-db`로 캐시 정리
4. **권한 오류**: 관리자 권한으로 실행

#### 디버깅 도구
```bash
# 상세 로그로 실행
python devmind.py --verbose

# 특정 테스트만 디버깅
pytest tests/test_specific.py -v -s

# 성능 프로파일링
python -m cProfile devmind.py scan --help
```

---

**이 가이드를 따라하면 MACHO-GPT 프로젝트를 효율적으로 개발할 수 있습니다!** 🚀
