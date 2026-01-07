# kantan-llm 😺✨

「LLM呼ぶたびに毎回書くやつ（キー/URL/プロバイダー判定）」を消して、`get_llm()` 一発で呼べる薄いPythonライブラリです。

**ポイント:** いろんなプロバイダー/モデルの環境変数をあらかじめ設定しておけば、あとは `get_llm("model-name")` するだけで “いい感じ” に繋がります 😺✨

## 更新内容（v0.1.7）

- Async導線（`get_async_llm` / `get_async_llm_client`）を追加
- KantanAsyncLLM の streaming API とまとめトレースを追加
- Streaming 出力のフォールバック順序（`output_text` → delta → `output_item`）を明確化
- Agents SDK 連携の利用方針を整理

## 対応プロバイダー（ざっくり）🌍

- OpenAI（Responses）
- Anthropic（Claude / OpenAI互換SDK）
- OpenRouter（OpenAI互換Chat）
- Google（Gemini / OpenAI互換Chat）
- LMStudio / Ollama / 任意のOpenAI互換（Chat）

## インストール 📦

```bash
pip install kantan-llm
```

## まずは最短で動かす 🚀

### OpenAI（Responses API が正本）

```bash
export OPENAI_API_KEY="sk-..."
```

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini")
res = llm.responses.create(input="こんにちは。1行で自己紹介して。")
print(res.output_text)
```

`llm` は OpenAI SDK 互換で、未定義属性は内部のクライアントへ委譲されます。

### OpenAI互換（Chat Completions が正本）

#### LMStudio（例: `openai/gpt-oss-20b`）

```bash
export LMSTUDIO_BASE_URL="http://192.168.11.16:1234"  # /v1 は省略OK
```

```python
from kantan_llm import get_llm

llm = get_llm("openai/gpt-oss-20b", provider="lmstudio")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Ollama（例）

```bash
export OLLAMA_BASE_URL="http://localhost:11434"  # /v1 は省略OK
```

```python
from kantan_llm import get_llm

llm = get_llm("llama3.2", provider="ollama")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Anthropic（Claude / OpenAI互換SDK）

```bash
export CLAUDE_API_KEY="sk-ant-..."
```

```python
from kantan_llm import get_llm

llm = get_llm("claude-3-5-sonnet-latest")  # `CLAUDE_API_KEY` があれば provider=anthropic（推測）
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### OpenRouter（Claude等を含む）

```bash
export OPENROUTER_API_KEY="..."
```

```python
from kantan_llm import get_llm

llm = get_llm("anthropic/claude-3.5-sonnet", provider="openrouter")  # Anthropic優先のためOpenRouterは明示推奨
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Google（Gemini / OpenAI互換エンドポイント扱い）

```bash
export GOOGLE_API_KEY="..."
```

```python
from kantan_llm import get_llm

llm = get_llm("gemini-2.0-flash")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

## 使い分けルール 🧭

- `gpt-oss-*` → 固定推測しない（環境変数フォールバック。必要なら `provider=` 指定）
- `gpt-*`（`gpt-oss-*` を除く） → `openai`
- `gemini-*` → `google`
- `claude-*` → `anthropic`（`CLAUDE_API_KEY` がある場合）→ `openrouter`（`OPENROUTER_API_KEY` がある場合）→ それ以外は `compat`
- 推測できないモデル名は、環境変数があるものを優先順で選びます: `lmstudio` → `ollama` → `openrouter` → `anthropic` → `google`

## 明示指定（上書き）🎯

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini", provider="openai")
```

## フォールバック（順番が優先度）🧯

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini", providers=["openai", "lmstudio", "openrouter"])
```

## Tracing / Tracer 🧵

デフォルトで、`get_llm()` は LLM 呼び出しの入力/出力を色分け表示する簡易トレーサー（PrintTracer）を有効にします。

```python
from kantan_llm import get_llm
from kantan_llm.tracing import trace

llm = get_llm("gpt-4.1-mini")
with trace("workflow"):
    llm.responses.create(input="こんにちは。1行で挨拶して。")
```

詳しく: `docs/tracing.md`

## Async（ASGI対応）
ASGI（FastAPI/Starlette）で event loop をブロックしないため、async 導線を提供します。

### get_async_llm()（推奨）
- kantan-llm の保証（正規化/フォールバック/ガード/トレース）を async でも維持します。

### Async streaming（KantanAsyncLLM）
KantanAsyncLLM では streaming API を提供し、最終応答でまとめてトレースします。

```python
from kantan_llm import get_async_llm

llm = get_async_llm("gpt-4.1-mini")
async with llm.responses.stream(input="1行で挨拶して。") as stream:
    async for _ in stream:
        pass
    final = await stream.get_final_response()
print(final.output_text)
```

注意:
- 出力の取得順序は `output_text` → ストリーム差分 → `output_item` の順です。
- いずれも無い場合は、ストリームは完了してもトレースの output は空になります（例: `gpt-5-mini`）。

### get_async_llm_client()（Escape hatch）
- `AsyncOpenAI` の raw client を返します（互換性最大化、Agents SDK 注入向け）。
- **注意:** raw client 返却では API ガード / 自動トレーシングは行いません。
- 代わりに `model/provider/base_url` を含む bundle を返し、正規化済み model 名を下流へ渡せます。

## OpenAI Agents SDK 連携
Agents SDK は AsyncOpenAI client を差し替え可能です。

- デフォルト client を差し替える:
  - `set_default_openai_client(AsyncOpenAI(...))`
- モデル単位で client を渡す:
  - `OpenAIResponsesModel(..., openai_client=AsyncOpenAI(...))`

kantan-agents では上記 2 つのメソッドを利用して client を差し替えます。

kantan-llm で Agents SDK を使う場合の推奨:

- 互換性優先: `bundle = get_async_llm_client(...)`
  - `bundle.client` を Agents SDK に渡す
  - `bundle.model`（正規化済み）を Agent/Model 側へ渡す
- kantan のガード/トレースも使いたい: `llm = get_async_llm(...)`
  - ただし Agents SDK 側と二重トレースになり得るため、どちらでトレースするか方針を決める（下記）。

### Tracing（二重計測を避ける）
Agents SDK 側にはトレーシング無効化の導線があります（例: `set_tracing_disabled(True)` や環境変数）。
運用では以下のどちらかを選びます。

- A) Agents SDK のトレースを有効、kantan 側トレースは無効（または raw client を使う）
- B) kantan のトレースを有効、Agents SDK 側トレースは無効

## 検索（SQLite）🔎

`SQLiteTracer` を使うと、Trace/Span を軽量に検索できます。

```python
from kantan_llm.tracing import SpanQuery, TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
traces = tracer.search_traces(query=TraceQuery(keywords=["hello"], limit=10))
spans = tracer.search_spans(query=SpanQuery(keywords=["hello"], limit=10))
```

詳しく: `docs/search.md`
チュートリアル: `docs/tutorial_trace_analysis.md`

## Examples / サンプル 📚

- `examples/tracing_basic.py`
- `examples/search_sqlite.py`

## 環境変数 🔐

- OpenAI
  - `OPENAI_API_KEY`（必須）
  - `OPENAI_BASE_URL`（任意）
- Generic互換（`compat`）
  - `KANTAN_LLM_BASE_URL`（必須）
  - `KANTAN_LLM_API_KEY`（任意：未設定ならダミー値を使う）
- LMStudio
  - `LMSTUDIO_BASE_URL`（必須）
- Ollama
  - `OLLAMA_BASE_URL`（必須）
- OpenRouter
  - `OPENROUTER_API_KEY`（必須）
- Anthropic
  - `CLAUDE_API_KEY`（必須）
  - `CLAUDE_BASE_URL`（任意）
- Google
  - `GOOGLE_API_KEY`（必須）
  - `GOOGLE_BASE_URL`（任意）

## エラー例 🧨

- 失敗（OpenAIキー不足）: `python -c 'from kantan_llm import get_llm; get_llm(\"gpt-4.1-mini\")'` → `[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai`

## テスト 🧪

ライブ統合テスト（実API）はオプトインです:

```bash
KANTAN_LLM_RUN_LIVE_TESTS=1 pytest -q -m integration
```
