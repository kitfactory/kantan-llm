# kantan-llm architecture（v0.2）

## 1. レイヤーと責務

- Public API layer
  - `kantan_llm.get_llm` を公開する
  - 入力バリデーション、推測/上書き、フォールバック選択を行う
- Provider layer
  - provider推測、環境変数/引数からの設定解決
  - OpenAI SDK `OpenAI` クライアントを適切な `api_key` / `base_url` で構築する
- Wrapper layer
  - `llm.responses.create(...)` / `llm.chat.completions.create(...)` を提供する
  - 返却（Responses/ChatCompletions）は原形保持（変換しない）
- Tracing layer（F8）
  - `kantan_llm.tracing.trace(...)` とカレントTrace管理（contextvars）を提供する
  - LLM呼び出しをSpanとして構造化し、Tracer（Processor）へ通知する
  - Tracer実装（Print/SQLite/OTEL）を提供する（外部SDKに必須依存しない）
- Search layer（F9）
  - Trace/Spanの検索I/Fを提供する（SQLite/OTEL共通）
  - 特定Span/Trace、評価スコア、tool_call有無などの検索を抽象化する

依存方向: Public API → Provider → Wrapper → Tracing（逆依存はしない）

## 2. 主要I/F（最小粒度・最小引数）

### 2.1 Public API

```python
def get_llm(
    model: str,
    *,
    provider: str | None = None,
    providers: list[str] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    tracer=None,
):
    ...
```

### 2.2 Wrapper

- `KantanLLM`
  - 属性: `provider: str`, `model: str`, `client: OpenAI`
  - `responses.create(...)`（provider=`openai` のみ）
  - `chat.completions.create(...)`（provider=`compat` のみ）

### 2.3 Tracing（最小I/F）

`kantan-llm` 内部では OpenAI Agents SDK の `TracingProcessor` と同等のメソッド集合を持つI/Fを採用する（必須依存はしない）。

```python
from typing import Any, Protocol


class TracingProcessor(Protocol):
    def on_trace_start(self, trace: Any) -> None: ...
    def on_trace_end(self, trace: Any) -> None: ...
    def on_span_start(self, span: Any) -> None: ...
    def on_span_end(self, span: Any) -> None: ...
    def shutdown(self) -> None: ...
    def force_flush(self) -> None: ...


def trace(
    workflow_name: str,
    trace_id: str | None = None,
    group_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    disabled: bool = False,
):
    ...
```

### 2.4 Search（最小I/F）

```python
from typing import Any, Protocol, Sequence


class TraceSearchService(Protocol):
    def search_traces(self, *, query: "TraceQuery") -> Sequence["TraceRecord"]: ...
    def search_spans(self, *, query: "SpanQuery") -> Sequence["SpanRecord"]: ...
    def get_trace(self, trace_id: str) -> "TraceRecord | None": ...
    def get_span(self, span_id: str) -> "SpanRecord | None": ...
    def get_spans_by_trace(self, trace_id: str) -> Sequence["SpanRecord"]: ...
    def get_spans_since(self, trace_id: str, since_seq: int | None = None) -> Sequence["SpanRecord"]: ...
    def capabilities(self) -> "TraceSearchCapabilities": ...
```

## 3. ログ/エラー方針

- 例外メッセージは必ず Error ID を含める（例: `[kantan-llm][E2] ...`）
- `providers=[...]` の全滅時は候補ごとの失敗理由をまとめて返す
- 機密情報（APIキー等）をエラー文面に含めない
- トレーシング失敗は非致命とし、LLM呼び出し自体は継続する（Tracer側で握りつぶす）
