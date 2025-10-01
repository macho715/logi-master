"""보고서 생성기 모듈 / Report builder module."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Sequence, Tuple

from openpyxl import Workbook

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in CI
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

QUEUE_PATH = Path('work/queue.json')
REPORT_XLSX = Path('work/daily_report.xlsx')
REPORT_TXT = Path('work/daily_summary.txt')
SAMPLE_DIR = Path('work/sample_attachments')
LOG_PATH = Path('logs/report_builder.log')

KEYWORDS = ['invoice', 'pl', 'vendor', 'otif', 'urgent', 'news']
TODO_PATTERN = re.compile(r'(?i)(?:TODO[:\-]\s*|TODO\s+)(.+)')


@dataclass(slots=True)
class QueuedMessage:
    """큐 메시지 구조 / Queued message structure."""

    entry_id: str
    subject: str
    sender: str
    received_time: str
    folder_path: str
    attachments: List[str]
    created_at: str
    processed_at: Optional[str] = None


class OCRAdapter(Protocol):
    """OCR 어댑터 인터페이스 / OCR adapter interface."""

    def extract_text(self, path: Path) -> str:
        """첨부 텍스트 추출 / Extract text from attachment."""


class TesseractOCRAdapter:
    """Tesseract OCR 구현 / Tesseract OCR implementation."""

    def extract_text(self, path: Path) -> str:
        """Tesseract로 텍스트 추출 / Extract text using Tesseract."""
        if pytesseract is None or Image is None:
            raise RuntimeError('pytesseract and Pillow are required for image OCR.')
        image = Image.open(path)
        return pytesseract.image_to_string(image)


class AbbyyOCRAdapter:
    """ABBYY OCR 어댑터 스텁 / ABBYY OCR adapter stub."""

    def __init__(self) -> None:
        """초기화 자리표시자 / Placeholder initialiser."""
        # REQUIRES_SECRETS_HANDLING: Configure ABBYY credentials via environment variables.

    def extract_text(self, path: Path) -> str:
        """ABBYY 서비스 연동 TODO / TODO integrate ABBYY service."""
        raise NotImplementedError('Plug in ABBYY Cloud OCR SDK client here.')


class PlainTextAdapter:
    """텍스트 파일 추출 어댑터 / Plain text extraction adapter."""

    def extract_text(self, path: Path) -> str:
        """텍스트 파일을 그대로 읽기 / Read text file as-is."""
        return path.read_text(encoding='utf-8', errors='ignore')


def ensure_environment() -> None:
    """필수 경로를 준비 / Prepare required paths."""
    REPORT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_logging(verbose: bool) -> None:
    """로그 설정 초기화 / Initialise log configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_queue() -> List[QueuedMessage]:
    """큐 파일을 불러오기 / Load queue file."""
    if not QUEUE_PATH.exists():
        return []
    with QUEUE_PATH.open('r', encoding='utf-8') as handle:
        raw_items = json.load(handle)
    messages: List[QueuedMessage] = []
    for item in raw_items:
        messages.append(
            QueuedMessage(
                entry_id=item['entry_id'],
                subject=item['subject'],
                sender=item['sender'],
                received_time=item['received_time'],
                folder_path=item.get('folder_path', ''),
                attachments=list(item.get('attachments', [])),
                created_at=item.get('created_at', datetime.utcnow().isoformat()),
                processed_at=item.get('processed_at'),
            )
        )
    return messages


def persist_queue(messages: Iterable[QueuedMessage]) -> None:
    """큐 파일을 업데이트 / Update queue file."""
    serialized = [asdict(message) for message in messages]
    with QUEUE_PATH.open('w', encoding='utf-8') as handle:
        json.dump(serialized, handle, indent=2, ensure_ascii=False)


def pick_ocr_adapter(prefer_abbyy: bool = False) -> OCRAdapter:
    """OCR 어댑터 선택 / Choose OCR adapter."""
    if prefer_abbyy:
        logging.info('Using ABBYY OCR adapter placeholder.')
        return AbbyyOCRAdapter()
    return TesseractOCRAdapter()


def extract_text_from_attachment(path: Path, adapter: OCRAdapter) -> str:
    """첨부 파일에서 텍스트 추출 / Extract text from attachment."""
    suffix = path.suffix.lower()
    if suffix in {'.txt', '.log', '.csv'}:
        return PlainTextAdapter().extract_text(path)
    try:
        return adapter.extract_text(path)
    except Exception as exc:
        logging.warning('Failed OCR for %s: %s', path.name, exc)
        return PlainTextAdapter().extract_text(path)


def extract_intel(text: str) -> Tuple[List[str], List[str]]:
    """키워드와 할 일을 추출 / Extract keywords and TODOs."""
    todos = [match.strip() for match in TODO_PATTERN.findall(text)]
    found_keywords = []
    lowered = text.lower()
    for keyword in KEYWORDS:
        if keyword in lowered:
            found_keywords.append(keyword.upper())
    return found_keywords, todos


def build_summary(messages: Sequence[QueuedMessage], prefer_abbyy: bool, limit: Optional[int]) -> None:
    """요약 보고서를 생성 / Build summary report."""
    adapter = pick_ocr_adapter(prefer_abbyy)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Daily Summary'
    sheet.append([
        'Entry ID',
        'Subject',
        'Sender',
        'Received',
        'Keywords',
        'Todos',
        'Attachment Count',
    ])
    summary_lines: List[str] = []
    processed: int = 0
    for message in messages:
        if message.processed_at is not None:
            continue
        if limit is not None and processed >= limit:
            break
        aggregated_text = ''
        for attachment in message.attachments:
            attachment_path = Path(attachment)
            if not attachment_path.exists():
                fallback_path = SAMPLE_DIR / attachment_path.name
                if fallback_path.exists():
                    attachment_path = fallback_path
            if not attachment_path.exists():
                logging.warning('Attachment missing: %s', attachment)
                continue
            aggregated_text += '\n' + extract_text_from_attachment(attachment_path, adapter)
        keywords, todos = extract_intel(aggregated_text)
        sheet.append([
            message.entry_id,
            message.subject,
            message.sender,
            message.received_time,
            ', '.join(keywords) or 'N/A',
            '; '.join(todos) or 'None',
            len(message.attachments),
        ])
        summary_lines.append(
            f"Subject: {message.subject}\nSender: {message.sender}\nKeywords: {', '.join(keywords) or 'N/A'}\n"
            f"Todos: {'; '.join(todos) or 'None'}\n---"
        )
        message.processed_at = datetime.utcnow().isoformat()
        processed += 1
    workbook.save(REPORT_XLSX)
    REPORT_TXT.write_text('\n'.join(summary_lines) if summary_lines else 'No new items.', encoding='utf-8')
    persist_queue(messages)
    logging.info('Report generated with %s messages.', processed)


def seed_sample_queue() -> None:
    """샘플 큐 데이터를 준비 / Prepare sample queue data."""
    ensure_environment()
    samples = [
        SAMPLE_DIR / 'sample_invoice.txt',
        SAMPLE_DIR / 'sample_status.txt',
    ]
    for sample in samples:
        if not sample.exists():
            raise FileNotFoundError(f'Missing sample attachment: {sample}')
    sample_entry = QueuedMessage(
        entry_id='SAMPLE-ENTRY-001',
        subject='Sample Logistics Digest',
        sender='sample@logi.dev',
        received_time=datetime.utcnow().isoformat(),
        folder_path='Sample/Auto-Reports',
        attachments=[str(path) for path in samples],
        created_at=datetime.utcnow().isoformat(),
    )
    persist_queue([sample_entry])


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """명령줄 인자 파싱 / Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate daily Outlook auto-report summary.')
    parser.add_argument('--prefer-abbyy', action='store_true', help='Prefer ABBYY OCR adapter (placeholder).')
    parser.add_argument('--limit', type=int, default=None, help='Process only the first N unprocessed messages.')
    parser.add_argument('--sample', action='store_true', help='Seed queue with bundled sample attachments.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging output.')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """메인 실행 함수 / Main execution function."""
    args = parse_args(argv)
    ensure_environment()
    init_logging(args.verbose)
    if args.sample:
        logging.info('Seeding sample queue data.')
        seed_sample_queue()
    messages = load_queue()
    build_summary(messages, args.prefer_abbyy, args.limit)
    print(f'Report written to {REPORT_XLSX} and {REPORT_TXT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
