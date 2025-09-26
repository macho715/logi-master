# tests/test_versioning.py
import json
import subprocess
from pathlib import Path

def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r

def test_versioning_and_organize(tmp_workspace):
    # scan→rules→cluster→organize
    run(["python", "devmind.py", "scan",
         "--paths", str(tmp_workspace/"C_HVDC_PJT"),
         "--paths", str(tmp_workspace/"C_cursor_mcp"),
         "--emit", ".cache/scan.json"], tmp_workspace)

    run(["python", "devmind.py", "rules",
         "--scan", ".cache/scan.json",
         "--emit", ".cache/scores.json"], tmp_workspace)

    run(["python", "devmind.py", "cluster",
         "--scores", ".cache/scores.json",
         "--emit", ".cache/projects.json"], tmp_workspace)

    target = tmp_workspace/"PROJECTS_STRUCT"
    journal = tmp_workspace/".cache/journal.jsonl"
    run(["python", "devmind.py", "organize",
         "--projects", ".cache/projects.json",
         "--scores", ".cache/scores.json",
         "--target", str(target),
         "--mode", "move",
         "--conflict", "version",
         "--journal", str(journal)], tmp_workspace)

    # 같은 이름 dup.txt 두 개가 모두 존재(해시 서픽스)해야 함
    dup_candidates = list(target.rglob("**/dup__*.txt"))
    assert len(dup_candidates) == 2, "중복 파일 2개 모두 버전 보존되어야 함"
