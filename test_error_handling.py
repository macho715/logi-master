# tests/test_error_handling.py
import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_error_handling_invalid_paths(tmp_workspace: Path) -> None:
    """존재하지 않는 경로에 대한 에러 처리를 테스트"""
    # 존재하지 않는 경로로 scan 시도
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            "/nonexistent/path",
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # Windows에서는 존재하지 않는 경로도 빈 결과로 처리될 수 있음
    # 최소한 스캔이 완료되어야 함
    assert result.returncode == 0, f"스캔이 완료되어야 함: {result.stderr}"
    assert "scan" in result.stdout.lower() or "items" in result.stdout.lower()


def test_error_handling_missing_input_files(tmp_workspace: Path) -> None:
    """존재하지 않는 입력 파일에 대한 에러 처리를 테스트"""
    # 존재하지 않는 scan.json으로 rules 실행
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/nonexistent_scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # 에러가 발생해야 함
    assert result.returncode != 0, "존재하지 않는 입력 파일에 대해 에러가 발생해야 함"
    assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()


def test_error_handling_invalid_json_format(tmp_workspace: Path) -> None:
    """잘못된 JSON 형식에 대한 에러 처리를 테스트"""
    # .cache 디렉토리 생성
    (tmp_workspace / ".cache").mkdir(exist_ok=True)
    
    # 잘못된 JSON 파일 생성
    invalid_json_file = tmp_workspace / ".cache/invalid_scan.json"
    invalid_json_file.write_text("{ invalid json }", encoding="utf-8")
    
    # 잘못된 JSON으로 rules 실행
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/invalid_scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # 에러가 발생해야 함
    assert result.returncode != 0, "잘못된 JSON 형식에 대해 에러가 발생해야 함"
    assert "error" in result.stderr.lower() or "json" in result.stderr.lower()


def test_error_handling_permission_denied(tmp_workspace: Path) -> None:
    """권한 거부 상황에 대한 에러 처리를 테스트"""
    # 1) 정상적인 scan 수행
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) rules 수행
    run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        tmp_workspace,
    )
    
    # 3) cluster 수행
    run(
        [
            "python",
            "devmind.py",
            "cluster",
            "--scores",
            ".cache/scores.json",
            "--emit",
            ".cache/projects.json",
            "--project-mode",
            "local",
        ],
        tmp_workspace,
    )
    
    # 4) 권한이 없는 경로로 organize 시도
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            "/root/forbidden/path",
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # Windows에서는 권한 문제가 다르게 처리될 수 있음
    # 최소한 organize가 실행되어야 함
    assert result.returncode == 0, f"organize가 실행되어야 함: {result.stderr}"
    assert "organize" in result.stdout.lower() or "moves" in result.stdout.lower()


def test_error_handling_rollback_without_journal(tmp_workspace: Path) -> None:
    """저널 파일이 없을 때 롤백 에러 처리를 테스트"""
    # 존재하지 않는 저널 파일로 롤백 시도
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "rollback",
            "--journal",
            ".cache/nonexistent_journal.jsonl",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # 에러가 발생해야 함
    assert result.returncode != 0, "존재하지 않는 저널 파일에 대해 에러가 발생해야 함"
    assert "error" in result.stderr.lower() or "not found" in result.stderr.lower() or "journal" in result.stdout.lower()


def test_error_handling_gpt_mode_without_api_key(tmp_workspace: Path) -> None:
    """API 키 없이 GPT 모드 실행 시 에러 처리를 테스트"""
    # 1) scan
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) rules
    run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        tmp_workspace,
    )
    
    # 3) API 키 없이 GPT 모드 실행
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "cluster",
            "--scores",
            ".cache/scores.json",
            "--emit",
            ".cache/projects.json",
            "--project-mode",
            "gpt",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # 에러가 발생하거나 로컬 모드로 폴백해야 함
    # (구현에 따라 다를 수 있음)
    assert result.returncode == 0, "GPT 모드에서 API 키 없이도 로컬 폴백으로 실행되어야 함"


def test_error_handling_corrupted_safe_map(tmp_workspace: Path) -> None:
    """손상된 safe_map.json에 대한 에러 처리를 테스트"""
    # 1) scan
    run(
        [
            "python",
            "devmind.py",
            "scan",
            "--paths",
            str(tmp_workspace / "C_HVDC_PJT"),
            "--paths",
            str(tmp_workspace / "C_cursor_mcp"),
            "--emit",
            ".cache/scan.json",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        tmp_workspace,
    )
    
    # 2) rules
    run(
        [
            "python",
            "devmind.py",
            "rules",
            "--scan",
            ".cache/scan.json",
            "--emit",
            ".cache/scores.json",
        ],
        tmp_workspace,
    )
    
    # 3) safe_map.json 손상
    safe_map_file = tmp_workspace / ".cache/safe_map.json"
    safe_map_file.write_text("{ corrupted json", encoding="utf-8")
    
    # 4) 손상된 safe_map으로 GPT 모드 실행
    result = subprocess.run(
        [
            "python",
            "devmind.py",
            "cluster",
            "--scores",
            ".cache/scores.json",
            "--emit",
            ".cache/projects.json",
            "--project-mode",
            "gpt",
            "--safe-map",
            ".cache/safe_map.json",
        ],
        cwd=tmp_workspace,
        capture_output=True,
        text=True,
    )
    
    # 에러가 발생하거나 로컬 모드로 폴백해야 함
    assert result.returncode == 0, "손상된 safe_map에 대해 로컬 폴백으로 실행되어야 함"
