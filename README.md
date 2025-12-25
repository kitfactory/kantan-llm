# kantan-llm 😺✨

A tiny Python library that removes the boring boilerplate (keys/URLs/provider selection) so you can call LLMs with a single `get_llm()` 💨

**Big idea:** set env vars for the providers/models you use, then just do `get_llm("model-name")` and it “just connects” 😺✨

## Supported providers (roughly) 🌍

- OpenAI (Responses)
- Anthropic (Claude via OpenAI-compatible SDK)
- OpenRouter (OpenAI-compatible Chat)
- Google (Gemini via OpenAI-compatible Chat)
- LMStudio / Ollama / any OpenAI-compatible Chat

## Install 📦

```bash
pip install kantan-llm
```

## Quickstart 🚀

### OpenAI (Responses API is the source of truth)

```bash
export OPENAI_API_KEY="sk-..."
```

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini")
res = llm.responses.create(input="Say hi in one short line.")
print(res.output_text)
```

`llm` is OpenAI SDK compatible (unknown attributes delegate to the underlying client).

### OpenAI-compatible (Chat Completions is the source of truth)

#### LMStudio (example: `openai/gpt-oss-20b`)

```bash
export LMSTUDIO_BASE_URL="http://192.168.11.16:1234"  # `/v1` is optional
```

```python
from kantan_llm import get_llm

llm = get_llm("openai/gpt-oss-20b", provider="lmstudio")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Ollama (example)

```bash
export OLLAMA_BASE_URL="http://localhost:11434"  # `/v1` is optional
```

```python
from kantan_llm import get_llm

llm = get_llm("llama3.2", provider="ollama")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Anthropic (Claude via OpenAI-compatible SDK)

```bash
export CLAUDE_API_KEY="sk-ant-..."
```

```python
from kantan_llm import get_llm

llm = get_llm("claude-3-5-sonnet-latest")  # if `CLAUDE_API_KEY` exists -> provider=anthropic (inferred)
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### OpenRouter (includes Claude, etc.)

```bash
export OPENROUTER_API_KEY="..."
```

```python
from kantan_llm import get_llm

llm = get_llm("anthropic/claude-3.5-sonnet", provider="openrouter")  # explicit is recommended (Anthropic takes precedence)
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

#### Google (Gemini via an OpenAI-compatible endpoint)

```bash
export GOOGLE_API_KEY="..."
```

```python
from kantan_llm import get_llm

llm = get_llm("gemini-2.0-flash")
cc = llm.chat.completions.create(messages=[{"role": "user", "content": "Return exactly: OK"}], max_tokens=16)
print(cc.choices[0].message.content)
```

## Provider rules 🧭

- `gpt-*` → `openai`
- `gemini-*` → `google`
- `claude-*` → `anthropic` (if `CLAUDE_API_KEY` is set) → `openrouter` (if `OPENROUTER_API_KEY` is set) → otherwise `compat`
- If the model name is not recognizable, it picks the first available provider by env vars: `lmstudio` → `ollama` → `openrouter` → `anthropic` → `google`

## Explicit provider 🎯

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini", provider="openai")
```

## Fallback (order = priority) 🧯

```python
from kantan_llm import get_llm

llm = get_llm("gpt-4.1-mini", providers=["openai", "lmstudio", "openrouter"])
```

## Tracing / Tracer 🧵

By default, `get_llm()` enables a simple tracer that prints input/output (colorized) for each LLM call.

```python
from kantan_llm import get_llm
from kantan_llm.tracing import trace

llm = get_llm("gpt-4.1-mini")
with trace("workflow"):
    llm.responses.create(input="Say hi.")
```

More: `docs/tracing.md`

## Search (SQLite) 🔎

Use `SQLiteTracer` as a lightweight search backend for traces/spans.

```python
from kantan_llm.tracing import SpanQuery, TraceQuery
from kantan_llm.tracing.processors import SQLiteTracer

tracer = SQLiteTracer("traces.sqlite3")
traces = tracer.search_traces(query=TraceQuery(keywords=["hello"], limit=10))
spans = tracer.search_spans(query=SpanQuery(keywords=["hello"], limit=10))
```

More: `docs/search.md`
Tutorial: `docs/tutorial_trace_analysis.md`

## Examples 📚

- `examples/tracing_basic.py`
- `examples/search_sqlite.py`

## Environment variables 🔐

- OpenAI
  - `OPENAI_API_KEY` (required)
  - `OPENAI_BASE_URL` (optional)
- Generic compatible (`compat`)
  - `KANTAN_LLM_BASE_URL` (required)
  - `KANTAN_LLM_API_KEY` (optional; falls back to a dummy value)
- LMStudio
  - `LMSTUDIO_BASE_URL` (required)
- Ollama
  - `OLLAMA_BASE_URL` (required)
- OpenRouter
  - `OPENROUTER_API_KEY` (required)
- Anthropic
  - `CLAUDE_API_KEY` (required)
  - `CLAUDE_BASE_URL` (optional)
- Google
  - `GOOGLE_API_KEY` (required)
  - `GOOGLE_BASE_URL` (optional)

## Error example 💥

- Missing OpenAI key: `python -c 'from kantan_llm import get_llm; get_llm(\"gpt-4.1-mini\")'` → `[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai`

## Tests 🧪

Live integration tests (real APIs) are opt-in:

```bash
KANTAN_LLM_RUN_LIVE_TESTS=1 pytest -q -m integration
```
