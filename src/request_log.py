"""Persistent request log backed by SQLite.

Stores every /margin request with its trace ID, body, X-Meta-* headers,
and response for post-hoc debugging and replay.

Writes are enqueued and flushed by a background drain task so they never
block the request handler.
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from datetime import date

from pydantic import BaseModel

from models import MarginResponse, Position


class RequestLogEntry(BaseModel):
    trace_id: str
    ts: str
    cob_date: date
    positions: list[Position]
    meta: dict
    status_code: int | None = None
    response: MarginResponse | None = None


_DB_PATH = (
    Path(os.environ["REQUEST_LOG_PATH"])
    if "REQUEST_LOG_PATH" in os.environ
    else Path(__file__).parent.parent / "requests.db"
)

_conn: sqlite3.Connection | None = None
_queue: asyncio.Queue = asyncio.Queue()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS request_log (
                trace_id    TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                payload     TEXT NOT NULL,
                status_code INTEGER,
                response    TEXT
            )
        """)
        _conn.commit()
    return _conn


def log_request(trace_id: str, request: BaseModel, meta: dict) -> None:
    payload = request.model_dump(mode="json")
    payload["meta"] = meta
    _queue.put_nowait(("request", trace_id, datetime.now(timezone.utc).isoformat(), json.dumps(payload)))


def log_response(trace_id: str, status_code: int, response: BaseModel | dict) -> None:
    response_json = (
        response.model_dump_json()
        if isinstance(response, BaseModel)
        else json.dumps(response)
    )
    _queue.put_nowait(("response", trace_id, status_code, response_json))


def get_log_entry(trace_id: str) -> RequestLogEntry | None:
    row = _get_conn().execute(
        "SELECT trace_id, ts, payload, status_code, response FROM request_log WHERE trace_id = ?",
        (trace_id,),
    ).fetchone()
    if row is None:
        return None
    trace_id, ts, payload, status_code, response = row
    return RequestLogEntry(
        trace_id=trace_id,
        ts=ts,
        status_code=status_code,
        response=json.loads(response) if response else None,
        **json.loads(payload),
    )


async def drain_loop(interval: float = 5.0) -> None:
    """Background task: flush enqueued log entries to SQLite every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)

        batch = []
        try:
            while True:
                batch.append(_queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        if not batch:
            continue

        conn = _get_conn()
        with conn:
            for item in batch:
                if item[0] == "request":
                    _, trace_id, ts, payload = item
                    conn.execute(
                        "INSERT OR REPLACE INTO request_log (trace_id, ts, payload) VALUES (?, ?, ?)",
                        (trace_id, ts, payload),
                    )
                else:
                    _, trace_id, status_code, response_json = item
                    conn.execute(
                        "UPDATE request_log SET status_code = ?, response = ? WHERE trace_id = ?",
                        (status_code, response_json, trace_id),
                    )

        for _ in batch:
            _queue.task_done()
