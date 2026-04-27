"""Structlog configuration and trace-ID middleware.

Sets up JSON-structured logging with stdlib routing so that uvicorn and
FastAPI log records are also rendered as JSON through the same pipeline.

TraceContextMiddleware must be added AFTER FastAPIInstrumentor.instrument_app
so that the OTel span is already active when it runs.
"""

import logging
import sys
import time

import structlog
from opentelemetry import trace

import re

_ACCESS_RE = re.compile(
    r'^(?P<client>\S+) - "(?P<method>\w+) (?P<path>\S+) HTTP/(?P<http_version>[\d.]+)" (?P<status_code>\d+)$'
)


def _parse_uvicorn_access(logger, method, event_dict: dict) -> dict:
    """Parse uvicorn.access log lines into structured fields.

    structlog consumes record.args before the pre-chain runs, so we regex
    the already-formatted event string instead.
    """
    record = event_dict.get("_record")
    if record and record.name == "uvicorn.access":
        m = _ACCESS_RE.match(event_dict.get("event", ""))
        if m:
            event_dict["event"] = "http.access"
            event_dict["client"] = m.group("client")
            event_dict["method"] = m.group("method")
            event_dict["path"] = m.group("path")
            event_dict["http_version"] = m.group("http_version")
            event_dict["status_code"] = int(m.group("status_code"))
    return event_dict


_shared_processors: list = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
]


def setup_logging() -> None:
    structlog.configure(
        processors=_shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[_parse_uvicorn_access] + _shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Uvicorn installs its own handlers on these loggers before our app loads.
    # Clear them so records propagate up to the root handler above.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True


class TraceContextMiddleware:
    """Bind the active OTel trace_id to structlog contextvars for each request."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            structlog.contextvars.bind_contextvars(trace_id=format(ctx.trace_id, "032x"))

        start = time.perf_counter()

        async def send_with_duration(message) -> None:
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                structlog.get_logger().info(
                    "http.response",
                    duration_ms=round((time.perf_counter() - start) * 1000, 2),
                )
            await send(message)

        await self.app(scope, receive, send_with_duration)
