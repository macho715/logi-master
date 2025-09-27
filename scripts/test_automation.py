#!/usr/bin/env python3
"""
MACHO-GPT 테스트 자동화 스크립트
CI/CD 파이프라인과 로컬 개발을 위한 통합 테스트 도구
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TestAutomation:
    """테스트 자동화 메인 클래스"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        self.results = {
            "start_time": time.time(),
            "tests": {},
            "coverage": {},
            "errors": []
        }
    
    def log(self, message: str, level: str = "INFO") -> None:
        """로깅 함수"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> Tuple[bool, str, str]:
        """명령어 실행"""
        try:
            self.log(f"실행: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            success = result.returncode == 0
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log("명령어 실행 타임아웃", "ERROR")
            return False, "", "Command timeout"
        except Exception as e:
            self.log(f"명령어 실행 실패: {e}", "ERROR")
            return False, "", str(e)
    
    def check_dependencies(self) -> bool:
        """의존성 확인"""
        self.log("의존성 확인 중...")
        
        required_packages = [
            "pytest", "pytest-cov", "flake8", "mypy", "black", 
            "bandit", "safety", "click", "blake3", "scikit-learn"
        ]
        
        missing_packages = []
        for package in required_packages:
            success, _, _ = self.run_command([sys.executable, "-c", f"import {package.replace('-', '_')}"])
            if not success:
                missing_packages.append(package)
        
        if missing_packages:
            self.log(f"누락된 패키지: {missing_packages}", "ERROR")
            return False
        
        self.log("모든 의존성이 설치되어 있습니다")
        return True
    
    def run_linting(self) -> bool:
        """린팅 실행"""
        self.log("코드 린팅 실행 중...")
        
        # flake8
        success, stdout, stderr = self.run_command([
            "flake8", ".", "--count", "--select=E9,F63,F7,F82", 
            "--show-source", "--statistics"
        ])
        
        if not success:
            self.log("flake8 오류 발견", "ERROR")
            self.results["errors"].append({"tool": "flake8", "output": stderr})
            return False
        
        # mypy
        success, stdout, stderr = self.run_command([
            "mypy", ".", "--ignore-missing-imports", "--no-strict-optional"
        ])
        
        if not success:
            self.log("mypy 타입 체크 오류", "WARNING")
            self.results["errors"].append({"tool": "mypy", "output": stderr})
        
        # black
        success, stdout, stderr = self.run_command([
            "black", "--check", "--diff", "."
        ])
        
        if not success:
            self.log("black 포맷팅 오류", "WARNING")
            self.results["errors"].append({"tool": "black", "output": stderr})
        
        self.log("린팅 완료")
        return True
    
    def run_security_scan(self) -> bool:
        """보안 스캔 실행"""
        self.log("보안 스캔 실행 중...")
        
        # bandit
        success, stdout, stderr = self.run_command([
            "bandit", "-r", ".", "-f", "json"
        ])
        
        if not success:
            self.log("bandit 보안 스캔 완료 (오류 포함)", "WARNING")
        
        # safety
        success, stdout, stderr = self.run_command([
            "safety", "check", "--json"
        ])
        
        if not success:
            self.log("safety 의존성 검사 완료 (오류 포함)", "WARNING")
        
        self.log("보안 스캔 완료")
        return True
    
    def run_tests(self, parallel: bool = False) -> bool:
        """테스트 실행"""
        self.log("테스트 실행 중...")
        
        cmd = ["pytest", "-v", "--cov=.", "--cov-report=json", "--cov-report=html"]
        
        if parallel:
            cmd.extend(["-n", "auto"])
        
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.log("테스트 실패", "ERROR")
            self.results["errors"].append({"tool": "pytest", "output": stderr})
            return False
        
        # 커버리지 결과 파싱
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file) as f:
                coverage_data = json.load(f)
                self.results["coverage"] = {
                    "total_coverage": coverage_data.get("totals", {}).get("percent_covered", 0),
                    "lines_covered": coverage_data.get("totals", {}).get("covered_lines", 0),
                    "lines_total": coverage_data.get("totals", {}).get("num_statements", 0)
                }
        
        self.log("테스트 완료")
        return True
    
    def run_integration_tests(self) -> bool:
        """통합 테스트 실행"""
        self.log("통합 테스트 실행 중...")
        
        # 테스트 데이터 생성
        test_data_dir = self.project_root / "test_data"
        test_data_dir.mkdir(exist_ok=True)
        
        (test_data_dir / "C_HVDC_PJT").mkdir(exist_ok=True)
        (test_data_dir / "C_cursor_mcp").mkdir(exist_ok=True)
        
        # 샘플 파일 생성
        (test_data_dir / "C_HVDC_PJT" / "README.md").write_text("# HVDC Project\nTest data for integration testing.")
        (test_data_dir / "C_cursor_mcp" / "test.py").write_text("print('Hello from cursor-mcp')")
        (test_data_dir / "C_cursor_mcp" / "config.json").write_text('{"test": true}')
        
        # 전체 파이프라인 실행
        steps = [
            ["python", "devmind.py", "scan", 
             "--paths", str(test_data_dir / "C_HVDC_PJT"),
             "--paths", str(test_data_dir / "C_cursor_mcp"),
             "--emit", ".cache/scan.json",
             "--safe-map", ".cache/safe_map.json"],
            
            ["python", "devmind.py", "rules",
             "--scan", ".cache/scan.json",
             "--emit", ".cache/scores.json"],
            
            ["python", "devmind.py", "cluster",
             "--scores", ".cache/scores.json",
             "--emit", ".cache/projects.json",
             "--project-mode", "local"],
            
            ["python", "devmind.py", "organize",
             "--projects", ".cache/projects.json",
             "--scores", ".cache/scores.json",
             "--target", "test_output",
             "--mode", "move",
             "--conflict", "version",
             "--journal", ".cache/journal.jsonl"],
            
            ["python", "devmind.py", "report",
             "--journal", ".cache/journal.jsonl",
             "--out", "reports/integration_test.html"]
        ]
        
        for i, step in enumerate(steps, 1):
            self.log(f"통합 테스트 단계 {i}/{len(steps)} 실행 중...")
            success, stdout, stderr = self.run_command(step)
            
            if not success:
                self.log(f"통합 테스트 단계 {i} 실패", "ERROR")
                self.results["errors"].append({"step": i, "output": stderr})
                return False
        
        # 결과 검증
        expected_files = [
            ".cache/scan.json",
            ".cache/scores.json", 
            ".cache/projects.json",
            ".cache/journal.jsonl",
            "reports/integration_test.html"
        ]
        
        for file_path in expected_files:
            if not (self.project_root / file_path).exists():
                self.log(f"예상 파일 누락: {file_path}", "ERROR")
                return False
        
        self.log("통합 테스트 완료")
        return True
    
    def generate_report(self) -> None:
        """테스트 결과 리포트 생성"""
        self.log("테스트 결과 리포트 생성 중...")
        
        self.results["end_time"] = time.time()
        self.results["duration"] = self.results["end_time"] - self.results["start_time"]
        
        # JSON 리포트
        report_file = self.project_root / "test_results.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        # HTML 리포트
        html_report = self.project_root / "test_report.html"
        self._generate_html_report(html_report)
        
        self.log(f"테스트 결과 저장: {report_file}")
        self.log(f"HTML 리포트 저장: {html_report}")
    
    def _generate_html_report(self, output_file: Path) -> None:
        """HTML 리포트 생성"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>MACHO-GPT 테스트 결과</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; }}
        .error {{ color: red; }}
        .warning {{ color: orange; }}
        .success {{ color: green; }}
        .coverage {{ background-color: #e8f5e8; padding: 10px; border-radius: 3px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MACHO-GPT 테스트 결과</h1>
        <p>실행 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>총 소요 시간: {self.results['duration']:.2f}초</p>
    </div>
    
    <div class="section">
        <h2>커버리지 정보</h2>
        <div class="coverage">
            <p>전체 커버리지: {self.results['coverage'].get('total_coverage', 0):.2f}%</p>
            <p>커버된 라인: {self.results['coverage'].get('lines_covered', 0)} / {self.results['coverage'].get('lines_total', 0)}</p>
        </div>
    </div>
    
    <div class="section">
        <h2>오류 및 경고</h2>
        {self._format_errors_html()}
    </div>
</body>
</html>
        """
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
    
    def _format_errors_html(self) -> str:
        """오류 HTML 포맷팅"""
        if not self.results["errors"]:
            return "<p class='success'>오류 없음</p>"
        
        html = "<table><tr><th>도구</th><th>오류 내용</th></tr>"
        for error in self.results["errors"]:
            tool = error.get("tool", "Unknown")
            output = error.get("output", "").replace("\n", "<br>")
            html += f"<tr><td>{tool}</td><td class='error'>{output}</td></tr>"
        html += "</table>"
        
        return html
    
    def run_full_pipeline(self, parallel: bool = False) -> bool:
        """전체 파이프라인 실행"""
        self.log("=== MACHO-GPT 테스트 파이프라인 시작 ===")
        
        steps = [
            ("의존성 확인", self.check_dependencies),
            ("린팅", self.run_linting),
            ("보안 스캔", self.run_security_scan),
            ("단위 테스트", lambda: self.run_tests(parallel)),
            ("통합 테스트", self.run_integration_tests)
        ]
        
        all_success = True
        for step_name, step_func in steps:
            self.log(f"=== {step_name} ===")
            success = step_func()
            if not success:
                self.log(f"{step_name} 실패", "ERROR")
                all_success = False
            else:
                self.log(f"{step_name} 성공", "SUCCESS")
        
        self.generate_report()
        
        if all_success:
            self.log("=== 모든 테스트 통과! ===", "SUCCESS")
        else:
            self.log("=== 일부 테스트 실패 ===", "ERROR")
        
        return all_success


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="MACHO-GPT 테스트 자동화")
    parser.add_argument("--parallel", action="store_true", help="병렬 테스트 실행")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")
    parser.add_argument("--lint-only", action="store_true", help="린팅만 실행")
    parser.add_argument("--test-only", action="store_true", help="테스트만 실행")
    parser.add_argument("--integration-only", action="store_true", help="통합 테스트만 실행")
    
    args = parser.parse_args()
    
    automation = TestAutomation(verbose=args.verbose)
    
    if args.lint_only:
        success = automation.run_linting()
    elif args.test_only:
        success = automation.run_tests(args.parallel)
    elif args.integration_only:
        success = automation.run_integration_tests()
    else:
        success = automation.run_full_pipeline(args.parallel)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
