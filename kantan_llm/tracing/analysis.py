from __future__ import annotations

from typing import Sequence

from ..errors import NotSupportedError
from .search import SpanQuery, SpanRecord, TraceQuery, TraceSearchService


def find_failed_judges(
    service: TraceSearchService,
    threshold: float,
    limit: int = 200,
    trace_query: TraceQuery | None = None,
) -> list[SpanRecord]:
    """Find judge spans under threshold. / 閾値未満のjudge Spanを抽出する。"""
    caps = service.capabilities()
    if limit and not caps.supports_limit:
        raise NotSupportedError("limit")

    if trace_query is not None:
        _ensure_trace_query_supported(caps, trace_query)
        trace_ids = [record.trace_id for record in service.search_traces(query=trace_query)]
        return _collect_failed_judges_by_trace(service, trace_ids, threshold, limit)

    spans = service.search_spans(query=SpanQuery(span_type="custom", name="judge", limit=limit))
    return [span for span in spans if _is_failed(span, threshold)]


def group_failed_by_bucket(spans: Sequence[SpanRecord]) -> dict[str, list[SpanRecord]]:
    """Group failed judges by bucket. / 失敗judgeをバケットでまとめる。"""
    grouped: dict[str, list[SpanRecord]] = {}
    for span in spans:
        bucket = _pick_bucket(span)
        grouped.setdefault(bucket, []).append(span)
    return grouped


def _ensure_trace_query_supported(caps, query: TraceQuery) -> None:
    if query.limit and not caps.supports_limit:
        raise NotSupportedError("limit")
    if query.keywords and not caps.supports_keywords:
        raise NotSupportedError("keywords")
    if query.has_tool_call is not None and not caps.supports_has_tool_call:
        raise NotSupportedError("has_tool_call")
    if query.metadata and not caps.supports_metadata_query:
        raise NotSupportedError("metadata query")


def _collect_failed_judges_by_trace(
    service: TraceSearchService,
    trace_ids: Sequence[str],
    threshold: float,
    limit: int,
) -> list[SpanRecord]:
    failed: list[SpanRecord] = []
    for trace_id in trace_ids:
        remaining = limit - len(failed)
        if remaining <= 0:
            break
        spans = service.search_spans(
            query=SpanQuery(trace_id=trace_id, span_type="custom", name="judge", limit=remaining)
        )
        for span in spans:
            if _is_failed(span, threshold):
                failed.append(span)
                if len(failed) >= limit:
                    return failed
    return failed


def _is_failed(span: SpanRecord, threshold: float) -> bool:
    if not span.rubric:
        return False
    score = span.rubric.get("score")
    if not isinstance(score, (int, float)):
        return False
    return score < threshold


def _pick_bucket(span: SpanRecord) -> str:
    rubric = span.rubric or {}
    tags = rubric.get("tags")
    if isinstance(tags, list) and tags:
        first = tags[0]
        if isinstance(first, str) and first:
            return first
    comment = rubric.get("comment")
    if isinstance(comment, str):
        token = comment.strip().split(" ", 1)[0]
        if token:
            return token
    return "other"
