from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .provider import get_trace_provider
from .sanitize import sanitize_text
from .scope import Scope
from .span_data import CustomSpanData, FunctionSpanData, GenerationSpanData
from .spans import Span
from .traces import Trace


def trace(
    workflow_name: str,
    trace_id: str | None = None,
    group_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    disabled: bool = False,
) -> Trace:
    """Create trace (Agents SDK compatible). / Traceを作成する（Agents SDK互換）。"""

    return get_trace_provider().create_trace(
        name=workflow_name,
        trace_id=trace_id,
        group_id=group_id,
        metadata=metadata,
        disabled=disabled,
    )


def get_current_trace() -> Trace | None:
    """Return current trace. / カレントTraceを返す。"""

    t = Scope.get_current_trace()
    return t  # type: ignore[return-value]


def get_current_span() -> Span[Any] | None:
    """Return current span. / カレントSpanを返す。"""

    s = Scope.get_current_span()
    return s  # type: ignore[return-value]


def custom_span(
    name: str,
    data: dict[str, Any] | None = None,
    span_id: str | None = None,
    parent: Trace | Span[Any] | None = None,
    disabled: bool = False,
) -> Span[CustomSpanData]:
    return get_trace_provider().create_span(
        span_data=CustomSpanData(name=name, data=data),
        span_id=span_id,
        parent=parent,
        disabled=disabled,
    )


def function_span(
    name: str,
    input: str | None = None,
    output: str | None = None,
    span_id: str | None = None,
    parent: Trace | Span[Any] | None = None,
    disabled: bool = False,
) -> Span[FunctionSpanData]:
    return get_trace_provider().create_span(
        span_data=FunctionSpanData(name=name, input=input, output=output),
        span_id=span_id,
        parent=parent,
        disabled=disabled,
    )


def generation_span(
    input: Sequence[Mapping[str, Any]] | str | None = None,
    output: Any | None = None,
    model: str | None = None,
    usage: dict[str, Any] | None = None,
    span_id: str | None = None,
    parent: Trace | Span[Any] | None = None,
    disabled: bool = False,
) -> Span[GenerationSpanData]:
    return get_trace_provider().create_span(
        span_data=GenerationSpanData(input=input, output=output, model=model, usage=usage),
        span_id=span_id,
        parent=parent,
        disabled=disabled,
    )


def dump_for_tracing(value: Any) -> str:
    """Best-effort dump for input/output. / 入出力の簡易ダンプ。"""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    formatted = _format_messages(value)
    if formatted is not None:
        return formatted
    try:
        return json.dumps(value, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return sanitize_text(str(value))


def _format_messages(value: Any) -> str | None:
    # Japanese/English: Chatのmessages配列は読みやすい形式にする / Format chat messages for readability.
    if not isinstance(value, (list, tuple)):
        return None
    lines: list[str] = []
    for item in value:
        role = None
        content = None
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
        if role is None or content is None:
            return None
        lines.append(str(content))
    return "\n".join(lines)


def sanitize_for_tracing(text: str) -> str:
    return sanitize_text(text)
