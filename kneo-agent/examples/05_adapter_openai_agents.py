"""
Example 05 — Adapter pattern with OpenAI Agents SDK
=====================================================
Wraps an existing @openai/agents Runner.  The SDK manages its own
multi-turn loop; the Adapter just translates the interface.

Run::

    python examples/05_adapter_openai_agents.py
"""

import asyncio

from kneo_agent import AgentBuilder
from kneo_agent.patterns import AdapterAgentFactory


class ExistingOAIRunner:
    """
    Represents a pre-existing openai-agents ``Runner``.
    Its interface mirrors the real SDK: ``Runner.run(starting_agent=...)`` and
    ``Runner.run_streamed(...)`` whose ``.stream_events()`` yields events.
    """

    async def run(self, *, starting_agent: dict, input: str, max_turns: int = 10) -> dict:
        return {
            "final_output": f"OpenAI Agents SDK answered: '{input[:30]}...' → 22 °C in Tokyo.",
            "new_items": [
                {"type": "tool_call_output_item", "call_id": "c-1", "tool_name": "get_weather"},
                {"type": "message_output_item"},
            ],
            # The real Runner result carries per-response usage; the adapter
            # aggregates raw_responses[*].usage into metadata["usage"].
            "raw_responses": [
                {"usage": {"input_tokens": 42, "output_tokens": 18}},
            ],
        }

    def run_streamed(self, *, starting_agent: dict, input: str, max_turns: int = 10):
        class _Streamed:
            async def stream_events(self_inner):
                for token in ["OpenAI ", "Agents ", "stream ", "reply."]:
                    yield {"type": "raw_response_event", "delta": token}

        return _Streamed()


async def main() -> None:
    existing_runner = ExistingOAIRunner()

    runtime = AdapterAgentFactory.for_openai(
        existing_runner,
        agent_definition={
            "name": "WeatherAgent",
            "instructions": "You are a helpful weather assistant.",
        },
    )
    agent = (
        AgentBuilder()
        .with_name("OAI Agents Adapter")
        .use_adapter(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Tokyo?")
    print(f"Runtime:       {agent.runtime_name}")
    print(f"Answer:        {result.final_message}")
    print(f"Tool events:   {len(result.tool_calls_performed)}")
    # Every built-in runtime (incl. this Adapter) reports token usage when the
    # provider does — read it from RunResult.metadata["usage"].
    print(f"Usage:         {result.metadata.get('usage')}")

    # Streaming
    agent.clear_history()
    print("\nStreaming:")
    async for chunk in await agent.stream("Tokyo weather?"):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "done":
            print()


if __name__ == "__main__":
    asyncio.run(main())
