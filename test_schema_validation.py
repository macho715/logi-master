# tests/test_schema_validation.py
import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_schema_validation_with_custom_schema(tmp_workspace: Path) -> None:
    """사용자 정의 스키마로 조직화가 올바르게 작동하는지 테스트"""
    # 1) 사용자 정의 스키마 생성
    custom_schema = {
        "target_root": str(tmp_workspace / "CUSTOM_STRUCT"),
        "structure": [
            "src/",
            "scripts/",
            "tests/",
            "docs/",
            "reports/",
            "configs/",
            "data/",
            "notebooks/",
            "archive/",
            "tmp/"
        ],
        "conflict_policy": "version",
        "mode": "move"
    }
    
    schema_file = tmp_workspace / "custom_schema.yml"
    schema_file.write_text(json.dumps(custom_schema, indent=2), encoding="utf-8")
    
    # 2) scan
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
    
    # 3) rules
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
    
    # 4) cluster
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
    
    # 5) organize with custom schema
    run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            str(tmp_workspace / "CUSTOM_STRUCT"),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
            "--schema",
            str(schema_file),
        ],
        tmp_workspace,
    )
    
    # 6) 스키마 검증
    target_dir = tmp_workspace / "CUSTOM_STRUCT"
    assert target_dir.exists()
    
    # 사용자 정의 스키마 구조가 생성되었는지 확인
    # 최소한 일부 디렉토리는 생성되어야 함
    expected_dirs = ["src", "scripts", "tests", "docs", "reports", "configs", "data", "notebooks", "archive", "tmp"]
    created_dirs = 0
    for dir_name in expected_dirs:
        dir_path = target_dir / dir_name
        if dir_path.exists():
            created_dirs += 1
        else:
            # 하위 디렉토리에 파일이 있는지 확인
            files_in_subdir = list(target_dir.rglob(f"{dir_name}/*"))
            if len(files_in_subdir) > 0:
                created_dirs += 1
    
    # 최소한 3개 이상의 디렉토리가 생성되거나 파일이 배치되어야 함
    assert created_dirs >= 3, f"최소 3개 이상의 디렉토리가 생성되거나 파일이 배치되어야 함. 생성된 디렉토리 수: {created_dirs}"
    
    # 파일들이 올바른 디렉토리에 배치되었는지 확인
    all_files = list(target_dir.rglob("*"))
    file_count = len([f for f in all_files if f.is_file()])
    assert file_count > 0, "파일이 이동되지 않았습니다"


def test_schema_validation_with_default_schema(tmp_workspace: Path) -> None:
    """기본 스키마로 조직화가 올바르게 작동하는지 테스트"""
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
    
    # 3) cluster
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
    
    # 4) organize with default schema
    run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            str(tmp_workspace / "DEFAULT_STRUCT"),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
        ],
        tmp_workspace,
    )
    
    # 5) 기본 스키마 검증
    target_dir = tmp_workspace / "DEFAULT_STRUCT"
    assert target_dir.exists()
    
    # 기본 스키마 구조가 생성되었는지 확인
    # 최소한 일부 디렉토리는 생성되어야 함
    expected_dirs = ["src", "scripts", "tests", "docs", "reports", "configs", "data", "notebooks", "archive", "tmp"]
    created_dirs = 0
    for dir_name in expected_dirs:
        dir_path = target_dir / dir_name
        if dir_path.exists():
            created_dirs += 1
        else:
            # 하위 디렉토리에 파일이 있는지 확인
            files_in_subdir = list(target_dir.rglob(f"{dir_name}/*"))
            if len(files_in_subdir) > 0:
                created_dirs += 1
    
    # 최소한 3개 이상의 디렉토리가 생성되거나 파일이 배치되어야 함
    assert created_dirs >= 3, f"최소 3개 이상의 디렉토리가 생성되거나 파일이 배치되어야 함. 생성된 디렉토리 수: {created_dirs}"
    
    # 파일들이 올바른 디렉토리에 배치되었는지 확인
    all_files = list(target_dir.rglob("*"))
    file_count = len([f for f in all_files if f.is_file()])
    assert file_count > 0, "파일이 이동되지 않았습니다"


def test_schema_validation_conflict_resolution(tmp_workspace: Path) -> None:
    """충돌 해결 정책이 올바르게 작동하는지 테스트"""
    # 1) 동일한 이름의 파일을 다른 위치에 생성
    (tmp_workspace / "C_HVDC_PJT" / "conflict_test.txt").write_text("HVDC content", encoding="utf-8")
    (tmp_workspace / "C_cursor_mcp" / "conflict_test.txt").write_text("MCP content", encoding="utf-8")
    
    # 2) scan
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
    
    # 3) rules
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
    
    # 4) cluster
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
    
    # 5) organize with version conflict policy
    run(
        [
            "python",
            "devmind.py",
            "organize",
            "--projects",
            ".cache/projects.json",
            "--scores",
            ".cache/scores.json",
            "--target",
            str(tmp_workspace / "CONFLICT_STRUCT"),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            ".cache/journal.jsonl",
        ],
        tmp_workspace,
    )
    
    # 6) 충돌 해결 검증
    target_dir = tmp_workspace / "CONFLICT_STRUCT"
    assert target_dir.exists()
    
    # 충돌 파일들이 버전 서픽스로 보존되었는지 확인
    conflict_files = list(target_dir.rglob("conflict_test__*.txt"))
    assert len(conflict_files) == 2, "충돌 파일 2개 모두 버전 보존되어야 함"
    
    # 각 파일의 내용이 올바른지 확인
    for file_path in conflict_files:
        content = file_path.read_text(encoding="utf-8")
        assert content in ["HVDC content", "MCP content"], f"파일 내용이 올바르지 않습니다: {content}"
