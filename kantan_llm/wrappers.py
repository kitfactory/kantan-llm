from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .errors import WrongAPIError
from .tracing import default_workflow_name
from .tracing.create import dump_for_tracing, generation_span, get_current_trace
from .tracing.sanitize import sanitize_text
from .tracing.span_data import GenerationSpanData
from .tracing.traces import Trace


class _CreateCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class _ResponsesAPI:
    _create: _CreateCallable
    _default_model: str

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return _traced_llm_create(
            api_kind="responses",
            default_model=self._default_model,
            create_callable=self._create,
            args=args,
            kwargs=kwargs,
        )


@dataclass(frozen=True)
class _ChatCompletionsAPI:
    _create: _CreateCallable
    _default_model: str

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return _traced_llm_create(
            api_kind="chat.completions",
            default_model=self._default_model,
            create_callable=self._create,
            args=args,
            kwargs=kwargs,
        )


@dataclass(frozen=True)
class _ChatAPI:
    completions: _ChatCompletionsAPI


@dataclass(frozen=True)
class KantanLLM:
    """
    Thin wrapper that exposes the right API for the provider.
    / provider に応じた正本APIだけを公開する薄いラッパー。
    """

    provider: str
    model: str
    client: Any

    @property
    def responses(self) -> _ResponsesAPI:
        if self.provider != "openai":
            raise WrongAPIError(f"[kantan-llm][E6] Responses API is not enabled for provider: {self.provider}")
        return _ResponsesAPI(_create=self.client.responses.create, _default_model=self.model)

    @property
    def chat(self) -> _ChatAPI:
        if self.provider not in {"compat", "lmstudio", "ollama", "openrouter", "google", "anthropic"}:
            raise WrongAPIError(
                f"[kantan-llm][E7] Chat Completions API is not enabled for provider: {self.provider}"
            )
        return _ChatAPI(
            completions=_ChatCompletionsAPI(_create=self.client.chat.completions.create, _default_model=self.model)
        )


def _traced_llm_create(
    *,
    api_kind: str,
    default_model: str,
    create_callable: _CreateCallable,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    # Japanese/English: with traceが無い場合は自動でTraceを作る / Auto-create trace if none exists.
    current = get_current_trace()
    auto_trace: Trace | None = None
    if current is None:
        from .tracing import trace as trace_factory

        auto_trace = trace_factory(default_workflow_name)

    model = kwargs.get("model") or default_model
    input_payload = _extract_input(api_kind=api_kind, args=args, kwargs=kwargs)
    input_text = sanitize_text(dump_for_tracing(input_payload))

    if auto_trace is not None:
        with auto_trace as t:
            return _run_with_generation_span(
                parent_trace=t,
                model=model,
                input_text=input_text,
                api_kind=api_kind,
                create_callable=create_callable,
                args=args,
                kwargs=kwargs,
            )

    return _run_with_generation_span(
        parent_trace=None,
        model=model,
        input_text=input_text,
        api_kind=api_kind,
        create_callable=create_callable,
        args=args,
        kwargs=kwargs,
    )


def _run_with_generation_span(
    *,
    parent_trace: Trace | None,
    model: str,
    input_text: str,
    api_kind: str,
    create_callable: _CreateCallable,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    span = generation_span(
        input=input_text,
        output=None,
        model=model,
        parent=parent_trace,
    )
    with span:
        try:
            result = create_callable(*args, **kwargs)
        except Exception as e:
            span.set_error({"message": str(e), "data": {"api_kind": api_kind}})
            raise

        output_text = sanitize_text(dump_for_tracing(_extract_output(api_kind=api_kind, response=result)))
        if isinstance(span.span_data, GenerationSpanData):
            span.span_data.output = output_text
        return result


def _extract_input(*, api_kind: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if api_kind == "responses":
        if "input" in kwargs:
            return kwargs["input"]
        if "messages" in kwargs:
            return kwargs["messages"]
        if args:
            return args[0]
        return None

    # chat.completions
    if "messages" in kwargs:
        return kwargs["messages"]
    if args:
        return args[0]
    return None


def _extract_output(*, api_kind: str, response: Any) -> Any:
    # Prefer: text -> structured -> tool calls. / 優先: テキスト -> 構造化 -> tool calls.
    if api_kind == "responses":
        text = getattr(response, "output_text", None)
        if text:
            return text

        output = getattr(response, "output", None)
        if output:
            return output

        return response

    # chat.completions
    try:
        choices = getattr(response, "choices", None) or (response.get("choices") if isinstance(response, dict) else None)
        if choices:
            msg = getattr(choices[0], "message", None) or choices[0].get("message")
            if msg:
                content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
                if content:
                    return content
                tool_calls = getattr(msg, "tool_calls", None) if not isinstance(msg, dict) else msg.get("tool_calls")
                if tool_calls:
                    return tool_calls
    except Exception:
        pass

    return response
