from __future__ import annotations

import threading
from typing import Any

from .processor_interface import TracingProcessor
from .scope import Scope
from .spans import NoOpSpan, Span, SpanImpl
from .span_data import SpanData
from .traces import NoOpTrace, Trace, TraceImpl


class SynchronousMultiTracingProcessor(TracingProcessor):
    """Forward to multiple processors (non-fatal). / 複数Processorへ転送（非致命）。"""

    def __init__(self) -> None:
        self._processors: tuple[TracingProcessor, ...] = ()
        self._lock = threading.Lock()

    def add_tracing_processor(self, tracing_processor: TracingProcessor) -> None:
        with self._lock:
            self._processors += (tracing_processor,)

    def set_processors(self, processors: list[TracingProcessor]) -> None:
        with self._lock:
            self._processors = tuple(processors)

    def get_processors(self) -> tuple[TracingProcessor, ...]:
        """Return current processors. / 現在のProcessor一覧を返す。"""

        with self._lock:
            return self._processors

    def on_trace_start(self, trace: Trace) -> None:
        for p in self._processors:
            try:
                p.on_trace_start(trace)
            except Exception:
                continue

    def on_trace_end(self, trace: Trace) -> None:
        for p in self._processors:
            try:
                p.on_trace_end(trace)
            except Exception:
                continue

    def on_span_start(self, span: Span[Any]) -> None:
        for p in self._processors:
            try:
                p.on_span_start(span)
            except Exception:
                continue

    def on_span_end(self, span: Span[Any]) -> None:
        for p in self._processors:
            try:
                p.on_span_end(span)
            except Exception:
                continue

    def shutdown(self) -> None:
        for p in self._processors:
            try:
                p.shutdown()
            except Exception:
                continue

    def force_flush(self) -> None:
        for p in self._processors:
            try:
                p.force_flush()
            except Exception:
                continue


class TraceProvider:
    """Trace/span factory. / Trace/Spanのファクトリー。"""

    def register_processor(self, processor: TracingProcessor) -> None:
        raise NotImplementedError

    def set_processors(self, processors: list[TracingProcessor]) -> None:
        raise NotImplementedError

    def get_processors(self) -> list[TracingProcessor]:
        raise NotImplementedError

    def set_disabled(self, disabled: bool) -> None:
        raise NotImplementedError

    def get_current_trace(self) -> Trace | None:
        return Scope.get_current_trace()

    def get_current_span(self) -> Span[Any] | None:
        return Scope.get_current_span()

    def create_trace(
        self,
        name: str,
        trace_id: str | None = None,
        group_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        disabled: bool = False,
    ) -> Trace:
        raise NotImplementedError

    def create_span(
        self,
        span_data: SpanData,
        span_id: str | None = None,
        parent: Trace | Span[Any] | Any | None = None,
        disabled: bool = False,
    ) -> Span[SpanData]:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError


class DefaultTraceProvider(TraceProvider):
    def __init__(self) -> None:
        self._multi_processor = SynchronousMultiTracingProcessor()
        self._disabled = False

    def register_processor(self, processor: TracingProcessor) -> None:
        self._multi_processor.add_tracing_processor(processor)

    def set_processors(self, processors: list[TracingProcessor]) -> None:
        self._multi_processor.set_processors(processors)

    def get_processors(self) -> list[TracingProcessor]:
        return list(self._multi_processor.get_processors())

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled

    def create_trace(
        self,
        name: str,
        trace_id: str | None = None,
        group_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        disabled: bool = False,
    ) -> Trace:
        if self._disabled or disabled:
            return NoOpTrace()
        return TraceImpl(name=name, trace_id=trace_id, group_id=group_id, metadata=metadata, processor=self._multi_processor)

    def create_span(
        self,
        span_data: SpanData,
        span_id: str | None = None,
        parent: Trace | Span[Any] | Any | None = None,
        disabled: bool = False,
    ) -> Span[SpanData]:
        if self._disabled or disabled:
            return NoOpSpan(span_data)

        if parent is None:
            current_span = Scope.get_current_span()
            current_trace = Scope.get_current_trace()
            if current_trace is None:
                return NoOpSpan(span_data)
            trace_id = getattr(current_trace, "trace_id", "no-op")
            parent_id = getattr(current_span, "span_id", None) if current_span else None
        else:
            trace_id = getattr(parent, "trace_id", "no-op")
            parent_id = getattr(parent, "span_id", None)

        if trace_id == "no-op":
            return NoOpSpan(span_data)

        return SpanImpl(
            trace_id=trace_id,
            span_id=span_id,
            parent_id=parent_id,
            processor=self._multi_processor,
            span_data=span_data,
        )

    def shutdown(self) -> None:
        if self._disabled:
            return
        self._multi_processor.shutdown()


_trace_provider: TraceProvider = DefaultTraceProvider()


def set_trace_provider(provider: TraceProvider) -> None:
    global _trace_provider
    _trace_provider = provider


def get_trace_provider() -> TraceProvider:
    return _trace_provider
