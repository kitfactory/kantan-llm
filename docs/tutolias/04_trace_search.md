# 04. Trace/Span の検索パターン

## シーン

Trace/Span が増えてきたら、条件で絞り込んで調査対象を最短で見つけたいはずです。
この単元ではよく使う検索条件をまとめて確認します。

## 使う機能

ここでは `TraceQuery` と `SpanQuery` を使います。
keywords 検索や tool call の有無、エラーの有無といった条件を指定できます。

## どう使うか

まず `TraceQuery` / `SpanQuery` を組み立て、検索条件を指定します。
次に `search_traces` / `search_spans` を呼び出し、結果を確認します。

## コード

```python
from kantan_llm.tracing import SpanQuery, TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
traces = tracer.search_traces(query=TraceQuery(keywords=["hello"], limit=10))
spans = tracer.search_spans(query=SpanQuery(keywords=["hello"], limit=10))
```

```python
from kantan_llm.tracing import TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
traces = tracer.search_traces(query=TraceQuery(has_tool_call=True, limit=10))
```

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
errors = tracer.search_spans(query=SpanQuery(has_error=True, limit=10))
```

## 次の単元

- `docs/tutolias/05_judge_loop.md`
