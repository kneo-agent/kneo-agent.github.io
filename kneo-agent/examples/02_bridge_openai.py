"""
Example 02 — OpenAI Agents SDK (native runtime)
========================================
Shows the OpenAI Agents SDK-backed runtime executing a tool call and
returning a final answer. Uses a mock runner to avoid network access.
Demonstrates skill-based tool wiring via ``ToolRegistry.to_skill()``.

Note: OpenAI is a **native** provider — the OpenAI Agents SDK owns its own
runtime, so there is no distinct "bridge" implementation. Use
``NativeRuntimeFactory.for_openai(...)`` (the canonical entry point); the
``BridgeAgentFactory.for_openai`` alias just forwards here and emits an
advisory ``UserWarning``.

Run::

    python examples/02_bridge_openai.py
"""

import asyncio
import json
from types import SimpleNamespace

from kneo_agent import AgentBuilder
from kneo_agent.patterns import NativeRuntimeFactory
from kneo_agent.utils import ToolRegistry

# ── Tool registry ─────────────────────────────────────────────

registry = ToolRegistry()


@registry.tool(
    name="get_weather",
    description="Return current weather for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
def get_weather(args: dict) -> str:
    return json.dumps({"city": args["city"], "temp_c": 22, "condition": "sunny"})


class MockOpenAIRunner:
    async def run(self, starting_agent, input, max_turns=10):
        return SimpleNamespace(
            final_output="It is 22 °C and sunny in Tokyo.",
            new_items=[
                SimpleNamespace(
                    type="tool_call_item",
                    raw_item=SimpleNamespace(
                        call_id="tc-1",
                        name="get_weather",
                        arguments='{"city": "Tokyo"}',
                    ),
                ),
                SimpleNamespace(
                    type="tool_call_output_item",
                    raw_item=SimpleNamespace(call_id="tc-1"),
                    output='{"city": "Tokyo", "temp_c": 22, "condition": "sunny"}',
                ),
            ],
            raw_responses=[object(), object()],
        )


async def main() -> None:
    weather_skill = registry.to_skill(
        "weather",
        system_prompt="You are a weather assistant. Use the get_weather tool.",
        defaults={"max_iterations": 5},
        tags=["domain:weather"],
    )

    runtime = NativeRuntimeFactory.for_openai(
        model="gpt-4o", strategy="react", runner=MockOpenAIRunner()
    )
    agent = (
        AgentBuilder()
        .with_name("OpenAI Weather Agent")
        .with_skills([weather_skill])
        .use_runtime(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Tokyo?")
    print(f"Runtime:     {agent.runtime_name}")
    print(f"Answer:      {result.final_message}")
    print(f"Iterations:  {result.iterations}")
    print(f"Tools called:{[r.name for r in result.tool_calls_performed]}")
    print(f"Duration:    {result.duration_ms:.1f} ms")


if __name__ == "__main__":
    asyncio.run(main())
