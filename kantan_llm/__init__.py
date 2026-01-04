from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

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
from .resolver import resolve_llm
from .wrappers import AsyncClientBundle, KantanAsyncLLM, KantanLLM
from .tracing import NoOpTracer, PrintTracer, get_trace_provider
from .tracing.setup import set_trace_processors

__all__ = [
    "get_llm",
    "get_async_llm",
    "get_async_llm_client",
    "KantanLLM",
    "KantanAsyncLLM",
    "AsyncClientBundle",
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

    if not isinstance(model, str) or not model.strip():
        raise TypeError("get_llm(model) requires non-empty str model")

    if provider is not None and providers is not None:
        raise InvalidOptionsError()

    _configure_tracer(tracer)

    resolved = resolve_llm(
        model,
        provider=provider,
        providers=providers,
        api_key=api_key,
        base_url=base_url,
    )
    client = OpenAI(api_key=resolved.api_key, base_url=resolved.base_url, timeout=timeout)
    return KantanLLM(provider=resolved.provider, model=resolved.model, client=client)


def get_async_llm(
    model: str,
    **options,
) -> KantanAsyncLLM:
    """
    Get async LLM client (escape hatch). / async LLMクライアントを取得する（escape hatch）。

    Options (minimal):
    - provider: explicit provider override. / provider 明示指定（上書き）
    - providers: fallback list. / フォールバック候補
    - api_key, base_url, timeout: override env. / 環境変数の上書き
    - tracer: enable tracing. / トレーシング
    """

    provider: str | None = options.pop("provider", None)
    providers: list[str] | None = options.pop("providers", None)
    api_key: str | None = options.pop("api_key", None)
    base_url: str | None = options.pop("base_url", None)
    timeout: float | None = options.pop("timeout", None)
    tracer = options.pop("tracer", _TRACER_UNSET)

    if options:
        unknown = ", ".join(sorted(options.keys()))
        raise TypeError(f"get_async_llm() got unexpected keyword arguments: {unknown}")

    if not isinstance(model, str) or not model.strip():
        raise TypeError("get_async_llm(model) requires non-empty str model")

    if provider is not None and providers is not None:
        raise InvalidOptionsError()

    _configure_tracer(tracer)

    resolved = resolve_llm(
        model,
        provider=provider,
        providers=providers,
        api_key=api_key,
        base_url=base_url,
    )
    client = AsyncOpenAI(api_key=resolved.api_key, base_url=resolved.base_url, timeout=timeout)
    return KantanAsyncLLM(provider=resolved.provider, model=resolved.model, client=client)


def get_async_llm_client(
    model: str,
    **options,
) -> AsyncClientBundle:
    """
    Return raw AsyncOpenAI client bundle. / raw AsyncOpenAI client bundle を返す。

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

    if options:
        unknown = ", ".join(sorted(options.keys()))
        raise TypeError(f"get_async_llm_client() got unexpected keyword arguments: {unknown}")

    if not isinstance(model, str) or not model.strip():
        raise TypeError("get_async_llm_client(model) requires non-empty str model")

    if provider is not None and providers is not None:
        raise InvalidOptionsError()

    resolved = resolve_llm(
        model,
        provider=provider,
        providers=providers,
        api_key=api_key,
        base_url=base_url,
    )
    client = AsyncOpenAI(api_key=resolved.api_key, base_url=resolved.base_url, timeout=timeout)
    return AsyncClientBundle(
        client=client,
        model=resolved.model,
        provider=resolved.provider,
        base_url=resolved.base_url,
    )


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


def _configure_tracer(tracer: object) -> None:
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
