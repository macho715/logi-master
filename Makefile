# MACHO-GPT Makefile
# 자동화된 테스트 파이프라인 및 개발 도구

.PHONY: help install test lint format security clean all

# 기본 타겟
help:
	@echo "MACHO-GPT 개발 도구"
	@echo ""
	@echo "사용 가능한 명령어:"
	@echo "  install     - 의존성 설치"
	@echo "  test        - 테스트 실행"
	@echo "  test-fast   - 빠른 테스트 (병렬)"
	@echo "  lint        - 코드 린팅"
	@echo "  format      - 코드 포맷팅"
	@echo "  security    - 보안 검사"
	@echo "  quality     - 품질 게이트 검사"
	@echo "  performance - 성능 테스트"
	@echo "  integration - 통합 테스트"
	@echo "  all         - 전체 파이프라인 실행"
	@echo "  clean       - 임시 파일 정리"

# 의존성 설치
install:
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-xdist pytest-benchmark
	pip install flake8 mypy black bandit safety
	pip install memory-profiler psutil

# 테스트 실행
test:
	python -m pytest -v --cov=. --cov-report=html --cov-report=term

# 빠른 테스트 (병렬)
test-fast:
	python -m pytest -v -n auto --cov=. --cov-report=html

# 코드 린팅
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
	mypy . --ignore-missing-imports --no-strict-optional

# 코드 포맷팅
format:
	black . --line-length 100
	isort . --profile black

# 보안 검사
security:
	bandit -r . -f json -o bandit-report.json
	safety check --json --output safety-report.json

# 품질 게이트 검사
quality:
	python quality_gates.py

# 성능 테스트
performance:
	python -m pytest tests/test_performance.py -v --benchmark-only

# 통합 테스트
integration:
	python scripts/test_automation.py --integration-only

# 전체 파이프라인 실행
all:
	python scripts/test_automation.py --parallel

# 로컬 개발용 빠른 검사
dev:
	python scripts/test_automation.py --lint-only
	python scripts/test_automation.py --test-only

# CI/CD 파이프라인 시뮬레이션
ci:
	python scripts/test_automation.py --parallel
	python quality_gates.py

# 임시 파일 정리
clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .cache/
	rm -rf test_output/
	rm -rf test_data/
	rm -rf reports/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# 데이터베이스 정리
clean-db:
	rm -rf .cache/*.db
	rm -rf .cache/*.db-wal
	rm -rf .cache/*.db-shm

# 리포트 생성
report:
	python scripts/test_automation.py
	python quality_gates.py
	@echo "리포트가 생성되었습니다:"
	@echo "  - test_results.json"
	@echo "  - test_report.html"
	@echo "  - quality_gate_report.json"

# 개발 환경 설정
setup-dev: install
	mkdir -p .cache
	mkdir -p reports
	mkdir -p test_data
	@echo "개발 환경 설정 완료"

# 프로덕션 빌드
build:
	python -m build
	@echo "빌드 완료: dist/ 디렉토리 확인"

# 패키지 설치 (로컬)
install-local: build
	pip install dist/*.whl

# 도움말
.DEFAULT_GOAL := help
