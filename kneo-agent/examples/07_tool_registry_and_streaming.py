"""
Example 07 — ToolRegistry decorator + streaming
================================================
Demonstrates the @registry.tool decorator, async tool handlers,
skill packaging via ``ToolRegistry.to_skill()``, streaming with
chunk-type introspection, and multi-turn conversation.

Run::

    python examples/07_tool_registry_and_streaming.py
"""

import asyncio
import json

from kneo_agent import AgentBuilder
from kneo_agent.patterns import BridgeAgentFactory
from kneo_agent.utils import ToolRegistry, configure_logging

# Enable INFO logging to see agent internals
configure_logging("INFO")

# ── Build a registry with sync and async tool handlers ────────

registry = ToolRegistry()


@registry.tool(
    name="get_weather",
    description="Return the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name"}},
        "required": ["city"],
    },
)
def get_weather(args: dict) -> str:
    """Synchronous tool handler."""
    db = {"Tokyo": (22, "sunny"), "Paris": (15, "cloudy"), "London": (10, "rainy")}
    temp, cond = db.get(args["city"], (20, "unknown"))
    return json.dumps({"city": args["city"], "temp_c": temp, "condition": cond})


@registry.tool(
    name="get_time",
    description="Return the current UTC time.",
    parameters={"type": "object", "properties": {}, "required": []},
)
async def get_time(args: dict) -> str:
    """Async tool handler — both are supported."""
    import datetime
    return json.dumps({"utc": datetime.datetime.utcnow().isoformat() + "Z"})


print(f"Registry has {len(registry)} tools: {registry.names}\n")

# ── Mock streaming model ──────────────────────────────────────

class MockStreamingModel:
    async def ainvoke(self, messages, **kwargs):
        class _R:
            content = "The weather is great! (mock)"
            tool_calls: list = []
        return _R()

    async def astream(self, messages):
        words = ["Kneo ", "Agent ", "streaming ", "response ", "— ", "done!"]
        for w in words:
            yield type("C", (), {"content": w})()


async def main() -> None:
    assistant_skill = registry.to_skill(
        "assistant-tools",
        system_prompt="You are a helpful assistant with weather and time tools.",
        defaults={"max_iterations": 5},
        tags=["demo", "streaming"],
    )

    runtime = BridgeAgentFactory.for_langchain(
        MockStreamingModel(),
        strategy="react",
    )

    agent = (
        AgentBuilder()
        .with_name("Tool + Stream Demo")
        .with_description("Demonstrates registry and streaming.")
        .with_version("1.0.0")
        .with_tags("demo", "streaming")
        .with_skills([assistant_skill])
        .use_bridge(runtime)
        .build()
    )

    print(f"Agent: {agent.agent_name!r}  runtime: {agent.runtime_name}\n")

    # ── Standard run ──────────────────────────────────────────
    result = await agent.run("What is the weather in Tokyo?")
    print(f"[run]  {result.final_message}")
    print(f"       {result.iterations} iteration(s), {result.duration_ms:.1f} ms\n")

    # ── Streaming run ─────────────────────────────────────────
    agent.clear_history()
    print("[stream] ", end="", flush=True)
    async for chunk in await agent.stream("Tell me something."):
        match chunk.type:
            case "text":
                print(chunk.content, end="", flush=True)
            case "tool_call":
                print(f"\n  → calling {chunk.tool_call.name}", end="")
            case "tool_result":
                print(f"\n  ← {chunk.tool_result.name}: {chunk.tool_result.result[:40]}", end="")
            case "done":
                print()

    # ── Multi-turn via chat() ─────────────────────────────────
    agent.clear_history()
    print("\n[multi-turn]")
    for msg in ["Hello!", "What tools do you have?", "Thanks, bye!"]:
        reply = await agent.chat(msg)
        print(f"  User: {msg!r}")
        print(f"  Agent: {reply!r}\n")

    print(f"History length: {len(agent.history)} messages")

    # ── ToolRegistry dispatch directly ────────────────────────
    from kneo_agent import ToolCall
    tc = ToolCall(id="x", name="get_weather", arguments={"city": "London"})
    direct = await registry.call(tc)
    print(f"\nDirect tool call result: {direct}")


if __name__ == "__main__":
    asyncio.run(main())
