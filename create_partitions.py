"""Create 15 hive-partitioned SQLite databases under dbs/cob_date=YYYY-MM-DD/sqlite.db.

Each partition gets the same ticker set with slightly perturbed multipliers so
the data looks like a realistic time series of daily risk parameters.
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

TICKERS: list[tuple[str, float]] = [
    ("AAPL", 1.25),
    ("GOOG", 0.95),
    ("MSFT", 1.10),
    ("AMZN", 1.30),
    ("TSLA", 1.75),
    ("NVDA", 2.00),
    ("META", 0.85),
    ("BRK",  0.60),
]

DBS_ROOT = Path(__file__).parent / "dbs"
NUM_PARTITIONS = 15
NOISE = 0.05  # ±5% daily drift


def business_days_ending(end: date, n: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:  # Mon–Fri
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def create_partition(cob: date, seed: int) -> None:
    rng = random.Random(seed)
    partition_dir = DBS_ROOT / f"cob_date={cob.isoformat()}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    db_path = partition_dir / "sqlite.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS multipliers (
                id         TEXT PRIMARY KEY,
                multiplier REAL NOT NULL
            )
            """
        )
        rows = [
            (ticker, round(base * (1 + rng.uniform(-NOISE, NOISE)), 6))
            for ticker, base in TICKERS
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO multipliers (id, multiplier) VALUES (?, ?)",
            rows,
        )
        conn.commit()
    print(f"  {db_path}  →  {len(rows)} rows")


def main() -> None:
    today = date(2026, 4, 24)
    dates = business_days_ending(today, NUM_PARTITIONS)
    print(f"Creating {NUM_PARTITIONS} partitions under {DBS_ROOT}/\n")
    for i, cob in enumerate(dates):
        create_partition(cob, seed=i)
    print(f"\nDone — {NUM_PARTITIONS} partitions created.")


if __name__ == "__main__":
    main()
