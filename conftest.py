# tests/conftest.py
import os
import shutil
from pathlib import Path
import pytest

@pytest.fixture
def tmp_workspace(tmp_path):
    """
    임시 워크스페이스:
      src_roots: C:\HVDC PJT, C:\cursor-mcp (유사 구조)
      target: C:\PROJECTS_STRUCT (테스트용 tmp 경로)
    """
    ws = tmp_path / "ws"
    (ws / "C_HVDC_PJT").mkdir(parents=True)
    (ws / "C_cursor_mcp").mkdir(parents=True)
    (ws / "PROJECTS_STRUCT").mkdir(parents=True)
    # 샘플 파일
    (ws / "C_HVDC_PJT" / "README.md").write_text("# INSTALLATION GUIDE\n", encoding="utf-8")
    (ws / "C_HVDC_PJT" / "run_job.ps1").write_text("Write-Host 'run'\n", encoding="utf-8")
    (ws / "C_HVDC_PJT" / "analysis_report.txt").write_text("final report\n", encoding="utf-8")
    (ws / "C_cursor_mcp" / "tool.py").write_text("print('tool')\n", encoding="utf-8")
    (ws / "C_cursor_mcp" / "test_sample.py").write_text("import pytest\n", encoding="utf-8")
    # 동일 이름 다른 내용(중복 보존 확인용)
    (ws / "C_cursor_mcp" / "dup.txt").write_text("A\n", encoding="utf-8")
    (ws / "C_HVDC_PJT" / "dup.txt").write_text("B\n", encoding="utf-8")
    return ws
