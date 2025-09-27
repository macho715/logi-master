# gpt_cluster/openai_adapter.py
from __future__ import annotations
import os
import json
from typing import List, Dict, Any
from .transport import to_ndjson_lines, post_json_gz, HTTPError

# ──────────────────────────────────────────────────────────────────────────────
# 프롬프트 구성
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a precise labeling assistant.
You MUST output newline-delimited JSON (NDJSON), one JSON object per line.
Each line MUST be: {"id":"<id>","label":"<cluster_label>"}
- Only use ASCII letters, digits, spaces, dashes for labels.
- Keep labels concise (1–4 words).
- Do NOT echo the input.
"""

_USER_INSTRUCTION = """Label each item with a concise cluster label.
Input items (NDJSON, one per line):
{items_ndjson}

Return ONLY NDJSON lines in the same order; no prose, no explanations.
"""


def build_messages_for_chat(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    items: [{"id":..., "name":..., "sample":...}, ...]
    """
    lines = to_ndjson_lines(items)
    user_content = _USER_INSTRUCTION.format(items_ndjson="\n".join(lines))
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI Chat Completions 호출 (NDJSON 응답 파싱)
# ──────────────────────────────────────────────────────────────────────────────


class OpenAIConfig:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_s: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com"
        ).rstrip("/")
        self.timeout_s = timeout_s
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is missing")

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"


def call_openai_ndjson_labels(
    items: List[Dict[str, Any]],
    cfg: OpenAIConfig | None = None,
) -> List[Dict[str, Any]]:
    """
    items를 NDJSON로 프롬프트에 넣어 Chat Completions 호출.
    반환: [{"id": "...", "label": "..."}, ...] (입력 순서 보존)
    - 실패 시 상태코드 문자열 포함된 예외를 던짐 (send_with_retry에서 캐치 가능)
    """
    cfg = cfg or OpenAIConfig()
    messages = build_messages_for_chat(items)

    body = {
        "model": cfg.model,
        "messages": messages,
        "temperature": 0,
        "top_p": 1,
        # 응답 길이 안전장치 (필요 시 조절)
        "max_tokens": 512,
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}"}

    try:
        r = post_json_gz(
            url=cfg.chat_completions_url,
            json_body=body,
            headers=headers,
            timeout_s=cfg.timeout_s,
        )
    except HTTPError as e:
        # 메시지에 식별자 심어 send_with_retry가 분기할 수 있게
        status = e.status
        msg = str(e)
        if status == 401:
            raise ValueError("401: Unauthorized - API key invalid or expired") from e
        if status == 400:
            raise ValueError("HTTP400: payload too large or invalid request") from e
        if status == 429:
            raise ValueError("429: Too Many Requests") from e
        if status in (500, 502, 503, 504):
            raise ValueError(f"{status}: temporarily unavailable") from e
        raise

    data = r.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise ValueError(f"Malformed OpenAI response: {json.dumps(data)[:400]}")

    # 모델이 NDJSON만 내놓도록 강하게 지시했지만, 방어적으로 필터링
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []
    for ln in lines:
        # JSON만 취급
        if not (ln.startswith("{") and ln.endswith("}")):
            # 잡소리/머릿말 줄은 버림
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        # 필수 키만 뽑아서 정규화
        _id = obj.get("id")
        label = obj.get("label")
        if _id is None or label is None:
            continue
        if isinstance(label, str):
            # 라벨 최소 정제: 개행/탭 제거, 과한 길이 컷
            label = " ".join(label.replace("\n", " ").replace("\t", " ").split())[:64]
        out.append({"id": _id, "label": label})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 네 send_with_retry()에서 쓰기 쉽게 감싼 callable
# ──────────────────────────────────────────────────────────────────────────────


def make_api_call_fn(
    model: str | None = None,
    base_url: str | None = None,
    timeout_s: float = 60.0,
):
    """
    사용 예:
      api_call = make_api_call_fn(model="gpt-4o-mini")
      results = send_with_retry(batch_items, api_call=api_call, min_batch_size=1)
    """
    cfg = OpenAIConfig(model=model, base_url=base_url, timeout_s=timeout_s)

    def _call(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return call_openai_ndjson_labels(batch, cfg)

    return _call
