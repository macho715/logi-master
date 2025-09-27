import subprocess
from pathlib import Path

def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r

def test_rollback(tmp_path):
    ws = tmp_path/"ws"; (ws/"A").mkdir(parents=True); (ws/"TARGET").mkdir()
    (ws/"A"/"f.md").write_text("# a")

    # devmind.py의 절대 경로 사용
    devmind_path = Path(__file__).parent.parent / "devmind.py"
    run(["python", str(devmind_path), "scan", "--paths", str(ws/"A"), "--emit", ".cache/scan.json", "--safe-map", ".cache/safe_map.json"], ws)
    run(["python", str(devmind_path), "rules", "--scan", ".cache/scan.json", "--emit", ".cache/scores.json"], ws)
    run(["python", str(devmind_path), "cluster", "--scores", ".cache/scores.json", "--emit", ".cache/projects.json", "--project-mode", "local"], ws)
    run(["python", str(devmind_path), "organize", "--projects", ".cache/projects.json", "--scores", ".cache/scores.json", "--target", str(ws/"TARGET"), "--mode", "move", "--conflict", "version", "--journal", ".cache/journal.jsonl"], ws)
    run(["python", str(devmind_path), "rollback", "--journal", ".cache/journal.jsonl"], ws)

    assert (ws/"A"/"f.md").exists()
