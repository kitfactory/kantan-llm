# 03. SQLiteTracer での記録と検索

## シーン

あとから掘り返せるように、Trace/Span をローカルに保存しておきたい場面を想定します。

## 使う機能

ここでは SQLiteTracer を使います。
`set_trace_processors` でトレーサを差し替えることで、記録先を SQLite に変更します。

## どう使うか

まず SQLiteTracer を作成して登録します。
その状態で `with trace` を使って LLM を呼び出すと、Span が SQLite に保存されます。
最後に `search_traces` で保存された Trace を簡単に取り出します。

## コード

```python
from kantan_llm import get_llm
from kantan_llm.tracing import set_trace_processors, trace
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
set_trace_processors([tracer])

llm = get_llm("gpt-4.1-mini")
with trace("demo"):
    llm.responses.create(input="hello")
```

```python
from kantan_llm.tracing import TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
traces = tracer.search_traces(query=TraceQuery(limit=5))
print([t.trace_id for t in traces])
```

## 次の単元

- `docs/tutolias/04_trace_search.md`
