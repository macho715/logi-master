# tests/test_rules.py
import json
import subprocess
from pathlib import Path

def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r

def test_rules_bucket_basic(tmp_workspace):
    # 1) scan
    run(["python", "devmind.py", "scan",
         "--paths", str(tmp_workspace/"C_HVDC_PJT"),
         "--paths", str(tmp_workspace/"C_cursor_mcp"),
         "--emit", ".cache/scan.json"], tmp_workspace)
    # 2) rules
    run(["python", "devmind.py", "rules",
         "--scan", ".cache/scan.json",
         "--emit", ".cache/scores.json"], tmp_workspace)

    data = json.loads((tmp_workspace/".cache/scores.json").read_text(encoding="utf-8"))
    # 기대: README.md -> docs, run_job.ps1 -> scripts, tool.py -> src|tmp(간단규칙상 .py는 src로 태깅)
    byname = {x["name"]: x for x in data if "name" in x}
    assert byname["README.md"]["bucket"] == "docs"
    assert byname["run_job.ps1"]["bucket"] == "scripts"
    assert byname["tool.py"]["bucket"] in ("src", "tmp")  # 규칙 수정해도 유연하게
