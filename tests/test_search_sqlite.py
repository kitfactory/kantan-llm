from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kantan_llm.tracing import (
    SpanQuery,
    TraceQuery,
    custom_span,
    function_span,
    generation_span,
    set_trace_processors,
    trace,
)
from kantan_llm.tracing.analysis import find_failed_judges, group_failed_by_bucket
from kantan_llm.tracing.processors import SQLiteTracer


def _setup_tracer(tmp_path) -> SQLiteTracer:
    tracer = SQLiteTracer(str(tmp_path / "traces.sqlite3"))
    set_trace_processors([tracer])
    return tracer


def _record_sample() -> str:
    with trace("workflow") as t:
        with generation_span(
            input="hello world",
            output="ok",
            model="gpt-4",
            usage={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
        ):
            pass
        with function_span(name="tool_a", input="in", output="out"):
            pass
        with custom_span(name="judge", data={"rubric": {"score": 0.7, "comment": "good"}}):
            pass
        with generation_span(
            input="score me",
            output='{"score": 0.2, "comment": "bad"}',
            model="gpt-4",
        ):
            pass
        with generation_span(input="tool check", output={"tool_calls": [{"name": "x"}]}, model="gpt-4"):
            pass
    return t.trace_id


def test_search_spans_by_name_and_rubric(tmp_path):
    tracer = _setup_tracer(tmp_path)
    trace_id = _record_sample()

    spans = tracer.search_spans(query=SpanQuery(span_type="function", name="tool_a"))
    assert len(spans) == 1
    assert spans[0].trace_id == trace_id

    judges = tracer.search_spans(query=SpanQuery(span_type="custom", name="judge"))
    assert len(judges) == 1
    assert judges[0].rubric["score"] == 0.7
    assert judges[0].rubric["comment"] == "good"
    assert judges[0].output_kind == "judge"

    auto_rubric = [s for s in tracer.search_spans(query=SpanQuery(span_type="generation")) if s.rubric]
    assert auto_rubric
    assert any(r.rubric["score"] == 0.2 for r in auto_rubric)
    assert any(r.output_kind == "judge" for r in auto_rubric)

    text_spans = [s for s in tracer.search_spans(query=SpanQuery(span_type="generation")) if s.output_kind == "text"]
    assert text_spans

    tool_spans = [s for s in tracer.search_spans(query=SpanQuery(span_type="generation")) if s.output_kind == "tool_calls"]
    assert tool_spans
    assert tool_spans[0].tool_calls
    assert tool_spans[0].structured is None


def test_usage_recorded_in_span_and_trace(tmp_path):
    tracer = _setup_tracer(tmp_path)

    with trace("usage") as t:
        with generation_span(
            input="hello",
            output="ok",
            model="gpt-4",
            usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        ):
            pass
        with generation_span(
            input="again",
            output="ok",
            model="gpt-4",
            usage={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        ):
            pass

    spans = tracer.get_spans_by_trace(t.trace_id)
    assert spans
    assert sum(sp.usage["total_tokens"] for sp in spans if sp.usage) == 6
    trace_record = tracer.get_trace(t.trace_id)
    assert trace_record is not None
    assert trace_record.metadata["usage_total"]["total_tokens"] == 6


def test_usage_normalization_minimal(tmp_path):
    tracer = _setup_tracer(tmp_path)

    with trace("usage-normalize") as t:
        with generation_span(
            input="hello",
            output="ok",
            model="gpt-4",
            usage={"prompt_tokens": 1, "completion_tokens": 2},
        ):
            pass

    spans = tracer.get_spans_by_trace(t.trace_id)
    assert spans
    usage = spans[0].usage
    assert usage["input_tokens"] == 1
    assert usage["output_tokens"] == 2
    assert usage["total_tokens"] == 3
    trace_record = tracer.get_trace(t.trace_id)
    assert trace_record is not None
    assert trace_record.metadata["usage_total"]["total_tokens"] == 3


def test_search_traces_keywords_and_tool_call(tmp_path):
    tracer = _setup_tracer(tmp_path)
    trace_id = _record_sample()

    traces = tracer.search_traces(query=TraceQuery(keywords=["hello"]))
    assert [t.trace_id for t in traces] == [trace_id]

    traces = tracer.search_traces(query=TraceQuery(has_tool_call=True))
    assert [t.trace_id for t in traces] == [trace_id]


def test_search_traces_metadata_query(tmp_path):
    tracer = _setup_tracer(tmp_path)
    with trace("meta", metadata={"env": "dev", "run": 1, "flag": True}) as t:
        with generation_span(input="hello", output="ok", model="gpt-4"):
            pass

    traces = tracer.search_traces(query=TraceQuery(metadata={"env": "dev"}))
    assert [tr.trace_id for tr in traces] == [t.trace_id]

    traces = tracer.search_traces(query=TraceQuery(metadata={"run": 2}))
    assert traces == []


def test_get_spans_since_order_and_exclusive(tmp_path):
    tracer = _setup_tracer(tmp_path)
    trace_id = _record_sample()

    spans = tracer.get_spans_by_trace(trace_id)
    assert len(spans) >= 2
    first_seq = spans[0].ingest_seq

    newer = tracer.get_spans_since(trace_id, since_seq=first_seq)
    assert all(s.ingest_seq > first_seq for s in newer)
    assert [s.ingest_seq for s in newer] == sorted([s.ingest_seq for s in newer])


def test_span_insert_atomic_when_usage_update_fails(tmp_path):
    class BrokenSQLiteTracer(SQLiteTracer):
        def _update_trace_usage_cache(self, conn, trace_id, usage):
            raise RuntimeError("boom")

    tracer = BrokenSQLiteTracer(str(tmp_path / "traces.sqlite3"))
    set_trace_processors([tracer])

    with trace("atomic") as t:
        with generation_span(
            input="hello",
            output="ok",
            model="gpt-4",
            usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        ):
            pass

    spans = tracer.get_spans_by_trace(t.trace_id)
    assert spans == []
    trace_record = tracer.get_trace(t.trace_id)
    assert trace_record is not None
    assert not trace_record.metadata or "usage_total" not in trace_record.metadata


def test_find_failed_judges_and_grouping(tmp_path):
    tracer = _setup_tracer(tmp_path)
    with trace("judge") as t:
        with custom_span(name="judge", data={"rubric": {"score": 0.7, "comment": "good", "tags": ["ok"]}}):
            pass
        with custom_span(name="judge", data={"rubric": {"score": 0.4, "comment": "bad output"}}):
            pass
        with custom_span(name="judge", data={"rubric": {"score": 0.3}}):
            pass

    failed = find_failed_judges(tracer, threshold=0.6, limit=10, trace_query=TraceQuery(trace_id=t.trace_id))
    assert all(s.rubric and s.rubric.get("score", 1) < 0.6 for s in failed)

    grouped = group_failed_by_bucket(failed)
    assert "bad" in grouped
    assert "other" in grouped


def test_time_return_naive_or_aware(tmp_path):
    tracer = _setup_tracer(tmp_path)
    _record_sample()

    aware_from = datetime.now(timezone.utc) - timedelta(minutes=1)
    aware_to = datetime.now(timezone.utc) + timedelta(minutes=1)
    spans = tracer.search_spans(query=SpanQuery(started_from=aware_from, started_to=aware_to))
    assert spans
    assert spans[0].started_at is None or spans[0].started_at.tzinfo is timezone.utc

    naive_from = datetime.now() - timedelta(minutes=1)
    naive_to = datetime.now() + timedelta(minutes=1)
    spans = tracer.search_spans(query=SpanQuery(started_from=naive_from, started_to=naive_to))
    assert spans
    assert spans[0].started_at is None or spans[0].started_at.tzinfo is None
