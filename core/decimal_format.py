'''소수 포맷 헬퍼(KR). Decimal formatting helpers (EN).'''

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Union

NumberLike = Union[str, int, float, Decimal]


def format_2d(value: NumberLike) -> str:
    '''값을 두 자리 소수 문자열로 변환한다 · Convert value to 2-decimal string.'''

    if isinstance(value, Decimal):
        decimal_value = value
    else:
        decimal_value = Decimal(str(value))
    quantized = decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f'{quantized:.2f}'


__all__ = ['format_2d', 'NumberLike']
