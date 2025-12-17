from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .errors import WrongAPIError


class _CreateCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class _ResponsesAPI:
    _create: _CreateCallable
    _default_model: str

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return self._create(*args, **kwargs)


@dataclass(frozen=True)
class _ChatCompletionsAPI:
    _create: _CreateCallable
    _default_model: str

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if "model" not in kwargs:
            kwargs["model"] = self._default_model
        return self._create(*args, **kwargs)


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
        if self.provider not in {"compat", "lmstudio", "ollama", "openrouter", "google"}:
            raise WrongAPIError(
                f"[kantan-llm][E7] Chat Completions API is not enabled for provider: {self.provider}"
            )
        return _ChatAPI(
            completions=_ChatCompletionsAPI(_create=self.client.chat.completions.create, _default_model=self.model)
        )
