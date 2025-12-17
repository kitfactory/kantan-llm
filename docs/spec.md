# kantan-llm spec（v0.1）

本書は `docs/concept.md` の Spec ID を参照し、Given/When/Then 形式で仕様を定義する。

## 1. 用語

- OpenAI: OpenAI公式API（Responses API を正本とする）
- 互換（Chat）: OpenAI Chat Completions API 互換のサーバー（他社/ローカル等）
- provider: `openai` / `compat` / `lmstudio` / `ollama` / `openrouter` / `google` 等の識別子

## 2. API（F1）

### 2.1 `get_llm` を呼び出した場合、LLMクライアントを返す（F1）

- Given: `model` が指定されている
- When: `get_llm(model, **options)` を呼ぶ
- Then: `llm` を返す
- And: OpenAIの場合 `llm.responses.create(...)` が利用できる
- And: 互換（Chat）の場合 `llm.chat.completions.create(...)` が利用できる

### 2.2 `provider` を指定した場合、推測結果を上書きする（F5）

- Given: `provider` が指定されている
- When: `get_llm(model, provider=provider)` を呼ぶ
- Then: プロバイダー推測より `provider` を優先する

### 2.3 `providers` を指定した場合、利用可能なものを順に試す（F6）

- Given: `providers` が指定されている
- When: `get_llm(model, providers=[...])` を呼ぶ
- Then: 指定順にプロバイダーを評価して最初に利用可能なものを選ぶ
- And: 全滅した場合、各候補の失敗理由が分かるエラーを送出する

## 3. プロバイダー推測（F2）

### 3.1 `gpt-*` を指定した場合、OpenAIとして扱う（F2）

- Given: `model` が `gpt-` で始まる
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openai` を選択する

### 3.2 `claude-*` を指定した場合、互換（Chat）として扱う（F2）

- Given: `model` が `claude-` で始まる
- And: `OPENROUTER_API_KEY` と `CLAUDE_API_KEY` のどちらも未設定
- When: `get_llm(model)` を呼ぶ
- Then: provider=`compat` を選択する

### 3.3 `claude-*` を指定した場合、OpenRouterとして扱う（F2）

- Given: `model` が `claude-` で始まる
- And: `OPENROUTER_API_KEY` または `CLAUDE_API_KEY` が設定されている
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openrouter` を選択する
- And: OpenRouter向けに必要な場合はモデル名を正規化してよい（例: `claude-3-5-sonnet-latest` → `anthropic/claude-3.5-sonnet`）

### 3.4 `gemini-*` を指定した場合、Googleとして扱う（F2）

- Given: `model` が `gemini-` で始まる
- When: `get_llm(model)` を呼ぶ
- Then: provider=`google` を選択する

### 3.5 `openai/...` の明示表記を指定した場合、OpenAIとして扱う（F2）

- Given: `model` が `openai/` で始まる（例: `openai/gpt-4.1-mini`）
- When: `get_llm(model)` を呼ぶ
- Then: provider=`openai` を選択する
- And: provider が `openai` のとき、実際のAPI呼び出しに使うモデル名は `openai/` を除いた値とする
- And: provider を明示指定して `openai` 以外を選ぶ場合、`openai/` はモデル名の一部として扱い保持してよい（例: LMStudio等）

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
- And: `OPENROUTER_API_KEY` と `CLAUDE_API_KEY` のどちらも未設定
- When: `get_llm(model)` を呼ぶ
- Then: Error ID 付きのエラーを送出する

### 5.4 Google のAPIキーが無い場合、キー不足エラーを返す（F4）

- Given: provider=`google`
- And: `GOOGLE_API_KEY` が未設定
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
| E11 | `MissingConfigError` | `[kantan-llm][E11] Missing OPENROUTER_API_KEY (or CLAUDE_API_KEY) for provider: openrouter` | OpenRouterキー不足 |
| E12 | `MissingConfigError` | `[kantan-llm][E12] Missing GOOGLE_API_KEY for provider: google` | Googleキー不足 |
