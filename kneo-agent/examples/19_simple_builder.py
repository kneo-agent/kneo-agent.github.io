"""
Example 19 — Simple builder
===========================
The shortest path from "I want an agent" to a working ``Agent``.

Two convenience paths from ``kneo_agent.simple`` (re-exported at the
package root):

- ``build_sync_agent`` — returns a blocking wrapper that hides
  ``asyncio`` entirely. Best for scripts and prototypes.
- ``build_agent`` — returns the regular async :class:`Agent`. Use when
  you're already writing async code.

Both accept the same arguments. Drop down to :class:`AgentBuilder` and
the explicit factories from :mod:`kneo_agent.patterns` when you need
fine-grained control.

This example uses a mock LangChain chat model so it runs without real
API keys, the same pattern the other example scripts use.

Run::

    python examples/19_simple_builder.py
"""

import json

from kneo_agent import build_sync_agent
from kneo_agent.utils import ToolRegistry

# ── 1. (Optional) Define some tools ─────────────────────────────

registry = ToolRegistry()


@registry.tool(
    name="lookup_weather",
    description="Return the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
def lookup_weather(args: dict) -> str:
    return json.dumps({"city": args["city"], "temp_c": 18, "condition": "cloudy"})


# ── 2. A toy chat model so the example runs offline ─────────────

class _MockChatModel:
    async def ainvoke(self, messages, **kwargs):
        return type("R", (), {"content": "It is 18 °C and cloudy in Paris.", "tool_calls": []})()

    async def astream(self, messages):
        for token in ["It ", "is ", "18 °C ", "and cloudy."]:
            yield type("C", (), {"content": token})()


# ── 3. One call returns a sync agent — no asyncio at the call site ──

agent = build_sync_agent(
    "langchain",
    chat_model=_MockChatModel(),
    name="Weather Bot",
    system_prompt="You are a concise weather assistant.",
    tools=registry,
)

# Plain blocking calls. No `async def main()` / `asyncio.run(...)` ceremony.
result = agent.run("What is the weather in Paris?")
print(f"Runtime:   {agent.runtime_name}")
print(f"Answer:    {result.final_message}")
print(f"Tools:     {[t.name for t in agent.config.tools]}")

# ── For comparison: the async path ─────────────────────────────────
#
#     import asyncio
#     from kneo_agent import build_agent
#
#     async def main():
#         agent = build_agent("langchain", chat_model=_MockChatModel(), tools=registry)
#         result = await agent.run("What is the weather in Paris?")
#         print(result.final_message)
#
#     asyncio.run(main())
#
# ── And the fully explicit version ─────────────────────────────────
#
#     from kneo_agent import AgentBuilder
#     from kneo_agent.patterns import BridgeAgentFactory
#
#     runtime = BridgeAgentFactory.for_langchain(
#         _MockChatModel(),
#         tool_registry=registry.handlers,
#         strategy="react",
#     )
#     agent = (
#         AgentBuilder()
#         .with_name("Weather Bot")
#         .with_system_prompt("You are a concise weather assistant.")
#         .with_tool_registry(registry)
#         .use_runtime(runtime)
#         .build()
#     )
