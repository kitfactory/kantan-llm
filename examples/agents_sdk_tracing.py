from __future__ import annotations

import os

from agents.tracing import add_trace_processor, trace

from kantan_llm import get_llm
from kantan_llm.tracing import PrintTracer


def main() -> None:
    # Japanese/English: サンプル用のキー設定（本番では環境変数で管理） / Sample key for demo.
    # os.environ.setdefault("OPENAI_API_KEY", "sk-...")

    # Japanese/English: Agents SDK側にTracerを登録 / Register tracer to Agents SDK.
    tracer = PrintTracer()
    add_trace_processor(tracer)

    # Japanese/English: tracer=None は NoOpTracer（出力なし） / tracer=None disables output.
    # Agents SDK の trace と kantan-llm の trace は別コンテキストなので、
    # 出力したい場合は kantan-llm 側にも同じTracerを渡す。/ Pass tracer to kantan-llm too.
    llm = get_llm("gpt-4.1-mini", tracer=tracer)

    # Japanese/English: Agents SDKのtraceコンテキストを利用 / Use Agents SDK trace context.
    with trace("agents-workflow"):
        llm.responses.create(input="Hello from Agents SDK trace.")


if __name__ == "__main__":
    main()
