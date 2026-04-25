"""Seed a single SQLite partition with sample data.

Run once to create/overwrite a specific cob_date partition:
    python seed_db.py
"""

from create_partitions import create_partition
from datetime import date

if __name__ == "__main__":
    cob = date(2026, 4, 24)
    create_partition(cob, seed=99)
    print(f"Seeded partition for {cob}")
