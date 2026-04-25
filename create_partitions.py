"""Create 15 hive-partitioned SQLite databases under dbs/cob_date=YYYY-MM-DD/sqlite.db.

Each partition gets 2,000 scenario rows (500 base scenarios × 4 tiers) and
16,000 pnl rows (8 positions × 2,000 scenarios) with per-date PnL variation.
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

NUM_BASE_SCENARIOS = 500
TIERS = [1, 2, 3, 4]
TIER_FACTORS = {1: 1.00, 2: 0.75, 3: 0.50, 4: 0.25}

POSITIONS: list[tuple[str, float]] = [
    ("AAPL",  125.0),
    ("GOOG",  -45.0),
    ("MSFT",   80.0),
    ("AMZN",  200.0),
    ("TSLA", -120.0),
    ("NVDA",  350.0),
    ("META",   60.0),
    ("BRK",    30.0),
]

DBS_ROOT = Path(__file__).parent / "dbs"
NUM_PARTITIONS = 15
NOISE = 0.05  # ±5% per-day drift on top of scenario factor


def _build_scenario_definitions() -> list[tuple[int, str, int]]:
    rows: list[tuple[int, str, int]] = []
    for scen_idx in range(NUM_BASE_SCENARIOS):
        name = f"scen_{scen_idx + 1:03d}"
        for tier_idx, tier in enumerate(TIERS):
            sid = scen_idx * len(TIERS) + tier_idx + 1
            rows.append((sid, name, tier))
    return rows


# Pre-computed once — same 2,000 scenario definitions in every partition
_SCENARIO_DEFINITIONS = _build_scenario_definitions()


def business_days_ending(end: date, n: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def create_partition(cob: date, seed: int) -> None:
    rng = random.Random(seed)
    partition_dir = DBS_ROOT / f"cob_date={cob.isoformat()}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    db_path = partition_dir / "sqlite.db"

    # One market factor per base scenario, drawn from a normal distribution
    # so scenarios span a realistic range of gains and losses.
    scenario_factors = [rng.gauss(1.0, 0.30) for _ in range(NUM_BASE_SCENARIOS)]

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenario_definition (
                id            INTEGER PRIMARY KEY,
                scenario_name TEXT    NOT NULL,
                tier          INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pnl (
                position_id TEXT    NOT NULL,
                pnl         REAL    NOT NULL,
                scenario_id INTEGER NOT NULL REFERENCES scenario_definition(id),
                PRIMARY KEY (position_id, scenario_id)
            )
        """)

        conn.executemany(
            "INSERT OR REPLACE INTO scenario_definition (id, scenario_name, tier) VALUES (?, ?, ?)",
            _SCENARIO_DEFINITIONS,
        )

        pnl_rows: list[tuple[str, float, int]] = []
        for scen_idx in range(NUM_BASE_SCENARIOS):
            mkt = scenario_factors[scen_idx]
            for tier_idx, tier in enumerate(TIERS):
                tier_factor = TIER_FACTORS[tier]
                sid = scen_idx * len(TIERS) + tier_idx + 1
                for position_id, base_pnl in POSITIONS:
                    value = round(base_pnl * mkt * tier_factor * (1 + rng.uniform(-NOISE, NOISE)), 4)
                    pnl_rows.append((position_id, value, sid))

        conn.executemany(
            "INSERT OR REPLACE INTO pnl (position_id, pnl, scenario_id) VALUES (?, ?, ?)",
            pnl_rows,
        )
        conn.commit()

    print(
        f"  {db_path}  →  {len(pnl_rows):,} pnl rows  "
        f"({NUM_BASE_SCENARIOS} scenarios × {len(TIERS)} tiers × {len(POSITIONS)} positions)"
    )


def main() -> None:
    today = date(2026, 4, 24)
    dates = business_days_ending(today, NUM_PARTITIONS)
    print(f"Creating {NUM_PARTITIONS} partitions under {DBS_ROOT}/\n")
    for i, cob in enumerate(dates):
        create_partition(cob, seed=i)
    print(f"\nDone — {NUM_PARTITIONS} partitions × {NUM_BASE_SCENARIOS * len(TIERS) * len(POSITIONS):,} pnl rows each.")


if __name__ == "__main__":
    main()
