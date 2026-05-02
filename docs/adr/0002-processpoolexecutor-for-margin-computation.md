# ADR-0002: ProcessPoolExecutor for Margin Computation
![Status](https://img.shields.io/badge/status-accepted-brightgreen)

| Date | Deciders | Supersedes |
|------|----------|------------|
| 2026-04-24 | Andy | — |

---

## Context

> [!NOTE]
> Margin calculation is CPU-bound: each request fans out across a list of positions, hits a SQLite partition for P&L data, and multiplies quantities. Python's GIL means threads do not provide true parallelism for CPU-bound work. The solution should be simple to operate, easy to observe, and viable in production without requiring a distributed compute layer unless scaling demands it.

## Decision

**We offload `compute_margin` to a `ProcessPoolExecutor`, spawning worker processes that each run their own OTel telemetry pipeline.**

Workers are initialised with `multiprocessing.get_context("spawn")` to avoid inheriting the parent's `BatchSpanProcessor`. Each worker calls `setup_worker_telemetry()` on startup, registering as `margin-calculator-worker` with its own `process.pid` resource attribute. Trace context is propagated from the main process via an OTel carrier dict, so worker spans appear as children of the originating request trace.

## Consequences

> [!IMPORTANT]
> - **True CPU parallelism** — each worker process bypasses the GIL, running DB lookups and arithmetic on a separate core.
> - **Full distributed trace** — the carrier propagation pattern (`propagate.inject` in the main process, `propagate.extract` in the worker) means every worker span is linked to its parent request span in Tempo. No trace context is lost at the process boundary.
> - **Per-worker telemetry** — each worker exports spans and metrics independently via OTLP, tagged with `process.pid`, so you can distinguish work done by different workers in Grafana without any additional instrumentation.
> - **Single-machine scaling** — the executor is sized to the cores available on one host. This is a valid production deployment topology; horizontal scaling (multi-host task queues) is only warranted if profiling shows this ceiling is actually hit.
> - **`spawn` is required** — `fork` would copy the parent's `BatchSpanProcessor` into each worker, causing duplicate span exports and potential deadlocks on the gRPC channel. The `spawn` context adds ~200ms of worker startup time per cold start.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| **ThreadPoolExecutor** | Threads share the GIL; CPU-bound work does not parallelise. Would not improve throughput over a single-threaded approach. |
| **asyncio tasks** | Same GIL constraint — async concurrency is I/O concurrency, not CPU concurrency. |
| **Celery / task queue** | Introduces a broker (Redis/RabbitMQ), worker daemons, and deployment config that adds operational complexity without throughput benefit until the single-machine ceiling is actually reached. Observability would also require separate broker instrumentation. |
| **Ray** | Powerful but heavyweight; designed for distributed compute clusters. Adds significant operational surface area that is only justified at scales beyond what a single host can handle. |
