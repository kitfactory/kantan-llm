# SPEC-ASYNC-001: Async client support (escape hatch) + Agents SDK integration

## Status
Draft

## 対応 Spec ID
- F12

## 1. 目的 / Scope
ASGI（FastAPI/Starlette）環境で event loop をブロックしない async 導線を追加する。
sync/async の推測・正規化の差分をなくし、Agents SDK 連携に必要な情報を外に出す。
KantanAsyncLLM では streaming API を提供し、最終応答でまとめてトレースする。

## 2. 非ゴール
- Async-first API を paved path にする
- Streaming の保証（sync / paved path）
- raw client 返却に対する API ガード / 自動トレーシングの強制

## 3. 用語
- AsyncClientBundle: raw AsyncOpenAI と正規化済み model/provider/base_url を持つ束
- Raw async client: SDK の AsyncOpenAI をそのまま返す導線
- KantanAsyncLLM: KantanLLM と同等保証を提供する async ラッパー
- Resolver: provider 推測 / model 正規化 / env 解決 / フォールバックの単一実装

## 4. Async escape hatch: get_async_llm_client（F12）

### 4.1 get_async_llm_client を呼び出した場合、AsyncClientBundle を返す（F12）
- Given: model が指定されている
- When: get_async_llm_client(model, **options) を呼ぶ
- Then: AsyncClientBundle を返す
- And: bundle.client は SDK の AsyncOpenAI を “そのまま” 返す

### 4.2 raw client 返却時、API ガードと自動トレーシングを強制しない（F12）
- Given: get_async_llm_client を利用する
- When: bundle.client を直接利用する
- Then: Responses/Chat の API ガードは行わない
- And: 自動トレーシングは有効化しない

### 4.3 AsyncClientBundle は正規化済み model/provider/base_url を含む（F12）
- Given: get_async_llm_client を利用する
- When: AsyncClientBundle を受け取る
- Then: bundle.model は正規化済みの model 名である
- And: bundle.provider と bundle.base_url は解決結果を保持する

## 5. 推奨 async: get_async_llm（KantanAsyncLLM）（F12）

### 5.1 get_async_llm を呼び出した場合、KantanAsyncLLM を返す（F12）
- Given: model が指定されている
- When: get_async_llm(model, **options) を呼ぶ
- Then: KantanAsyncLLM を返す

### 5.2 KantanAsyncLLM は sync と同等の保証を提供する（F12）
- Given: get_async_llm を利用する
- When: LLM を呼び出す
- Then: 正規化 / フォールバック / API ガード / 自動トレーシング（有効時）を適用する

### 5.3 KantanAsyncLLM は基盤 AsyncOpenAI にアクセスできる（F12）
- Given: KantanAsyncLLM を利用する
- When: llm.client にアクセスする
- Then: AsyncOpenAI を返す

### 5.4 KantanAsyncLLM の streaming API を利用できる（F12）
- Given: KantanAsyncLLM を利用する
- When: llm.responses.stream(...) または llm.chat.completions.stream(...) を呼ぶ
- Then: async stream を返す

### 5.5 streaming のトレースは最終応答でまとめて記録する（F12）
- Given: KantanAsyncLLM の streaming API を利用する
- When: ストリームが終了する
- Then: 最終応答をもとに output/usage をまとめて記録する
- And: 最終応答を取得できない場合は、ストリームのテキスト差分を結合して output を記録する
- And: `response.output_item.*` の `output_text` がある場合はそれも結合して記録する
- And: 取得順序は `output_text` → ストリーム差分 → `output_item` の順とする

### 5.6 streaming のテキスト差分も無い場合、output が空になることがある（F12）
- Given: KantanAsyncLLM の streaming API を利用する
- When: `output_text` もテキスト差分も返らない（例: `gpt-5-mini` が `response.output_item.*` のみ返す）
- Then: output が空のまま Span が記録される

## 6. Agents SDK 連携（F12）

kantan-agents では本章の差し替え導線を利用して client を注入する。

### 6.1 AsyncOpenAI client を Agents SDK のデフォルトに差し替えできる（F12）
- Given: AsyncClientBundle が返されている
- When: bundle.client を set_default_openai_client(...) に渡す
- Then: Agents SDK のデフォルト client として利用できる

### 6.2 モデル単位で openai_client を差し替えできる（F12）
- Given: AsyncClientBundle が返されている
- When: bundle.client を OpenAIResponsesModel(..., openai_client=...) に渡す
- Then: モデル単位で client を差し替えできる

### 6.3 正規化済み model 名を Agents SDK に渡せる（F12）
- Given: AsyncClientBundle が返されている
- When: bundle.model を Agent/Model 側へ渡す
- Then: 正規化済み model 名で動作する

## 7. Tracing policy（二重計測回避）（F12）

### 7.1 Agents SDK のトレースを使う場合、kantan 側は無効化できる（F12）
- Given: Agents SDK のトレーシング導線が利用可能
- When: Agents SDK 側のトレースを有効にする
- Then: kantan 側は raw client もしくはトレース無効で利用できる

### 7.2 kantan のトレースを使う場合、Agents SDK 側は無効化できる（F12）
- Given: Agents SDK のトレーシング導線が利用可能
- When: kantan 側のトレースを有効にする
- Then: Agents SDK 側のトレースを無効化できる

## 8. Resolver parity（最重要保証）（F12）

### 8.1 sync/async の推測・正規化結果が一致する（F12）
- Given: 同一の model と options と環境変数
- When: get_llm() と get_async_llm()/get_async_llm_client() を呼ぶ
- Then: provider/model/base_url の解決結果が一致する

## 9. 入力バリデーション / エラー（F12）

### 9.1 provider と providers を同時に指定した場合、InvalidOptionsError を返す（F12）
- Given: provider と providers が同時に指定されている
- When: get_async_llm()/get_async_llm_client() を呼ぶ
- Then: `[kantan-llm][E8] ...` を含むエラーを送出する

### 9.2 provider 推測に失敗した場合、ProviderInferenceError を返す（F12）
- Given: model から provider が推測できない
- When: get_async_llm()/get_async_llm_client() を呼ぶ
- Then: `[kantan-llm][E1] ...` を含むエラーを送出する

### 9.3 必要な環境変数が未設定の場合、MissingConfigError を返す（F12）
- Given: provider に必要な環境変数が未設定
- When: get_async_llm()/get_async_llm_client() を呼ぶ
- Then: `[kantan-llm][E2/E3/E9/E10/E11/E12/E13] ...` を含むエラーを送出する

### 9.4 providers が全滅した場合、ProviderUnavailableError を返す（F12）
- Given: providers が指定されている
- And: すべての候補が利用不可
- When: get_async_llm()/get_async_llm_client() を呼ぶ
- Then: `[kantan-llm][E4] ...` を含むエラーを送出する

### 9.5 未対応 provider を指定した場合、UnsupportedProviderError を返す（F12）
- Given: 未対応 provider が指定されている
- When: get_async_llm()/get_async_llm_client() を呼ぶ
- Then: `[kantan-llm][E5] ...` を含むエラーを送出する

### 9.6 tracer が不正な場合、InvalidTracerError を返す（F12）
- Given: tracer が TracingProcessor 互換ではない
- When: get_async_llm(..., tracer=tracer) を呼ぶ
- Then: `[kantan-llm][E14] ...` を含むエラーを送出する

### 9.7 Tracer の依存が未導入の場合、MissingDependencyError を返す（F12）
- Given: OTEL 等の任意依存が未導入
- When: get_async_llm(..., tracer=...) を呼ぶ
- Then: `[kantan-llm][E15] ...` を含むエラーを送出する

### 9.8 API ガードに違反した場合、WrongAPIError を返す（F12）
- Given: KantanAsyncLLM を利用している
- When: provider に対して不正な API を呼ぶ
- Then: `[kantan-llm][E6/E7] ...` を含むエラーを送出する

## 10. エラー一覧（メッセージは実装と完全一致）

| Error ID | 例外名 | メッセージ | 備考 |
|---|---|---|---|
| E1 | `ProviderInferenceError` | `[kantan-llm][E1] Provider inference failed for model: {model}` | 推測不能 |
| E2 | `MissingConfigError` | `[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai` | OpenAIキー不足 |
| E3 | `MissingConfigError` | `[kantan-llm][E3] Missing base_url (set KANTAN_LLM_BASE_URL or base_url=...) for provider: compat` | 互換URL不足 |
| E4 | `ProviderUnavailableError` | `[kantan-llm][E4] No available provider. Reasons: {reasons}` | `providers=[...]` 全滅 |
| E5 | `UnsupportedProviderError` | `[kantan-llm][E5] Unsupported provider: {provider}` | 未対応provider |
| E6 | `WrongAPIError` | `[kantan-llm][E6] Responses API is not enabled for provider: {provider}` | 互換でResponses呼び出し |
| E7 | `WrongAPIError` | `[kantan-llm][E7] Chat Completions API is not enabled for provider: {provider}` | OpenAIでChat呼び出し |
| E8 | `InvalidOptionsError` | `[kantan-llm][E8] Specify only one of provider=... or providers=[...]` | オプション不整合 |
| E9 | `MissingConfigError` | `[kantan-llm][E9] Missing base_url (set LMSTUDIO_BASE_URL or base_url=...) for provider: lmstudio` | LMStudio URL不足 |
| E10 | `MissingConfigError` | `[kantan-llm][E10] Missing base_url (set OLLAMA_BASE_URL or base_url=...) for provider: ollama` | Ollama URL不足 |
| E11 | `MissingConfigError` | `[kantan-llm][E11] Missing OPENROUTER_API_KEY for provider: openrouter` | OpenRouterキー不足 |
| E12 | `MissingConfigError` | `[kantan-llm][E12] Missing GOOGLE_API_KEY for provider: google` | Googleキー不足 |
| E13 | `MissingConfigError` | `[kantan-llm][E13] Missing CLAUDE_API_KEY for provider: anthropic` | Anthropicキー不足 |
| E14 | `InvalidTracerError` | `[kantan-llm][E14] Invalid tracer (expected TracingProcessor): {tracer}` | `tracer=` が不正 |
| E15 | `MissingDependencyError` | `[kantan-llm][E15] Missing optional dependency for tracer: {dependency}` | OTEL等が未導入 |

## 11. テスト観点（最低限）

### 11.1 resolver parity を確認する（F12）
- Given: 同一の model と options と環境変数
- When: get_llm() と get_async_llm()/get_async_llm_client() を呼ぶ
- Then: provider/model/base_url が一致する

### 11.2 model 正規化が一致する（F12）
- Given: openai/ prefix や alias を含む model
- When: sync/async の両方で resolver を通す
- Then: 正規化済み model が一致する

### 11.3 tracer 既定挙動が一致する（F12）
- Given: tracer 未指定
- When: get_llm() と get_async_llm() を呼ぶ
- Then: 既定の tracer 方針が一致する

### 11.4 streaming のまとめトレースが記録される（F12）
- Given: KantanAsyncLLM の streaming API を利用する
- When: 最終応答を取得してストリームを完了させる
- Then: span の output/usage が記録される
