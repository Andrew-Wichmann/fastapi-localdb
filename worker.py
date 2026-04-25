"""ProcessPool worker logic.

Each function here runs inside a worker process spawned by ProcessPoolExecutor.
A single batched DB query is used per request to minimise connection overhead.
Trace context is propagated from the main process via a carrier dict so spans
appear as children of the originating request trace.
"""

from opentelemetry import propagate, trace

from database import get_multipliers

_tracer = trace.get_tracer(__name__)


def compute_margin(cob_date: str, positions: list[dict], carrier: dict) -> dict:
    ctx = propagate.extract(carrier)
    with _tracer.start_as_current_span("worker.compute_margin", context=ctx) as span:
        span.set_attribute("cob_date", cob_date)
        span.set_attribute("num_positions", len(positions))

        ids = [pos["id"] for pos in positions]
        multipliers = get_multipliers(cob_date, ids)

        total = sum(
            pos["quantity"] * multipliers[pos["id"]]
            for pos in positions
            if pos["id"] in multipliers
        )

        span.set_attribute("total_margin", total)
        return {"total_margin": total, "cob_date": cob_date}
