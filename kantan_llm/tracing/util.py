from __future__ import annotations

from datetime import datetime, timezone
import uuid


def time_iso() -> str:
    """Return the current time in ISO 8601 format. / 現在時刻をISO 8601で返す。"""

    return datetime.now(timezone.utc).isoformat()


def gen_trace_id() -> str:
    """Generate a trace id. / trace_id を生成する。"""

    return f"trace_{uuid.uuid4().hex}"


def gen_span_id() -> str:
    """Generate a span id. / span_id を生成する。"""

    return f"span_{uuid.uuid4().hex[:24]}"

