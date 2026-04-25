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

from opentelemetry import propagate
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from database import init_db, partition_path
from telemetry import setup_telemetry, setup_worker_telemetry
from worker import compute_margin

# Must run before app creation so FastAPIInstrumentor sees the real provider
# and the middleware stack is instrumented before it is frozen.
setup_telemetry("margin-calculator")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class Position(BaseModel):
    id: str
    quantity: float


class MarginRequest(BaseModel):
    cob_date: str
    positions: list[Position]

    @field_validator("cob_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        from datetime import date

        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("cob_date must be in YYYY-MM-DD format")
        return v


class MarginResponse(BaseModel):
    total_margin: float
    cob_date: str


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
    yield
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


@app.post("/margin", response_model=MarginResponse)
async def calculate_margin(request: MarginRequest) -> MarginResponse:
    """Compute total margin for all positions using a ProcessPool."""
    if not request.positions:
        return MarginResponse(total_margin=0.0, cob_date=request.cob_date)

    loop = asyncio.get_running_loop()

    # Serialize positions to plain dicts — Pydantic models aren't picklable
    # across process boundaries.
    positions = [pos.model_dump() for pos in request.positions]

    # Inject current trace context so the worker can parent its spans correctly.
    carrier: dict = {}
    propagate.inject(carrier)

    try:
        # SLA: 45 seconds total.
        result: dict = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                compute_margin,
                request.cob_date,
                positions,
                carrier,
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Margin calculation exceeded the 45-second SLA.",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MarginResponse(**result)
