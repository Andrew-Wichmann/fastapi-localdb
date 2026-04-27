"""OpenTelemetry setup shared by the main process and worker processes.

Main process uses a BatchSpanProcessor (background thread, efficient).
Worker processes use SimpleSpanProcessor (synchronous) to avoid the
fork+thread issue where BatchSpanProcessor threads don't survive fork.
"""

import os

from opentelemetry import _logs as otel_logs, metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor


def setup_telemetry(service_name: str, batch: bool = True, extra_resource: dict = {}) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": service_name, **extra_resource})

    tracer_provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=endpoint, insecure=True),
                export_interval_millis=15_000,
            )
        ],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
    )
    otel_logs.set_logger_provider(logger_provider)
    LoggingInstrumentor().instrument(set_logging_format=False)

    SystemMetricsInstrumentor().instrument()


def setup_worker_telemetry() -> None:
    import os
    setup_telemetry("margin-calculator-worker", batch=False, extra_resource={"process.pid": os.getpid()})
