"""
Cookbook — Export agent traces to an OTLP collector
====================================================
A runnable companion to ``docs/user/self_hosted_observability.md``. It
wires ``OpenTelemetryMiddleware`` to an **OTLP exporter** pointed at a
collector (OpenTelemetry Collector / Jaeger / Grafana Tempo / SigNoz —
they all speak OTLP), runs one agent turn, and flushes the span.

kneo-agent emits the spans; shipping them is your deployment's job, so
the exporter is **not** bundled. Install it alongside the telemetry extra::

    pip install "kneo-agent[telemetry]" opentelemetry-sdk opentelemetry-exporter-otlp

Point it at your collector via the standard OTel env var (defaults to a
local collector's OTLP/HTTP port)::

    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

Run a collector first (e.g. ``docker run -p 4318:4318 otel/opentelemetry-collector``),
then::

    python examples/cookbook/otlp_collector_export.py

This recipe degrades gracefully: with no telemetry extra / exporter
installed it prints what to install and exits cleanly, so it stays in the
runnable example set. A real model is *not* required — a tiny offline
runtime stands in so the span is produced and exported without a live LLM.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from kneo_agent import AgentBuilder, RunConfig, RunResult


class _DemoRuntime:
    """Minimal offline runtime so a span is produced without a live model.
    In your app this is a real Bridge/Native/Adapter runtime."""

    name = "openai-agents"

    async def run(self, messages: list[Any], config: RunConfig) -> RunResult:
        return RunResult(
            final_message="The answer is 4.",
            messages=[],
            iterations=1,
            tool_calls_performed=[],
            duration_ms=12.0,
            metadata={"usage": {"input_tokens": 18, "output_tokens": 6}},
        )

    async def stream(self, messages: list[Any], config: RunConfig) -> Any:
        if False:  # pragma: no cover - never streamed in this recipe
            yield

    def supports_streaming(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return True


def main() -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print(
            "This recipe needs the telemetry extra and the OTel SDK:\n"
            "  pip install 'kneo-agent[telemetry]' opentelemetry-sdk"
        )
        return

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError:
        print(
            "Install an OTLP exporter to ship spans to a collector:\n"
            "  pip install opentelemetry-exporter-otlp"
        )
        return

    from kneo_agent.observability import OpenTelemetryMiddleware

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    # OTLP/HTTP wants the signal-specific path; the gRPC exporter would take
    # the bare endpoint instead.
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")

    provider = TracerProvider(resource=Resource.create({"service.name": "kneo-agent-demo"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # The middleware picks up the global tracer provider set above.
    agent = (
        AgentBuilder()
        .with_name("Traced Agent")
        .with_middlewares([OpenTelemetryMiddleware(record_arguments=True)])
        .use_runtime(_DemoRuntime())
        .build()
    )

    result = asyncio.run(agent.run("What is 2 + 2?"))
    print("Answer        :", result.final_message)
    print("Exporting to  :", f"{endpoint.rstrip('/')}/v1/traces")

    # Flush: BatchSpanProcessor exports asynchronously, so force it before exit.
    # A failed export (no collector listening) is logged by OTel, not raised —
    # the script still exits cleanly.
    provider.shutdown()
    print("Span flushed (check your collector / Jaeger / Tempo / SigNoz UI).")


if __name__ == "__main__":
    main()
