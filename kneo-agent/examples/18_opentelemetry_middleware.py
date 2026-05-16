"""
Example 18 — OpenTelemetry middleware
=====================================
Wires :class:`OpenTelemetryMiddleware` into an Agent so that every run,
model call, and tool execution emits a span following the OpenTelemetry
GenAI semantic conventions.

This example uses ``ConsoleSpanExporter`` so you can see spans printed to
stdout. In a real deployment, swap it for ``OTLPSpanExporter`` to send
traces to Jaeger, Tempo, Honeycomb, Datadog, or any other OTel backend.

Install::

    pip install "kneo-agent[telemetry]" opentelemetry-sdk

Run::

    python examples/18_opentelemetry_middleware.py
"""

from __future__ import annotations

import asyncio
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from kneo_agent import AgentBuilder
from kneo_agent.observability import OpenTelemetryMiddleware
from kneo_agent.patterns import BridgeAgentFactory
from kneo_agent.utils import ToolRegistry

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)


registry = ToolRegistry()


@registry.tool(
    name="lookup_weather",
    description="Return weather details for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
def lookup_weather(args: dict) -> str:
    return json.dumps({"city": args["city"], "temp_c": 18, "condition": "cloudy"})


class MockToolCallingModel:
    def __init__(self) -> None:
        self._calls = 0

    async def ainvoke(self, messages, **kwargs):
        self._calls += 1
        if self._calls == 1:
            return type(
                "Resp",
                (),
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "tool-1", "name": "lookup_weather", "args": {"city": "Paris"}}
                    ],
                },
            )()
        return type("Resp", (), {"content": "Paris is 18 C and cloudy.", "tool_calls": []})()

    async def astream(self, messages):
        for token in ["Paris ", "is ", "18 C ", "and cloudy."]:
            yield type("Chunk", (), {"content": token})()


async def main() -> None:
    runtime = BridgeAgentFactory.for_langchain(
        MockToolCallingModel(),
        strategy="react",
        tool_registry=registry.handlers,
    )

    agent = (
        AgentBuilder()
        .with_name("OTel Demo")
        .with_system_prompt("You are a weather assistant.")
        .with_tool_registry(registry, skill_name="weather-tools")
        .add_middleware(OpenTelemetryMiddleware())
        .use_bridge(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Paris?")
    print(f"\nFinal answer: {result.final_message}")


if __name__ == "__main__":
    asyncio.run(main())
