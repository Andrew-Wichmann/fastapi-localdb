"""OpenTelemetry setup shared by the main process and worker processes.

Main process uses a BatchSpanProcessor (background thread, efficient).
Worker processes use SimpleSpanProcessor (synchronous) to avoid the
fork+thread issue where BatchSpanProcessor threads don't survive fork.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor


def setup_telemetry(service_name: str, batch: bool = True) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


def setup_worker_telemetry() -> None:
    setup_telemetry("margin-calculator-worker", batch=False)
