from __future__ import annotations

from .processor_interface import TracingProcessor
from .provider import get_trace_provider


def add_trace_processor(span_processor: TracingProcessor) -> None:
    """Add a processor. / Processorを追加する。"""

    get_trace_provider().register_processor(span_processor)


def set_trace_processors(processors: list[TracingProcessor]) -> None:
    """Replace processor list. / Processor一覧を置き換える。"""

    get_trace_provider().set_processors(processors)


def set_tracing_disabled(disabled: bool) -> None:
    """Enable/disable tracing. / トレーシング全体の有効/無効。"""

    get_trace_provider().set_disabled(disabled)

