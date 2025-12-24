from __future__ import annotations

import os

from agents.tracing import add_trace_processor, trace

from kantan_llm import get_llm
from kantan_llm.tracing import PrintTracer


def main() -> None:
    # Japanese/English: LMStudioのURLを設定（本番は環境変数で管理） / LMStudio base URL.
    os.environ.setdefault("LMSTUDIO_BASE_URL", "http://192.168.11.16:1234")

    tracer = PrintTracer()
    add_trace_processor(tracer)

    # Japanese/English: LMStudioはChat Completionsを正本として使う / Use Chat Completions.
    llm = get_llm("openai/gpt-oss-20b", provider="lmstudio", tracer=tracer)

    with trace("agents-lmstudio"):
        llm.chat.completions.create(
            messages=[{"role": "user", "content": "Return exactly: OK"}],
            max_tokens=16,
        )

        # Japanese/English: function calling の例 / Example for function calling.
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather by city.",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ]
        llm.chat.completions.create(
            messages=[{"role": "user", "content": "Call get_weather for Tokyo."}],
            tools=tools,
            tool_choice="auto",
        )

        # Japanese/English: structured output の例 / Example for structured output.
        schema = {
            "type": "object",
            "properties": {"title": {"type": "string"}, "score": {"type": "number"}},
            "required": ["title", "score"],
            "additionalProperties": False,
        }
        llm.chat.completions.create(
            messages=[{"role": "user", "content": "Summarize with title and score."}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "summary", "schema": schema},
            },
        )


if __name__ == "__main__":
    main()
