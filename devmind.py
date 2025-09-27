'''DevMind 호환 래퍼(KR). DevMind compatibility wrapper (EN).'''

from __future__ import annotations

import sys
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping, Sequence

# Ensure local packages are discoverable when copied to temp workspace
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
parent = CURRENT_DIR.parent
if str(parent) not in sys.path:
    sys.path.insert(0, str(parent))

from cli.devmind import main  # noqa: E402  pylint: disable=wrong-import-position

DEFAULT_HINTS: Sequence[str] = (
    'hvdc',
    'warehouse',
    'ontology',
    'mcp',
    'cursor',
    'layoutapp',
    'ldg',
    'logi',
    'stow',
)


def _choose_project_label(parts: Sequence[str]) -> str:
    '''경로에서 프로젝트 레이블을 추출 · Derive project label from path parts.'''

    ignore = {'src', 'scripts', 'docs', 'tests', 'data', 'tmp'}
    for part in reversed(parts[:-1]):
        if not part:
            continue
        normalized = ''.join(ch.lower() for ch in part if ch.isalnum())
        if normalized and normalized not in ignore:
            return normalized
    return 'project'


def local_cluster(
    items: Sequence[Mapping[str, Any]], k: int = 1, hints: Sequence[str] | None = None
) -> dict[str, Any]:
    '''로컬 규칙 기반 간이 클러스터링 · Lightweight local clustering.'''

    hints = tuple(hints or DEFAULT_HINTS)
    clusters: dict[str, dict[str, Any]] = {}
    for item in items:
        raw_path = str(item.get('path', ''))
        if '\\' in raw_path or ':' in raw_path:
            parts = tuple(str(p) for p in PureWindowsPath(raw_path).parts if str(p))
        else:
            parts = tuple(str(p) for p in Path(raw_path).parts if str(p))
        label = _choose_project_label(parts) if parts else 'project'
        bucket = item.get('bucket', 'misc')
        key = f'{label}-{bucket}' if k > 1 else label
        cluster = clusters.setdefault(
            key,
            {
                'project_id': label,
                'project_label': label,
                'files': [],
            },
        )
        cluster['files'].append(dict(item))
    return {'mode': 'local', 'projects': list(clusters.values()), 'hints': list(hints)}


__all__ = ['DEFAULT_HINTS', 'local_cluster', 'main']


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
