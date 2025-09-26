# tests/test_gpt_mode.py
import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_gpt_mode_clustering_with_mock(tmp_workspace: Path) -> None:
    """GPT 모드에서 클러스터링이 올바르게 작동하는지 테스트"""
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
    
    # 3) GPT 모드 클러스터링 (API 키 없이 로컬 폴백)
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
    
    # GPT 모드에서 API 키 없이도 로컬 폴백으로 실행되어야 함
    assert result.returncode == 0, f"GPT 모드가 로컬 폴백으로 실행되어야 함: {result.stderr}"
    
    # 4) 결과 검증
    projects_data = json.loads((tmp_workspace / ".cache/projects.json").read_text(encoding="utf-8"))
    
    # 프로젝트가 생성되었는지 확인
    assert "projects" in projects_data
    assert len(projects_data["projects"]) > 0
    
    # 각 프로젝트에 doc_ids가 있는지 확인
    for project in projects_data["projects"]:
        assert "doc_ids" in project
        assert len(project["doc_ids"]) > 0


def test_gpt_mode_fallback_to_local_on_error(tmp_workspace: Path) -> None:
    """GPT 모드에서 에러 발생 시 로컬 모드로 폴백하는지 테스트"""
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
    
    # 3) GPT 모드 실행 (API 키 없이 로컬 폴백)
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
    
    # 에러가 발생해도 프로젝트 파일이 생성되어야 함 (로컬 폴백)
    assert result.returncode == 0, f"GPT 모드가 로컬 폴백으로 실행되어야 함: {result.stderr}"
    assert (tmp_workspace / ".cache/projects.json").exists()
    
    # 프로젝트 데이터가 유효한지 확인
    projects_data = json.loads((tmp_workspace / ".cache/projects.json").read_text(encoding="utf-8"))
    assert "projects" in projects_data
    assert len(projects_data["projects"]) > 0
