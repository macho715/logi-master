# tests/test_rollback.py
import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def run(cmd: list[str], cwd: Path) -> CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_rollback_moves_files_back(tmp_workspace: Path) -> None:
    # organize 먼저 수행
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
        ],
        tmp_workspace,
    )

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

    run(
        [
            "python",
            "devmind.py",
            "cluster",
            "--scores",
            ".cache/scores.json",
            "--emit",
            ".cache/projects.json",
        ],
        tmp_workspace,
    )

    target = tmp_workspace / "PROJECTS_STRUCT"
    journal = tmp_workspace / ".cache/journal.jsonl"
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
            str(target),
            "--mode",
            "move",
            "--conflict",
            "version",
            "--journal",
            str(journal),
        ],
        tmp_workspace,
    )

    # 롤백
    run(["python", "devmind.py", "rollback", "--journal", str(journal)], tmp_workspace)

    # 원래 위치의 대표 파일 몇 개가 되돌아왔는지 샘플 확인
    assert (tmp_workspace / "C_HVDC_PJT" / "README.md").exists()
    assert (tmp_workspace / "C_cursor_mcp" / "tool.py").exists()
