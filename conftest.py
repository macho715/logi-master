'''KR: 테스트 워크스페이스 픽스처. EN: Pytest workspace fixture.'''

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    '''임시 워크스페이스를 구성한다(KR). Provision a temporary workspace for tests (EN).'''

    ws = tmp_path / 'ws'
    (ws / 'C_HVDC_PJT').mkdir(parents=True)
    (ws / 'C_cursor_mcp').mkdir(parents=True)
    (ws / 'PROJECTS_STRUCT').mkdir(parents=True)
    # 샘플 파일
    (ws / 'C_HVDC_PJT' / 'README.md').write_text('# INSTALLATION GUIDE\n', encoding='utf-8')
    (ws / 'C_HVDC_PJT' / 'run_job.ps1').write_text('Write-Host \'run\'\n', encoding='utf-8')
    (ws / 'C_HVDC_PJT' / 'analysis_report.txt').write_text('final report\n', encoding='utf-8')
    (ws / 'C_cursor_mcp' / 'tool.py').write_text('print(\'tool\')\n', encoding='utf-8')
    (ws / 'C_cursor_mcp' / 'test_sample.py').write_text('import pytest\n', encoding='utf-8')
    # 동일 이름 다른 내용(중복 보존 확인용)
    (ws / 'C_cursor_mcp' / 'dup.txt').write_text('A\n', encoding='utf-8')
    (ws / 'C_HVDC_PJT' / 'dup.txt').write_text('B\n', encoding='utf-8')
    repo_root = Path(__file__).resolve().parent
    shutil.copy2(repo_root / 'devmind.py', ws / 'devmind.py')
    for package in ('logi', 'core', 'cli'):
        package_root = repo_root / package
        if package_root.exists():
            shutil.copytree(package_root, ws / package, dirs_exist_ok=True)
    resources_root = repo_root / 'resources'
    if resources_root.exists():
        shutil.copytree(resources_root, ws / 'resources', dirs_exist_ok=True)
    fixtures_root = repo_root / 'tests' / 'fixtures'
    if fixtures_root.exists():
        shutil.copytree(fixtures_root, ws / 'fixtures', dirs_exist_ok=True)
    sitecustomize_path = repo_root / 'sitecustomize.py'
    if sitecustomize_path.exists():
        shutil.copy2(sitecustomize_path, ws / 'sitecustomize.py')
    for template in ('rules.yml', 'schema.yml', 'agents.json'):
        template_path = repo_root / template
        if template_path.exists():
            shutil.copy2(template_path, ws / template)
    return ws
