"""
Example 10 — Workflow Orchestrations
====================================
Demonstrates the built-in workflow orchestration builders. Shows:

- how the built-in orchestration runtimes share one orchestration family
- concurrent fan-out orchestration
- selector-driven handoff orchestration
- round-robin group chat orchestration

Run::

    python examples/10_workflow_orchestrations.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kneo_agent import AgentBuilder, Message, RunConfig, RunResult
from kneo_agent.workflows import (
    ConcurrentBuilder,
    GroupChatBuilder,
    HandoffBuilder,
)


class MockRuntime:
    """Simple runtime that derives a reply from the current conversation."""

    def __init__(self, name: str, handler):
        self.name = name
        self._handler = handler

    async def run(self, messages, config):
        reply = self._handler(messages, config)
        return RunResult(
            final_message=reply,
            messages=[*messages, Message(role="assistant", content=reply, name=self.name)],
            iterations=1,
            tool_calls_performed=[],
            duration_ms=1.0,
        )

    async def stream(self, messages, config):
        if False:
            yield None

    def supports_streaming(self):
        return False

    def supports_tools(self):
        return True


def make_agent(name: str, handler):
    return AgentBuilder().with_name(name).use_runtime(MockRuntime(name, handler)).build()


async def main() -> None:
    alpha = make_agent("alpha", lambda messages, config: f"Alpha sees: {messages[-1].content}")
    beta = make_agent("beta", lambda messages, config: f"Beta sees: {messages[-1].content}")
    triage = make_agent(
        "triage",
        lambda messages, config: "Route urgent requests to beta." if "urgent" in messages[0].content.lower() else "Route general requests to alpha.",
    )

    concurrent = ConcurrentBuilder(
        [alpha, beta],
        name="fanout-workflow",
        description="Runs both specialists in parallel against the same snapshot.",
    ).build()
    concurrent_result = await concurrent.run(
        [Message(role="user", content="Summarize the workflow feature launch.")],
        RunConfig(),
    )

    handoff_selector_calls = iter(["alpha", "beta", None])
    handoff = HandoffBuilder(
        [alpha, beta],
        lambda messages, config, index: next(handoff_selector_calls),
        name="handoff-workflow",
        description="Transfers control between specialists dynamically.",
    ).build()
    handoff_result = await handoff.run(
        [Message(role="user", content="Urgent: prepare rollout guidance.")],
        RunConfig(max_iterations=4),
    )

    group_chat = GroupChatBuilder(
        [triage, alpha, beta],
        rounds=1,
        name="group-chat-workflow",
        description="Shared conversation among coordinator and specialists.",
    ).build()
    group_chat_result = await group_chat.run(
        [Message(role="user", content="Discuss how the workflow API should be documented.")],
        RunConfig(),
    )

    print("Concurrent workflow:")
    print(f"  Final answer: {concurrent_result.final_message}")
    print(f"  Steps:        {concurrent_result.metadata['workflow_steps']}")

    print("\nHandoff workflow:")
    print(f"  Final answer: {handoff_result.final_message}")
    print(f"  Steps:        {handoff_result.metadata['workflow_steps']}")

    print("\nGroup chat workflow:")
    print(f"  Final answer: {group_chat_result.final_message}")
    print(f"  Steps:        {group_chat_result.metadata['workflow_steps']}")


if __name__ == "__main__":
    asyncio.run(main())
