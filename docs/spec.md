# kantan-llm spec（v0.2）

本書は `docs/concept.md` の Spec ID を参照し、Given/When/Then 形式で仕様を定義する。

## 1. 用語

- OpenAI: OpenAI公式API（Responses API を正本とする）
- 互換（Chat）: OpenAI Chat Completions API 互換のサーバー（他社/ローカル等）
- provider: `openai` / `compat` / `lmstudio` / `ollama` / `openrouter` / `anthropic` / `google` 等の識別子

## 2. API（F1）

### 2.1 `get_llm` を呼び出した場合、LLMクライアントを返す（F1）

- Given: `model` が指定されている
- When: `get_llm(model, **options)` を呼ぶ
- Then: `llm` を返す
- And: OpenAIの場合 `llm.responses.create(...)` が利用できる
- And: 互換（Chat）の場合 `llm.chat.completions.create(...)` が利用できる
- And: `llm` は OpenAI SDK クライアント互換として、未定義属性を内部クライアントへ委譲する

### 2.2 `provider` を指定した場合、推測結果を上書きする（F5）

- Given: `provider` が指定されている
- When: `get_llm(model, provider=provider)` を呼ぶ
- Then: プロバイダー推測より `provider` を優先する

### 2.3 `providers` を指定した場合、利用可能なものを順に試す（F6）

- Given: `providers` が指定されている
- When: `get_llm(model, providers=[...])` を呼ぶ
- Then: 指定順にプロバイダーを評価して最初に利用可能なものを選ぶ
- And: 全滅した場合、各候補の失敗理由が分かるエラーを送出する

### 2.4 `tracer` を指定した場合、返却LLMにトレーシングを適用する（F8）

- Given: `tracer` が指定されている（または未指定）
- When: `get_llm(model, tracer=tracer)` を呼ぶ
- Then: 返却される `llm` のAPI呼び出し（`responses.create` / `chat.completions.create`）はスパンとして記録される
- And: `tracer` 未指定の場合は PrintTracer をデフォルトとして利用する

## 3. プロバイダー推測（F2）

### 3.1 `gpt-*`（`gpt-oss-*` を除く）を指定した場合、OpenAIとして扱う（F2）

- Given: `model` が `gpt-` で始まる
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openai` を選択する

### 3.1.1 `gpt-oss-*` を指定した場合、プロバイダー推測を固定しない（F2）

- Given: `model` が `gpt-oss-` で始まる
- When: `get_llm(model)` を呼ぶ（`provider` / `providers` 未指定）
- Then: provider 推測は `openai` に固定しない
- And: 利用可能な環境変数の候補を優先順で評価する
- And: 候補が存在しない場合は ProviderInferenceError（E1）を送出する

### 3.2 `claude-*` を指定した場合、互換（Chat）として扱う（F2）

- Given: `model` が `claude-` で始まる
- And: `CLAUDE_API_KEY` と `OPENROUTER_API_KEY` のどちらも未設定
- When: `get_llm(model)` を呼ぶ
- Then: provider=`compat` を選択する

### 3.3 `claude-*` を指定した場合、Anthropicとして扱う（F2）

- Given: `model` が `claude-` で始まる
- And: `CLAUDE_API_KEY` が設定されている
- When: `get_llm(model)` を呼ぶ
- Then: provider=`anthropic` を選択する
- And: Anthropic向けに必要な場合はモデル名を正規化してよい（例: `claude-3-5-sonnet-latest` → `claude-3-7-sonnet-20250219`）

### 3.4 `claude-*` を指定した場合、OpenRouterとして扱う（F2）

- Given: `model` が `claude-` で始まる
- And: `CLAUDE_API_KEY` が未設定
- And: `OPENROUTER_API_KEY` が設定されている
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openrouter` を選択する
- And: OpenRouter向けに必要な場合はモデル名を正規化してよい（例: `claude-3-5-sonnet-latest` → `anthropic/claude-3.5-sonnet`）

### 3.5 `gemini-*` を指定した場合、Googleとして扱う（F2）

- Given: `model` が `gemini-` で始まる
- When: `get_llm(model)` を呼ぶ
- Then: provider=`google` を選択する

### 3.6 `openai/...` の明示表記を指定した場合、OpenAIとして扱う（F2）

- Given: `model` が `openai/` で始まる（例: `openai/gpt-4.1-mini`）
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openai` を選択する
- And: provider が `openai` のとき、実際のAPI呼び出しに使うモデル名は `openai/` を除いた値とする
- And: provider を明示指定して `openai` 以外を選ぶ場合、`openai/` はモデル名の一部として扱い保持してよい（例: LMStudio等）
- And: `gpt-oss-*` の場合は 3.1.1 の推測方針を優先する

## 4. API採用方針（F3）

### 4.1 OpenAIモデルの場合、Responses API を正本として提供する（F3）

- Given: provider=`openai`
- When: `get_llm(...)` が返す `llm` を利用する
- Then: `llm.responses.create(...)` を正本として提供する
- And: 返却はOpenAI SDKの自然な返却（Responsesの原形）を保持する

### 4.2 互換（Chat）の場合、Chat Completions API を正本として提供する（F3）

- Given: provider=`compat`
- When: `get_llm(...)` が返す `llm` を利用する
- Then: `llm.chat.completions.create(...)` を正本として提供する
- And: 返却はOpenAI SDKの自然な返却（ChatCompletionsの原形）を保持する
- And: ChatCompletionsの応答をResponses形式へ変換して返す実装は禁止する

## 5. 設定（環境変数）（F4）

### 5.1 OpenAIのAPIキーが無い場合、キー不足エラーを返す（F4）

- Given: provider=`openai`
- And: `OPENAI_API_KEY` が未設定
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する

### 5.2 互換（Chat）の接続先が無い場合、URL不足エラーを返す（F4）

- Given: provider=`compat` または `lmstudio` または `ollama`
- And: base_url が未指定かつ（対応する環境変数も未設定）
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する

### 5.3 OpenRouter のAPIキーが無い場合、キー不足エラーを返す（F4）

- Given: provider=`openrouter`
- And: `OPENROUTER_API_KEY` が未設定
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する

### 5.4 Google のAPIキーが無い場合、キー不足エラーを返す（F4）

- Given: provider=`google`
- And: `GOOGLE_API_KEY` が未設定
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する

### 5.5 Anthropic のAPIキーが無い場合、キー不足エラーを返す（F4）

- Given: provider=`anthropic`
- And: `CLAUDE_API_KEY` が未設定
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する


## 6. エラー一覧（メッセージは実装と完全一致）

| Error ID | 例外名 | メッセージ | 備考 |
|---|---|---|---|
| E1 | `ProviderInferenceError` | `[kantan-llm][E1] Provider inference failed for model: {model}` | 推測不能 |
| E2 | `MissingConfigError` | `[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai` | OpenAIキー不足 |
| E3 | `MissingConfigError` | `[kantan-llm][E3] Missing base_url (set KANTAN_LLM_BASE_URL or base_url=...) for provider: compat` | 互換URL不足 |
| E4 | `ProviderUnavailableError` | `[kantan-llm][E4] No available provider. Reasons: {reasons}` | `providers=[...]` 全滅 |
| E5 | `UnsupportedProviderError` | `[kantan-llm][E5] Unsupported provider: {provider}` | 未対応provider |
| E6 | `WrongAPIError` | `[kantan-llm][E6] Responses API is not enabled for provider: {provider}` | 互換でResponses呼び出し |
| E7 | `WrongAPIError` | `[kantan-llm][E7] Chat Completions API is not enabled for provider: {provider}` | OpenAIでChat呼び出し（ガード用） |
| E8 | `InvalidOptionsError` | `[kantan-llm][E8] Specify only one of provider=... or providers=[...]` | オプション不整合 |
| E9 | `MissingConfigError` | `[kantan-llm][E9] Missing base_url (set LMSTUDIO_BASE_URL or base_url=...) for provider: lmstudio` | LMStudio URL不足 |
| E10 | `MissingConfigError` | `[kantan-llm][E10] Missing base_url (set OLLAMA_BASE_URL or base_url=...) for provider: ollama` | Ollama URL不足 |
| E11 | `MissingConfigError` | `[kantan-llm][E11] Missing OPENROUTER_API_KEY for provider: openrouter` | OpenRouterキー不足 |
| E12 | `MissingConfigError` | `[kantan-llm][E12] Missing GOOGLE_API_KEY for provider: google` | Googleキー不足 |
| E13 | `MissingConfigError` | `[kantan-llm][E13] Missing CLAUDE_API_KEY for provider: anthropic` | Anthropicキー不足 |
| E14 | `InvalidTracerError` | `[kantan-llm][E14] Invalid tracer (expected TracingProcessor): {tracer}` | `tracer=` が不正 |
| E15 | `MissingDependencyError` | `[kantan-llm][E15] Missing optional dependency for tracer: {dependency}` | OTEL等が未導入 |
| E16 | `NotSupportedError` | `[kantan-llm][E16] Not supported: {feature}` | 検索機能の未対応 |

## 7. Tracing / Tracer（F8）

本章は `docs/concept.md` の F8 を定義し、OpenAI Agents SDK と同等の利用感を目標とする（ただし `kantan-llm` は OpenAI Agents SDK に必須依存しない）。

### 7.1 `trace` を利用した場合、Traceコンテキストを生成できる（F8）

- Given: `workflow_name` が指定されている
- When: `kantan_llm.tracing.trace(workflow_name, ...)` を呼ぶ
- Then: `Trace` を返す
- And: `with trace(...):` で `Trace` が開始/終了される

### 7.2 `with trace` を使わずにLLMを呼んだ場合、自動でTraceを作成して記録する（F8）

- Given: カレントTraceが存在しない
- When: `llm.responses.create(...)` または `llm.chat.completions.create(...)` を呼ぶ
- Then: 呼び出し単位で `Trace` を自動生成し、その中にスパンを1つ作成して記録する
- And: 自動生成Traceの `workflow_name` は `default_workflow_name` とする

### 7.3 `with trace` の内側でLLMを呼んだ場合、同一Traceにスパンを追加して記録する（F8）

- Given: カレントTraceが存在する（`with trace(...):` の内側）
- When: `llm.responses.create(...)` または `llm.chat.completions.create(...)` を呼ぶ
- Then: 既存Traceの子スパンとして記録する

### 7.4 Tracer（Processor）I/F は OpenAI Agents SDK と同一のメソッド集合を持つ（F8）

- Given: `tracer` が TracingProcessor互換オブジェクトである
- When: `tracer.on_trace_start/ on_trace_end/ on_span_start/ on_span_end/ shutdown/ force_flush` を呼ぶ
- Then: 例外を呼び出し元へ伝播させない（トレーシング失敗は非致命とする）

備考:
- `kantan-llm` は `agents` を import しないことを保証する（オプション連携を除く）。
- 互換性は「同名メソッド + 同様の引数」を前提とする（Pythonのダックタイピング）。

### 7.5 OpenAI Agents SDK に Tracer を登録した場合、同じTracer実装で収集できる（F8）

- Given: OpenAI Agents SDK が利用されている
- When: `agents.tracing.add_trace_processor(tracer)` のように登録する
- Then: `kantan-llm` の PrintTracer / SQLiteTracer / OTELTracer はそのまま Tracer として利用できる

### 7.6 `get_llm(..., tracer=...)` のデフォルトは PrintTracer とし、色分け表示する（F8）

- Given: `tracer` が未指定
- When: `get_llm(model)` を呼ぶ
- Then: PrintTracer を利用する
- And: 入力（プロンプト）と出力が色分けされて標準出力へ表示される
- And: usage等の付帯情報はデフォルトでは表示しない
- And: trace_id / span_id / 経過時間等の付帯情報もデフォルトでは表示しない

### 7.7 Tracer実装を提供する（F8）

#### 7.7.1 PrintTracer

- Given: PrintTracerが有効
- When: Trace/Span が開始/終了する
- Then: 入力（プロンプト）と出力を色分けしてログを出力する
- And: Token/KEY等の秘匿値っぽい文字列は簡易マスクする（例: `sk-...` / `Bearer ...` / `api_key=...`）
- And: 省略はデフォルトで行わない
- And: 環境変数 `KANTAN_LLM_TRACING_MAX_CHARS` が設定されている場合のみ、入力/出力を指定文字数で省略して表示する
- And: 表示は入力と出力のみとし、usage等の付帯情報は表示しない

#### 7.7.2 SQLiteTracer

- Given: SQLiteTracerが有効
- When: Trace/Span が開始/終了する
- Then: SQLiteに永続化する（TraceとSpanを後から参照可能）
- And: 環境変数 `KANTAN_LLM_TRACING_MAX_CHARS` が設定されている場合のみ、保存する入力/出力を指定文字数で省略する

#### 7.7.3 OTELTracer

- Given: OTELTracerが有効
- When: Trace/Span が開始/終了する
- Then: OpenTelemetryのSpanとしてエクスポートできる
- And: 環境変数 `KANTAN_LLM_TRACING_MAX_CHARS` が設定されている場合のみ、送信する入力/出力を指定文字数で省略する

### 7.8 LLM入出力の記録内容（F8）

#### 7.8.1 入力（プロンプト）

- Given: LLM呼び出しが行われる
- When: Tracerへ入力を記録する
- Then: `messages`（Chat）または `input`（Responses）に相当する内容を記録する

#### 7.8.2 出力

- Given: LLM呼び出しが成功して応答が返る
- When: Tracerへ出力を記録する
- Then: 出力テキストを優先して記録する
- And: 出力テキストが無い場合、構造化出力（structured output）を記録する
- And: さらに無い場合、function calling（tool call）の内容を記録する

#### 7.8.3 出力を記録した場合、output_kind を区別保存する（F8）

- Given: LLM呼び出しの出力が記録される
- When: Tracerが出力を保存する
- Then: `output_kind` を `text` / `tool_calls` / `structured` / `judge` のいずれかで保存する
- And: tool call を検出できる場合、`tool_calls_json` に保存する
- And: 構造化出力を検出できる場合、`structured_json` に保存する
- And: rubric を抽出できる場合、`output_kind="judge"` を優先する

### 7.9 usage を記録する（F8）

- Given: LLM呼び出しの応答に usage 情報が含まれる
- When: Spanを記録する
- Then: Spanの `usage` に best-effort で記録する
- And: Trace側に合計usageをキャッシュしてもよい（任意、正本はSpan）

## 8. Trace検索サービス（F9）

本章は Trace/Span を検索・抽出する共通I/Fを定義する。

### 8.1 検索サービスを呼び出した場合、Trace/Span を取得できる（F9）

- Given: `TraceSearchService` が利用可能
- When: `search_traces(query=...)` または `search_spans(query=...)` を呼ぶ
- Then: 条件に一致する `TraceRecord` / `SpanRecord` を返す

### 8.2 trace_id を指定した場合、単一Trace/Spanを取得できる（F9）

- Given: `trace_id` または `span_id` が指定されている
- When: `get_trace(trace_id)` または `get_span(span_id)` を呼ぶ
- Then: 対象が存在すれば `Record` を返し、存在しなければ `None` を返す

### 8.3 既存Traceに追加されたSpanを取得できる（F9）

- Given: `trace_id` が指定されている
- When: `get_spans_since(trace_id, since_seq)` を呼ぶ
- Then: `since_seq` より後に追加されたSpanを返す（`ingest_seq > since_seq`）
- And: 返却順は `ingest_seq` 昇順とする
- And: `since_seq=None` の場合は全件を返す

### 8.4 tool_call / structured output を含むTrace/Spanを抽出できる（F9）

- Given: `has_tool_call` や `keywords` 等の条件が指定されている
- When: `search_traces` / `search_spans` を呼ぶ
- Then: 条件に一致するTrace/Spanのみを返す

### 8.5 ルーブリックスコア等の評価値を抽出できる（F9）

- Given: structured output に `rubric.score` 等の値が含まれる
- When: 検索または抽出処理を実行する
- Then: 指定キーの値を取得できる
 - And: `SpanRecord.rubric.score` / `SpanRecord.rubric.comment` に正規化して保持する

### 8.6 keywords の意味は固定とする（F9）

- Given: `keywords` が指定されている
- When: 検索条件を評価する
- Then: `input`/`output` を対象に部分一致で検索する
- And: 複数語は AND として扱う
- And: 大文字小文字は区別しない

### 8.7 時刻はUTCのaware datetimeで扱う（F9）

- Given: `started_from` / `started_to` を指定して検索する
- When: 時刻の比較を行う
- Then: UTCのaware datetimeを正本とし、利用側でユーザーのタイムゾーンへ変換する

### 8.8 capabilities を返す（F9）

- Given: `TraceSearchService` が利用可能
- When: `capabilities()` を呼ぶ
- Then: `supports_since` / `supports_limit` 等の可否情報を返す

### 8.9 supports_since=False の場合の挙動（F9）

- Given: `capabilities.supports_since=False`
- When: `get_spans_since` を呼ぶ
- Then: `NotSupportedError` を送出する

## 9. SQLite正本の改善ループ強化（F10/F11）

### 9.1 SQLiteTracerでSpanを記録した場合、Span挿入とusage_total更新は原子化される（F10）

- Given: SQLiteTracer が有効
- And: Spanの usage が取得できる
- When: `on_span_end` が呼ばれる
- Then: `spans` への INSERT/REPLACE と `traces.metadata_json` の usage_total 更新は同一トランザクションで実行される
- And: commit は最後に1回だけ行われる
- And: 途中で例外が起きた場合は rollback され、部分書き込みにならない

### 9.2 usage を保存する場合、最小正規化ルールを適用する（F10）

- Given: `usage` が dict として取得できる
- When: Spanを保存する
- Then: `usage_json` は best-effort で記録される
- And: `input_tokens` が無く `prompt_tokens` があれば `input_tokens=prompt_tokens` を付与する
- And: `output_tokens` が無く `completion_tokens` があれば `output_tokens=completion_tokens` を付与する
- And: `total_tokens` が無い場合は `input_tokens + output_tokens` を優先し、無ければ `prompt_tokens + completion_tokens` を使う
- And: 数値でない値は加算しない

### 9.3 Traceの usage_total は正規化後のusageで合算される（F10）

- Given: Spanの usage が正規化された
- When: `usage_total` を更新する
- Then: 正規化後の数値のみを合算して保持する

### 9.4 `find_failed_judges` を使った場合、閾値未満のjudgeのみ返す（F11）

- Given: `TraceSearchService` が利用可能
- When: `find_failed_judges(service, threshold, ...)` を呼ぶ
- Then: `span_type="custom"` かつ `name="judge"` の Span だけを対象とする
- And: `rubric.score < threshold` の Span のみを返す

### 9.5 `trace_query` を指定した場合、対象Traceに限定してjudgeを抽出する（F11）

- Given: `trace_query` が指定されている
- When: `find_failed_judges` を呼ぶ
- Then: 先に `search_traces(trace_query)` で trace_id を絞り、その範囲だけを検索する

### 9.6 capabilitiesで未対応の条件がある場合、NotSupportedErrorを返す（F11）

- Given: `capabilities()` が条件に対して未対応を返す
- When: `find_failed_judges` がその条件を利用する
- Then: `NotSupportedError` を送出する

### 9.7 `group_failed_by_bucket` を使った場合、最小ルールでグルーピングする（F11）

- Given: failed な judge Span の一覧がある
- When: `group_failed_by_bucket(spans)` を呼ぶ
- Then: `rubric.tags[0]` があればそれを bucket として使う
- And: 無ければ `rubric.comment` の先頭トークンを使う
- And: それも無ければ `"other"` を使う
