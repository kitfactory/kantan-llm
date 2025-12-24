from __future__ import annotations

import os

from kantan_llm import get_llm
from kantan_llm.tracing import PrintTracer, trace


def main() -> None:
    # Japanese/English: サンプル用のキー設定（本番では環境変数で管理） / Sample key for demo.
    # os.environ.setdefault("OPENAI_API_KEY", "sk-...")

    # Japanese/English: デフォルトはPrintTracer / Default tracer is PrintTracer.
    llm = get_llm("gpt-4.1-mini")
    llm.responses.create(input="Say hi in one short line.")

    # Japanese/English: 明示的にTracerを指定 / Provide tracer explicitly.
    llm_with_tracer = get_llm("gpt-4.1-mini", tracer=PrintTracer())
    with trace("workflow"):
        llm_with_tracer.responses.create(input="Second call.")

    # Japanese/English: function calling の例 / Example for function calling.
    tools = [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get weather by city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    llm.responses.create(input="Call get_weather for Tokyo.", tools=tools)

    # Japanese/English: structured output の例 / Example for structured output.
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "score": {"type": "number"},
        },
        "required": ["title", "score"],
        "additionalProperties": False,
    }
    llm.responses.create(
        input="Summarize the topic with title and score.",
        text={
            "format": {
                "type": "json_schema",
                "name": "summary",
                "schema": schema,
            }
        },
    )


if __name__ == "__main__":
    main()
