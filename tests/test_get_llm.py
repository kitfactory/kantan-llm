import pytest

from kantan_llm import InvalidOptionsError, MissingConfigError, WrongAPIError, get_llm


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


def test_claude_inference_uses_openrouter_when_claude_api_key_exists(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "openrouter-like-test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    llm = get_llm("claude-3-5-sonnet-latest")
    assert llm.provider == "openrouter"
    assert llm.model == "anthropic/claude-3.5-sonnet"
    assert callable(llm.chat.completions.create)


def test_openrouter_key_missing_is_clear(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    with pytest.raises(MissingConfigError) as exc:
        get_llm("claude-3-5-sonnet-latest", provider="openrouter")
    assert str(exc.value) == "[kantan-llm][E11] Missing OPENROUTER_API_KEY (or CLAUDE_API_KEY) for provider: openrouter"


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
