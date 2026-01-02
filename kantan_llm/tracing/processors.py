from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any

from .processor_interface import TracingProcessor
from ..errors import NotSupportedError
from .search import SpanQuery, SpanRecord, TraceQuery, TraceRecord, TraceSearchCapabilities
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
        output_kind, _, _, _ = _extract_output_parts(data)

        if raw_in is not None:
            self._write_block("INPUT:", _to_text(raw_in), self._C_IN)
        if raw_out is not None:
            self._write_block(_output_label(output_kind), _to_text(raw_out), self._C_OUT)

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
        self._supports_json1: bool | None = None
        self.default_tz = datetime.now().astimezone().tzinfo or timezone.utc

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
            if self._supports_json1 is None:
                self._supports_json1 = _detect_json1(self._conn)
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
            self._ensure_columns_traces()
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spans (
                  id TEXT PRIMARY KEY,
                  trace_id TEXT,
                  parent_id TEXT,
                  started_at TEXT,
                  ended_at TEXT,
                  span_type TEXT,
                  name TEXT,
                  ingest_seq INTEGER,
                  input TEXT,
                  output TEXT,
                  output_kind TEXT,
                  tool_calls_json TEXT,
                  structured_json TEXT,
                  rubric_json TEXT,
                  error_json TEXT,
                  raw_json TEXT
                )
                """
            )
            self._ensure_columns()
            self._conn.commit()
        return self._conn

    def _ensure_columns_traces(self) -> None:
        conn = self._conn
        if conn is None:
            return
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(traces)").fetchall()}
        if "metadata_json" not in cols:
            conn.execute("ALTER TABLE traces ADD COLUMN metadata_json TEXT")
        conn.commit()

    def _ensure_columns(self) -> None:
        conn = self._conn
        if conn is None:
            return
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(spans)").fetchall()}
        if "name" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN name TEXT")
        if "ingest_seq" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN ingest_seq INTEGER")
        if "rubric_json" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN rubric_json TEXT")
        if "usage_json" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN usage_json TEXT")
        if "output_kind" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN output_kind TEXT")
        if "tool_calls_json" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN tool_calls_json TEXT")
        if "structured_json" not in cols:
            conn.execute("ALTER TABLE spans ADD COLUMN structured_json TEXT")
        conn.commit()

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

    def _update_trace_usage_cache(self, conn: sqlite3.Connection, trace_id: str, usage: dict[str, Any]) -> None:
        row = conn.execute("SELECT metadata_json FROM traces WHERE id = ?", (trace_id,)).fetchone()
        metadata = _json_or_none(row["metadata_json"]) if row else None
        if metadata is None:
            metadata = {}
        usage_total = metadata.get("usage_total") or {}
        for key, value in usage.items():
            if isinstance(value, (int, float)):
                usage_total[key] = usage_total.get(key, 0) + value
        metadata["usage_total"] = usage_total
        conn.execute(
            "UPDATE traces SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False, default=str), trace_id),
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

        span_data = exported.get("span_data") or {}
        span_usage = exported.get("usage")
        raw_in = span_data.get("input")
        raw_out = span_data.get("output_raw", span_data.get("output"))
        span_name = span_data.get("name")
        usage = span_usage or _extract_usage(span_data)

        input_text = sanitize_text(_to_text(raw_in)) if raw_in is not None else None
        output_text = sanitize_text(_to_text(span_data.get("output"))) if span_data.get("output") is not None else None
        output_kind, tool_calls, structured, rubric = _extract_output_parts(span_data, raw_out)

        if isinstance(usage, dict):
            usage = _normalize_usage(usage)
        else:
            usage = None

        conn = self._ensure_conn()
        with conn:
            # Ensure trace row exists even if we didn't see on_trace_start (interop). / trace startを見ていなくてもtrace行を作る。
            self._upsert_trace(getattr(span, "_trace", None) or _TraceLike(trace_id=trace_id))
            conn.execute(
                """
                INSERT OR REPLACE INTO spans(
                  id, trace_id, parent_id, started_at, ended_at, span_type, name, ingest_seq, input, output,
                  output_kind, tool_calls_json, structured_json, rubric_json, usage_json, error_json, raw_json
                ) VALUES(
                  ?, ?, ?, ?, ?, ?, ?, (SELECT COALESCE(MAX(ingest_seq), 0) + 1 FROM spans WHERE trace_id = ?),
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    exported.get("id") or getattr(span, "span_id", None),
                    trace_id,
                    exported.get("parent_id"),
                    exported.get("started_at"),
                    exported.get("ended_at"),
                    span_data.get("type"),
                    span_name,
                    trace_id,
                    input_text,
                    output_text,
                    output_kind,
                    json.dumps(tool_calls, ensure_ascii=False, default=str) if tool_calls is not None else None,
                    json.dumps(structured, ensure_ascii=False, default=str) if structured is not None else None,
                    json.dumps(rubric, ensure_ascii=False, default=str) if rubric is not None else None,
                    json.dumps(usage, ensure_ascii=False, default=str) if usage is not None else None,
                    json.dumps(exported.get("error"), ensure_ascii=False, default=str),
                    json.dumps(exported, ensure_ascii=False, default=str),
                ),
            )
            if usage:
                self._update_trace_usage_cache(conn, trace_id, usage)

    def capabilities(self) -> TraceSearchCapabilities:
        return TraceSearchCapabilities(
            supports_keywords=True,
            supports_has_tool_call=True,
            supports_metadata_query=bool(self._supports_json1),
            supports_limit=True,
            supports_since=True,
        )

    def search_traces(self, *, query: TraceQuery) -> list[TraceRecord]:
        conn = self._ensure_conn()
        where, params = _build_trace_where(query, self.default_tz)
        if query.metadata:
            if not self._supports_json1:
                raise NotSupportedError("metadata query")
            meta_where, meta_params = _build_metadata_where(query.metadata)
            where.extend(meta_where)
            params.extend(meta_params)
        sql = "SELECT id, workflow_name, group_id, metadata_json FROM traces"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        if query.limit:
            sql += " LIMIT ?"
            params.append(query.limit)
        rows = conn.execute(sql, params).fetchall()
        records: list[TraceRecord] = []
        for row in rows:
            trace_id = row["id"]
            started_at, ended_at = _trace_times(conn, trace_id)
            records.append(
                TraceRecord(
                    trace_id=trace_id,
                    workflow_name=row["workflow_name"] or "",
                    group_id=row["group_id"],
                    started_at=_return_dt(started_at, query, self.default_tz),
                    ended_at=_return_dt(ended_at, query, self.default_tz),
                    metadata=_json_or_none(row["metadata_json"]),
                )
            )
        return records

    def search_spans(self, *, query: SpanQuery) -> list[SpanRecord]:
        conn = self._ensure_conn()
        where, params = _build_span_where(query, self.default_tz)
        sql = (
            "SELECT id, trace_id, parent_id, span_type, name, started_at, ended_at, "
            "COALESCE(ingest_seq, 0) AS ingest_seq, input, output, output_kind, tool_calls_json, structured_json, "
            "rubric_json, usage_json, error_json, raw_json "
            "FROM spans"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ingest_seq ASC"
        if query.limit:
            sql += " LIMIT ?"
            params.append(query.limit)
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_span_record(row, query, self.default_tz) for row in rows]

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        conn = self._ensure_conn()
        row = conn.execute(
            "SELECT id, workflow_name, group_id, metadata_json FROM traces WHERE id = ?",
            (trace_id,),
        ).fetchone()
        if not row:
            return None
        started_at, ended_at = _trace_times(conn, trace_id)
        return TraceRecord(
            trace_id=row["id"],
            workflow_name=row["workflow_name"] or "",
            group_id=row["group_id"],
            started_at=_return_dt(started_at, None, self.default_tz),
            ended_at=_return_dt(ended_at, None, self.default_tz),
            metadata=_json_or_none(row["metadata_json"]),
        )

    def get_span(self, span_id: str) -> SpanRecord | None:
        conn = self._ensure_conn()
        row = conn.execute(
            "SELECT id, trace_id, parent_id, span_type, name, started_at, ended_at, "
            "COALESCE(ingest_seq, 0) AS ingest_seq, input, output, output_kind, tool_calls_json, structured_json, "
            "rubric_json, usage_json, error_json, raw_json "
            "FROM spans WHERE id = ?",
            (span_id,),
        ).fetchone()
        if not row:
            return None
        return _row_to_span_record(row, None, self.default_tz)

    def get_spans_by_trace(self, trace_id: str) -> list[SpanRecord]:
        conn = self._ensure_conn()
        rows = conn.execute(
            "SELECT id, trace_id, parent_id, span_type, name, started_at, ended_at, "
            "COALESCE(ingest_seq, 0) AS ingest_seq, input, output, output_kind, tool_calls_json, structured_json, "
            "rubric_json, usage_json, error_json, raw_json "
            "FROM spans WHERE trace_id = ? ORDER BY ingest_seq ASC",
            (trace_id,),
        ).fetchall()
        return [_row_to_span_record(row, None, self.default_tz) for row in rows]

    def get_spans_since(self, trace_id: str, since_seq: int | None = None) -> list[SpanRecord]:
        conn = self._ensure_conn()
        since_value = since_seq or 0
        rows = conn.execute(
            "SELECT id, trace_id, parent_id, span_type, name, started_at, ended_at, "
            "COALESCE(ingest_seq, 0) AS ingest_seq, input, output, output_kind, tool_calls_json, structured_json, "
            "rubric_json, usage_json, error_json, raw_json "
            "FROM spans WHERE trace_id = ? AND COALESCE(ingest_seq, 0) > ? "
            "ORDER BY ingest_seq ASC",
            (trace_id, since_value),
        ).fetchall()
        return [_row_to_span_record(row, None, self.default_tz) for row in rows]

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


def _output_label(output_kind: str | None) -> str:
    if output_kind == "text":
        return "OUTPUT(text):"
    if output_kind == "tool_calls":
        return "TOOL_CALLS:"
    if output_kind == "structured":
        return "STRUCTURED:"
    if output_kind == "judge":
        return "JUDGE:"
    return "OUTPUT:"


def _extract_output_parts(
    span_data: dict[str, Any],
    raw_out: Any | None = None,
) -> tuple[str | None, list[dict[str, Any]] | None, Any | None, dict[str, Any] | None]:
    output_value = raw_out if raw_out is not None else span_data.get("output")
    rubric = _extract_rubric(span_data, output_value)
    tool_calls = _extract_tool_calls(output_value)
    structured = _extract_structured_output(output_value, tool_calls)

    output_kind = None
    if rubric is not None:
        output_kind = "judge"
    elif tool_calls is not None:
        output_kind = "tool_calls"
    elif structured is not None:
        output_kind = "structured"
    elif output_value is not None:
        output_kind = "text"

    return output_kind, tool_calls, structured, rubric


def _extract_rubric(span_data: dict[str, Any], output: Any | None = None) -> dict[str, Any] | None:
    if "rubric" in span_data and isinstance(span_data["rubric"], dict):
        return span_data["rubric"]
    data = span_data.get("data")
    if isinstance(data, dict) and isinstance(data.get("rubric"), dict):
        return data["rubric"]
    rubric = _extract_rubric_from_output(output)
    if rubric is not None:
        return rubric
    return None


def _extract_tool_calls(output: Any) -> list[dict[str, Any]] | None:
    if output is None:
        return None
    if isinstance(output, dict):
        tool_calls = output.get("tool_calls")
        if isinstance(tool_calls, (list, tuple)):
            return _normalize_tool_calls(tool_calls)
        item_type = output.get("type")
        if item_type in {"tool_call", "function_call", "tool"} or "function_call" in output:
            return [_normalize_tool_call_item(output)]
        return None
    if isinstance(output, (list, tuple)):
        calls: list[dict[str, Any]] = []
        for item in output:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type in {"tool_call", "function_call", "tool"}:
                    calls.append(_normalize_tool_call_item(item))
                    continue
                nested = item.get("tool_calls")
                if isinstance(nested, (list, tuple)):
                    calls.extend(_normalize_tool_calls(nested))
                    continue
                if "function_call" in item:
                    calls.append(_normalize_tool_call_item(item))
                    continue
            else:
                item_type = getattr(item, "type", None)
                if item_type in {"tool_call", "function_call", "tool"}:
                    calls.append(_normalize_tool_call_item(item))
        return calls or None
    return None


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(tool_calls, dict):
        return [_normalize_tool_call_item(tool_calls)]
    if not isinstance(tool_calls, (list, tuple)):
        return normalized
    for call in tool_calls:
        normalized.append(_normalize_tool_call_item(call))
    return normalized


def _normalize_tool_call_item(call: Any) -> dict[str, Any]:
    if isinstance(call, dict):
        return dict(call)
    function = getattr(call, "function", None)
    return {
        "id": getattr(call, "id", None),
        "call_id": getattr(call, "call_id", None),
        "type": getattr(call, "type", None),
        "name": getattr(call, "name", None) or getattr(function, "name", None),
        "arguments": getattr(call, "arguments", None) or getattr(function, "arguments", None),
    }


def _extract_structured_output(output: Any, tool_calls: list[dict[str, Any]] | None) -> Any | None:
    if output is None:
        return None
    if isinstance(output, dict):
        if "tool_calls" in output and len(output) == 1:
            return None
        return output
    if isinstance(output, (list, tuple)):
        if tool_calls is not None:
            only_tool_calls = all(
                isinstance(item, dict) and item.get("type") in {"tool_call", "function_call", "tool"}
                for item in output
            )
            if only_tool_calls:
                return None
        return list(output)
    return None


def _extract_usage(span_data: dict[str, Any]) -> dict[str, Any] | None:
    usage = span_data.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def _normalize_usage(usage: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(usage)

    def _num(value: Any) -> int | float | None:
        if isinstance(value, (int, float)):
            return value
        return None

    prompt_tokens = _num(normalized.get("prompt_tokens"))
    completion_tokens = _num(normalized.get("completion_tokens"))
    input_tokens = _num(normalized.get("input_tokens"))
    output_tokens = _num(normalized.get("output_tokens"))

    if input_tokens is None and prompt_tokens is not None:
        normalized["input_tokens"] = prompt_tokens
        input_tokens = prompt_tokens
    if output_tokens is None and completion_tokens is not None:
        normalized["output_tokens"] = completion_tokens
        output_tokens = completion_tokens

    total_tokens = _num(normalized.get("total_tokens"))
    if total_tokens is None:
        if input_tokens is not None and output_tokens is not None:
            normalized["total_tokens"] = input_tokens + output_tokens
        elif prompt_tokens is not None and completion_tokens is not None:
            normalized["total_tokens"] = prompt_tokens + completion_tokens

    return normalized


def _extract_rubric_from_output(output: Any) -> dict[str, Any] | None:
    if output is None:
        return None
    if isinstance(output, dict):
        if isinstance(output.get("rubric"), dict):
            return output["rubric"]
        if "score" in output or "comment" in output:
            return {"score": output.get("score"), "comment": output.get("comment")}
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except Exception:
            return None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("rubric"), dict):
                return parsed["rubric"]
            if "score" in parsed or "comment" in parsed:
                return {"score": parsed.get("score"), "comment": parsed.get("comment")}
    return None


def _json_or_none(value: str | None) -> Any | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _return_dt(value: datetime | None, query: TraceQuery | SpanQuery | None, default_tz) -> datetime | None:
    if value is None:
        return None

    has_query_dt = False
    query_dt = None
    if query is not None:
        query_dt = query.started_from or query.started_to
        if query_dt is not None:
            has_query_dt = True

    if query_dt is not None and query_dt.tzinfo is not None:
        return value.astimezone(query_dt.tzinfo)

    # Query naive or no query: return naive in default_tz.
    local = value.astimezone(default_tz)
    return local.replace(tzinfo=None) if (query_dt is None or query_dt.tzinfo is None) else local


def _normalize_query_dt(value: datetime | None, default_tz) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_tz)
    return value.astimezone(timezone.utc)


def _build_trace_where(query: TraceQuery, default_tz) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    if query.trace_id:
        where.append("id = ?")
        params.append(query.trace_id)
    if query.workflow_name:
        where.append("workflow_name = ?")
        params.append(query.workflow_name)
    if query.group_id:
        where.append("group_id = ?")
        params.append(query.group_id)
    # keywords on spans input/output (AND over keywords)
    if query.keywords:
        for kw in query.keywords:
            where.append(
                "EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id "
                "AND (LOWER(COALESCE(s.input,'')) LIKE ? OR LOWER(COALESCE(s.output,'')) LIKE ?))"
            )
            like = f"%{kw.lower()}%"
            params.extend([like, like])
    if query.has_error is True:
        where.append(
            "EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id "
            "AND s.error_json IS NOT NULL AND s.error_json != 'null')"
        )
    if query.has_error is False:
        where.append(
            "NOT EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id "
            "AND s.error_json IS NOT NULL AND s.error_json != 'null')"
        )
    if query.has_tool_call is True:
        where.append(
            "EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id "
            "AND (s.tool_calls_json IS NOT NULL "
            "OR s.raw_json LIKE '%tool_calls%' OR s.raw_json LIKE '%function_call%'))"
        )
    if query.has_tool_call is False:
        where.append(
            "NOT EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id "
            "AND (s.tool_calls_json IS NOT NULL "
            "OR s.raw_json LIKE '%tool_calls%' OR s.raw_json LIKE '%function_call%'))"
        )
    started_from = _normalize_query_dt(query.started_from, default_tz=default_tz)
    started_to = _normalize_query_dt(query.started_to, default_tz=default_tz)
    if started_from or started_to:
        clause = "EXISTS (SELECT 1 FROM spans s WHERE s.trace_id = traces.id"
        if started_from:
            clause += " AND s.started_at >= ?"
            params.append(started_from.isoformat())
        if started_to:
            clause += " AND s.started_at <= ?"
            params.append(started_to.isoformat())
        clause += ")"
        where.append(clause)
    return where, params


def _build_metadata_where(metadata: dict[str, Any]) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    for key, value in metadata.items():
        path = f"$.{key}"
        if value is None:
            where.append("json_extract(metadata_json, ?) IS NULL")
            params.append(path)
            continue
        if isinstance(value, bool):
            where.append("json_extract(metadata_json, ?) = ?")
            params.extend([path, 1 if value else 0])
            continue
        if isinstance(value, (int, float, str)):
            where.append("json_extract(metadata_json, ?) = ?")
            params.extend([path, value])
            continue
        raise NotSupportedError("metadata query (non-scalar)")
    return where, params


def _detect_json1(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT json_extract('{\"a\":1}', '$.a')").fetchone()
    except sqlite3.OperationalError:
        return False
    return True


def _build_span_where(query: SpanQuery, default_tz) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    if query.span_id:
        where.append("id = ?")
        params.append(query.span_id)
    if query.trace_id:
        where.append("trace_id = ?")
        params.append(query.trace_id)
    if query.span_type:
        where.append("span_type = ?")
        params.append(query.span_type)
    if query.name:
        where.append("name = ?")
        params.append(query.name)
    if query.has_error is True:
        where.append("error_json IS NOT NULL AND error_json != 'null'")
    if query.has_error is False:
        where.append("(error_json IS NULL OR error_json = 'null')")
    if query.keywords:
        for kw in query.keywords:
            where.append("(LOWER(COALESCE(input,'')) LIKE ? OR LOWER(COALESCE(output,'')) LIKE ?)")
            like = f"%{kw.lower()}%"
            params.extend([like, like])
    if query.started_from or query.started_to:
        # started_at is stored as ISO string in UTC
        if query.started_from:
            params.append(_normalize_query_dt(query.started_from, default_tz).isoformat())
            where.append("started_at >= ?")
        if query.started_to:
            params.append(_normalize_query_dt(query.started_to, default_tz).isoformat())
            where.append("started_at <= ?")
    return where, params


def _row_to_span_record(row: sqlite3.Row, query: SpanQuery | None, default_tz) -> SpanRecord:
    started_at = _parse_dt(row["started_at"])
    ended_at = _parse_dt(row["ended_at"])
    return SpanRecord(
        trace_id=row["trace_id"],
        span_id=row["id"],
        parent_id=row["parent_id"],
        span_type=row["span_type"],
        name=row["name"],
        started_at=_return_dt(started_at, query, default_tz),
        ended_at=_return_dt(ended_at, query, default_tz),
        ingest_seq=int(row["ingest_seq"] or 0),
        input=row["input"],
        output=row["output"],
        output_kind=row["output_kind"],
        tool_calls=_json_or_none(row["tool_calls_json"]),
        structured=_json_or_none(row["structured_json"]),
        rubric=_json_or_none(row["rubric_json"]),
        usage=_json_or_none(row["usage_json"]),
        error=_json_or_none(row["error_json"]),
        raw=_json_or_none(row["raw_json"]),
    )


def _trace_times(conn: sqlite3.Connection, trace_id: str) -> tuple[datetime | None, datetime | None]:
    row = conn.execute(
        "SELECT MIN(started_at) AS started_at, MAX(ended_at) AS ended_at FROM spans WHERE trace_id = ?",
        (trace_id,),
    ).fetchone()
    if not row:
        return None, None
    return _parse_dt(row["started_at"]), _parse_dt(row["ended_at"])




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
            data = exported.get("span_data") or {}
            output_kind, tool_calls, structured, _ = _extract_output_parts(data, data.get("output_raw"))
            if output_kind:
                otel_span.set_attribute("kantan_llm.output_kind", output_kind)
            if tool_calls is not None:
                otel_span.set_attribute("kantan_llm.tool_calls_json", sanitize_text(_to_text(tool_calls)))
            if structured is not None:
                otel_span.set_attribute("kantan_llm.structured_json", sanitize_text(_to_text(structured)))
            otel_span.end()

    def shutdown(self) -> None:
        # Provider shutdown is handled by OTEL global provider. / OTELのProvider側で扱う。
        return

    def force_flush(self) -> None:
        return
