# ADR-0003: SQLite for P&L Storage
![Status](https://img.shields.io/badge/status-accepted-brightgreen)

| Date | Deciders | Supersedes |
|------|----------|------------|
| 2026-04-24 | Andy | — |

---

## Context

> [!NOTE]
> The P&L dataset is relational: a `pnl` table references a `scenario_definition` table via a foreign key, and queries aggregate across scenario tiers using `GROUP BY`. Each close-of-business date is an independent snapshot — data for a given date never changes after it is written. The dataset for a single date is bounded (16,000 rows across 8 positions × 2,000 scenarios) and must be queried at low latency by worker processes running concurrently.

## Decision

**We store each COB date's P&L data in a separate SQLite file, partitioned under `dbs/cob_date=YYYY-MM-DD/sqlite.db`, and load the entire file into an in-memory database on first access.**

The schema uses two tables — `scenario_definition` and `pnl` — with a foreign key enforced via `PRAGMA foreign_keys = ON`. Queries use standard SQL aggregation (`SUM`, `GROUP BY`). Each worker process caches its in-memory connection via `lru_cache`, so repeated queries within a process hit RAM rather than disk.

## Consequences

> [!IMPORTANT]
> - **Relational integrity** — the `scenario_definition` / `pnl` foreign key relationship is enforced by the database, not application code. SQL joins and aggregations (`SUM(pnl) GROUP BY position_id`) are expressed naturally without custom data-wrangling logic.
> - **Full in-memory execution** — `sqlite3.Connection.backup()` copies the on-disk file into `:memory:` on first access. Subsequent queries within the same worker process execute entirely in RAM, with no disk I/O on the hot path.
> - **Standard query language** — the data model and query logic are expressed in SQL, which is universally understood and straightforward to inspect, test, or extend without knowledge of the application code.
> - **Self-contained application state** — each partition is a single file. A COB date's dataset can be copied, archived, inspected with any SQLite client, or shipped as an attachment. The `/debug/partition/{cob_date}` endpoint exploits this directly, streaming the file as a zip for local debugging.
> - **Hive-compatible layout** — the `cob_date=YYYY-MM-DD` directory naming is compatible with partitioned dataset conventions (Parquet, Delta, Hive), making future migration to a columnar format straightforward if the dataset grows.
> - **Per-process connections** — SQLite connections are not safe to share across processes. Each worker opens its own connection; the `lru_cache` is process-local, so a cold worker always pays one load cost before hitting the in-memory cache.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| **PostgreSQL / other RDBMS** | Adds a network hop, a running server process, and connection pool management. The dataset is read-only after write and bounded in size — there is no workload that justifies a client-server database. |
| **Parquet / columnar files** | No foreign key enforcement, no SQL aggregation without an additional query engine (DuckDB, Polars). Better fit for analytical bulk scans than row-lookup-and-aggregate queries. |
| **In-process dict / numpy array** | Loses the relational structure and SQL interface. Querying and aggregating across scenarios would require custom Python logic that a SQL engine handles for free. |
| **DuckDB** | A strong alternative if the dataset grows to where columnar compression or vectorised execution matters. Not warranted at current data volumes. |
