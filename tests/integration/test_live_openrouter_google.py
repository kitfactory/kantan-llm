import os

import pytest

from kantan_llm import get_llm


pytestmark = pytest.mark.integration


def _live_enabled() -> bool:
    # Japanese/English: 誤課金・不要通信を避けるため明示的に有効化 / explicit opt-in to avoid unintended calls
    return os.getenv("KANTAN_LLM_RUN_LIVE_TESTS") == "1"


@pytest.mark.skipif(not _live_enabled(), reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 to run live tests")
def test_anthropic_claude_chat_completions_live():
    # Uses Anthropic OpenAI-compatible endpoint (Claude) via Chat Completions.
    # / AnthropicのOpenAI互換エンドポイント経由でClaudeを叩く。
    llm = get_llm("claude-3-5-sonnet-latest")
    assert llm.provider == "anthropic"
    cc = llm.chat.completions.create(
        messages=[{"role": "user", "content": "Return exactly: OK"}],
        max_tokens=16,
        temperature=0,
    )
    assert cc.choices
    assert isinstance(cc.choices[0].message.content, str)
    assert "OK" in cc.choices[0].message.content


@pytest.mark.skipif(not _live_enabled(), reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 to run live tests")
def test_openrouter_claude_chat_completions_live():
    # Uses OpenRouter (Claude) via OpenAI-compatible Chat Completions.
    # / OpenAI互換Chat Completions経由でOpenRouter(Claude)を叩く。
    llm = get_llm("anthropic/claude-3.5-sonnet", provider="openrouter")
    assert llm.provider == "openrouter"
    cc = llm.chat.completions.create(
        messages=[{"role": "user", "content": "Return exactly: OK"}],
        max_tokens=16,
        temperature=0,
    )
    assert cc.choices
    assert isinstance(cc.choices[0].message.content, str)
    assert "OK" in cc.choices[0].message.content


@pytest.mark.skipif(not _live_enabled(), reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 to run live tests")
def test_google_gemini_chat_completions_live():
    # Uses Google Gemini via Google's OpenAI-compatible endpoint.
    # / GoogleのOpenAI互換エンドポイント経由でGeminiを叩く。
    llm = get_llm("gemini-2.0-flash")
    cc = llm.chat.completions.create(
        messages=[{"role": "user", "content": "Return exactly: OK"}],
        max_tokens=16,
        temperature=0,
    )
    assert cc.choices
    assert isinstance(cc.choices[0].message.content, str)
    assert "OK" in cc.choices[0].message.content
