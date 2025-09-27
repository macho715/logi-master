'''시간대 유틸리티(KR). Timezone utilities (EN).'''

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DUBAI_TZ = ZoneInfo('Asia/Dubai')


def dubai_now() -> str:
    '''두바이 기준 현재 시각을 ISO8601로 반환 · Return Dubai now as ISO8601.'''

    return datetime.now(tz=DUBAI_TZ).isoformat(timespec='seconds')


__all__ = ['dubai_now', 'DUBAI_TZ']
