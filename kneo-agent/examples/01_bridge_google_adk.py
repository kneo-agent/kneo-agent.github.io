"""
Example 01 — Bridge pattern with Google ADK
============================================
Demonstrates how to use three different loop strategies (simple, react,
plan-act) against a single Google ADK runner object.

Note: ``BridgeAgentFactory.for_google_adk`` is a Kneo compatibility bridge
over ADK-shaped payloads (Kneo owns the loop). It emits an advisory
``UserWarning`` on purpose — the bridge is fully supported, but if you want
Google ADK to own the loop natively, prefer ``AdapterAgentFactory.for_google_adk``
(see example 04). This example deliberately demonstrates the Bridge path.

Run::

    python examples/01_bridge_google_adk.py
"""

import asyncio

from kneo_agent import AgentBuilder, ToolDefinition
from kneo_agent.patterns import BridgeAgentFactory

WEATHER_TOOL = ToolDefinition(
    name="get_weather",
    description="Return current weather for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)


class MockADKRunner:
    """Stand-in for google.adk.runners.InMemoryRunner."""

    async def run(self, session_id: str, payload: dict) -> dict:
        return {
            "candidates": [{
                "content": {
                    "parts": [{"text": "The weather in Tokyo is 22 °C and sunny."}]
                }
            }]
        }


async def main() -> None:
    runner = MockADKRunner()

    # ── Simple strategy: one-shot, no loop ────────────────────
    simple_runtime = BridgeAgentFactory.for_google_adk(runner, "s-001", strategy="simple")
    agent = (
        AgentBuilder()
        .with_name("ADK Simple Agent")
        .with_system_prompt("You are a helpful weather assistant.")
        .with_tools([WEATHER_TOOL])
        .use_bridge(simple_runtime)
        .build()
    )
    result = await agent.run("What is the weather in Tokyo?")
    print(f"[{agent.runtime_name}]  {result.final_message}")

    # ── ReAct strategy: reason → act → observe loop ───────────
    react_runtime = BridgeAgentFactory.for_google_adk(runner, "s-002", strategy="react")
    agent2 = (
        AgentBuilder()
        .with_name("ADK ReAct Agent")
        .with_tools([WEATHER_TOOL])
        .use_bridge(react_runtime)
        .build()
    )
    result2 = await agent2.run("What is the weather in Tokyo?")
    print(f"[{agent2.runtime_name}]  {result2.final_message}")

    # ── Plan-Act strategy: plan first, then execute ───────────
    plan_runtime = BridgeAgentFactory.for_google_adk(runner, "s-003", strategy="plan-act")
    agent3 = (
        AgentBuilder()
        .with_name("ADK PlanAct Agent")
        .with_tools([WEATHER_TOOL])
        .use_bridge(plan_runtime)
        .build()
    )
    result3 = await agent3.run("What is the weather in Tokyo?")
    print(f"[{agent3.runtime_name}]  {result3.final_message}")
    if result3.metadata.get("plan"):
        print(f"  Plan used: {result3.metadata['plan'][:60]}…")

    # KEY INSIGHT: changing strategy requires ZERO changes to MockADKRunner.
    # Changing the runner requires ZERO changes to the loop strategies.
    print("\n✓ All three strategies ran against the same ADK runner.")


if __name__ == "__main__":
    asyncio.run(main())
