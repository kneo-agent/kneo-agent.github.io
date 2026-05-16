"""
Example 16 — Agent middleware for logging and tool interception
===============================================================
Demonstrates class-based middleware that observes and modifies:

- full agent runs
- model calls inside the Bridge executor loop
- tool execution

Run::

    python examples/16_agent_middleware_logging.py
"""

from __future__ import annotations

import asyncio
import json

from kneo_agent import (
    AgentBuilder,
    BaseAgentMiddleware,
    ModelCallContext,
    ToolCallContext,
)
from kneo_agent.patterns import BridgeAgentFactory
from kneo_agent.utils import ToolRegistry

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
    city = args["city"]
    return json.dumps({"city": city, "temp_c": 18, "condition": "cloudy"})


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

        return type(
            "Resp",
            (),
            {
                "content": "Paris is 18 C and cloudy.",
                "tool_calls": [],
            },
        )()

    async def astream(self, messages):
        for token in ["Paris ", "is ", "18 C ", "and cloudy."]:
            yield type("Chunk", (), {"content": token})()


class ObservabilityMiddleware(BaseAgentMiddleware):
    async def wrap_run(self, context, handler):
        print(f"[run:start] agent={context.agent_name} runtime={context.runtime_name}")
        result = await handler(context)
        result.metadata["observed_by"] = "ObservabilityMiddleware"
        print(f"[run:end] final={result.final_message!r}")
        return result

    async def wrap_model_call(self, context: ModelCallContext, handler):
        print(
            f"[model] iteration={context.iteration} "
            f"messages={len(context.messages)}"
        )
        response = await handler(context)
        if response.tool_calls:
            print(f"[model] tool requests={[call.name for call in response.tool_calls]}")
        else:
            response.text = response.text + " Logged by middleware."
        return response

    async def wrap_tool_call(self, context: ToolCallContext, handler):
        print(
            f"[tool] name={context.tool_call.name} "
            f"args={context.tool_call.arguments}"
        )
        result = await handler(context)
        payload = json.loads(result.result)
        payload["source"] = "middleware"
        result.result = json.dumps(payload)
        return result


async def main() -> None:
    runtime = BridgeAgentFactory.for_langchain(
        MockToolCallingModel(),
        strategy="react",
        tool_registry=registry.handlers,
    )

    agent = (
        AgentBuilder()
        .with_name("Middleware Demo")
        .with_system_prompt("You are a weather assistant.")
        .with_tool_registry(registry, skill_name="weather-tools")
        .add_middleware(ObservabilityMiddleware())
        .use_bridge(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Paris?")
    print(f"\nFinal answer: {result.final_message}")
    print(f"Tool result:  {result.tool_calls_performed[0].result}")
    print(f"Metadata:     {result.metadata}")


if __name__ == "__main__":
    asyncio.run(main())
