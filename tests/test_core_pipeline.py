from __future__ import annotations

from pathlib import Path

from core.io import append_jsonl, read_json, read_json_object, read_jsonl
from core.pipeline import (
    apply_rules,
    cluster_projects,
    generate_report,
    organize_projects,
    scan_paths,
)


def test_pipeline_scan_cluster_and_report(tmp_path: Path) -> None:
    '''파이프라인 스캔/리포트 흐름을 검증 · Validate pipeline scan/report flow.'''

    source_dir = tmp_path / 'source'
    cache_dir = tmp_path / 'cache'
    target_dir = tmp_path / 'target'
    safe_map_path = cache_dir / 'safe.json'
    scan_path = cache_dir / 'scan.json'
    scores_path = cache_dir / 'scores.json'
    projects_path = cache_dir / 'projects.json'
    journal_path = cache_dir / 'journal.jsonl'
    report_path = cache_dir / 'report.html'
    source_dir.mkdir()
    cache_dir.mkdir()
    target_dir.mkdir()
    (source_dir / 'README.md').write_text('# readme\n', encoding='utf-8')
    (source_dir / 'test_sample.py').write_text('print(1)\n', encoding='utf-8')
    records = scan_paths([source_dir], emit=scan_path, safe_map_path=safe_map_path)
    assert len(records) == 2
    assert scan_path.exists()
    enriched = apply_rules(records, emit=scores_path)
    assert all('bucket' in row for row in enriched)
    payload = cluster_projects(enriched, emit=projects_path, mode='local')
    assert projects_path.exists()
    projects = payload['projects']
    summary = organize_projects(
        projects, target_dir=target_dir, journal_path=journal_path, mode='copy'
    )
    assert summary['files'] == 2
    assert journal_path.exists()
    generate_report(journal_path, out_path=report_path)
    report_text = report_path.read_text(encoding='utf-8')
    assert 'Project Autosort Summary' in report_text
    assert 'README.md' in report_text


def test_pipeline_generate_report_tail(tmp_path: Path) -> None:
    '''리포트는 마지막 엔트리를 강조한다 · Report includes tail entries.'''

    journal_path = tmp_path / 'journal.jsonl'
    report_path = tmp_path / 'report.html'
    for index in range(25):
        append_jsonl(
            journal_path,
            {
                'timestamp': f'2024-01-01T00:00:{index:02d}',
                'project': f'p-{index}',
                'source': f'source-{index}',
                'destination': f'destination-{index}',
            },
        )
    generate_report(journal_path, out_path=report_path)
    html = report_path.read_text(encoding='utf-8')
    assert 'p-24' in html
    assert 'p-4' not in html


def test_organize_projects_skip_and_version(tmp_path: Path) -> None:
    '''충돌 정책을 검증한다 · Validate conflict policy handling.'''

    target_dir = tmp_path / 'target'
    journal_path = tmp_path / 'journal.jsonl'
    target_dir.mkdir()
    src_one = tmp_path / 'src_one'
    src_two = tmp_path / 'src_two'
    src_one.mkdir()
    src_two.mkdir()
    file_one = src_one / 'a.txt'
    file_two = src_two / 'a.txt'
    file_one.write_text('first', encoding='utf-8')
    file_two.write_text('second', encoding='utf-8')
    sample = {
        'project': 'local_docs',
        'files': [
            {
                'path': str(file_one),
                'name': 'a.txt',
                'bucket': 'docs',
                'safe_id': 'abc1234',
            },
            {
                'path': str(file_two),
                'name': 'a.txt',
                'bucket': 'docs',
                'safe_id': 'zzz9999',
            },
        ],
    }
    summary = organize_projects(
        [sample], target_dir=target_dir, journal_path=journal_path, conflict_policy='version'
    )
    doc_files = sorted(f.name for f in (target_dir / 'docs').iterdir())
    assert summary['files'] == 2
    assert len(doc_files) == 2
    assert journal_path.exists()


def test_scan_paths_persists_safe_map(tmp_path: Path) -> None:
    '''스캔 결과는 JSON과 세이프맵을 기록한다 · Scan persists JSON and safe-map.'''

    source_dir = tmp_path / 'src'
    source_dir.mkdir()
    (source_dir / 'note.txt').write_text('data', encoding='utf-8')
    emit = tmp_path / 'scan.json'
    safe_map_path = tmp_path / 'safe.json'
    records = scan_paths([source_dir], emit=emit, safe_map_path=safe_map_path)
    persisted = read_json(emit)
    safe_map = read_json_object(safe_map_path)
    assert records == persisted
    assert safe_map
    assert list(safe_map.values())[0].endswith('note.txt')


def test_read_jsonl_handles_invalid_lines(tmp_path: Path) -> None:
    '''JSONL 유틸은 잘못된 라인을 무시한다 · JSONL helper skips invalid lines.'''

    payload_path = tmp_path / 'events.jsonl'
    payload_path.write_text('{"ok": 1}\nnot-json\n{"ok": 2}\n', encoding='utf-8')
    entries = read_jsonl(payload_path)
    assert len(entries) == 2
