from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SpanData:
    """Span specific payload. / Span固有データ。"""

    def export(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class CustomSpanData(SpanData):
    name: str
    data: dict[str, Any] | None = None

    def export(self) -> dict[str, Any]:
        return {"type": "custom", "name": self.name, "data": self.data}


@dataclass
class FunctionSpanData(SpanData):
    name: str
    input: str | None = None
    output: str | None = None

    def export(self) -> dict[str, Any]:
        return {"type": "function", "name": self.name, "input": self.input, "output": self.output}


@dataclass
class GenerationSpanData(SpanData):
    input: Any | None = None
    output: Any | None = None
    output_raw: Any | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None

    def export(self) -> dict[str, Any]:
        return {
            "type": "generation",
            "input": self.input,
            "output": self.output,
            "output_raw": self.output_raw,
            "model": self.model,
            "usage": self.usage,
        }
