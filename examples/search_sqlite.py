from __future__ import annotations

from kantan_llm.tracing import SpanQuery, TraceQuery, generation_span, set_trace_processors, trace
from kantan_llm.tracing.processors import SQLiteTracer


def main() -> None:
    tracer = SQLiteTracer("traces.sqlite3")
    set_trace_processors([tracer])

    with trace("search-demo") as t:
        with generation_span(input="hello world", output="ok", model="gpt-4"):
            pass

    # Search traces by keyword (AND, case-insensitive).
    traces = tracer.search_traces(query=TraceQuery(keywords=["hello"], limit=10))
    print("traces:", [tr.trace_id for tr in traces])

    # Search spans by keyword.
    spans = tracer.search_spans(query=SpanQuery(keywords=["hello"], limit=10))
    print("spans:", [sp.span_id for sp in spans])

    # Diff spans by ingest_seq.
    all_spans = tracer.get_spans_by_trace(t.trace_id)
    if all_spans:
        since_seq = all_spans[0].ingest_seq
        newer = tracer.get_spans_since(t.trace_id, since_seq=since_seq)
        print("newer spans:", [sp.span_id for sp in newer])


if __name__ == "__main__":
    main()
