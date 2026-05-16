"""
Example 04 — Adapter pattern with Google ADK
=============================================
Wraps an existing ADK runner that already manages its own agentic loop.
The Adapter translates its event-stream interface to AgentRuntime.

Run::

    python examples/04_adapter_google_adk.py
"""

import asyncio

from kneo_agent import AgentBuilder
from kneo_agent.patterns import AdapterAgentFactory


class ExistingADKRunner:
    """
    Represents a pre-existing google.adk runner your app already has.
    Its run_async interface cannot be changed — the Adapter wraps it.
    """

    async def run_async(self, app_name, user_id, session_id, new_message):
        # ADK yields typed Event objects; we simulate text + function call events
        yield {
            "author": "weather-agent",
            "content": {
                "parts": [
                    {"functionCall": {"id": "fc-1", "name": "get_weather", "args": {"city": "Tokyo"}}},
                ]
            },
        }
        yield {
            "author": "weather-agent",
            "content": {
                "parts": [{"text": "ADK handled everything: Tokyo is 22 °C."}]
            },
        }


async def main() -> None:
    # The runner already exists — we cannot change its interface
    existing_runner = ExistingADKRunner()

    # Adapter wraps it; no strategy choice — ADK owns the loop
    runtime = AdapterAgentFactory.for_google_adk(
        existing_runner,
        app_name="weather-app",
        user_id="demo-user",
        session_id="session-42",
    )

    agent = (
        AgentBuilder()
        .with_name("ADK Adapter Agent")
        .use_adapter(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Tokyo?")
    print(f"Runtime:       {agent.runtime_name}")
    print(f"Answer:        {result.final_message}")
    print(f"Tool events:   {len(result.tool_calls_performed)}")

    # Streaming
    agent.clear_history()
    print("\nStreaming:")
    async for chunk in await agent.stream("Tokyo weather?"):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "tool_call":
            print(f"\n[tool_call → {chunk.tool_call.name}]")
        elif chunk.type == "done":
            print()

    print("\n✓ Adapter: zero changes to ExistingADKRunner.")


if __name__ == "__main__":
    asyncio.run(main())
