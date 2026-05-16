"""
Example 03 — Bridge pattern with LangChain
===========================================
Uses LangChainImpl as the RuntimeImpl with a mock BaseChatModel.
Demonstrates a skill-backed agent and the React strategy.

Run::

    python examples/03_bridge_langchain.py
"""

import asyncio
import json

from kneo_agent import AgentBuilder
from kneo_agent.patterns import BridgeAgentFactory
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
    return json.dumps({"city": args["city"], "temp_c": 19, "condition": "cloudy"})


# ── Mock LangChain BaseChatModel ──────────────────────────────

class MockChatModel:
    async def ainvoke(self, messages, **kwargs):
        class _Resp:
            content = "LangChain: it is 19 °C and cloudy in Paris."
            tool_calls: list = []
        return _Resp()

    async def astream(self, messages):
        for word in ["LangChain: ", "19 °C, ", "cloudy ", "in Paris."]:
            yield type("C", (), {"content": word})()


async def main() -> None:
    weather_skill = registry.to_skill(
        "weather",
        system_prompt="You are a weather assistant.",
        defaults={"max_iterations": 5},
    )

    runtime = BridgeAgentFactory.for_langchain(
        MockChatModel(),
        strategy="react",
    )
    agent = (
        AgentBuilder()
        .with_name("LangChain Weather Agent")
        .with_skills([weather_skill])
        .use_bridge(runtime)
        .build()
    )

    # Standard run
    result = await agent.run("What is the weather in Paris?")
    print(f"Runtime:     {agent.runtime_name}")
    print(f"Answer:      {result.final_message}")
    print(f"Iterations:  {result.iterations}")

    # Streaming run
    agent.clear_history()
    print("\nStreaming:")
    async for chunk in await agent.stream("Paris weather?"):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "done":
            print()


if __name__ == "__main__":
    asyncio.run(main())
