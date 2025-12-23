from __future__ import annotations

import contextvars
from typing import Any

# Japanese/English: カレントTrace/Spanは contextvars で保持する / Keep current trace/span via contextvars.
_current_trace: contextvars.ContextVar[Any | None] = contextvars.ContextVar("kantan_llm_current_trace", default=None)
_current_span: contextvars.ContextVar[Any | None] = contextvars.ContextVar("kantan_llm_current_span", default=None)


class Scope:
    """Manage current trace/span in context. / 実行コンテキストのTrace/Spanを管理する。"""

    @classmethod
    def get_current_trace(cls) -> Any | None:
        return _current_trace.get()

    @classmethod
    def set_current_trace(cls, trace: Any | None) -> contextvars.Token[Any | None]:
        return _current_trace.set(trace)

    @classmethod
    def reset_current_trace(cls, token: contextvars.Token[Any | None]) -> None:
        _current_trace.reset(token)

    @classmethod
    def get_current_span(cls) -> Any | None:
        return _current_span.get()

    @classmethod
    def set_current_span(cls, span: Any | None) -> contextvars.Token[Any | None]:
        return _current_span.set(span)

    @classmethod
    def reset_current_span(cls, token: contextvars.Token[Any | None]) -> None:
        _current_span.reset(token)

