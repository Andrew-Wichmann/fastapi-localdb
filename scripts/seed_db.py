"""Seed a single SQLite partition with sample data.

Run once to create/overwrite a specific cob_date partition:
    python seed_db.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from create_partitions import create_partition

if __name__ == "__main__":
    cob = date(2026, 4, 24)
    create_partition(cob, seed=99)
    print(f"Seeded partition for {cob}")
