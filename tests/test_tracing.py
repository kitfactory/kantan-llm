from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import kantan_llm
from kantan_llm.tracing import get_trace_provider, set_trace_processors, trace
from kantan_llm.tracing.processors import NoOpTracer, PrintTracer
from kantan_llm.tracing.processor_interface import TracingProcessor


class RecordingTracer(TracingProcessor):
    """Japanese/English: テスト用の記録Tracer / recording tracer for tests."""

    def __init__(self) -> None:
        self.trace_started: list[Any] = []
        self.trace_ended: list[Any] = []
        self.span_started: list[Any] = []
        self.span_ended: list[dict[str, Any]] = []

    def on_trace_start(self, trace_obj) -> None:
        self.trace_started.append(trace_obj)

    def on_trace_end(self, trace_obj) -> None:
        self.trace_ended.append(trace_obj)

    def on_span_start(self, span) -> None:
        self.span_started.append(span)

    def on_span_end(self, span) -> None:
        exported = span.export()
        if exported:
            self.span_ended.append(exported)

    def shutdown(self) -> None:
        return

    def force_flush(self) -> None:
        return


class ExplodingTracer(RecordingTracer):
    """Japanese/English: コールバックで例外を投げるTracer / tracer that raises in callback."""

    def on_span_end(self, span) -> None:
        raise RuntimeError("boom")


class _DummyClient:
    def __init__(self, *, responses_text: str = "ok") -> None:
        self._responses_text = responses_text
        self.responses = SimpleNamespace(create=self._responses_create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))

    def _responses_create(self, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(output_text=self._responses_text)

    def _chat_create(self, *args: Any, **kwargs: Any) -> Any:
        msg = SimpleNamespace(content=self._responses_text, tool_calls=[{"name": "f", "arguments": "x"}])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _patch_openai(monkeypatch, *, responses_text: str) -> None:
    # Japanese/English: OpenAIクライアント生成を差し替え / patch OpenAI client constructor.
    def _fake_openai(*args: Any, **kwargs: Any) -> Any:
        return _DummyClient(responses_text=responses_text)

    monkeypatch.setattr(kantan_llm, "OpenAI", _fake_openai, raising=True)


def test_auto_trace_creates_trace_and_span(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="Bearer abcdefghijkl")

    tracer = RecordingTracer()
    llm = kantan_llm.get_llm("gpt-4.1-mini", tracer=tracer)

    _ = llm.responses.create(input="hello sk-test-1234567890")

    assert len(tracer.trace_started) == 1
    assert len(tracer.trace_ended) == 1
    assert len(tracer.span_started) == 1
    assert len(tracer.span_ended) == 1

    span_export = tracer.span_ended[0]
    span_data = span_export["span_data"]
    assert "sk-***" in span_data["input"]
    assert "Bearer ***" in span_data["output"]


def test_with_trace_creates_single_trace_multiple_spans(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="ok")

    tracer = RecordingTracer()
    llm = kantan_llm.get_llm("gpt-4.1-mini", tracer=tracer)

    with trace("workflow") as t:
        _ = llm.responses.create(input="one")
        _ = llm.responses.create(input="two")

    assert len(tracer.trace_started) == 1
    assert len(tracer.trace_ended) == 1
    assert len(tracer.span_ended) == 2
    assert all(s["trace_id"] == t.trace_id for s in tracer.span_ended)


def test_tracer_exception_is_non_fatal(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="ok")

    tracer = ExplodingTracer()
    llm = kantan_llm.get_llm("gpt-4.1-mini", tracer=tracer)

    # Should not raise from tracer. / tracer由来の例外は伝播しない。
    _ = llm.responses.create(input="hello")


def test_tracing_max_chars_env_truncates_input_output(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("KANTAN_LLM_TRACING_MAX_CHARS", "5")
    _patch_openai(monkeypatch, responses_text="0123456789")

    tracer = RecordingTracer()
    llm = kantan_llm.get_llm("gpt-4.1-mini", tracer=tracer)
    _ = llm.responses.create(input="abcdefghij")

    span_export = tracer.span_ended[0]
    span_data = span_export["span_data"]
    assert span_data["input"] == "abcde"
    assert span_data["output"] == "01234"


def test_tracer_none_uses_noop_tracer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="ok")

    set_trace_processors([])
    llm = kantan_llm.get_llm("gpt-4.1-mini", tracer=None)
    _ = llm.responses.create(input="hello")

    processors = get_trace_provider().get_processors()
    assert len(processors) == 1
    assert isinstance(processors[0], NoOpTracer)


def test_tracer_default_uses_print_tracer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="ok")

    set_trace_processors([])
    llm = kantan_llm.get_llm("gpt-4.1-mini")
    _ = llm.responses.create(input="hello")

    processors = get_trace_provider().get_processors()
    assert len(processors) == 1
    assert isinstance(processors[0], PrintTracer)


def test_tracer_unset_preserves_existing_processors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    _patch_openai(monkeypatch, responses_text="ok")

    existing = RecordingTracer()
    set_trace_processors([existing])

    llm = kantan_llm.get_llm("gpt-4.1-mini")
    _ = llm.responses.create(input="hello")

    processors = get_trace_provider().get_processors()
    assert len(processors) == 1
    assert processors[0] is existing
