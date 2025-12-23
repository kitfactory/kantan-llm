from __future__ import annotations

import os

from kantan_llm import get_llm
from kantan_llm.tracing import PrintTracer, trace


def main() -> None:
    # Japanese/English: サンプル用のキー設定（本番では環境変数で管理） / Sample key for demo.
    os.environ.setdefault("OPENAI_API_KEY", "sk-...")

    # Japanese/English: デフォルトはPrintTracer / Default tracer is PrintTracer.
    llm = get_llm("gpt-4.1-mini")
    llm.responses.create(input="Say hi in one short line.")

    # Japanese/English: 明示的にTracerを指定 / Provide tracer explicitly.
    llm_with_tracer = get_llm("gpt-4.1-mini", tracer=PrintTracer())
    with trace("workflow"):
        llm_with_tracer.responses.create(input="Second call.")


if __name__ == "__main__":
    main()
