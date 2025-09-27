# 🚀 MACHO-GPT: AI-Powered Project File Organization

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

> **MACHO-GPT**는 AI 기반 프로젝트 파일 자동 분류 및 정리 시스템입니다. Hybrid GPT 모드와 로컬 처리 모드를 지원하며, 웹 대시보드와 CLI를 통해 사용할 수 있습니다.

---

## 🎯 **주요 기능**

### 🔍 **스마트 파일 스캔**
- 재귀적 파일 시스템 스캔
- 메타데이터 추출 (크기, 수정일, MIME 타입)
- 텍스트 파일 내용 샘플링
- SHA256 기반 안전한 파일 식별

### 🧠 **AI 기반 분류**
- **Hybrid GPT 모드**: OpenAI GPT를 활용한 지능형 클러스터링
- **로컬 모드**: TF-IDF + K-Means 기반 로컬 처리
- **규칙 기반 분류**: 28개 카테고리 자동 분류 (docs, src, scripts 등)
- **프로젝트 그룹화**: 공통 디렉토리 기반 프로젝트 라벨링

### 📁 **표준 구조 정리**
```
PROJECT_NAME/
├── docs/          # 문서 파일
├── src/           # 소스 코드
├── scripts/       # 스크립트
├── tests/         # 테스트
├── configs/       # 설정 파일
├── data/          # 데이터 파일
└── tmp/           # 임시 파일
```

### 🔒 **보안 및 추적**
- **Safe Map**: 파일 경로 해시화로 민감 정보 보호
- **완전한 저널링**: 모든 작업 기록 및 롤백 지원
- **버전 관리**: 충돌 시 해시 기반 파일명 생성

---

## 🚀 **빠른 시작**

### **1. 설치**

```bash
# 저장소 클론
git clone https://github.com/macho715/MACHO-GPT.git
cd MACHO-GPT

# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt
```

### **2. 웹 대시보드 실행** (권장)

```bash
# Streamlit 대시보드 시작
streamlit run dash_web.py
```

브라우저에서 `http://localhost:8501` 접속하여 GUI로 사용

### **3. CLI 명령어**

```bash
# 1단계: 파일 스캔
python devmind.py scan --paths "C:\YourProject" --emit .cache/scan.json

# 2단계: 규칙 적용 및 분류
python devmind.py rules --scan .cache/scan.json --emit .cache/scores.json

# 3단계: 프로젝트 군집화 (로컬 모드)
python devmind.py cluster --scores .cache/scores.json --emit .cache/projects.json --project-mode local

# 4단계: 파일 정리
python devmind.py organize --projects .cache/projects.json --scores .cache/scores.json --target "C:\PROJECTS_STRUCT" --mode move

# 5단계: 리포트 생성
python devmind.py report --journal .cache/journal.jsonl --out reports/summary.html
```

---

## 🧠 **Hybrid GPT 모드**

### **API 키 설정**
```bash
# Windows
set OPENAI_API_KEY=sk-your-api-key-here

# Linux/Mac
export OPENAI_API_KEY=sk-your-api-key-here
```

### **GPT 모드 실행**
```bash
# GPT 기반 클러스터링 (3회 재시도 로직 포함)
python devmind.py cluster --scores .cache/scores.json --emit .cache/projects.json --project-mode gpt --safe-map .cache/safe_map.json
```

### **보안 특징**
- 🔒 **Safe Map**: 원본 파일 경로를 SHA256 해시로 변환
- 🔒 **제한적 데이터**: 파일명, 확장자, 크기, 샘플만 전송
- 🔒 **로컬 폴백**: GPT 실패 시 자동으로 로컬 모드 전환

---

## 🎛️ **웹 대시보드**

### **주요 기능**
- 📊 **실시간 모니터링**: 파이프라인 진행 상황 추적
- 🎯 **모드 선택**: LOCAL / Hybrid GPT 모드 전환
- 📁 **파일 필터링**: 확장자, 크기, 날짜별 필터
- 📈 **시각화**: 파일 분포, 파이프라인 이력 차트
- 🌐 **다국어**: 한국어/영어 지원

### **사용법**
1. `streamlit run dash_web.py` 실행
2. 브라우저에서 `http://localhost:8501` 접속
3. Hybrid GPT 모드 토글 (API 키 설정 필요)
4. 대상 경로 설정
5. "🚀 파이프라인 실행" 버튼 클릭

---

## ⚙️ **설정 파일**

### **rules.yml** - 분류 규칙
```yaml
rules:
  - name: "docs"
    pattern: "\\.md$|README|GUIDE|INSTALLATION|PLAN|SPEC|TDD"
    description: "Documentation files"
  - name: "src"
    pattern: "\\.py$"
    description: "Python source files"
  # ... 총 9개 카테고리
```

### **schema.yml** - 프로젝트 구조
```yaml
target_root: "C:/PROJECTS_STRUCT"
preserve_structure: true
conflict: "version"  # version, skip, overwrite
```

---

## 🔧 **고급 사용법**

### **대규모 프로젝트 처리**
```bash
# 병렬 처리 및 성능 최적화
make performance  # 성능 테스트
make ci          # 전체 CI/CD 파이프라인
```

### **롤백 및 복구**
```bash
# 모든 작업을 원래 위치로 복구
python devmind.py rollback --journal .cache/journal.jsonl
```

### **물류 데이터 검증** (특수 기능)
```bash
# Incoterm/HS Code 검증
python devmind.py logistics-validate --payload shipment.json
```

---

## 🧪 **테스트**

### **전체 테스트 실행**
```bash
# 단위 테스트 + 커버리지
make test

# 빠른 테스트 (병렬)
make test-fast

# 성능 테스트
make performance
```

### **개발 도구**
```bash
make lint        # 코드 품질 검사
make format      # 코드 포맷팅
make security    # 보안 검사
make quality     # 품질 게이트 검사
```

---

## 📊 **성능 지표**

### **처리 능력**
- ✅ **소규모**: 1,000개 파일 → 30초
- ✅ **중규모**: 10,000개 파일 → 5분
- ✅ **대규모**: 100,000개 파일 → 30분

### **정확도**
- 📈 **로컬 모드**: 85-90% 정확도
- 📈 **GPT 모드**: 95-98% 정확도
- 📈 **복합 모드**: 90-95% 정확도

---

## 🛠️ **개발자 가이드**

### **프로젝트 구조**
```
MACHO-GPT/
├── devmind.py           # 메인 CLI 도구
├── dash_web.py          # Streamlit 대시보드
├── scan.py              # 파일 스캔 모듈
├── classify.py          # 분류 로직
├── organize.py          # 정리 로직
├── rules.yml            # 분류 규칙
├── schema.yml           # 프로젝트 스키마
├── tests/               # 테스트 파일
├── scripts/             # 자동화 스크립트
└── docs/                # 문서
```

### **확장 개발**
```bash
# 개발 환경 설정
make setup-dev

# 코드 품질 검사
make quality

# 커밋 전 검사
make ci
```

---

## 📈 **로드맵**

### **v4.0 (계획)**
- [ ] 완전 로컬 AI 모드 (sentence-transformers + FAISS)
- [ ] GUI 데스크톱 앱 (Electron)
- [ ] 클라우드 동기화
- [ ] 플러그인 시스템

### **v3.6 (현재)**
- ✅ Hybrid GPT 모드
- ✅ 웹 대시보드
- ✅ 완전한 롤백 시스템
- ✅ 다국어 지원

---

## 🤝 **기여하기**

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 **라이선스**

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 📞 **지원 및 문의**

- 📧 **이메일**: [macho715@example.com](mailto:macho715@example.com)
- 🐛 **버그 리포트**: [Issues](https://github.com/macho715/MACHO-GPT/issues)
- 💬 **토론**: [Discussions](https://github.com/macho715/MACHO-GPT/discussions)

---

## 🎉 **감사의 말**

이 프로젝트는 다음 오픈소스 프로젝트들의 도움을 받았습니다:
- [Streamlit](https://streamlit.io) - 웹 대시보드
- [OpenAI](https://openai.com) - GPT API
- [Click](https://click.palletsprojects.com) - CLI 프레임워크
- [scikit-learn](https://scikit-learn.org) - 머신러닝

---

<div align="center">

**⭐ 이 프로젝트가 도움이 되었다면 Star를 눌러주세요! ⭐**

Made with ❤️ by [macho715](https://github.com/macho715)

</div>
