from __future__ import annotations

import abc
import contextvars
from typing import Any

from . import util
from .processor_interface import TracingProcessor
from .scope import Scope


class Trace(abc.ABC):
    """End-to-end workflow trace. / ワークフロー全体のTrace。"""

    @abc.abstractmethod
    def __enter__(self) -> "Trace": ...

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb): ...

    @abc.abstractmethod
    def start(self, mark_as_current: bool = False) -> None: ...

    @abc.abstractmethod
    def finish(self, reset_current: bool = False) -> None: ...

    @property
    @abc.abstractmethod
    def trace_id(self) -> str: ...

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def export(self) -> dict[str, Any] | None: ...


class NoOpTrace(Trace):
    """No-op trace (when tracing disabled). / 無効時のno-op Trace。"""

    def __init__(self) -> None:
        self._started = False
        self._prev_context_token: contextvars.Token[Any | None] | None = None

    def __enter__(self) -> "Trace":
        if not self._started:
            self._started = True
            self.start(mark_as_current=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(reset_current=True)

    def start(self, mark_as_current: bool = False) -> None:
        if mark_as_current:
            self._prev_context_token = Scope.set_current_trace(self)

    def finish(self, reset_current: bool = False) -> None:
        if reset_current and self._prev_context_token is not None:
            Scope.reset_current_trace(self._prev_context_token)
            self._prev_context_token = None

    @property
    def trace_id(self) -> str:
        return "no-op"

    @property
    def name(self) -> str:
        return "no-op"

    def export(self) -> dict[str, Any] | None:
        return None


class TraceImpl(Trace):
    """Recorded trace. / 記録対象Trace。"""

    __slots__ = ("_name", "_trace_id", "group_id", "metadata", "_processor", "_started", "_prev_context_token")

    def __init__(
        self,
        name: str,
        trace_id: str | None,
        group_id: str | None,
        metadata: dict[str, Any] | None,
        processor: TracingProcessor,
    ) -> None:
        self._name = name
        self._trace_id = trace_id or util.gen_trace_id()
        self.group_id = group_id
        self.metadata = metadata
        self._processor = processor
        self._started = False
        self._prev_context_token: contextvars.Token[Any | None] | None = None

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def name(self) -> str:
        return self._name

    def start(self, mark_as_current: bool = False) -> None:
        if self._started:
            return
        self._started = True
        self._processor.on_trace_start(self)
        if mark_as_current:
            self._prev_context_token = Scope.set_current_trace(self)

    def finish(self, reset_current: bool = False) -> None:
        if not self._started:
            return
        self._processor.on_trace_end(self)
        if reset_current and self._prev_context_token is not None:
            Scope.reset_current_trace(self._prev_context_token)
            self._prev_context_token = None

    def __enter__(self) -> "Trace":
        if not self._started:
            self.start(mark_as_current=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(reset_current=exc_type is not GeneratorExit)

    def export(self) -> dict[str, Any] | None:
        return {
            "object": "trace",
            "id": self.trace_id,
            "workflow_name": self.name,
            "group_id": self.group_id,
            "metadata": self.metadata,
        }

