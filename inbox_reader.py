"""Outlook 자동 보고서 큐 수집기 / Outlook auto-report queue collector."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    import pywintypes  # type: ignore
    import win32com.client  # type: ignore
except ImportError:  # pragma: no cover - Windows only dependency
    win32com = None  # type: ignore
    pywintypes = None  # type: ignore

QUEUE_PATH = Path('work/queue.json')
ATTACHMENTS_DIR = Path('work/attachments')
LOG_PATH = Path('logs/inbox_reader.log')
DEFAULT_FOLDER = 'Auto/Inbox/Auto-Reports'


@dataclass(slots=True)
class MessageMetadata:
    """메시지 메타데이터 구조 / Message metadata structure."""

    entry_id: str
    subject: str
    sender: str
    received_time: str
    folder_path: str
    attachments: List[str]
    created_at: str


def ensure_environment() -> None:
    """필수 디렉터리를 보장 / Ensure required directories exist."""
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_queue() -> Dict[str, MessageMetadata]:
    """큐 파일을 불러오기 / Load queue file into memory."""
    if not QUEUE_PATH.exists():
        return {}
    with QUEUE_PATH.open('r', encoding='utf-8') as queue_file:
        raw_items = json.load(queue_file)
    loaded: Dict[str, MessageMetadata] = {}
    for item in raw_items:
        entry_id = item['entry_id']
        loaded[entry_id] = MessageMetadata(
            entry_id=entry_id,
            subject=item['subject'],
            sender=item['sender'],
            received_time=item['received_time'],
            folder_path=item.get('folder_path', DEFAULT_FOLDER),
            attachments=list(item.get('attachments', [])),
            created_at=item.get('created_at', datetime.utcnow().isoformat()),
        )
    return loaded


def persist_queue(items: Iterable[MessageMetadata]) -> None:
    """큐 파일을 저장 / Persist queue file to disk."""
    serialized = [asdict(item) for item in items]
    with QUEUE_PATH.open('w', encoding='utf-8') as queue_file:
        json.dump(serialized, queue_file, indent=2, ensure_ascii=False)


def init_logging(verbose: bool) -> None:
    """로그 설정을 초기화 / Initialise log configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )


def detect_new_outlook_error(exc: Exception) -> bool:
    """New Outlook 여부 감지 / Detect whether New Outlook is implied."""
    message = str(exc)
    return 'new outlook' in message.lower() or 'class not registered' in message.lower()


def connect_namespace() -> Optional[object]:
    """Outlook 네임스페이스 연결 / Connect to Outlook namespace."""
    if win32com is None:
        logging.error('pywin32 (win32com) is not available. Install pywin32 on Windows.')
        return None
    try:
        outlook = win32com.Dispatch('Outlook.Application')  # type: ignore[attr-defined]
        namespace = outlook.GetNamespace('MAPI')
        return namespace
    except Exception as exc:  # pragma: no cover - Windows specific flow
        if pywintypes is not None and isinstance(exc, pywintypes.com_error):
            logging.error('COM error when opening Outlook: %s', exc)
            if detect_new_outlook_error(exc):
                logging.error(
                    'Detected failure that matches New Outlook restrictions. '
                    'Switch Outlook to the classic interface or use the fallback export instructions.'
                )
            return None
        if detect_new_outlook_error(exc):
            logging.error(
                'Detected failure that matches New Outlook restrictions. '
                'Switch Outlook to the classic interface or use the fallback export instructions.'
            )
        else:
            logging.exception('Unable to acquire Outlook namespace: %s', exc)
        return None


def resolve_folder(namespace: object, folder_path: str) -> Optional[object]:
    """폴더 경로를 Outlook 폴더로 변환 / Resolve folder path into an Outlook folder."""
    segments = [segment for segment in folder_path.split('/') if segment]
    if not segments:
        logging.error('Folder path %s is invalid.', folder_path)
        return None
    try:
        folder = namespace.Folders.Item(segments[0])
        for segment in segments[1:]:
            folder = folder.Folders.Item(segment)
        return folder
    except Exception as exc:  # pragma: no cover - Windows specific flow
        logging.error('Unable to resolve folder %s: %s', folder_path, exc)
        return None


def download_attachments(message: object, entry_id: str) -> List[str]:
    """첨부파일을 저장 / Download attachments for a message."""
    saved_files: List[str] = []
    target_dir = ATTACHMENTS_DIR / entry_id
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        attachments = getattr(message, 'Attachments', None)
    except Exception:
        attachments = None
    if not attachments:
        return saved_files
    for index in range(1, attachments.Count + 1):  # type: ignore[attr-defined]
        attachment = attachments.Item(index)
        filename = getattr(attachment, 'FileName', f'attachment_{index}')
        safe_name = filename.replace('\\', '_').replace('/', '_')
        target_path = target_dir / safe_name
        try:
            attachment.SaveAsFile(str(target_path))
            saved_files.append(str(target_path))
        except Exception as exc:  # pragma: no cover - Windows specific flow
            logging.error('Failed to save attachment %s: %s', safe_name, exc)
    return saved_files


def collect_messages(folder: object, max_items: Optional[int]) -> List[MessageMetadata]:
    """폴더에서 메시지를 수집 / Collect messages from folder."""
    items: List[MessageMetadata] = []
    raw_items = folder.Items
    raw_items.Sort('[ReceivedTime]', True)
    count = raw_items.Count  # type: ignore[attr-defined]
    limit = min(count, max_items) if max_items else count
    for index in range(1, limit + 1):
        message = raw_items.Item(index)
        entry_id = getattr(message, 'EntryID', f'NO-ID-{index}')
        parent_folder = getattr(message, 'Parent', None)
        folder_path = getattr(parent_folder, 'FullFolderPath', DEFAULT_FOLDER)
        metadata = MessageMetadata(
            entry_id=entry_id,
            subject=str(getattr(message, 'Subject', '')),
            sender=str(getattr(getattr(message, 'Sender', None), 'Name', 'Unknown sender')),
            received_time=str(getattr(message, 'ReceivedTime', '')),
            folder_path=folder_path,
            attachments=download_attachments(message, entry_id),
            created_at=datetime.utcnow().isoformat(),
        )
        items.append(metadata)
    return items


def merge_queue(existing: Dict[str, MessageMetadata], new_items: Iterable[MessageMetadata]) -> int:
    """큐를 업데이트 / Merge queue with new items."""
    added = 0
    for item in new_items:
        if item.entry_id in existing:
            continue
        existing[item.entry_id] = item
        added += 1
    return added


def run(folder_path: str, max_items: Optional[int], dry_run: bool) -> int:
    """메시지 수집기 실행 / Execute message collector."""
    ensure_environment()
    namespace = connect_namespace()
    if namespace is None:
        return 0
    folder = resolve_folder(namespace, folder_path)
    if folder is None:
        return 0
    logging.info('Monitoring folder: %s', folder_path)
    new_messages = collect_messages(folder, max_items)
    if dry_run:
        logging.info('Dry run enabled, skipping queue persistence.')
        return len(new_messages)
    queue_items = load_queue()
    added = merge_queue(queue_items, new_messages)
    if added:
        persist_queue(queue_items.values())
    logging.info('FOUND %s messages (added=%s)', len(new_messages), added)
    return len(new_messages)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """명령줄 인자를 파싱 / Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Outlook Auto-Report inbox reader')
    parser.add_argument('--folder', default=DEFAULT_FOLDER, help='Target Outlook folder path')
    parser.add_argument('--max-items', type=int, default=None, help='Optional maximum items to fetch')
    parser.add_argument('--dry-run', action='store_true', help='Process without writing queue.json')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """모듈 실행 진입점 / Module execution entry point."""
    args = parse_args(argv)
    init_logging(args.verbose)
    count = run(args.folder, args.max_items, args.dry_run)
    print(f'FOUND {count} messages')
    return 0


if __name__ == '__main__':
    sys.exit(main())
