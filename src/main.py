"""FastAPI margin calculator backed by SQLite.

POST /margin
  Body: { "cob_date": "YYYY-MM-DD", "positions": [{"id": "...", "quantity": 1.0}, ...] }
  Response: { "total_margin": <float>, "cob_date": "YYYY-MM-DD" }

Processing is delegated to a ProcessPoolExecutor so that CPU-bound DB lookups
and multiplications run in parallel without blocking the event loop.
SLA target: respond in ≤ 15 seconds.
"""

import asyncio
import io
import multiprocessing
import zipfile
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from opentelemetry import propagate, trace as otel_trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from database import init_db, partition_path
from models import MarginRequest, MarginResponse, Position  # noqa: F401 (Position re-exported for FastAPI schema)
from request_log import RequestLogEntry, drain_loop, get_log_entry, log_request, log_response
from telemetry import setup_telemetry, setup_worker_telemetry
from worker import compute_margin

# Must run before app creation so FastAPIInstrumentor sees the real provider
# and the middleware stack is instrumented before it is frozen.
setup_telemetry("margin-calculator")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

_executor: ProcessPoolExecutor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _executor
    init_db()
    # spawn avoids inheriting the parent's BatchSpanProcessor into workers
    _executor = ProcessPoolExecutor(
        mp_context=multiprocessing.get_context("spawn"),
        initializer=setup_worker_telemetry,
    )
    drain_task = asyncio.create_task(drain_loop())
    yield
    drain_task.cancel()
    _executor.shutdown(wait=False)


app = FastAPI(title="Margin Calculator", lifespan=lifespan)
# Instrument after app creation but before any request — middleware stack is
# built lazily on first request, so this registration is still in time.
FastAPIInstrumentor.instrument_app(app)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.get("/debug/partition/{cob_date}")
async def download_partition(cob_date: str) -> StreamingResponse:
    """Zip and stream a raw SQLite partition for local debugging."""
    db = partition_path(cob_date)
    if not db.exists():
        raise HTTPException(status_code=404, detail=f"No partition for cob_date={cob_date}")

    def zip_stream():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db, arcname=f"dbs/cob_date={cob_date}/sqlite.db")
        buf.seek(0)
        yield from buf

    filename = f"partition_{cob_date}.zip"
    return StreamingResponse(
        zip_stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/debug/request/{trace_id}", response_model=RequestLogEntry)
async def get_request(trace_id: str) -> RequestLogEntry:
    """Return a logged request entry by trace ID."""
    entry = get_log_entry(trace_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No log entry for trace_id={trace_id}")
    return entry


@app.post("/margin", response_model=MarginResponse)
async def calculate_margin(request: MarginRequest, http_request: Request) -> MarginResponse:
    """Compute total margin for all positions using a ProcessPool."""
    if not request.positions:
        return MarginResponse(total_margin=0.0, cob_date=request.cob_date)

    loop = asyncio.get_running_loop()
    positions = [pos.model_dump() for pos in request.positions]

    trace_id = format(otel_trace.get_current_span().get_span_context().trace_id, "032x")
    meta = {
        k.lower().removeprefix("x-meta-"): v
        for k, v in http_request.headers.items()
        if k.lower().startswith("x-meta-")
    }
    log_request(trace_id, request, meta)

    carrier: dict = {}
    propagate.inject(carrier)

    try:
        # SLA: 45 seconds total.
        result: dict = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                compute_margin,
                request.cob_date.isoformat(),
                positions,
                carrier,
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        detail = "Margin calculation exceeded the 45-second SLA."
        log_response(trace_id, 504, {"detail": detail})
        raise HTTPException(status_code=504, detail=detail)
    except FileNotFoundError as exc:
        log_response(trace_id, 404, {"detail": str(exc)})
        raise HTTPException(status_code=404, detail=str(exc))

    response = MarginResponse(**result)
    log_response(trace_id, 200, response)
    return response
