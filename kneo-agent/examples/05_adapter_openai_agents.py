"""
Example 05 — Adapter pattern with OpenAI Agents SDK
=====================================================
Wraps an existing ``openai-agents`` Runner.  The SDK manages its own
multi-turn loop; the Adapter just translates the interface.

The adapter builds a **real** ``agents.Agent`` from the ``agent_definition``
plus the run's tools (and ``RunConfig.extra["tool_handlers"]``), passes it as
``Runner.run(starting_agent=…)``, and reads tool-call metadata from
``item.raw_item`` — the shape the live SDK produces. Requires the ``[openai]``
extra (``pip install 'kneo-agent[openai]'``). The ``ExistingOAIRunner`` below
stands in for a real ``Runner`` so the example runs offline; its items use the
real ``raw_item`` nesting.

Run::

    python examples/05_adapter_openai_agents.py
"""

import asyncio
from types import SimpleNamespace

from kneo_agent import AgentBuilder
from kneo_agent.patterns import AdapterAgentFactory


class ExistingOAIRunner:
    """
    Represents a pre-existing openai-agents ``Runner``.
    Its interface mirrors the real SDK: ``Runner.run(starting_agent=...)`` and
    ``Runner.run_streamed(...)`` whose ``.stream_events()`` yields events. Run
    items nest their metadata under ``raw_item`` like the real SDK.
    """

    async def run(self, *, starting_agent, input: str, max_turns: int = 10):
        return SimpleNamespace(
            final_output=f"OpenAI Agents SDK answered: '{input[:30]}...' → 22 °C in Tokyo.",
            new_items=[
                SimpleNamespace(
                    type="tool_call_item",
                    raw_item=SimpleNamespace(call_id="c-1", name="get_weather", arguments="{}"),
                ),
                SimpleNamespace(
                    type="tool_call_output_item",
                    output='{"temp": 22, "condition": "sunny"}',
                    raw_item=SimpleNamespace(call_id="c-1"),
                ),
                SimpleNamespace(type="message_output_item"),
            ],
            # The real Runner result carries per-response usage; the adapter
            # aggregates raw_responses[*].usage into metadata["usage"].
            raw_responses=[SimpleNamespace(usage=SimpleNamespace(input_tokens=42, output_tokens=18))],
        )

    def run_streamed(self, *, starting_agent, input: str, max_turns: int = 10):
        class _Streamed:
            async def stream_events(self_inner):
                for token in ["OpenAI ", "Agents ", "stream ", "reply."]:
                    yield SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(type="response.output_text.delta", delta=token),
                    )

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
