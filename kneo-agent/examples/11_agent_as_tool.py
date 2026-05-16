"""
Example 11 — Agent As Tool
==========================
Demonstrates exposing one agent as a first-class tool for another agent.

Run::

    python examples/11_agent_as_tool.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kneo_agent import AgentBuilder, Message, RunConfig, RunResult, ToolCall
from kneo_agent.runtime.bridge import ReActAgentExecutor
from kneo_agent.utils import ToolRegistry


class WeatherAgentRuntime:
    name = "weather-agent"

    async def run(self, messages, config):
        city = messages[-1].content
        answer = f'{{"city": "{city}", "temp_c": 22, "condition": "sunny"}}'
        return RunResult(
            final_message=answer,
            messages=[*messages, Message(role="assistant", content=answer)],
            iterations=1,
            tool_calls_performed=[],
            duration_ms=1.0,
        )

    async def stream(self, messages, config):
        yield

    def supports_streaming(self):
        return False

    def supports_tools(self):
        return True


class CoordinatorImpl:
    platform_name = "coordinator-demo"

    async def complete(self, messages, config):
        if any(message.role == "tool" and message.name == "get_weather" for message in messages):
            return f"The delegated weather agent replied: {messages[-1].content}", []
        return "", [ToolCall(id="tc-1", name="get_weather", arguments={"city": "Tokyo"})]

    async def execute_tool(self, call, config):
        handler = config.extra["tool_handlers"][call.name]
        return await handler(call.arguments)

    async def stream_tokens(self, messages, config):
        yield "streaming"

    def supports_tools(self):
        return True

    def supports_streaming(self):
        return False


async def main() -> None:
    weather_agent = (
        AgentBuilder()
        .with_name("Weather Specialist")
        .with_description("Looks up structured weather results for a city.")
        .use_runtime(WeatherAgentRuntime())
        .build()
    )

    registry = ToolRegistry()
    registry.add_agent(
        weather_agent,
        name="get_weather",
        description="Delegate weather questions to the Weather Specialist agent.",
        arg_name="city",
    )

    coordinator = (
        AgentBuilder()
        .with_name("Coordinator")
        .with_tools(registry.definitions)
        .use_runtime(ReActAgentExecutor(CoordinatorImpl()))
        .build()
    )

    result = await coordinator.run(
        "What is the weather in Tokyo?",
        run_config=RunConfig(
            tools=registry.definitions,
            extra={"tool_handlers": {name: registry._tools[name][1] for name in registry.names}},
        ),
    )

    print(f"Coordinator reply: {result.final_message}")
    print(f"Tool calls: {[tool.name for tool in result.tool_calls_performed]}")


if __name__ == "__main__":
    asyncio.run(main())
