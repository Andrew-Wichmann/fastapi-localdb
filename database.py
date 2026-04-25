"""SQLite database setup and per-process query helpers.

Each worker process must open its own connection — SQLite connections are not
fork-safe to share across processes.
"""

import sqlite3
from functools import lru_cache
from pathlib import Path

from opentelemetry import trace

_ROOT = Path(__file__).parent
_tracer = trace.get_tracer(__name__)


def partition_path(cob_date: str) -> Path:
    return _ROOT / "dbs" / f"cob_date={cob_date}" / "sqlite.db"


def _load_partition(db_path: str) -> sqlite3.Connection:
    """Open the on-disk DB and copy it entirely into an in-memory DB.

    Only called on an LRU cache miss.
    """
    with _tracer.start_as_current_span("db.load_partition") as span:
        span.set_attribute("db.path", db_path)
        disk = sqlite3.connect(db_path)
        mem = sqlite3.connect(":memory:", check_same_thread=False)
        disk.backup(mem)
        disk.close()
        mem.execute("PRAGMA foreign_keys = ON")
        return mem


@lru_cache(maxsize=3)
def _get_connection(db_path: str) -> sqlite3.Connection:
    return _load_partition(db_path)


def init_db() -> None:
    """No-op — partitions are pre-created by create_partitions.py."""


def get_pnl(cob_date: str, position_ids: list[str]) -> dict[str, float]:
    """Fetch total PnL (summed across all scenarios) for the requested positions.

    Returns only the position_ids that exist in the database; missing ids are
    omitted from the result.
    """
    if not position_ids:
        return {}
    db = partition_path(cob_date)
    if not db.exists():
        raise FileNotFoundError(f"No partition for cob_date={cob_date}")

    before = _get_connection.cache_info()
    conn = _get_connection(str(db))
    cache_hit = _get_connection.cache_info().hits > before.hits

    with _tracer.start_as_current_span("db.query") as span:
        span.set_attribute("db.system", "sqlite")
        span.set_attribute("db.cob_date", cob_date)
        span.set_attribute("db.cache_hit", cache_hit)
        span.set_attribute("db.num_ids", len(position_ids))
        placeholders = ",".join("?" * len(position_ids))
        rows = conn.execute(
            f"""
            SELECT position_id, SUM(pnl)
            FROM pnl
            WHERE position_id IN ({placeholders})
            GROUP BY position_id
            """,
            position_ids,
        ).fetchall()
        span.set_attribute("db.rows_returned", len(rows))
        return {row[0]: row[1] for row in rows}
