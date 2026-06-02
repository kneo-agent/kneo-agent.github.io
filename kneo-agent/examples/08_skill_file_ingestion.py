"""
Example 08 — standardized skill file ingestion
==============================================
Loads a skill from an Agent Skills-compatible ``SKILL.md`` directory,
binds local tool handlers, and runs the agent through the SDK's normal
skill pipeline.

Run::

    python examples/08_skill_file_ingestion.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kneo_agent import AgentBuilder, discover_skills, load_skill
from kneo_agent.patterns import BridgeAgentFactory
from kneo_agent.utils import ToolRegistry

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
    return json.dumps({"city": args["city"], "temp_c": 22, "condition": "sunny"})


class MockChatModel:
    async def ainvoke(self, messages, **kwargs):
        class _Resp:
            content = "The standardized weather skill says it is 22 °C and sunny in Tokyo."
            tool_calls: list = []
        return _Resp()

    async def astream(self, messages):
        for chunk in ["The ", "standardized ", "weather ", "skill ", "works."]:
            yield type("C", (), {"content": chunk})()


async def main() -> None:
    skills_root = Path(__file__).with_name("skills")
    catalog = discover_skills([skills_root])
    skill_path = skills_root / "weather"
    file_skill = load_skill(skill_path)
    bound_skill = file_skill.with_tool_handlers(registry.handlers)

    runtime = BridgeAgentFactory.for_langchain(MockChatModel(), strategy="react")
    agent = (
        AgentBuilder()
        .with_name("Skill File Demo")
        .with_description("Loads a standardized skill definition from disk.")
        .with_skills([bound_skill])
        .use_bridge(runtime)
        .build()
    )

    result = await agent.run("What is the weather in Tokyo?")
    print("Catalog:")
    for entry in catalog:
        print(f"  - {entry.name}: {entry.description}")
    print(f"Loaded skill: {file_skill.name!r}")
    print(f"Source path:   {file_skill.source_path}")
    print(f"Runtime:      {agent.runtime_name}")
    print(f"Answer:       {result.final_message}")
    print(f"Tags:         {bound_skill.tags}")
    print(f"Tools:        {[tool.name for tool in bound_skill.tools]}")
    print(f"Resources:    {bound_skill.resource_paths()}")
    print("\nActivation prompt preview:\n")
    print(bound_skill.activation_prompt())


if __name__ == "__main__":
    asyncio.run(main())
