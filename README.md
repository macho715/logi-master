# MACHO-GPT: Intelligent Project Organization System

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red.svg)](https://streamlit.io)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-green.svg)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MACHO-GPT**는 AI 기반의 지능형 프로젝트 자동 분류 및 조직화 시스템입니다. 대량의 파일과 프로젝트를 GPT의 지능을 활용하여 의미있는 구조로 자동 정리합니다.

---

## 🚀 주요 기능 (Key Features)

### 🤖 Hybrid GPT Mode
- **OpenAI GPT-4** 기반 지능형 파일 분류
- **95% 신뢰도**로 프로젝트 자동 그룹화
- **재시도 로직** 및 **오류 복구** 메커니즘
- **API 키 관리** 및 **보안** 강화

### 📊 실시간 대시보드
- **Streamlit** 기반 웹 인터페이스
- **실시간 진행률** 표시
- **인터랙티브** 파일 탐색
- **시각화** 및 **분석** 도구

### 🔧 고성능 파이프라인
- **병렬 처리** 및 **배치 처리**
- **SQLite 캐시** 시스템
- **메모리 최적화**
- **타임아웃** 및 **오류 처리**

### 📁 스마트 파일 분류
- **확장자** 기반 자동 분류
- **내용 분석** 기반 그룹화
- **중복 파일** 감지
- **버전 관리** 지원

---

## 📋 시스템 요구사항 (System Requirements)

### 필수 요구사항
- **Python**: 3.13 이상
- **메모리**: 최소 4GB RAM (권장 8GB+)
- **저장공간**: 최소 1GB 여유공간
- **네트워크**: OpenAI API 접근 가능

### 권장 요구사항
- **SSD**: 빠른 파일 I/O를 위한 SSD 권장
- **CPU**: 멀티코어 프로세서
- **네트워크**: 안정적인 인터넷 연결

---

## 🛠️ 설치 및 설정 (Installation & Setup)

### 1. 저장소 클론
```bash
git clone https://github.com/your-org/macho-gpt.git
cd macho-gpt
```

### 2. 가상환경 설정
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. OpenAI API 키 설정
```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "your-api-key-here"

# Linux/Mac
export OPENAI_API_KEY="your-api-key-here"
```

### 5. 대시보드 실행
```bash
streamlit run dash_web.py
```

---

## 🎯 사용법 (Usage)

### 웹 대시보드 사용
1. **브라우저**에서 `http://localhost:8505` 접속
2. **Hybrid GPT 모드** 토글 활성화
3. **스캔 경로** 설정 (예: `C:\ABU_sample`)
4. **"Start Pipeline"** 버튼 클릭
5. **실시간 진행률** 확인

### 명령줄 사용
```bash
# 파일 스캔
python devmind.py scan --paths "C:\your\project\path"

# GPT 기반 클러스터링
python devmind.py cluster --project-mode gpt

# 프로젝트 조직화
python devmind.py organize --target "C:\organized_projects"

# 보고서 생성
python devmind.py report
```

---

## 📊 성능 지표 (Performance Metrics)

### 현재 성능
| 작업 | 소규모 (7파일) | 대규모 (22,926파일) |
|------|----------------|-------------------|
| 스캔 | 1-2초 | ⚠️ 성능 이슈 |
| 클러스터링 | 2-3초 | 5-10분 |
| 전체 파이프라인 | 5-10초 | 수십 분 |

### SLA 목표
- **스캔 시간**: ≤ 5초 (소규모)
- **클러스터링**: ≤ 15초
- **전체 파이프라인**: ≤ 60초
- **메모리 사용량**: ≤ 500MB 증가

---

## 🔧 고급 설정 (Advanced Configuration)

### 스캔 최적화
```bash
# 파일 크기 제한
python devmind.py scan --paths "C:\path" --max-size "5MB"

# 샘플 크기 조정
python devmind.py scan --paths "C:\path" --sample-bytes 1024
```

### 캐시 관리
```bash
# 캐시 정리
rm -rf .cache/*

# 캐시 위치 변경
python devmind.py scan --cache-db "custom_cache.sqlite3"
```

---

## 🚨 알려진 문제점 (Known Issues)

### Critical Issues
1. **대용량 스캔**: 20,000+ 파일 시 성능 저하
2. **파일 접근 오류**: WinError 2 발생
3. **진행률 표시**: 실시간 업데이트 문제
4. **메모리 사용량**: 대용량 데이터 처리 시 과다 사용

### 해결 방안
1. **스캔 범위 제한**: 샘플 디렉토리 사용
2. **필터링 옵션**: 불필요한 파일 제외
3. **배치 처리**: 청크 단위 처리
4. **모니터링**: 메모리 사용량 추적

---

## 📈 로드맵 (Roadmap)

### 단기 (1-2주)
- [ ] 파일 필터링 옵션 구현
- [ ] 타임아웃 설정 추가
- [ ] 진행률 표시 개선
- [ ] WinError 2 문제 해결

### 중기 (1개월)
- [ ] 캐시 시스템 최적화
- [ ] 배치 처리 구현
- [ ] API 키 관리 개선
- [ ] 모니터링 시스템 구축

### 장기 (3개월)
- [ ] 아키텍처 개선
- [ ] 클라우드 연동
- [ ] 분산 처리 시스템
- [ ] 고급 분석 기능

---

## 🤝 기여하기 (Contributing)

### 개발 환경 설정
```bash
# 개발 의존성 설치
pip install -r requirements-dev.txt

# 테스트 실행
pytest tests/

# 코드 품질 검사
black .
flake8 .
mypy .
```

### 기여 가이드라인
1. **Fork** 저장소
2. **Feature 브랜치** 생성
3. **변경사항** 커밋
4. **Pull Request** 제출

---

## 📄 라이선스 (License)

이 프로젝트는 **MIT 라이선스** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 📞 지원 및 문의 (Support & Contact)

### 문서
- **시스템 문제점 보고서**: [SYSTEM_ISSUES_REPORT.md](SYSTEM_ISSUES_REPORT.md)
- **변경 이력**: [CHANGELOG.md](CHANGELOG.md)
- **API 문서**: [docs/](docs/)

### 문의처
- **이메일**: support@macho-gpt.com
- **이슈 트래커**: [GitHub Issues](https://github.com/your-org/macho-gpt/issues)
- **토론**: [GitHub Discussions](https://github.com/your-org/macho-gpt/discussions)

---

## 🙏 감사의 말 (Acknowledgments)

- **OpenAI** - GPT-4 API 제공
- **Streamlit** - 웹 대시보드 프레임워크
- **Python Community** - 다양한 라이브러리 지원

---

**⚠️ 중요**: 현재 시스템은 대용량 파일 처리 시 성능 이슈가 있으므로, 소규모 데이터셋으로 테스트하시기 바랍니다.

**🚀 시작하기**: `C:\ABU_sample` 같은 작은 디렉토리로 시작하여 시스템을 테스트해보세요!
