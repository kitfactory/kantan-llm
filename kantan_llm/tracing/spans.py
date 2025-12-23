from __future__ import annotations

import abc
import contextvars
from typing import Any, Generic, TypeVar, TypedDict

from . import util
from .processor_interface import TracingProcessor
from .scope import Scope
from .span_data import SpanData

TSpanData = TypeVar("TSpanData", bound=SpanData)


class SpanError(TypedDict):
    """Span error payload. / Spanエラーペイロード。"""

    message: str
    data: dict[str, Any] | None


class Span(abc.ABC, Generic[TSpanData]):
    """Trace span. / Trace内のSpan。"""

    @property
    @abc.abstractmethod
    def trace_id(self) -> str: ...

    @property
    @abc.abstractmethod
    def span_id(self) -> str: ...

    @property
    @abc.abstractmethod
    def span_data(self) -> TSpanData: ...

    @property
    @abc.abstractmethod
    def parent_id(self) -> str | None: ...

    @property
    @abc.abstractmethod
    def started_at(self) -> str | None: ...

    @property
    @abc.abstractmethod
    def ended_at(self) -> str | None: ...

    @abc.abstractmethod
    def start(self, mark_as_current: bool = False) -> None: ...

    @abc.abstractmethod
    def finish(self, reset_current: bool = False) -> None: ...

    @abc.abstractmethod
    def set_error(self, error: SpanError) -> None: ...

    @property
    @abc.abstractmethod
    def error(self) -> SpanError | None: ...

    @abc.abstractmethod
    def export(self) -> dict[str, Any] | None: ...

    @abc.abstractmethod
    def __enter__(self) -> "Span[TSpanData]": ...

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb): ...


class NoOpSpan(Span[TSpanData]):
    """No-op span. / 無効時のno-op Span。"""

    __slots__ = ("_span_data", "_prev_span_token")

    def __init__(self, span_data: TSpanData) -> None:
        self._span_data = span_data
        self._prev_span_token: contextvars.Token[Any | None] | None = None

    @property
    def trace_id(self) -> str:
        return "no-op"

    @property
    def span_id(self) -> str:
        return "no-op"

    @property
    def span_data(self) -> TSpanData:
        return self._span_data

    @property
    def parent_id(self) -> str | None:
        return None

    @property
    def started_at(self) -> str | None:
        return None

    @property
    def ended_at(self) -> str | None:
        return None

    def start(self, mark_as_current: bool = False) -> None:
        if mark_as_current:
            self._prev_span_token = Scope.set_current_span(self)

    def finish(self, reset_current: bool = False) -> None:
        if reset_current and self._prev_span_token is not None:
            Scope.reset_current_span(self._prev_span_token)
            self._prev_span_token = None

    def set_error(self, error: SpanError) -> None:
        return

    @property
    def error(self) -> SpanError | None:
        return None

    def export(self) -> dict[str, Any] | None:
        return None

    def __enter__(self) -> "Span[TSpanData]":
        self.start(mark_as_current=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(reset_current=True)


class SpanImpl(Span[TSpanData]):
    """Recorded span. / 記録対象Span。"""

    __slots__ = (
        "_trace_id",
        "_span_id",
        "_parent_id",
        "_started_at",
        "_ended_at",
        "_error",
        "_processor",
        "_span_data",
        "_prev_span_token",
    )

    def __init__(
        self,
        trace_id: str,
        span_id: str | None,
        parent_id: str | None,
        processor: TracingProcessor,
        span_data: TSpanData,
    ) -> None:
        self._trace_id = trace_id
        self._span_id = span_id or util.gen_span_id()
        self._parent_id = parent_id
        self._processor = processor
        self._span_data = span_data
        self._started_at: str | None = None
        self._ended_at: str | None = None
        self._error: SpanError | None = None
        self._prev_span_token: contextvars.Token[Any | None] | None = None

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def span_id(self) -> str:
        return self._span_id

    @property
    def span_data(self) -> TSpanData:
        return self._span_data

    @property
    def parent_id(self) -> str | None:
        return self._parent_id

    @property
    def started_at(self) -> str | None:
        return self._started_at

    @property
    def ended_at(self) -> str | None:
        return self._ended_at

    def start(self, mark_as_current: bool = False) -> None:
        if self._started_at is not None:
            return
        self._started_at = util.time_iso()
        self._processor.on_span_start(self)
        if mark_as_current:
            self._prev_span_token = Scope.set_current_span(self)

    def finish(self, reset_current: bool = False) -> None:
        if self._ended_at is not None:
            return
        self._ended_at = util.time_iso()
        self._processor.on_span_end(self)
        if reset_current and self._prev_span_token is not None:
            Scope.reset_current_span(self._prev_span_token)
            self._prev_span_token = None

    def set_error(self, error: SpanError) -> None:
        self._error = error

    @property
    def error(self) -> SpanError | None:
        return self._error

    def export(self) -> dict[str, Any] | None:
        return {
            "object": "trace.span",
            "id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self._parent_id,
            "started_at": self._started_at,
            "ended_at": self._ended_at,
            "span_data": self.span_data.export(),
            "error": self._error,
        }

    def __enter__(self) -> "Span[TSpanData]":
        self.start(mark_as_current=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(reset_current=exc_type is not GeneratorExit)

