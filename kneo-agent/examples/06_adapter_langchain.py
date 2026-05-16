"""
Example 06 — Adapter pattern with LangChain AgentExecutor
==========================================================
Wraps an existing LangChain AgentExecutor (or CompiledGraph).
The Adapter translates the (input, chat_history) interface to AgentRuntime.

Run::

    python examples/06_adapter_langchain.py
"""

import asyncio

from kneo_agent import AgentBuilder
from kneo_agent.patterns import AdapterAgentFactory


class ExistingLCExecutor:
    """
    Represents a fully assembled LangChain AgentExecutor your app
    already has.  Its ainvoke / astream interface cannot be changed.
    """

    async def ainvoke(self, input_dict: dict, config: dict | None = None) -> dict:
        user_input = input_dict.get("input", "")
        history = input_dict.get("chat_history", [])
        return {
            "output": f"LangChain answered: {user_input!r} (history turns: {len(history)})",
            "intermediate_steps": [
                {
                    "action": {
                        "tool": "get_weather",
                        "toolInput": {"city": "Tokyo"},
                        "log": "Calling get_weather",
                    },
                    "observation": '{"temp": 22, "condition": "sunny"}',
                }
            ],
        }

    async def astream(self, input_dict: dict):
        yield {"steps": [{"action": {"tool": "get_weather"}, "observation": '{"temp":22}'}]}
        yield {"output": "LangChain stream: 22 °C in Tokyo."}


async def main() -> None:
    existing_executor = ExistingLCExecutor()

    runtime = AdapterAgentFactory.for_langchain(existing_executor)
    agent = (
        AgentBuilder()
        .with_name("LC Adapter Agent")
        .use_adapter(runtime)
        .build()
    )

    # Single turn
    result = await agent.run("What is the weather in Tokyo?")
    print(f"Runtime:       {agent.runtime_name}")
    print(f"Answer:        {result.final_message}")
    print(f"Iterations:    {result.iterations}")
    print(f"Tool calls:    {[r.name for r in result.tool_calls_performed]}")

    # Multi-turn: the Adapter correctly maps history to chat_history tuples
    result2 = await agent.run("And what about Paris?")
    print(f"\nFollow-up:     {result2.final_message}")
    print(f"History turns: {len(agent.history)}")

    # Streaming
    agent.clear_history()
    print("\nStreaming:")
    async for chunk in await agent.stream("Tokyo weather?"):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "tool_result":
            print(f"\n[tool_result ← {chunk.tool_result.name}]")
        elif chunk.type == "done":
            print()

    print("\n✓ Adapter: zero changes to ExistingLCExecutor.")


if __name__ == "__main__":
    asyncio.run(main())
