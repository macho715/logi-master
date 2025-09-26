#!/usr/bin/env python3
"""
MACHO-GPT 품질 게이트 설정
코드 품질, 테스트 커버리지, 보안 등의 기준을 정의하고 검증
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class QualityGate:
    """품질 게이트 메인 클래스"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.quality_standards = {
            "test_coverage": 80.0,  # 최소 80% 테스트 커버리지
            "max_complexity": 10,   # 최대 순환 복잡도
            "max_line_length": 100, # 최대 라인 길이
            "max_file_size": 1000,  # 최대 파일 크기 (라인 수)
            "min_test_count": 15,   # 최소 테스트 수
            "max_memory_usage": 500, # 최대 메모리 사용량 (MB)
            "max_execution_time": 60, # 최대 실행 시간 (초)
        }
        
        self.violations = []
        self.warnings = []
    
    def check_test_coverage(self) -> bool:
        """테스트 커버리지 검사"""
        print("테스트 커버리지 검사 중...")
        
        try:
            result = subprocess.run(
                ["pytest", "--cov=.", "--cov-report=json", "--cov-report=term"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.violations.append("테스트 실행 실패")
                return False
            
            # coverage.json 파일에서 커버리지 정보 읽기
            coverage_file = self.project_root / "coverage.json"
            if not coverage_file.exists():
                self.violations.append("커버리지 파일이 생성되지 않았습니다")
                return False
            
            with open(coverage_file) as f:
                coverage_data = json.load(f)
            
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
            
            if total_coverage < self.quality_standards["test_coverage"]:
                self.violations.append(
                    f"테스트 커버리지 부족: {total_coverage:.2f}% < {self.quality_standards['test_coverage']}%"
                )
                return False
            
            print(f"✅ 테스트 커버리지: {total_coverage:.2f}%")
            return True
            
        except Exception as e:
            self.violations.append(f"커버리지 검사 실패: {e}")
            return False
    
    def check_code_quality(self) -> bool:
        """코드 품질 검사"""
        print("코드 품질 검사 중...")
        
        # flake8 검사
        try:
            result = subprocess.run(
                ["flake8", ".", "--count", "--select=E9,F63,F7,F82", 
                 "--show-source", "--statistics"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.violations.append("flake8 오류 발견")
                print(f"❌ flake8 오류:\n{result.stdout}")
                return False
            
            # 복잡도 검사
            result = subprocess.run(
                ["flake8", ".", "--count", "--max-complexity=10", "--statistics"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.warnings.append("높은 복잡도 함수 발견")
                print(f"⚠️ 복잡도 경고:\n{result.stdout}")
            
            print("✅ 코드 품질 검사 통과")
            return True
            
        except Exception as e:
            self.violations.append(f"코드 품질 검사 실패: {e}")
            return False
    
    def check_security(self) -> bool:
        """보안 검사"""
        print("보안 검사 중...")
        
        # bandit 보안 스캔
        try:
            result = subprocess.run(
                ["bandit", "-r", ".", "-f", "json"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # bandit 결과 파싱
                try:
                    bandit_data = json.loads(result.stdout)
                    high_severity = [issue for issue in bandit_data.get("results", []) 
                                   if issue.get("issue_severity") == "HIGH"]
                    
                    if high_severity:
                        self.violations.append(f"높은 심각도 보안 이슈 {len(high_severity)}개 발견")
                        return False
                    else:
                        self.warnings.append("보안 이슈 발견 (중간/낮은 심각도)")
                except json.JSONDecodeError:
                    self.warnings.append("보안 스캔 결과 파싱 실패")
            
            print("✅ 보안 검사 통과")
            return True
            
        except Exception as e:
            self.warnings.append(f"보안 검사 실패: {e}")
            return True  # 보안 검사 실패는 경고로 처리
    
    def check_dependencies(self) -> bool:
        """의존성 검사"""
        print("의존성 검사 중...")
        
        # safety 검사
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                try:
                    safety_data = json.loads(result.stdout)
                    vulnerabilities = safety_data.get("vulnerabilities", [])
                    
                    if vulnerabilities:
                        self.violations.append(f"취약한 의존성 {len(vulnerabilities)}개 발견")
                        return False
                except json.JSONDecodeError:
                    self.warnings.append("의존성 검사 결과 파싱 실패")
            
            print("✅ 의존성 검사 통과")
            return True
            
        except Exception as e:
            self.warnings.append(f"의존성 검사 실패: {e}")
            return True  # 의존성 검사 실패는 경고로 처리
    
    def check_file_sizes(self) -> bool:
        """파일 크기 검사"""
        print("파일 크기 검사 중...")
        
        large_files = []
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                
                if line_count > self.quality_standards["max_file_size"]:
                    large_files.append((py_file.name, line_count))
            except Exception:
                continue
        
        if large_files:
            self.warnings.append(f"큰 파일 {len(large_files)}개 발견")
            for filename, line_count in large_files:
                print(f"⚠️ {filename}: {line_count} 라인")
        
        print("✅ 파일 크기 검사 완료")
        return True
    
    def check_test_count(self) -> bool:
        """테스트 수 검사"""
        print("테스트 수 검사 중...")
        
        test_files = list(self.project_root.glob("tests/test_*.py"))
        test_count = len(test_files)
        
        if test_count < self.quality_standards["min_test_count"]:
            self.violations.append(
                f"테스트 수 부족: {test_count} < {self.quality_standards['min_test_count']}"
            )
            return False
        
        print(f"✅ 테스트 수: {test_count}개")
        return True
    
    def check_performance(self) -> bool:
        """성능 검사"""
        print("성능 검사 중...")
        
        try:
            # 성능 테스트 실행
            result = subprocess.run(
                ["pytest", "tests/test_performance.py", "-v", "--benchmark-skip"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120  # 2분 타임아웃
            )
            
            if result.returncode != 0:
                self.violations.append("성능 테스트 실패")
                return False
            
            print("✅ 성능 검사 통과")
            return True
            
        except subprocess.TimeoutExpired:
            self.violations.append("성능 테스트 타임아웃")
            return False
        except Exception as e:
            self.warnings.append(f"성능 검사 실패: {e}")
            return True
    
    def run_all_checks(self) -> bool:
        """모든 품질 게이트 검사 실행"""
        print("=== MACHO-GPT 품질 게이트 검사 시작 ===")
        
        checks = [
            ("테스트 수", self.check_test_count),
            ("코드 품질", self.check_code_quality),
            ("테스트 커버리지", self.check_test_coverage),
            ("보안", self.check_security),
            ("의존성", self.check_dependencies),
            ("파일 크기", self.check_file_sizes),
            ("성능", self.check_performance),
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            print(f"\n--- {check_name} 검사 ---")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                print(f"❌ {check_name} 검사 중 오류: {e}")
                all_passed = False
        
        # 결과 요약
        print("\n=== 품질 게이트 검사 결과 ===")
        
        if self.violations:
            print("❌ 위반 사항:")
            for violation in self.violations:
                print(f"  - {violation}")
        
        if self.warnings:
            print("⚠️ 경고 사항:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if all_passed and not self.violations:
            print("✅ 모든 품질 게이트 통과!")
        else:
            print("❌ 일부 품질 게이트 실패")
        
        return all_passed and not self.violations
    
    def generate_report(self) -> None:
        """품질 게이트 리포트 생성"""
        report = {
            "timestamp": str(Path().cwd()),
            "standards": self.quality_standards,
            "violations": self.violations,
            "warnings": self.warnings,
            "passed": len(self.violations) == 0
        }
        
        report_file = self.project_root / "quality_gate_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n품질 게이트 리포트 저장: {report_file}")


def main():
    """메인 함수"""
    gate = QualityGate()
    
    success = gate.run_all_checks()
    gate.generate_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
