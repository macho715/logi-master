'''Streamlit 대시보드 컴포넌트(KR). Streamlit dashboard components (EN).'''

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, TypedDict


class _PipelineConfigData(TypedDict):
    base_path: Path
    cache_path: Path
    reports_path: Path
    target_path: str


@dataclass(slots=True)
class PipelineConfig:
    '''대시보드 파이프라인 설정을 보관 · Hold dashboard pipeline configuration.'''

    base_path: Path = field(default_factory=lambda: Path.cwd())
    cache_path: Path = field(default_factory=lambda: Path.cwd() / '.cache')
    reports_path: Path = field(default_factory=lambda: Path.cwd() / 'reports')
    target_path: str = field(default_factory=lambda: str(Path.cwd() / 'PROJECTS_STRUCT'))
    config_file: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        '''필수 디렉터리를 보장 · Ensure required directories exist.'''

        if self.config_file:
            parsed = self._parse_config(self.config_file)
            self.base_path = parsed['base_path']
            self.cache_path = parsed['cache_path']
            self.reports_path = parsed['reports_path']
            self.target_path = parsed['target_path']
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        Path(self.target_path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_config(config_file: Path | str) -> _PipelineConfigData:
        '''설정 파일을 파싱 · Parse configuration file.'''

        import yaml

        cfg_path = Path(config_file)
        data = yaml.safe_load(cfg_path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('configuration must be a mapping')
        base = cfg_path.parent
        return {
            'base_path': base,
            'cache_path': Path(data.get('cache_path', base / '.cache')),
            'reports_path': Path(data.get('reports_path', base / 'reports')),
            'target_path': str(Path(data.get('target_path', base / 'PROJECTS_STRUCT'))),
        }

    @classmethod
    def from_file(cls, config_file: Path) -> 'PipelineConfig':
        '''설정 파일을 로드 · Load configuration file.'''

        parsed = cls._parse_config(config_file)
        return cls(
            base_path=parsed['base_path'],
            cache_path=parsed['cache_path'],
            reports_path=parsed['reports_path'],
            target_path=parsed['target_path'],
            config_file=config_file,
        )


@dataclass(slots=True)
class PipelineRunner:
    '''파이프라인 실행기를 관리 · Manage pipeline runner.'''

    config: PipelineConfig
    is_running: bool = False

    def run_pipeline(self, mode: str) -> bool:
        '''지정 모드로 파이프라인 실행 · Run pipeline with mode.'''

        if mode not in {'local', 'gpt'}:
            raise ValueError('Invalid mode')
        self.is_running = True
        try:
            result = subprocess.run(
                ['python', 'devmind.py', 'run', '--mode', mode],
                cwd=self.config.base_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        finally:
            self.is_running = False


@dataclass(slots=True)
class StatusDisplay:
    '''파이프라인 상태를 추적 · Track pipeline status.'''

    current_status: str = 'Idle'
    progress: int = 0

    def update_status(self, status: str, progress: int) -> None:
        '''상태와 진척을 갱신 · Update status and progress.'''

        self.current_status = status
        self.progress = progress

    def reset(self) -> None:
        '''초기 상태로 되돌림 · Reset to initial state.'''

        self.current_status = 'Idle'
        self.progress = 0


@dataclass(slots=True)
class LogDisplay:
    '''로그 출력을 관리 · Manage log output.'''

    max_lines: int = 800
    lines: List[str] = field(default_factory=list)

    def add_line(self, line: str) -> None:
        '''로그 라인을 추가 · Append log line.'''

        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            overflow = len(self.lines) - self.max_lines
            del self.lines[:overflow]

    def clear(self) -> None:
        '''로그를 비움 · Clear logs.'''

        self.lines.clear()


@dataclass(slots=True)
class SidebarControls:
    '''사이드바 제어 상태 · Sidebar control state.'''

    mode: str = 'LOCAL'
    run_button_clicked: bool = False
    clear_button_clicked: bool = False

    def validate_mode(self) -> bool:
        '''GPT 모드 사용 가능 여부 확인 · Validate GPT mode availability.'''

        if self.mode.upper() != 'GPT':
            return True
        return bool(os.environ.get('OPENAI_API_KEY'))

    def reset_buttons(self) -> None:
        '''버튼 상태 초기화 · Reset button state.'''

        self.run_button_clicked = False
        self.clear_button_clicked = False


__all__ = [
    'PipelineConfig',
    'PipelineRunner',
    'StatusDisplay',
    'LogDisplay',
    'SidebarControls',
]
