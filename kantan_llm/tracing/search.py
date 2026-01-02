from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any, Protocol, Sequence


@dataclass
class TraceQuery:
    workflow_name: str | None = None
    group_id: str | None = None
    trace_id: str | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None
    has_error: bool | None = None
    has_tool_call: bool | None = None
    keywords: list[str] | None = None
    metadata: dict[str, Any] | None = None
    limit: int | None = None


@dataclass
class SpanQuery:
    trace_id: str | None = None
    span_id: str | None = None
    span_type: str | None = None
    name: str | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None
    has_error: bool | None = None
    keywords: list[str] | None = None
    limit: int | None = None


@dataclass
class TraceRecord:
    trace_id: str
    workflow_name: str
    group_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    metadata: dict[str, Any] | None


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_id: str | None
    span_type: str | None
    name: str | None
    started_at: datetime | None
    ended_at: datetime | None
    ingest_seq: int
    input: str | None
    output: str | None
    output_kind: str | None
    tool_calls: list[dict[str, Any]] | None
    structured: Any | None
    rubric: dict[str, Any] | None
    usage: dict[str, Any] | None
    error: dict[str, Any] | None
    raw: dict[str, Any] | None


@dataclass
class TraceSearchCapabilities:
    supports_keywords: bool
    supports_has_tool_call: bool
    supports_metadata_query: bool
    supports_limit: bool
    supports_since: bool


class TraceSearchService(Protocol):
    default_tz: tzinfo

    def search_traces(self, *, query: TraceQuery) -> Sequence[TraceRecord]: ...

    def search_spans(self, *, query: SpanQuery) -> Sequence[SpanRecord]: ...

    def get_trace(self, trace_id: str) -> TraceRecord | None: ...

    def get_span(self, span_id: str) -> SpanRecord | None: ...

    def get_spans_by_trace(self, trace_id: str) -> Sequence[SpanRecord]: ...

    def get_spans_since(self, trace_id: str, since_seq: int | None = None) -> Sequence[SpanRecord]: ...

    def capabilities(self) -> TraceSearchCapabilities: ...
