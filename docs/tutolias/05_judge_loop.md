# 05. judge ループ（閾値未満→掘る→再評価）

## シーン

評価（judge）の結果が悪いケースだけを拾って原因を掘りたい。
そんなときに最短で回せる改善ループを確認します。

## 使う機能

ここでは `custom_span(name="judge")` を使って評価Spanを記録します。
その後 `SpanQuery` で judge を抽出し、`get_spans_by_trace` で原因を掘ります。

## どう使うか

まず judge Span を記録します。
次に `span_type="custom"` と `name="judge"` を指定して検索し、閾値未満を抽出します。
最後に trace_id で関連 Span をたどり、原因を確認します。

## コード

```python
from kantan_llm.tracing import custom_span, trace

with trace("workflow"):
    with custom_span(name="judge", data={"rubric": {"score": 0.4, "comment": "bad"}}):
        pass
```

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
judges = tracer.search_spans(query=SpanQuery(span_type="custom", name="judge", limit=200))
failed = [s for s in judges if s.rubric and s.rubric.get("score", 1) < 0.6]
```

```python
for span in failed:
    spans = tracer.get_spans_by_trace(span.trace_id)
    print(span.trace_id, len(spans))
```

## 次の単元

- `docs/tutolias/06_utilities.md`
