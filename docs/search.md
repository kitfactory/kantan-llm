# Trace検索サービス（v0.3 / F9）

本書は Trace/Span を検索・抽出する共通I/Fを定義するための整理ドキュメントです。
SQLiteTracer / OTELTracer それぞれで検索機能を持ちますが、利用側は同じインターフェースで使えることを目指します。

## 1. 想定ユースケース

- Trace検索（workflow_name / trace_id / group_id / 時間範囲）
- Span検索（span_id / span_type / trace_id）
- 入出力キーワード検索（prompt/response に特定語句）
- tool_call / function_call を含むTraceの抽出
- structured output の特定キー抽出（例: `rubric.score`）
- ルーブリックスコア集計（平均/分布/閾値未満の抽出）
- エラーSpanの抽出（`error` 有無）
- 同一 `group_id` の時系列Trace取得
- 遅延の大きいSpan/Traceの抽出（開始・終了時間の差）
- 既存Traceに後から追加されたSpanの差分取得

## 2. 共通I/F（案）

### 2.1 検索サービス

```python
from typing import Any, Protocol, Sequence
from datetime import datetime, tzinfo


class TraceSearchService(Protocol):
    default_tz: "tzinfo"
    def search_traces(self, *, query: "TraceQuery") -> Sequence["TraceRecord"]: ...
    def search_spans(self, *, query: "SpanQuery") -> Sequence["SpanRecord"]: ...
    def get_trace(self, trace_id: str) -> "TraceRecord | None": ...
    def get_span(self, span_id: str) -> "SpanRecord | None": ...
    def get_spans_by_trace(self, trace_id: str) -> Sequence["SpanRecord"]: ...
    def get_spans_since(self, trace_id: str, since_seq: int | None = None) -> Sequence["SpanRecord"]: ...
    def capabilities(self) -> "TraceSearchCapabilities": ...
```

### 2.2 Query/Record

```python
class TraceQuery:
    workflow_name: str | None
    group_id: str | None
    trace_id: str | None
    started_from: datetime | None
    started_to: datetime | None
    has_error: bool | None
    has_tool_call: bool | None
    keywords: list[str] | None
    metadata: dict[str, Any] | None
    limit: int | None


class SpanQuery:
    trace_id: str | None
    span_id: str | None
    span_type: str | None
    name: str | None
    started_from: datetime | None
    started_to: datetime | None
    has_error: bool | None
    keywords: list[str] | None
    limit: int | None


class TraceRecord:
    trace_id: str
    workflow_name: str
    group_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    metadata: dict[str, Any] | None


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
    rubric: dict[str, Any] | None  # {"score": float | int, "comment": str | None, ...}
    usage: dict[str, Any] | None
    error: dict[str, Any] | None
    raw: dict[str, Any] | None


class TraceSearchCapabilities:
    supports_keywords: bool
    supports_has_tool_call: bool
    supports_metadata_query: bool
    supports_limit: bool
    supports_since: bool
```

## 3. 追加Spanの取得

同じTraceに後からSpanが追加されるケースを想定し、`get_spans_since(trace_id, since_seq)` で差分取得できるようにします。
`since_seq` が `None` の場合は全件を返します。

仕様:
- `since_seq` は排他的（`ingest_seq > since_seq`）
- 返却順は `ingest_seq` 昇順

## 4. SQLite / OTEL 実装方針（案）

- SQLiteTracer（正式な検索実装の一つ / 仕様障壁が低い実装）:
  - `traces` / `spans` テーブルを検索対象とする
  - JSONカラム（raw_json）から `tool_call` の有無や structured output を抽出できるようにする
  - `keywords` は `input` / `output` への部分一致で実装
  - `metadata` は JSON1 の `json_extract` でトップレベルのスカラー一致に対応
- OTELTracer（Tempo想定）:
  - OTELのSpan属性へ `kantan_llm.input` / `kantan_llm.output` を付与済み
  - Tempoの検索APIに委譲する前提で設計する
  - `capabilities.supports_since=False` の場合、`get_spans_since` は `NotSupportedError` を返す

## 5. 非機能

- 取得データにAPIキー等の機密は含めない（簡易マスク後の値）
- 例外は Error ID で統一し、検索機能の失敗は致命にしない
- 検索/記録の内部正本はUTCのaware datetimeとして扱う
- keywords は「AND / input_output / case-insensitive」を固定仕様とする

## 6. 時刻の解釈・返却ルール（最小仕様）

### 6.1 Query の時刻は naive / aware 両対応

- `started_from` / `started_to` は `datetime | None` のまま扱う
- naive の場合: `TraceSearchService.default_tz` のローカル時刻として解釈する
- aware の場合: `tzinfo` を尊重して解釈する
- 内部検索はUTCに正規化して実行してよい

### 6.2 Record の返却時刻は問い合わせ文脈に合わせる

- Query の時刻が naive の場合: 返却も naive（`default_tz` ローカル前提）
- Query の時刻が aware の場合: 返却も aware（Query の `tzinfo` に合わせる）
- Query に時刻条件が無い場合: 返却は naive（`default_tz` ローカル）をデフォルトとする
- get_trace / get_span / get_spans_by_trace / get_spans_since は Query が無いので、返却は naive（`default_tz` ローカル）とする

### 6.3 default_tz の責務

- `TraceSearchService` は `default_tz` を持つ
- naive datetime は常に `default_tz` のローカル時刻として扱う（入力/返却とも）

## 7. Span規約（最小コア）

“自由に足せる” を残しつつ、検索・分析で最低限揃えるためのコア規約。
OpenAI Agents SDK の Span 種別に合わせ、可能な限り変換を不要にする。

| 項目 | 必須？ | 固定する内容（規約） | 目的（何が楽になる？） | 自由にしていい範囲 |
|---|---|---|---|---|
| span_type | ✅（全Span） | 固定集合（OpenAI Agents SDK準拠）: `agent` / `function` / `generation` / `response` / `guardrail` / `handoff` / `custom` / `mcp_tools` / `speech` / `speech_group` / `transcription` | 検索・集計の軸がブレない | 将来タイプ追加はOK（既存名は変えない） |
| name | ✅（推奨） | `function` / `custom` / `guardrail` 等で名前を持つ | tool/custom の特定が容易 | 命名規則は自由 |
| input | ✅（推奨: 検索したいSpan） | 検索したい入力はここに要約/抜粋 | keywords 検索が効く | 具体的な中身・整形形式は自由 |
| output | ✅（推奨: 検索したいSpan） | 検索したい出力はここに要約/抜粋 | 生成結果確認・失敗調査が早い | 具体的な中身・整形形式は自由 |
| usage | ✅（推奨: LLM呼び出し） | 使用量（tokens等）を best-effort で記録 | コストや効率の分析がしやすい | 詳細フィールドは自由 |
| error | ✅（あるなら） | `None` or `dict`。`dict`は最小で `type` / `message`（推奨） | エラー抽出・分類が安定 | `stack` / `retryable` / `code` 等は自由 |
| parent_id | ✅（推奨） | 親子関係を張る（無いなら `None`） | 失敗原因の辿りが簡単 | ツリーの粒度は自由 |
| started_at / ended_at | ✅ | 仕様どおり（返却はQuery文脈に追随） | 遅延分析・時系列が安定 | 表示用の追加フィールドは自由 |
| raw | ✅（推奨） | 自由辞書（詳細は基本ここ） | 拡張性の担保 | ほぼ全部自由（ただし一部固定パスあり） |
| judge Span の有無 | ❌（任意） | 評価を実施した時だけ作る | 評価が無い実行も扱える | いつ評価するかは自由 |
| judge の span_type | ✅（judgeがあるなら） | `span_type="custom"` に固定し、`name="judge"` を使用 | SDK互換と検索の両立 | 方式の違いは `raw` で表現 |
| ルーブリック score/comment の置き場所 | ✅（judgeがあるなら） | `rubric.score` / `rubric.comment` に固定（rawとは独立） | 閾値未満抽出・コメント分析が安定 | `reasons` / `dimensions` / `method` 等は自由 |
| OTEL/Tempo 属性キー（推奨） | ❌（推奨） | `kantan.span_type` / `kantan.workflow_name` / `kantan.group_id` / `kantan.has_error` / `kantan.rubric.score` | Tempo側検索がやりやすい | 追加属性は自由 |
| tool呼び出し情報（推奨） | ❌（推奨） | tool呼び出しは `span_type="function"` を使用し、要約を `input/output`、詳細は `raw.tool_calls` 等 | tool起因の異常検知・追跡 | toolスキーマ詳細は自由 |
