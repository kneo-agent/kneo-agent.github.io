"""
Example 09 — Workflow as Agent with Composite Participants
==========================================================
Demonstrates workflow executors, orchestration builders, and the
workflow-as-agent pattern. Shows:

- the default sequential orchestration runtime
- graph workflow building with edges
- wrapping workflows as regular agents

Run::

    python examples/09_workflow_as_agent.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kneo_agent import AgentBuilder, Message, RunResult
from kneo_agent.workflows import SequentialBuilder, WorkflowBuilder


class MockRuntime:
    """Simple runtime that derives its response from the conversation."""

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


async def main() -> None:
    writer = (
        AgentBuilder()
        .with_name("writer")
        .use_runtime(
            MockRuntime(
                "writer",
                lambda messages, config: "Draft: Kneo Agent now supports composite workflows.",
            )
        )
        .build()
    )

    reviewer = (
        AgentBuilder()
        .with_name("reviewer")
        .use_runtime(
            MockRuntime(
                "reviewer",
                lambda messages, config: f"Review: tighten '{messages[-1].content}'",
            )
        )
        .build()
    )

    editorial_workflow = SequentialBuilder(
        [writer, reviewer],
        name="editorial-workflow",
        description="Drafts copy and reviews it.",
    ).build()

    publisher = WorkflowBuilder.step(
        "publisher",
        lambda messages, config: Message(
            role="assistant",
            content=f"Published: {messages[-1].content}",
            name="publisher",
        ),
        description="Publishes the reviewed output.",
    )

    release_workflow = SequentialBuilder(
        [editorial_workflow, publisher],
        name="release-workflow",
        description="Nested workflow plus custom publish step.",
    ).build()

    graph_review = WorkflowBuilder.step(
        "graph-review",
        lambda messages, config: Message(
            role="assistant",
            content=f"Graph review: {messages[-1].content}",
            name="graph-review",
        ),
    )
    graph_workflow = (
        WorkflowBuilder(writer, name="graph-workflow", description="Graph-based editorial flow.")
        .add_executor(graph_review)
        .add_edge("writer", "graph-review")
        .build()
    )

    workflow_agent = release_workflow.as_agent(name="Release Workflow Agent")
    result = await workflow_agent.run("Prepare the workflow launch announcement.")
    graph_result = await graph_workflow.run(
        [Message(role="user", content="Prepare a graph workflow demo.")],
        __import__("kneo_agent").RunConfig(),
    )

    print(f"Agent name:   {workflow_agent.agent_name}")
    print(f"Runtime:      {workflow_agent.runtime_name}")
    print(f"Final answer: {result.final_message}")
    print(f"Steps:        {result.metadata['workflow_steps']}")
    print("\nConversation:")
    for i, message in enumerate(result.messages, start=1):
        speaker = message.name or message.role
        print(f"  {i:02d}. {speaker}: {message.content}")

    print("\nGraph workflow:")
    print(f"  Final answer: {graph_result.final_message}")
    print(f"  Supersteps:   {graph_result.metadata['workflow_supersteps']}")


if __name__ == "__main__":
    asyncio.run(main())
