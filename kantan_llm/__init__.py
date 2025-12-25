from __future__ import annotations

from openai import OpenAI

from .errors import (
    InvalidOptionsError,
    InvalidTracerError,
    KantanLLMError,
    MissingConfigError,
    MissingDependencyError,
    NotSupportedError,
    ProviderInferenceError,
    ProviderUnavailableError,
    UnsupportedProviderError,
    WrongAPIError,
)
import os

from .providers import infer_provider_from_model, normalize_providers, resolve_provider_config, split_model_prefix
from .wrappers import KantanLLM
from .tracing import NoOpTracer, PrintTracer, get_trace_provider
from .tracing.setup import set_trace_processors

__all__ = [
    "get_llm",
    "KantanLLM",
    "KantanLLMError",
    "ProviderInferenceError",
    "MissingConfigError",
    "UnsupportedProviderError",
    "ProviderUnavailableError",
    "WrongAPIError",
    "InvalidOptionsError",
    "InvalidTracerError",
    "MissingDependencyError",
    "NotSupportedError",
]


def get_llm(
    model: str,
    **options,
) -> KantanLLM:
    """
    Get LLM client with minimum boilerplate. / 最短記述でLLMクライアントを取得する。

    Options (minimal):
    - provider: explicit provider override. / provider 明示指定（上書き）
    - providers: fallback list. / フォールバック候補
    - api_key, base_url, timeout: override env. / 環境変数の上書き
    """

    provider: str | None = options.pop("provider", None)
    providers: list[str] | None = options.pop("providers", None)
    api_key: str | None = options.pop("api_key", None)
    base_url: str | None = options.pop("base_url", None)
    timeout: float | None = options.pop("timeout", None)
    tracer = options.pop("tracer", _TRACER_UNSET)

    if options:
        unknown = ", ".join(sorted(options.keys()))
        raise TypeError(f"get_llm() got unexpected keyword arguments: {unknown}")

    if provider is not None and providers is not None:
        raise InvalidOptionsError()

    if not isinstance(model, str) or not model.strip():
        raise TypeError("get_llm(model) requires non-empty str model")

    # Japanese/English: Tracerを設定する（デフォルトはPrintTracer） / Configure tracer (default: PrintTracer)
    if tracer is _TRACER_UNSET:
        existing = get_trace_provider().get_processors()
        if not existing:
            tracer = PrintTracer()
        else:
            tracer = _TRACER_SKIP
    elif tracer is None:
        tracer = NoOpTracer()

    if tracer is not _TRACER_SKIP:
        if not _is_tracing_processor(tracer):
            raise InvalidTracerError(tracer)
        set_trace_processors([tracer])

    prefixed_provider, bare_model = split_model_prefix(model.strip())

    if provider is not None:
        selected_providers = [provider]
    elif providers is not None:
        selected_providers = list(providers)
    else:
        try:
            default_provider = infer_provider_from_model(model.strip())
            selected_providers = [default_provider]
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
            selected_providers = env_candidates

    candidates = normalize_providers(selected_providers)

    def _resolve_model_for_provider(provider_name: str) -> str:
        if prefixed_provider is not None and prefixed_provider == provider_name:
            return bare_model

        raw = model.strip()
        if "/" in raw:
            return raw

        if provider_name == "openrouter":
            aliases = {
                "claude-3-5-sonnet-latest": "anthropic/claude-3.5-sonnet",
                "claude-3-5-haiku-latest": "anthropic/claude-3.5-haiku",
                "claude-3-opus-latest": "anthropic/claude-3-opus",
                "claude-3-7-sonnet-latest": "anthropic/claude-3.7-sonnet",
            }
            return aliases.get(raw, raw)

        if provider_name == "anthropic":
            aliases = {
                "claude-3-5-sonnet-latest": "claude-3-7-sonnet-20250219",
                "claude-3-7-sonnet-latest": "claude-3-7-sonnet-20250219",
                "claude-3-5-haiku-latest": "claude-3-5-haiku-20241022",
                "claude-3-haiku-latest": "claude-3-haiku-20240307",
                "claude-3-opus-latest": "claude-3-opus-20240229",
            }
            return aliases.get(raw, raw)

        return raw

    if providers is None:
        candidate = candidates[0]
        cfg = resolve_provider_config(provider=candidate, api_key=api_key, base_url=base_url)
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=timeout)
        used_model = _resolve_model_for_provider(cfg.provider)
        return KantanLLM(provider=cfg.provider, model=used_model, client=client)

    reasons: list[str] = []
    for candidate in candidates:
        try:
            cfg = resolve_provider_config(provider=candidate, api_key=api_key, base_url=base_url)
            client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=timeout)
            used_model = _resolve_model_for_provider(cfg.provider)
            return KantanLLM(provider=cfg.provider, model=used_model, client=client)
        except MissingConfigError as e:
            reasons.append(str(e))
            continue

    raise ProviderUnavailableError(reasons="; ".join(reasons) or "unknown")


def _is_tracing_processor(obj: object) -> bool:
    required = (
        "on_trace_start",
        "on_trace_end",
        "on_span_start",
        "on_span_end",
        "shutdown",
        "force_flush",
    )
    for name in required:
        if not hasattr(obj, name):
            return False
        if not callable(getattr(obj, name)):
            return False
    return True


_TRACER_UNSET = object()
_TRACER_SKIP = object()
