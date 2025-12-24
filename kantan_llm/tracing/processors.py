from __future__ import annotations

import json
import os
import sqlite3
import sys
from typing import Any

from .processor_interface import TracingProcessor
from .sanitize import sanitize_text


class PrintTracer(TracingProcessor):
    """Print input/output with colors. / 入出力を色分けして標準出力に表示する。"""

    _C_RESET = "\033[0m"
    _C_IN = "\033[36m"  # cyan
    _C_OUT = "\033[32m"  # green

    def __init__(self, *, stream=None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    def _use_color(self) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        try:
            return bool(self._stream.isatty())
        except Exception:
            return False

    def _write_block(self, label: str, text: str, color: str) -> None:
        safe = sanitize_text(text)
        if self._use_color():
            self._stream.write(f"{color}{label}\n{safe}{self._C_RESET}\n")
        else:
            self._stream.write(f"{label}\n{safe}\n")
        self._stream.flush()

    def on_trace_start(self, trace) -> None:
        return

    def on_trace_end(self, trace) -> None:
        return

    def on_span_start(self, span) -> None:
        return

    def on_span_end(self, span) -> None:
        exported = getattr(span, "export", lambda: None)()
        if not exported:
            return
        data = exported.get("span_data") or {}
        span_type = data.get("type")
        if span_type != "generation":
            return

        raw_in = data.get("input")
        raw_out = data.get("output")

        if raw_in is not None:
            self._write_block("INPUT:", _to_text(raw_in), self._C_IN)
        if raw_out is not None:
            self._write_block("OUTPUT:", _to_text(raw_out), self._C_OUT)

    def shutdown(self) -> None:
        return

    def force_flush(self) -> None:
        return


class NoOpTracer(TracingProcessor):
    """No-op tracer. / 何もしないTracer。"""

    def on_trace_start(self, trace) -> None:
        return

    def on_trace_end(self, trace) -> None:
        return

    def on_span_start(self, span) -> None:
        return

    def on_span_end(self, span) -> None:
        return

    def shutdown(self) -> None:
        return

    def force_flush(self) -> None:
        return


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return str(value)


class SQLiteTracer(TracingProcessor):
    """Persist traces/spans to SQLite. / Trace/SpanをSQLiteへ保存する。"""

    def __init__(self, path: str = "kantan_llm_traces.sqlite3") -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                  id TEXT PRIMARY KEY,
                  workflow_name TEXT,
                  group_id TEXT,
                  metadata_json TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spans (
                  id TEXT PRIMARY KEY,
                  trace_id TEXT,
                  parent_id TEXT,
                  started_at TEXT,
                  ended_at TEXT,
                  span_type TEXT,
                  input TEXT,
                  output TEXT,
                  error_json TEXT,
                  raw_json TEXT
                )
                """
            )
            self._conn.commit()
        return self._conn

    def _upsert_trace(self, trace) -> None:
        exported = getattr(trace, "export", lambda: None)()
        if not exported:
            return
        conn = self._ensure_conn()
        conn.execute(
            "INSERT OR IGNORE INTO traces(id, workflow_name, group_id, metadata_json) VALUES(?,?,?,?)",
            (
                exported.get("id") or getattr(trace, "trace_id", None),
                exported.get("workflow_name") or getattr(trace, "name", None),
                exported.get("group_id"),
                json.dumps(exported.get("metadata"), ensure_ascii=False, default=str),
            ),
        )

    def on_trace_start(self, trace) -> None:
        self._upsert_trace(trace)
        self._ensure_conn().commit()

    def on_trace_end(self, trace) -> None:
        self._upsert_trace(trace)
        self._ensure_conn().commit()

    def on_span_start(self, span) -> None:
        return

    def on_span_end(self, span) -> None:
        exported = getattr(span, "export", lambda: None)()
        if not exported:
            return

        trace_id = exported.get("trace_id") or getattr(span, "trace_id", None)
        if trace_id is None:
            return

        # Ensure trace row exists even if we didn't see on_trace_start (interop). / trace startを見ていなくてもtrace行を作る。
        self._upsert_trace(getattr(span, "_trace", None) or _TraceLike(trace_id=trace_id))

        span_data = exported.get("span_data") or {}
        raw_in = span_data.get("input")
        raw_out = span_data.get("output")

        input_text = sanitize_text(_to_text(raw_in)) if raw_in is not None else None
        output_text = sanitize_text(_to_text(raw_out)) if raw_out is not None else None

        conn = self._ensure_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO spans(
              id, trace_id, parent_id, started_at, ended_at, span_type, input, output, error_json, raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                exported.get("id") or getattr(span, "span_id", None),
                trace_id,
                exported.get("parent_id"),
                exported.get("started_at"),
                exported.get("ended_at"),
                span_data.get("type"),
                input_text,
                output_text,
                json.dumps(exported.get("error"), ensure_ascii=False, default=str),
                json.dumps(exported, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()

    def shutdown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def force_flush(self) -> None:
        if self._conn is not None:
            self._conn.commit()


class _TraceLike:
    def __init__(self, trace_id: str, name: str | None = None) -> None:
        self.trace_id = trace_id
        self.name = name or trace_id

    def export(self) -> dict[str, Any]:
        return {"object": "trace", "id": self.trace_id, "workflow_name": self.name, "group_id": None, "metadata": None}


class OTELTracer(TracingProcessor):
    """Export spans to OpenTelemetry. / OpenTelemetryへSpanを送る。"""

    def __init__(self, service_name: str = "kantan-llm") -> None:
        try:
            from opentelemetry import trace as ot_trace  # type: ignore
            from opentelemetry.sdk.resources import Resource  # type: ignore
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore
            from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter  # type: ignore
        except Exception as e:  # pragma: no cover
            from kantan_llm.errors import MissingDependencyError

            raise MissingDependencyError("opentelemetry-sdk") from e

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        ot_trace.set_tracer_provider(provider)
        self._tracer = ot_trace.get_tracer(__name__)
        self._otel = ot_trace

        self._trace_spans: dict[str, Any] = {}
        self._span_spans: dict[str, Any] = {}

    def on_trace_start(self, trace) -> None:
        trace_id = getattr(trace, "trace_id", None) or getattr(trace, "id", None)
        name = getattr(trace, "name", None) or getattr(trace, "workflow_name", None) or "trace"
        if not trace_id:
            return
        span = self._tracer.start_span(name)
        self._trace_spans[trace_id] = span

    def on_trace_end(self, trace) -> None:
        trace_id = getattr(trace, "trace_id", None) or getattr(trace, "id", None)
        if not trace_id:
            return
        span = self._trace_spans.pop(trace_id, None)
        if span is not None:
            span.end()

    def on_span_start(self, span) -> None:
        exported = getattr(span, "export", lambda: None)()
        if not exported:
            return

        trace_id = exported.get("trace_id")
        parent_id = exported.get("parent_id")
        name = (exported.get("span_data") or {}).get("type") or "span"
        span_id = exported.get("id") or getattr(span, "span_id", None)
        if not trace_id or not span_id:
            return

        parent = None
        if parent_id and parent_id in self._span_spans:
            parent = self._span_spans[parent_id]
        elif trace_id in self._trace_spans:
            parent = self._trace_spans[trace_id]

        ctx = self._otel.set_span_in_context(parent) if parent is not None else None
        otel_span = self._tracer.start_span(name, context=ctx)
        self._span_spans[span_id] = otel_span

        # Attach sanitized input/output as attributes (optional). / 入出力を属性として付与（任意）。
        data = exported.get("span_data") or {}
        if "input" in data and data["input"] is not None:
            otel_span.set_attribute("kantan_llm.input", sanitize_text(_to_text(data["input"])))
        if "output" in data and data["output"] is not None:
            otel_span.set_attribute("kantan_llm.output", sanitize_text(_to_text(data["output"])))

    def on_span_end(self, span) -> None:
        exported = getattr(span, "export", lambda: None)()
        if not exported:
            return
        span_id = exported.get("id") or getattr(span, "span_id", None)
        if not span_id:
            return
        otel_span = self._span_spans.pop(span_id, None)
        if otel_span is not None:
            otel_span.end()

    def shutdown(self) -> None:
        # Provider shutdown is handled by OTEL global provider. / OTELのProvider側で扱う。
        return

    def force_flush(self) -> None:
        return
