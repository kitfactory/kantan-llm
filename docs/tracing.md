# Tracing / Tracer マニュアル（v0.2 / F8）

`kantan-llm` は `get_llm()` で取得したLLM呼び出しを Trace/Span として記録できます。
設計方針は OpenAI Agents SDK の Tracing と同じインターフェース感（同名メソッド群）ですが、`kantan-llm` 自体は OpenAI Agents SDK に必須依存しません。

## 1. 最短（デフォルト: PrintTracer）

`tracer` を指定しない場合、デフォルトで `PrintTracer` が使われ、入力と出力が色分け表示されます。

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini")
res = llm.responses.create(input="1行で自己紹介して。")
print(res.output_text)
```

## 2. `with trace`（同一TraceにSpanを追加）

`with trace(...)` の内側で LLM を呼ぶと、同一TraceにSpanが追加されます。

```python
from kantan_llm import get_llm
from kantan_llm.tracing import trace

llm = get_llm("gpt-4.1-mini")
with trace("workflow") as t:
    llm.responses.create(input="1つ目")
    llm.responses.create(input="2つ目")
    print(t.trace_id)
```

## 3. `with trace` なし（自動Trace）

`with trace` が無い状態で LLM を呼ぶと、呼び出し単位で自動的にTraceを作り、その中にSpanを1つ作って記録します。

- 自動生成Traceの `workflow_name` は `default_workflow_name` です

## 4. Tracerの差し替え（Print/SQLite/OTEL）

### 4.1 PrintTracer（明示）

```python
from kantan_llm import get_llm
from kantan_llm.tracing import PrintTracer

llm = get_llm("gpt-4.1-mini", tracer=PrintTracer())
llm.responses.create(input="hello")
```

### 4.2 SQLiteTracer

Span（入力/出力など）を SQLite に保存します。

```python
from kantan_llm import get_llm
from kantan_llm.tracing import SQLiteTracer

llm = get_llm("gpt-4.1-mini", tracer=SQLiteTracer("traces.sqlite3"))
llm.responses.create(input="hello")
```

### 4.3 OTELTracer（オプション依存）

OpenTelemetry SDK を追加すると利用できます（未導入の場合は E15）。

```bash
uv pip install opentelemetry-sdk
```

```python
from kantan_llm import get_llm
from kantan_llm.tracing import OTELTracer

llm = get_llm("gpt-4.1-mini", tracer=OTELTracer())
llm.responses.create(input="hello")
```

失敗例（依存不足）:

- `OTELTracer()` → `[kantan-llm][E15] Missing optional dependency for tracer: opentelemetry-sdk`

## 5. トレーシングの無効化

### 5.1 `tracer=None`（出力しない）

`get_llm(..., tracer=None)` とすると、NoOpTracer が使われ、何も表示されません（Trace/Spanは生成されますが、出力や保存はしません）。

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini", tracer=None)
llm.responses.create(input="no output")
```

### 5.2 `set_tracing_disabled(True)`（Trace/Span自体を作らない）

```python
from kantan_llm.tracing import set_tracing_disabled

set_tracing_disabled(True)
```

## 6. `with` でTracerを一時的に切り替える

`with` ブロックの間だけ Tracer を差し替えたい場合は、`get_trace_provider().get_processors()` と `set_trace_processors(...)` を使って復帰させます。

```python
from contextlib import contextmanager

from kantan_llm.tracing import PrintTracer, SQLiteTracer, get_trace_provider, set_trace_processors


@contextmanager
def use_tracer(tracer):
    prev = get_trace_provider().get_processors()
    set_trace_processors([tracer])
    try:
        yield
    finally:
        set_trace_processors(prev)


with use_tracer(SQLiteTracer("traces.sqlite3")):
    # このブロック内だけ SQLiteTracer
    ...

with use_tracer(PrintTracer()):
    # このブロック内だけ PrintTracer
    ...
```

## 7. 省略上限（全Tracer共通）

デフォルトでは入力/出力を省略しません。
環境変数 `KANTAN_LLM_TRACING_MAX_CHARS` を設定すると、入力/出力の記録対象を指定文字数に省略します（Print/SQLite/OTEL 共通）。

```bash
export KANTAN_LLM_TRACING_MAX_CHARS=2000
```

## 8. 簡易マスク（全Tracer共通）

PII等の高度な対策は将来オプションとし、現時点では Token/KEY っぽい文字列を簡易マスクします。

対象（現状）:

- `sk-...`（OpenAI形式）
- `Bearer ...`
- `api_key=...` / `api_key: ...`

## 9. LLM入出力の記録内容

出力は次の優先順位で記録し、`output_kind` で区別保存します。

1. 出力テキスト
2. 構造化出力（structured output）
3. function calling（tool call）の内容

rubric が抽出できる場合は `output_kind="rubric"` を優先します。

## 10. OpenAI Agents SDK での利用（任意）

`kantan-llm` の Tracer は、OpenAI Agents SDK が期待する TracingProcessor と同じメソッド集合を持つため、Agents SDK 側に登録して使えます（Agents SDK 依存はユーザー側）。

```python
from agents.tracing import add_trace_processor
from kantan_llm.tracing import PrintTracer

add_trace_processor(PrintTracer())
```

## 11. エラー例

- 失敗（不正な tracer）: `get_llm("gpt-4.1-mini", tracer=object())` → `[kantan-llm][E14] Invalid tracer (expected TracingProcessor): <object object at ...>`
