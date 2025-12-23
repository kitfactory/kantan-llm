from __future__ import annotations

import abc
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .spans import Span
    from .traces import Trace


class TracingProcessor(abc.ABC):
    """Tracing processor interface (Agents SDK compatible). / トレーサーI/F（Agents SDK互換）。"""

    @abc.abstractmethod
    def on_trace_start(self, trace: "Trace") -> None: ...

    @abc.abstractmethod
    def on_trace_end(self, trace: "Trace") -> None: ...

    @abc.abstractmethod
    def on_span_start(self, span: "Span[Any]") -> None: ...

    @abc.abstractmethod
    def on_span_end(self, span: "Span[Any]") -> None: ...

    @abc.abstractmethod
    def shutdown(self) -> None: ...

    @abc.abstractmethod
    def force_flush(self) -> None: ...

