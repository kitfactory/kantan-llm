# kantan-llm 😺✨

「LLM呼ぶたびに毎回書くやつ（キー/URL/プロバイダー判定）」を消して、`get_llm()` 一発で呼べる薄いPythonライブラリです。

**ポイント:** いろんなプロバイダー/モデルの環境変数をあらかじめ設定しておけば、あとは `get_llm("model-name")` するだけで “いい感じ” に繋がります 😺✨

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

- `gpt-*` → `openai`
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
