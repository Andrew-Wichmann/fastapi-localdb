# ADR-0002: ProcessPoolExecutor for Margin Computation
![Status](https://img.shields.io/badge/status-accepted-brightgreen)

| Date | Deciders | Supersedes |
|------|----------|------------|
| 2026-04-24 | Andy | — |

---

## Context

> [!NOTE]
> Margin calculation is CPU-bound: each request fans out across a list of positions, hits a SQLite partition for P&L data, and multiplies quantities. Python's GIL means threads do not provide true parallelism for CPU-bound work. At the same time, the service is a local development tool — not a production system managing a fleet of machines — so the solution should be simple to operate and easy to observe.

## Decision

**We offload `compute_margin` to a `ProcessPoolExecutor`, spawning worker processes that each run their own OTel telemetry pipeline.**

Workers are initialised with `multiprocessing.get_context("spawn")` to avoid inheriting the parent's `BatchSpanProcessor`. Each worker calls `setup_worker_telemetry()` on startup, registering as `margin-calculator-worker` with its own `process.pid` resource attribute. Trace context is propagated from the main process via an OTel carrier dict, so worker spans appear as children of the originating request trace.

## Consequences

> [!IMPORTANT]
> - **True CPU parallelism** — each worker process bypasses the GIL, running DB lookups and arithmetic on a separate core.
> - **Full distributed trace** — the carrier propagation pattern (`propagate.inject` in the main process, `propagate.extract` in the worker) means every worker span is linked to its parent request span in Tempo. No trace context is lost at the process boundary.
> - **Per-worker telemetry** — each worker exports spans and metrics independently via OTLP, tagged with `process.pid`, so you can distinguish work done by different workers in Grafana without any additional instrumentation.
> - **Simplicity ceiling** — the executor is sized to local hardware. Scaling beyond one machine means replacing this with a task queue (Celery, Ray, etc.), but that complexity is not justified for a local dev tool with a 45-second SLA.
> - **`spawn` is required** — `fork` would copy the parent's `BatchSpanProcessor` into each worker, causing duplicate span exports and potential deadlocks on the gRPC channel. The `spawn` context adds ~200ms of worker startup time per cold start.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| **ThreadPoolExecutor** | Threads share the GIL; CPU-bound work does not parallelise. Would not improve throughput over a single-threaded approach. |
| **asyncio tasks** | Same GIL constraint — async concurrency is I/O concurrency, not CPU concurrency. |
| **Celery / task queue** | Introduces a broker (Redis/RabbitMQ), worker daemons, and deployment config that is disproportionate for a local tool. Observability would also require separate broker instrumentation. |
| **Ray** | Powerful but heavyweight; designed for distributed compute clusters, not a single-machine dev service. |
