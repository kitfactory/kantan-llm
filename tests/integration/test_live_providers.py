import os

import pytest

from kantan_llm import get_llm


pytestmark = pytest.mark.integration


def _live_enabled() -> bool:
    # Japanese/English: 誤課金・不要通信を避けるため明示的に有効化 / explicit opt-in to avoid unintended calls
    return os.getenv("KANTAN_LLM_RUN_LIVE_TESTS") == "1"


@pytest.mark.skipif(not _live_enabled(), reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 to run live tests")
def test_openai_responses_live():
    llm = get_llm("gpt-4.1-mini", provider="openai")
    res = llm.responses.create(
        input="Return exactly: OK",
        max_output_tokens=16,
    )
    assert isinstance(res.output_text, str)
    assert "OK" in res.output_text


@pytest.mark.skipif(not _live_enabled(), reason="set KANTAN_LLM_RUN_LIVE_TESTS=1 to run live tests")
def test_lmstudio_chat_completions_live():
    # Requires LMStudio OpenAI-compatible server. / LMStudioのOpenAI互換サーバーが必要
    llm = get_llm("openai/gpt-oss-20b", provider="lmstudio")
    cc = llm.chat.completions.create(
        messages=[{"role": "user", "content": "Return exactly: OK"}],
        max_tokens=16,
        temperature=0,
    )
    assert cc.choices
    assert isinstance(cc.choices[0].message.content, str)
    assert "OK" in cc.choices[0].message.content
