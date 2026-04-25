"""Seed the SQLite multipliers table with sample data.

Run once before starting the app:
    python seed_db.py
"""

import sqlite3
from database import DB_PATH, init_db

SEED_DATA: list[tuple[str, float]] = [
    ("AAPL", 1.25),
    ("GOOG", 0.95),
    ("MSFT", 1.10),
    ("AMZN", 1.30),
    ("TSLA", 1.75),
    ("NVDA", 2.00),
    ("META", 0.85),
    ("BRK", 0.60),
]


def seed() -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO multipliers (id, multiplier) VALUES (?, ?)",
            SEED_DATA,
        )
        conn.commit()
    print(f"Seeded {len(SEED_DATA)} rows into {DB_PATH}")


if __name__ == "__main__":
    seed()
