# Trace分析チュートリアル（v0.3）

本書は Trace/Span の検索・分析を「使い方ベース」で説明するチュートリアルです。
仕様の詳細は `docs/search.md` を参照してください。

## 1. Trace/Spanの基本

- **Traceとは**: LLMのやり取りの記録をまとめたものです。動作状況の確認や改善のために使います。
- **Trace**: 1つの処理や会話のまとまり（ワークフロー全体）です。
- **Span**: Trace内の個々の処理（LLM呼び出し、tool呼び出し、評価など）です。
- **属性**: Spanには `span_type`, `name`, `input`, `output`, `output_kind`, `tool_calls`, `structured`, `error`, `rubric` などの属性があります。
- **usage**: 取得できる場合は tokens などの使用量が自動で記録されます（best-effort）。

### 1.1 LLM呼び出しは自動でSpanになります

`get_llm()` で取得したLLM呼び出しは、自動でSpanとして記録されます。
`with trace(...)` が無い場合でも、自動Traceが作成されます。

## 2. 前提（SQLiteTracer で記録します）

まずは SQLiteTracer を使って Trace/Span を記録します。

```python
from kantan_llm import get_llm
from kantan_llm.tracing import set_trace_processors, trace
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
set_trace_processors([tracer])

# LLM呼び出しでSpanを自動記録します
llm = get_llm("gpt-4.1-mini")
llm.responses.create(input="hello world")

# with trace で同一TraceにSpanをまとめます
with trace("demo"):
    llm.responses.create(input="another call")
```

## 3. ユースケース別チュートリアル

### 3.1 キーワード検索（入力/出力）

入力/出力に特定語句が含まれるTrace/Spanを探します（AND / case-insensitive）。

```python
from kantan_llm.tracing import SpanQuery, TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")

traces = tracer.search_traces(query=TraceQuery(keywords=["hello"], limit=10))
spans = tracer.search_spans(query=SpanQuery(keywords=["hello"], limit=10))
```

### 3.2 ルーブリック評価の抽出（judge）

評価Spanは `span_type="custom"` + `name="judge"` を使います。
`rubric.score` / `rubric.comment` を直接取り出せます。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
judges = tracer.search_spans(query=SpanQuery(span_type="custom", name="judge", limit=50))

scores = [s.rubric["score"] for s in judges if s.rubric]
comments = [s.rubric.get("comment") for s in judges if s.rubric]
```

### 3.3 特定ツールだけ抽出する（function + name）

tool/function の Span は `span_type="function"` + `name` で絞り込みます。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
tool_spans = tracer.search_spans(query=SpanQuery(span_type="function", name="get_weather"))
```

### 3.4 追加Spanの差分取得（ingest_seq）

同じTraceに後からSpanが追加された場合は `get_spans_since` を使います。

```python
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
all_spans = tracer.get_spans_by_trace("trace_xxx")

if all_spans:
    since_seq = all_spans[0].ingest_seq
    newer = tracer.get_spans_since("trace_xxx", since_seq=since_seq)
```

### 3.5 エラーSpanだけ抽出する

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
errors = tracer.search_spans(query=SpanQuery(has_error=True, limit=50))
```

### 3.6 時刻範囲で検索する（naive/aware）

- naive: ローカル時刻（`default_tz`）として扱われます
- aware: `tzinfo` を尊重して検索されます

```python
from datetime import datetime, timezone, timedelta
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")

aware_from = datetime.now(timezone.utc) - timedelta(hours=1)
aware_to = datetime.now(timezone.utc)
spans = tracer.search_spans(query=SpanQuery(started_from=aware_from, started_to=aware_to, limit=50))
```

## 4. 関数コール / structured output / ルーブリック

### 4.1 関数コール（tool/function call）

tool呼び出しは `span_type="function"` として記録されます。
検索は `span_type="function"` + `name` で行います。
LLM出力側の tool call は `output_kind="tool_calls"` と `tool_calls_json` に保存されます。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
tool_spans = tracer.search_spans(query=SpanQuery(span_type="function", name="get_weather"))
```

### 4.2 structured output

structured output は `output` と `structured_json`（SpanRecordでは `structured`）に保存されます（検索は `keywords` で行います）。
`score` / `comment` を含む structured output は、自動で `rubric` として記録されます（`output_kind="rubric"`）。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
spans = tracer.search_spans(query=SpanQuery(keywords=["summary"], limit=10))
```

### 4.3 ルーブリック評価

評価Spanは `span_type="custom"` + `name="judge"` です。
`rubric.score` / `rubric.comment` で抽出できます。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
judges = tracer.search_spans(query=SpanQuery(span_type="custom", name="judge", limit=50))
scores = [s.rubric["score"] for s in judges if s.rubric]
```

## 5. 特別なSpanを自分で作成する

自動Spanに加えて、必要であれば手動でSpanを作成できます。

```python
from kantan_llm.tracing import custom_span, trace

with trace("workflow"):
    with custom_span(name="custom_event", data={"note": "something happened"}):
        pass
```

## 6. judgeループ（閾値未満→掘る→再評価）

最短ステップで「評価→閾値未満→原因Traceを掘る」を行う例です。

```python
from kantan_llm.tracing import SpanQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")

judges = tracer.search_spans(query=SpanQuery(span_type="custom", name="judge", limit=200))
failed = [s for s in judges if s.rubric and s.rubric.get("score", 1) < 0.6]

for span in failed:
    # 原因Traceの全Spanを取得して確認します
    spans = tracer.get_spans_by_trace(span.trace_id)
    print(span.trace_id, len(spans))
```

### 6.1 ユーティリティで閾値未満を抽出する（最短）

SQLを書かずに judge の閾値未満を抽出し、バケットでまとめます。

```python
from kantan_llm.tracing.analysis import find_failed_judges, group_failed_by_bucket
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
failed = find_failed_judges(tracer, threshold=0.6, limit=200)
grouped = group_failed_by_bucket(failed)
print({k: len(v) for k, v in grouped.items()})
```

## 7. まとめ

- 仕様の詳細: `docs/search.md`
- サンプル: `examples/search_sqlite.py`
