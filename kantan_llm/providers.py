from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse, urlunparse
from typing import Iterable

from .errors import MissingConfigError, ProviderInferenceError, UnsupportedProviderError

ProviderName = str


def _canonical_provider(provider: str) -> ProviderName:
    provider = provider.strip().lower()
    if provider in {"openai"}:
        return "openai"
    if provider in {"compat", "lmstudio", "ollama", "openrouter", "google", "anthropic"}:
        return provider
    raise UnsupportedProviderError(provider)


def split_model_prefix(model: str) -> tuple[str | None, str]:
    """
    Split `provider/model` prefix. / `provider/model` 接頭辞を分解する。
    Returns (provider_or_none, model_without_prefix).
    """

    if "/" not in model:
        return None, model
    maybe_provider, rest = model.split("/", 1)
    maybe_provider = maybe_provider.strip().lower()
    if maybe_provider in {"openai", "compat", "lmstudio", "ollama", "openrouter", "google", "anthropic"} and rest:
        return maybe_provider, rest
    return None, model


def infer_provider_from_model(model: str) -> ProviderName:
    """
    Infer provider from model name. / モデル名から provider を推測する。
    """

    prefixed_provider, bare_model = split_model_prefix(model)
    if prefixed_provider is not None:
        return _canonical_provider(prefixed_provider)

    lower = bare_model.lower()
    if lower.startswith("gpt-"):
        return "openai"
    if lower.startswith("claude-"):
        if os.getenv("CLAUDE_API_KEY"):
            return "anthropic"
        if os.getenv("OPENROUTER_API_KEY"):
            return "openrouter"
        return "compat"
    if lower.startswith("gemini-"):
        return "google"

    raise ProviderInferenceError(model)


@dataclass(frozen=True)
class ProviderConfig:
    provider: ProviderName
    api_key: str
    base_url: str | None


def _normalize_compat_base_url(base_url: str) -> str:
    """
    Normalize compat base_url to include /v1 when omitted. / 互換 base_url の /v1 省略を補完する。
    """

    parsed = urlparse(base_url)
    path = parsed.path or ""
    if path in {"", "/"}:
        parsed = parsed._replace(path="/v1")
    normalized = urlunparse(parsed)
    return normalized.rstrip("/")


def resolve_provider_config(
    *,
    provider: ProviderName,
    api_key: str | None,
    base_url: str | None,
) -> ProviderConfig:
    """
    Resolve api_key/base_url from args and env. / 引数と環境変数から設定を解決する。
    """

    provider = _canonical_provider(provider)

    if provider == "openai":
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise MissingConfigError("[kantan-llm][E2] Missing OPENAI_API_KEY for provider: openai")
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "anthropic":
        resolved_api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not resolved_api_key:
            raise MissingConfigError("[kantan-llm][E13] Missing CLAUDE_API_KEY for provider: anthropic")
        resolved_base_url = base_url or os.getenv("CLAUDE_BASE_URL") or "https://api.anthropic.com/v1"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "google":
        resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not resolved_api_key:
            raise MissingConfigError("[kantan-llm][E12] Missing GOOGLE_API_KEY for provider: google")
        resolved_base_url = base_url or os.getenv("GOOGLE_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "compat":
        resolved_base_url = base_url or os.getenv("KANTAN_LLM_BASE_URL")
        if not resolved_base_url:
            raise MissingConfigError(
                "[kantan-llm][E3] Missing base_url (set KANTAN_LLM_BASE_URL or base_url=...) for provider: compat"
            )
        resolved_base_url = _normalize_compat_base_url(resolved_base_url)
        resolved_api_key = api_key or os.getenv("KANTAN_LLM_API_KEY") or "DUMMY"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "lmstudio":
        resolved_base_url = base_url or os.getenv("LMSTUDIO_BASE_URL")
        if not resolved_base_url:
            raise MissingConfigError(
                "[kantan-llm][E9] Missing base_url (set LMSTUDIO_BASE_URL or base_url=...) for provider: lmstudio"
            )
        resolved_base_url = _normalize_compat_base_url(resolved_base_url)
        resolved_api_key = api_key or os.getenv("KANTAN_LLM_API_KEY") or "DUMMY"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "ollama":
        resolved_base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        if not resolved_base_url:
            raise MissingConfigError(
                "[kantan-llm][E10] Missing base_url (set OLLAMA_BASE_URL or base_url=...) for provider: ollama"
            )
        resolved_base_url = _normalize_compat_base_url(resolved_base_url)
        resolved_api_key = api_key or os.getenv("KANTAN_LLM_API_KEY") or "DUMMY"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    if provider == "openrouter":
        resolved_api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not resolved_api_key:
            raise MissingConfigError(
                "[kantan-llm][E11] Missing OPENROUTER_API_KEY for provider: openrouter"
            )
        resolved_base_url = base_url or "https://openrouter.ai/api/v1"
        return ProviderConfig(provider=provider, api_key=resolved_api_key, base_url=resolved_base_url)

    raise UnsupportedProviderError(provider)


def normalize_providers(providers: Iterable[str]) -> list[ProviderName]:
    """
    Normalize providers list. / providers を正規化する。
    """

    normalized: list[ProviderName] = []
    for provider in providers:
        normalized.append(_canonical_provider(provider))
    return normalized
