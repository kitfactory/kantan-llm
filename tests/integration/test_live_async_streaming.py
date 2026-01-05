import asyncio
import os

import pytest

from kantan_llm import get_async_llm


pytestmark = pytest.mark.integration


def _get_attr(event, name: str):
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _extract_delta_text(event) -> str | None:
    event_type = _get_attr(event, "type")
    if event_type and "output_text" in event_type:
        delta = _get_attr(event, "delta")
        if isinstance(delta, str) and delta:
            return delta
        text = _get_attr(event, "text")
        if isinstance(text, str) and text:
            return text

    choices = _get_attr(event, "choices")
    if choices:
        first = choices[0]
        delta = _get_attr(first, "delta")
        content = _get_attr(delta, "content") if delta is not None else _get_attr(first, "content")
        if isinstance(content, str) and content:
            return content

    delta = _get_attr(event, "delta")
    if isinstance(delta, str) and delta:
        return delta
    return None


def _live_enabled() -> bool:
    # Japanese/English: 誤課金・不要通信を避けるため明示的に有効化 / explicit opt-in to avoid unintended calls
    return os.getenv("KANTAN_LLM_RUN_LIVE_TESTS") == "1"


def _openai_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _lmstudio_enabled() -> bool:
    return bool(os.getenv("LMSTUDIO_BASE_URL"))


@pytest.mark.skipif(
    not _live_enabled() or not _openai_enabled(),
    reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 and OPENAI_API_KEY to run live tests",
)
def test_openai_responses_streaming_live():
    async def _run() -> dict[str, object]:
        llm = get_async_llm("gpt-5-mini", provider="openai")
        async with llm.responses.stream(input="Return exactly: OK", max_output_tokens=16) as stream:
            parts: list[str] = []
            event_types: set[str] = set()
            async for event in stream:
                etype = _get_attr(event, "type")
                if isinstance(etype, str):
                    event_types.add(etype)
                text = _extract_delta_text(event)
                if text:
                    parts.append(text)
            if parts:
                return {"text": "".join(parts), "event_types": event_types}
            try:
                final = await stream.get_final_response()
                return {"text": final.output_text, "event_types": event_types}
            except Exception:
                return {"text": "", "event_types": event_types}

    result = asyncio.run(_run())
    output = result.get("text", "")
    event_types = result.get("event_types", set())
    assert isinstance(output, str)
    if "OK" not in output:
        assert "response.output_item.added" in event_types or "response.output_item.done" in event_types


@pytest.mark.skipif(
    not _live_enabled() or not _lmstudio_enabled(),
    reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 and LMSTUDIO_BASE_URL to run live tests",
)
def test_lmstudio_chat_completions_streaming_live():
    # Japanese/English: LMStudio OpenAI互換サーバーが必要 / Requires LMStudio OpenAI-compatible server
    async def _run() -> str:
        llm = get_async_llm("openai/gpt-oss-20b", provider="lmstudio")
        async with llm.chat.completions.stream(
            messages=[{"role": "user", "content": "Return exactly: OK"}],
            max_tokens=16,
            temperature=0,
        ) as stream:
            parts: list[str] = []
            async for event in stream:
                text = _extract_delta_text(event)
                if text:
                    parts.append(text)
            return "".join(parts)

    output = asyncio.run(_run())
    assert isinstance(output, str)
    assert "OK" in output
