"""
GPT 클러스터링을 위한 토큰 기반 배치 처리 유틸리티
"""

import json
import asyncio
from typing import Dict, Any, List, Sequence


def sha256_string(s: str) -> str:
    """문자열의 SHA256 해시 반환"""
    import hashlib

    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def extract_sample_text(item: dict, limit_chars: int = 200) -> str:
    """아이템에서 샘플 텍스트를 추출"""
    # content 필드에서 텍스트 추출
    content = item.get("content", "")
    if isinstance(content, str):
        return content[:limit_chars]

    # sample 필드가 있으면 사용
    sample = item.get("sample", "")
    if isinstance(sample, str):
        return sample[:limit_chars]

    # name 필드 사용
    name = item.get("name", "")
    if isinstance(name, str):
        return name[:limit_chars]

    return ""


# ── 간단한 토큰 카운터: 외부 의존 없게 평균치 기반
class SimpleEncoder:
    def __init__(self, avg_chars_per_token: int = 4):
        self.k = max(1, int(avg_chars_per_token))

    def count_text_tokens(self, text: str) -> int:
        # 너무 복잡하게 가지 말고 대략치(문자/평균)로 처리
        return max(1, len(text) // self.k)

    def count_item_tokens(self, item: dict) -> int:
        name = item.get("name", "")
        sample = item.get("sample", "")
        # 필요한 필드만 합산
        return (
            self.count_text_tokens(name) + self.count_text_tokens(sample) + 8
        )  # 여유 토큰


def serialize_min_item(item: dict, max_sample_chars: int = 200) -> dict:
    # id가 없으면 path에서 생성
    item_id = item.get("id")
    if not item_id and "path" in item:
        item_id = sha256_string(item["path"])

    # sample이 없으면 extract_sample_text로 생성
    sample = item.get("sample", "")
    if not sample:
        sample = extract_sample_text(item, limit_chars=max_sample_chars)

    return {
        "id": item_id,
        "name": (item.get("name") or "")[:120],
        "sample": sample[:max_sample_chars],
    }


def extract_sample_text(item: Dict[str, Any], limit_chars: int = 800) -> str:
    """아이템에서 샘플 텍스트 추출 (멀티바이트 안전)"""
    # 파일 내용이 있다면 앞부분 추출
    if "content" in item and item["content"]:
        content = item["content"]
        if isinstance(content, str):
            # 멀티바이트 안전하게 자르기
            sample = content[:limit_chars]
            # 마지막 문자가 중간에 잘렸을 수 있으므로 마지막 완전한 라인까지만
            if len(content) > limit_chars:
                last_newline = sample.rfind("\n")
                if last_newline > limit_chars // 2:  # 너무 짧게 자르지 않도록
                    sample = sample[:last_newline]
            return sample

    # 파일명 기반 힌트
    name = item.get("name", "")
    if name:
        return f"File: {name}"

    return "No content available"


def pack_items_by_tokens(
    items, max_tokens: int, encoder: SimpleEncoder
) -> list[list[dict]]:
    """토큰 예산 기준 배치 생성 (NDJSON 전송 전에 아이템 수를 안정화)"""
    batch, used = [], 0
    out = []
    for it in items:
        lean = serialize_min_item(it)
        # lean이 dict인지 확인
        if isinstance(lean, dict):
            t = encoder.count_item_tokens(lean)
        else:
            # 문자열인 경우 dict로 변환 시도
            try:
                lean_dict = json.loads(lean) if isinstance(lean, str) else lean
                t = encoder.count_item_tokens(lean_dict)
            except:
                # 변환 실패 시 기본값 사용
                t = 100  # 기본 토큰 수
                lean = {"id": str(hash(str(lean))), "name": "", "sample": ""}

        if batch and used + t > max_tokens:
            out.append(batch)
            batch, used = [], 0
        batch.append(lean)
        used += t
    if batch:
        out.append(batch)
    return out


def _split_in_half(seq: list[dict]) -> tuple[list[dict], list[dict]]:
    mid = len(seq) // 2
    return seq[:mid], seq[mid:]


def send_with_retry_new(
    batch_items: list[dict], api_call, min_batch_size: int = 1, max_retry: int = 5
):
    """
    - 400(페이로드 초과) 시 자동 분할
    - 429/일시 오류는 지수 백오프
    - api_call: (list[dict]) -> list[dict]
    """

    def backoff(n):
        import time, random

        time.sleep(min(2 ** min(n, 5) * 0.2 + random.random() * 0.1, 4.0))

    # 지역 재귀
    def _run(items, depth=0):
        try:
            return api_call(items)
        except Exception as e:
            msg = str(e)
            # 401은 즉시 상위로 전파 (재시도 불가)
            if "401" in msg or "Unauthorized" in msg:
                raise
            if "HTTP400" in msg or "payload too large" in msg.lower():
                if len(items) <= min_batch_size:
                    # 더 못 줄이면 호출자에게 알림(혹은 상위 폴백)
                    raise
                left, right = _split_in_half(items)
                return _run(left, depth + 1) + _run(right, depth + 1)
            if "429" in msg or "Too Many Requests" in msg:
                backoff(depth + 1)
                return _run(items, depth + 1)
            # 기타 일시 오류 대응(선택)
            if (
                any(k in msg for k in ("timeout", "temporarily", "EOF"))
                and depth < max_retry
            ):
                backoff(depth + 1)
                return _run(items, depth + 1)
            raise

    return _run(batch_items)


# 간단한 동시성 수립
async def bounded_gather(jobs, max_concurrency: int = 4):
    sem = asyncio.Semaphore(max_concurrency)

    async def run(job):
        async with sem:
            return await job()

    return await asyncio.gather(*[run(j) for j in jobs])
