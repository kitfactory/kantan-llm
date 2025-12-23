from __future__ import annotations

import os
import re


# Japanese/English: hyphen/underscoreも許容 / allow hyphen/underscore too.
_RE_SK = re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")
_RE_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._-]{10,}\b")
_RE_API_KEY = re.compile(r"\bapi_key\s*[:=]\s*([A-Za-z0-9._-]{6,})\b", re.IGNORECASE)


def _max_chars_from_env() -> int | None:
    raw = os.getenv("KANTAN_LLM_TRACING_MAX_CHARS")
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def sanitize_text(text: str) -> str:
    """Mask secrets and optionally truncate. / 秘匿値の簡易マスク + 任意の省略。"""

    masked = _RE_SK.sub("sk-***", text)
    masked = _RE_BEARER.sub("Bearer ***", masked)
    masked = _RE_API_KEY.sub("api_key=***", masked)

    max_chars = _max_chars_from_env()
    if max_chars is None:
        return masked
    if len(masked) <= max_chars:
        return masked
    # Japanese/English: 省略はidempotentにする / Make truncation idempotent.
    return masked[:max_chars]
