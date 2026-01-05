from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Awaitable, Callable, Protocol

from openai import AsyncOpenAI

from .errors import NotSupportedError, WrongAPIError
from .tracing import default_workflow_name
from .tracing.create import dump_for_tracing, generation_span, get_current_trace
from .tracing.sanitize import sanitize_text
from .tracing.span_data import GenerationSpanData
from .tracing.traces import Trace


class _CreateCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class _AsyncCreateCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Awaitable[Any]: ...


@dataclass(frozen=True)
class AsyncClientBundle:
    client: AsyncOpenAI
    model: str
    provider: str
    base_url: str | None


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
class _AsyncResponsesAPI:
    _create: _AsyncCreateCallable
    _stream: Callable[..., Any] | None
    _default_model: str

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return await _traced_llm_create_async(
            api_kind="responses",
            default_model=self._default_model,
            create_callable=self._create,
            args=args,
            kwargs=kwargs,
        )

    def stream(self, *args: Any, **kwargs: Any) -> "_AsyncTracedStream":
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        if self._stream is not None:
            stream_factory = lambda: self._stream(*args, **kwargs)
        else:
            kwargs.setdefault("stream", True)
            stream_factory = lambda: self._create(*args, **kwargs)
        return _traced_llm_stream_async(
            api_kind="responses",
            default_model=self._default_model,
            stream_factory=stream_factory,
            args=args,
            kwargs=kwargs,
        )


@dataclass(frozen=True)
class _AsyncChatCompletionsAPI:
    _create: _AsyncCreateCallable
    _stream: Callable[..., Any] | None
    _default_model: str

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return await _traced_llm_create_async(
            api_kind="chat.completions",
            default_model=self._default_model,
            create_callable=self._create,
            args=args,
            kwargs=kwargs,
        )

    def stream(self, *args: Any, **kwargs: Any) -> "_AsyncTracedStream":
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        if self._stream is not None:
            stream_factory = lambda: self._stream(*args, **kwargs)
        else:
            kwargs.setdefault("stream", True)
            stream_factory = lambda: self._create(*args, **kwargs)
        return _traced_llm_stream_async(
            api_kind="chat.completions",
            default_model=self._default_model,
            stream_factory=stream_factory,
            args=args,
            kwargs=kwargs,
        )


@dataclass(frozen=True)
class _AsyncChatAPI:
    completions: _AsyncChatCompletionsAPI


@dataclass(frozen=True)
class KantanLLM:
    """
    Thin wrapper that exposes the right API for the provider.
    / provider に応じた正本APIだけを公開する薄いラッパー。
    """

    provider: str
    model: str
    client: Any

    # Japanese/English: 未定義属性はOpenAIクライアントへ委譲 / Delegate unknown attrs to OpenAI client.
    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self.client)))

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


@dataclass(frozen=True)
class KantanAsyncLLM:
    """
    Thin async wrapper that exposes the right API for the provider.
    / provider に応じた正本APIだけを公開する async ラッパー。
    """

    provider: str
    model: str
    client: Any

    # Japanese/English: 未定義属性はAsyncOpenAIクライアントへ委譲 / Delegate unknown attrs to AsyncOpenAI client.
    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self.client)))

    @property
    def responses(self) -> _AsyncResponsesAPI:
        if self.provider != "openai":
            raise WrongAPIError(f"[kantan-llm][E6] Responses API is not enabled for provider: {self.provider}")
        stream_method = getattr(self.client.responses, "stream", None)
        return _AsyncResponsesAPI(_create=self.client.responses.create, _stream=stream_method, _default_model=self.model)

    @property
    def chat(self) -> _AsyncChatAPI:
        if self.provider not in {"compat", "lmstudio", "ollama", "openrouter", "google", "anthropic"}:
            raise WrongAPIError(
                f"[kantan-llm][E7] Chat Completions API is not enabled for provider: {self.provider}"
            )
        return _AsyncChatAPI(
            completions=_AsyncChatCompletionsAPI(
                _create=self.client.chat.completions.create,
                _stream=getattr(self.client.chat.completions, "stream", None),
                _default_model=self.model,
            )
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


async def _traced_llm_create_async(
    *,
    api_kind: str,
    default_model: str,
    create_callable: _AsyncCreateCallable,
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
            return await _run_with_generation_span_async(
                parent_trace=t,
                model=model,
                input_text=input_text,
                api_kind=api_kind,
                create_callable=create_callable,
                args=args,
                kwargs=kwargs,
            )

    return await _run_with_generation_span_async(
        parent_trace=None,
        model=model,
        input_text=input_text,
        api_kind=api_kind,
        create_callable=create_callable,
        args=args,
        kwargs=kwargs,
    )


def _traced_llm_stream_async(
    *,
    api_kind: str,
    default_model: str,
    stream_factory: Callable[[], Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> "_AsyncTracedStream":
    # Japanese/English: with traceが無い場合は自動でTraceを作る / Auto-create trace if none exists.
    current = get_current_trace()
    auto_trace: Trace | None = None
    if current is None:
        from .tracing import trace as trace_factory

        auto_trace = trace_factory(default_workflow_name)
        auto_trace.start(mark_as_current=True)

    model = kwargs.get("model") or default_model
    input_payload = _extract_input(api_kind=api_kind, args=args, kwargs=kwargs)
    input_text = sanitize_text(dump_for_tracing(input_payload))

    span = generation_span(
        input=input_text,
        output=None,
        model=model,
        parent=auto_trace if auto_trace is not None else None,
    )
    span.start(mark_as_current=True)

    return _AsyncTracedStream(
        stream_factory=stream_factory,
        api_kind=api_kind,
        span=span,
        auto_trace=auto_trace,
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

        output_raw = _extract_output(api_kind=api_kind, response=result)
        output_text = sanitize_text(dump_for_tracing(output_raw))
        if isinstance(span.span_data, GenerationSpanData):
            span.span_data.output = output_text
            span.span_data.output_raw = output_raw
            span.span_data.usage = _extract_usage(api_kind=api_kind, response=result)
        return result


async def _run_with_generation_span_async(
    *,
    parent_trace: Trace | None,
    model: str,
    input_text: str,
    api_kind: str,
    create_callable: _AsyncCreateCallable,
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
            result = await create_callable(*args, **kwargs)
        except Exception as e:
            span.set_error({"message": str(e), "data": {"api_kind": api_kind}})
            raise

        output_raw = _extract_output(api_kind=api_kind, response=result)
        output_text = sanitize_text(dump_for_tracing(output_raw))
        if isinstance(span.span_data, GenerationSpanData):
            span.span_data.output = output_text
            span.span_data.output_raw = output_raw
            span.span_data.usage = _extract_usage(api_kind=api_kind, response=result)
        return result


class _AsyncTracedStream:
    def __init__(
        self,
        *,
        stream_factory: Callable[[], Any],
        api_kind: str,
        span: Any,
        auto_trace: Trace | None,
    ) -> None:
        self._stream_factory = stream_factory
        self._api_kind = api_kind
        self._span = span
        self._auto_trace = auto_trace
        self._stream_obj: Any | None = None
        self._aiter: Any | None = None
        self._final_response: Any | None = None
        self._text_parts: list[str] = []
        self._output_item_text_parts: list[str] = []
        self._final_text_override: str | None = None
        self._closed = False

    # Japanese/English: 未解決のstreamは遅延で解決する / Lazily resolve stream object.
    async def _ensure_stream(self) -> Any:
        if self._stream_obj is not None:
            return self._stream_obj
        stream_obj = self._stream_factory()
        if inspect.isawaitable(stream_obj):
            stream_obj = await stream_obj
        self._stream_obj = stream_obj
        return stream_obj

    async def __aenter__(self) -> "_AsyncTracedStream":
        try:
            stream_obj = await self._ensure_stream()
            if hasattr(stream_obj, "__aenter__"):
                stream_obj = await stream_obj.__aenter__()
                self._stream_obj = stream_obj
            return self
        except Exception as e:
            self._record_error(e)
            await self._finalize()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_val is not None:
                self._record_error(exc_val)
            try:
                stream_obj = await self._ensure_stream()
            except Exception as e:
                self._record_error(e)
                return False
            if hasattr(stream_obj, "__aexit__"):
                return await stream_obj.__aexit__(exc_type, exc_val, exc_tb)
            return False
        finally:
            await self._finalize()

    def __aiter__(self) -> "_AsyncTracedStream":
        return self

    async def __anext__(self) -> Any:
        try:
            stream_obj = await self._ensure_stream()
        except Exception as e:
            self._record_error(e)
            await self._finalize()
            raise
        if self._aiter is None:
            if hasattr(stream_obj, "__aiter__"):
                self._aiter = stream_obj.__aiter__()
            else:
                await self._finalize()
                raise StopAsyncIteration
        try:
            item = await self._aiter.__anext__()
            self._collect_event_output(item)
            return item
        except StopAsyncIteration:
            await self._finalize()
            raise
        except Exception as e:
            self._record_error(e)
            await self._finalize()
            raise

    async def get_final_response(self) -> Any:
        try:
            stream_obj = await self._ensure_stream()
        except Exception as e:
            self._record_error(e)
            await self._finalize()
            raise
        getter = getattr(stream_obj, "get_final_response", None)
        if getter is None:
            raise NotSupportedError("stream.get_final_response")
        result = getter()
        if inspect.isawaitable(result):
            result = await result
        self._final_response = result
        await self._finalize()
        return result

    def __getattr__(self, name: str) -> Any:
        if self._stream_obj is None:
            raise AttributeError(name)
        return getattr(self._stream_obj, name)

    def _record_error(self, err: Exception) -> None:
        self._span.set_error({"message": str(err), "data": {"api_kind": self._api_kind}})

    async def _finalize(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self._final_response is None:
            response = await self._try_get_final_response()
            if response is not None:
                self._final_response = response

        output_raw: Any | None = None
        output_text: str | None = None
        if self._final_response is not None:
            output_raw = _extract_output(api_kind=self._api_kind, response=self._final_response)
            output_text = sanitize_text(dump_for_tracing(output_raw))
        elif self._final_text_override is not None:
            output_raw = self._final_text_override
            output_text = self._final_text_override
        elif self._text_parts:
            output_raw = "".join(self._text_parts)
            output_text = output_raw
        elif self._output_item_text_parts:
            output_raw = "".join(self._output_item_text_parts)
            output_text = output_raw

        if output_text is not None and isinstance(self._span.span_data, GenerationSpanData):
            self._span.span_data.output = output_text
            self._span.span_data.output_raw = output_raw
            if self._final_response is not None:
                self._span.span_data.usage = _extract_usage(api_kind=self._api_kind, response=self._final_response)

        self._span.finish(reset_current=True)
        if self._auto_trace is not None:
            self._auto_trace.finish(reset_current=True)

    async def _try_get_final_response(self) -> Any | None:
        stream_obj = await self._ensure_stream()
        getter = getattr(stream_obj, "get_final_response", None)
        if getter is None:
            return None
        try:
            result = getter()
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception:
            return None

    def _collect_event_output(self, event: Any) -> None:
        # Japanese/English: streamingイベントからテキストを回収 / Collect text from stream events.
        event_type = _get_event_attr(event, "type")
        if event_type == "response.completed":
            response = _get_event_attr(event, "response")
            if response is not None:
                self._final_response = response

        text = _extract_stream_text(api_kind=self._api_kind, event=event)
        if text is None:
            output_item_texts = _extract_output_item_text(event=event)
            if output_item_texts and event_type == "response.output_item.done":
                self._output_item_text_parts.extend(output_item_texts)
            return
        if event_type == "response.output_text.done":
            self._final_text_override = text
            return
        self._text_parts.append(text)


def _get_event_attr(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _extract_stream_text(*, api_kind: str, event: Any) -> str | None:
    event_type = _get_event_attr(event, "type")
    if event_type and "output_text" in event_type:
        delta = _get_event_attr(event, "delta")
        if isinstance(delta, str) and delta:
            return delta
        text = _get_event_attr(event, "text")
        if isinstance(text, str) and text:
            return text

    if api_kind == "chat.completions":
        choices = _get_event_attr(event, "choices")
        if choices:
            first = choices[0]
            delta = _get_event_attr(first, "delta")
            content = _get_event_attr(delta, "content") if delta is not None else _get_event_attr(first, "content")
            if isinstance(content, str) and content:
                return content

    delta = _get_event_attr(event, "delta")
    if isinstance(delta, str) and delta:
        return delta

    return None


def _extract_output_item_text(*, event: Any) -> list[str] | None:
    # Japanese/English: output_itemのcontentからテキストを抽出 / Extract text from output_item content.
    item = _get_event_attr(event, "item") or _get_event_attr(event, "output_item")
    if item is None:
        return None
    content = _get_event_attr(item, "content")
    if not content:
        return None

    parts = content if isinstance(content, (list, tuple)) else [content]
    texts: list[str] = []
    for part in parts:
        part_type = _get_event_attr(part, "type")
        if part_type == "output_text":
            text = _get_event_attr(part, "text")
            if isinstance(text, str) and text:
                texts.append(text)
        elif part_type == "refusal":
            refusal = _get_event_attr(part, "refusal")
            if isinstance(refusal, str) and refusal:
                texts.append(refusal)

    return texts or None


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
            return _normalize_response_output(output)

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
                    return _normalize_tool_calls(tool_calls)
                reasoning = getattr(msg, "reasoning", None) if not isinstance(msg, dict) else msg.get("reasoning")
                if reasoning:
                    return reasoning
    except Exception:
        pass

    return response


def _extract_usage(*, api_kind: str, response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        return usage
    if usage is not None:
        try:
            return usage.model_dump()  # type: ignore[attr-defined]
        except Exception:
            try:
                return dict(usage)
            except Exception:
                return None
    return None


def _normalize_tool_calls(tool_calls: Any) -> Any:
    # Japanese/English: tool_calls をJSONに近い形へ正規化 / Normalize tool_calls to JSON-like dicts.
    if isinstance(tool_calls, dict):
        return tool_calls
    if not isinstance(tool_calls, (list, tuple)):
        return tool_calls

    normalized: list[dict[str, Any]] = []
    for call in tool_calls:
        if isinstance(call, dict):
            normalized.append(call)
            continue

        function = getattr(call, "function", None)
        normalized.append(
            {
                "id": getattr(call, "id", None),
                "call_id": getattr(call, "call_id", None),
                "type": getattr(call, "type", None),
                "name": getattr(call, "name", None) or getattr(function, "name", None),
                "arguments": getattr(call, "arguments", None) or getattr(function, "arguments", None),
            }
        )

    return normalized


def _normalize_response_output(output: Any) -> Any:
    if isinstance(output, dict):
        return output
    if not isinstance(output, (list, tuple)):
        return output

    normalized: list[Any] = []
    has_tool_call = False
    for item in output:
        item_type = getattr(item, "type", None) if not isinstance(item, dict) else item.get("type")
        if item_type in {"function_call", "tool_call", "tool"}:
            has_tool_call = True
            normalized.append(
                {
                    "id": getattr(item, "id", None),
                    "call_id": getattr(item, "call_id", None),
                    "type": item_type,
                    "name": getattr(item, "name", None),
                    "arguments": getattr(item, "arguments", None),
                    "status": getattr(item, "status", None),
                }
            )
        else:
            normalized.append(item)

    return normalized if has_tool_call else output
