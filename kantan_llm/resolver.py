from __future__ import annotations

from dataclasses import dataclass
import os

from .errors import (
    InvalidOptionsError,
    LLMErrorContext,
    MissingConfigError,
    ProviderInferenceError,
    ProviderUnavailableError,
    attach_error_context,
)
from .providers import (
    _is_api_key_present,
    _resolve_base_url_for_provider,
    infer_provider_from_model,
    normalize_providers,
    resolve_provider_config,
    split_model_prefix,
)


@dataclass(frozen=True)
class ResolvedLLM:
    provider: str
    model: str
    api_key: str
    base_url: str | None
    api_key_present: bool


def resolve_llm(
    model: str,
    *,
    provider: str | None,
    providers: list[str] | None,
    api_key: str | None,
    base_url: str | None,
) -> ResolvedLLM:
    if provider is not None and providers is not None:
        raise InvalidOptionsError()

    raw_model = model.strip()
    prefixed_provider, bare_model = split_model_prefix(raw_model)
    selected_providers = _select_providers(raw_model, provider=provider, providers=providers)
    candidates = normalize_providers(selected_providers)

    if providers is None:
        candidate = candidates[0]
        try:
            cfg = resolve_provider_config(provider=candidate, api_key=api_key, base_url=base_url)
        except MissingConfigError as e:
            attach_error_context(
                e,
                _build_error_context(
                    provider=candidate,
                    model=raw_model,
                    api_key=api_key,
                    base_url=base_url,
                ),
            )
            raise
        used_model = _resolve_model_for_provider(
            raw_model=raw_model,
            prefixed_provider=prefixed_provider,
            bare_model=bare_model,
            provider_name=cfg.provider,
        )
        api_key_present = _is_api_key_present(cfg.provider, api_key)
        return ResolvedLLM(
            provider=cfg.provider,
            model=used_model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            api_key_present=api_key_present,
        )

    reasons: list[str] = []
    for candidate in candidates:
        try:
            cfg = resolve_provider_config(provider=candidate, api_key=api_key, base_url=base_url)
            used_model = _resolve_model_for_provider(
                raw_model=raw_model,
                prefixed_provider=prefixed_provider,
                bare_model=bare_model,
                provider_name=cfg.provider,
            )
            api_key_present = _is_api_key_present(cfg.provider, api_key)
            return ResolvedLLM(
                provider=cfg.provider,
                model=used_model,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                api_key_present=api_key_present,
            )
        except MissingConfigError as e:
            attach_error_context(
                e,
                _build_error_context(
                    provider=candidate,
                    model=raw_model,
                    api_key=api_key,
                    base_url=base_url,
                ),
            )
            reasons.append(str(e))
            continue

    raise ProviderUnavailableError(reasons="; ".join(reasons) or "unknown")


def _select_providers(model: str, *, provider: str | None, providers: list[str] | None) -> list[str]:
    if provider is not None:
        return [provider]
    if providers is not None:
        return list(providers)
    try:
        default_provider = infer_provider_from_model(model)
        return [default_provider]
    except ProviderInferenceError:
        env_candidates: list[str] = []
        if os.getenv("LMSTUDIO_BASE_URL"):
            env_candidates.append("lmstudio")
        if os.getenv("OLLAMA_BASE_URL"):
            env_candidates.append("ollama")
        if os.getenv("OPENROUTER_API_KEY"):
            env_candidates.append("openrouter")
        if os.getenv("CLAUDE_API_KEY"):
            env_candidates.append("anthropic")
        if os.getenv("GOOGLE_API_KEY"):
            env_candidates.append("google")
        if not env_candidates:
            raise
        return env_candidates


def _resolve_model_for_provider(
    *,
    raw_model: str,
    prefixed_provider: str | None,
    bare_model: str,
    provider_name: str,
) -> str:
    lower_bare = bare_model.lower()
    if prefixed_provider is not None and prefixed_provider == provider_name and not lower_bare.startswith("gpt-oss"):
        return bare_model

    if "/" in raw_model:
        return raw_model

    if provider_name == "openrouter":
        aliases = {
            "claude-3-5-sonnet-latest": "anthropic/claude-3.5-sonnet",
            "claude-3-5-haiku-latest": "anthropic/claude-3.5-haiku",
            "claude-3-opus-latest": "anthropic/claude-3-opus",
            "claude-3-7-sonnet-latest": "anthropic/claude-3.7-sonnet",
        }
        return aliases.get(raw_model, raw_model)

    if provider_name == "anthropic":
        aliases = {
            "claude-3-5-sonnet-latest": "claude-3-7-sonnet-20250219",
            "claude-3-7-sonnet-latest": "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-latest": "claude-3-5-haiku-20241022",
            "claude-3-haiku-latest": "claude-3-haiku-20240307",
            "claude-3-opus-latest": "claude-3-opus-20240229",
        }
        return aliases.get(raw_model, raw_model)

    return raw_model


def _build_error_context(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> LLMErrorContext:
    return LLMErrorContext(
        provider=provider,
        base_url=_resolve_base_url_for_provider(provider, base_url),
        api_key_present=_is_api_key_present(provider, api_key),
        model=model,
    )
