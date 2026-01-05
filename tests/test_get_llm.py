import asyncio
import pytest

from types import SimpleNamespace

from kantan_llm import (
    InvalidOptionsError,
    MissingConfigError,
    WrongAPIError,
    get_async_llm,
    get_async_llm_client,
    get_llm,
)
from kantan_llm.tracing import PrintTracer, get_trace_provider, set_trace_processors


def test_openai_inference_and_guard(monkeypatch):
    # Japanese/English: 最小スモーク（推測とガード） / minimal smoke (inference + guards)
    # (コメントは日本語/英語併記のルールに従う)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    llm = get_llm("gpt-4.1-mini")
    assert llm.provider == "openai"
    assert llm.model == "gpt-4.1-mini"
    assert callable(llm.responses.create)

    with pytest.raises(WrongAPIError) as exc:
        _ = llm.chat
    assert "[kantan-llm][E7]" in str(exc.value)


def test_openai_prefix_strips_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm = get_llm("openai/gpt-4.1-mini")
    assert llm.provider == "openai"
    assert llm.model == "gpt-4.1-mini"


def test_missing_openai_key_is_clear(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("gpt-4.1-mini")
    assert str(exc.value) == "[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai"


def test_compat_inference_and_guard(monkeypatch):
    monkeypatch.setenv("KANTAN_LLM_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.delenv("KANTAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    llm = get_llm("claude-3-5-sonnet-latest")
    assert llm.provider == "compat"
    assert llm.model == "claude-3-5-sonnet-latest"
    assert callable(llm.chat.completions.create)

    with pytest.raises(WrongAPIError) as exc:
        _ = llm.responses
    assert "[kantan-llm][E6]" in str(exc.value)


def test_google_inference_from_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")

    llm = get_llm("gemini-2.0-flash")
    assert llm.provider == "google"
    assert llm.model == "gemini-2.0-flash"
    assert callable(llm.chat.completions.create)


def test_missing_google_key_is_clear(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("gemini-2.0-flash", provider="google")
    assert str(exc.value) == "[kantan-llm][E12] Missing GOOGLE_API_KEY for provider: google"


def test_claude_inference_uses_anthropic_when_claude_api_key_exists(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    llm = get_llm("claude-3-5-sonnet-latest")
    assert llm.provider == "anthropic"
    assert llm.model == "claude-3-7-sonnet-20250219"
    assert callable(llm.chat.completions.create)


def test_claude_inference_uses_openrouter_when_openrouter_key_exists(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    llm = get_llm("claude-3-5-sonnet-latest")
    assert llm.provider == "openrouter"
    assert llm.model == "anthropic/claude-3.5-sonnet"
    assert callable(llm.chat.completions.create)


def test_openrouter_key_missing_is_clear(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("claude-3-5-sonnet-latest", provider="openrouter")
    assert str(exc.value) == "[kantan-llm][E11] Missing OPENROUTER_API_KEY for provider: openrouter"


def test_anthropic_key_missing_is_clear(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("claude-3-5-sonnet-latest", provider="anthropic")
    assert str(exc.value) == "[kantan-llm][E13] Missing CLAUDE_API_KEY for provider: anthropic"


def test_missing_compat_base_url_is_clear(monkeypatch):
    monkeypatch.delenv("KANTAN_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("claude-3-opus-latest")
    assert str(exc.value) == (
        "[kantan-llm][E3] Missing base_url (set KANTAN_LLM_BASE_URL or base_url=...) for provider: compat"
    )


def test_fallback_providers_works(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234")

    llm = get_llm("gpt-4.1-mini", providers=["openai", "lmstudio"])
    assert llm.provider == "lmstudio"


def test_provider_and_providers_is_invalid(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(InvalidOptionsError) as exc:
        get_llm("gpt-4.1-mini", provider="openai", providers=["openai"])
    assert str(exc.value) == "[kantan-llm][E8] Specify only one of provider=... or providers=[...]"


def test_llm_delegates_unknown_attrs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class DummyClient:
        def __init__(self):
            self.foo = "bar"
            self.models = SimpleNamespace(list=lambda: ["ok"])

    monkeypatch.setattr("kantan_llm.OpenAI", lambda **kwargs: DummyClient())
    llm = get_llm("gpt-4.1-mini")
    assert llm.foo == "bar"
    assert llm.models.list() == ["ok"]


def test_async_client_bundle_normalizes_openai_prefix(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    bundle = get_async_llm_client("openai/gpt-4.1-mini")
    assert bundle.provider == "openai"
    assert bundle.model == "gpt-4.1-mini"


def test_async_llm_guard_and_create(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class DummyResponses:
        async def create(self, *args, **kwargs):
            return SimpleNamespace(output_text="ok", usage={"total_tokens": 1})

    class DummyChatCompletions:
        async def create(self, *args, **kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

    class DummyChat:
        completions = DummyChatCompletions()

    class DummyAsyncClient:
        def __init__(self):
            self.responses = DummyResponses()
            self.chat = DummyChat()

    monkeypatch.setattr("kantan_llm.AsyncOpenAI", lambda **kwargs: DummyAsyncClient())

    llm = get_async_llm("gpt-4.1-mini")
    assert llm.provider == "openai"

    with pytest.raises(WrongAPIError) as exc:
        _ = llm.chat
    assert "[kantan-llm][E7]" in str(exc.value)

    async def _run() -> str:
        res = await llm.responses.create(input="hi")
        return res.output_text

    assert asyncio.run(_run()) == "ok"


def test_async_resolver_parity_openrouter(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    llm = get_llm("claude-3-5-sonnet-latest")
    bundle = get_async_llm_client("claude-3-5-sonnet-latest")

    assert llm.provider == bundle.provider
    assert llm.model == bundle.model


def test_async_tracer_default_parity(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    original_processors = get_trace_provider().get_processors()
    try:
        set_trace_processors([])
        get_llm("gpt-4.1-mini")
        sync_processors = get_trace_provider().get_processors()

        set_trace_processors([])
        get_async_llm("gpt-4.1-mini")
        async_processors = get_trace_provider().get_processors()
    finally:
        set_trace_processors(list(original_processors))

    assert sync_processors and async_processors
    assert isinstance(sync_processors[0], PrintTracer)
    assert isinstance(async_processors[0], PrintTracer)


def test_async_stream_traces_summary(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class CollectingTracer:
        def __init__(self):
            self.spans = []

        def on_trace_start(self, trace) -> None:
            return

        def on_trace_end(self, trace) -> None:
            return

        def on_span_start(self, span) -> None:
            return

        def on_span_end(self, span) -> None:
            self.spans.append(span)

        def shutdown(self) -> None:
            return

        def force_flush(self) -> None:
            return

    class DummyStream:
        def __init__(self):
            self._events = iter([{"type": "delta"}, {"type": "done"}])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._events)
            except StopIteration:
                raise StopAsyncIteration

        async def get_final_response(self):
            return SimpleNamespace(output_text="streamed", usage={"total_tokens": 2})

    class DummyResponses:
        async def create(self, *args, **kwargs):
            return SimpleNamespace(output_text="ok", usage={"total_tokens": 1})

        def stream(self, *args, **kwargs):
            return DummyStream()

    class DummyChatCompletions:
        async def create(self, *args, **kwargs):
            return {"choices": [{"message": {"content": "ok"}}]}

        def stream(self, *args, **kwargs):
            return DummyStream()

    class DummyChat:
        completions = DummyChatCompletions()

    class DummyAsyncClient:
        def __init__(self):
            self.responses = DummyResponses()
            self.chat = DummyChat()

    monkeypatch.setattr("kantan_llm.AsyncOpenAI", lambda **kwargs: DummyAsyncClient())

    tracer = CollectingTracer()
    original_processors = get_trace_provider().get_processors()
    try:
        llm = get_async_llm("gpt-4.1-mini", tracer=tracer)

        async def _run() -> str:
            async with llm.responses.stream(input="hi") as stream:
                async for _ in stream:
                    pass
                final = await stream.get_final_response()
                return final.output_text

        assert asyncio.run(_run()) == "streamed"
    finally:
        set_trace_processors(list(original_processors))

    assert tracer.spans
    span = tracer.spans[-1]
    assert span.span_data.output == "streamed"


def test_async_stream_output_item_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class CollectingTracer:
        def __init__(self):
            self.spans = []

        def on_trace_start(self, trace) -> None:
            return

        def on_trace_end(self, trace) -> None:
            return

        def on_span_start(self, span) -> None:
            return

        def on_span_end(self, span) -> None:
            self.spans.append(span)

        def shutdown(self) -> None:
            return

        def force_flush(self) -> None:
            return

    class DummyStream:
        def __init__(self):
            self._events = iter(
                [
                    {
                        "type": "response.output_item.done",
                        "item": {"content": [{"type": "output_text", "text": "OK"}]},
                    }
                ]
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._events)
            except StopIteration:
                raise StopAsyncIteration

    class DummyResponses:
        async def create(self, *args, **kwargs):
            return SimpleNamespace(output_text="ok", usage={"total_tokens": 1})

        def stream(self, *args, **kwargs):
            return DummyStream()

    class DummyAsyncClient:
        def __init__(self):
            self.responses = DummyResponses()

    monkeypatch.setattr("kantan_llm.AsyncOpenAI", lambda **kwargs: DummyAsyncClient())

    tracer = CollectingTracer()
    original_processors = get_trace_provider().get_processors()
    try:
        llm = get_async_llm("gpt-4.1-mini", tracer=tracer)

        async def _run() -> None:
            async with llm.responses.stream(input="hi") as stream:
                async for _ in stream:
                    pass

        asyncio.run(_run())
    finally:
        set_trace_processors(list(original_processors))

    assert tracer.spans
    span = tracer.spans[-1]
    assert span.span_data.output == "OK"
