"""Locust load test for the margin calculator.

Run headless (recommended for a first look):
    locust --headless -u 20 -r 2 --run-time 60s --host http://localhost:8000

Open the web UI instead:
    locust --host http://localhost:8000
    then open http://localhost:8089

Flags used above:
  -u  total users to spawn
  -r  users spawned per second (ramp rate)
  --run-time  stop after this duration
"""

import random

from locust import HttpUser, between, task

COB_DATES = [
    "2026-04-06", "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10",
    "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17",
    "2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-24",
]

POSITION_IDS = ["AAPL", "GOOG", "MSFT", "AMZN", "TSLA", "NVDA", "META", "BRK"]

SLA_SECONDS = 45.0


class MarginUser(HttpUser):
    # Think time between requests — simulates a realistic caller, not a tight loop.
    wait_time = between(0.5, 1.5)

    @task(6)
    def full_portfolio_hot_date(self):
        """Most common case: full portfolio on today's date.

        After the first request warms the LRU cache this stays on the fast
        path indefinitely, so it dominates the steady-state latency picture.
        """
        self._post(
            cob_date="2026-04-24",
            position_ids=POSITION_IDS,
        )

    @task(3)
    def partial_portfolio_hot_date(self):
        """Second most common: a few positions, still on today's date."""
        self._post(
            cob_date="2026-04-24",
            position_ids=random.sample(POSITION_IDS, random.randint(1, 4)),
        )

    @task(1)
    def random_date(self):
        """Occasional historical lookup — any date, any size portfolio.

        Keeps the LRU cache honest and represents the tail of the distribution.
        """
        self._post(
            cob_date=random.choice(COB_DATES),
            position_ids=random.sample(POSITION_IDS, random.randint(1, len(POSITION_IDS))),
        )

    def _post(self, cob_date: str, position_ids: list[str]) -> None:
        payload = {
            "cob_date": cob_date,
            "positions": [
                {"id": pid, "quantity": round(random.uniform(1.0, 1000.0), 2)}
                for pid in position_ids
            ],
        }
        with self.client.post("/margin", json=payload, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:120]}")
            elif resp.elapsed.total_seconds() > SLA_SECONDS:
                resp.failure(f"SLA breach: {resp.elapsed.total_seconds():.2f}s > {SLA_SECONDS}s")
            else:
                resp.success()
