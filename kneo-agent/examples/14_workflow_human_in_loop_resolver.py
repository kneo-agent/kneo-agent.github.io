"""
Example 14 — workflow human-in-the-loop with inline resolver
============================================================
Demonstrates a human approval step that resolves immediately through a
callback, so the workflow continues in a single run.

Run::

    python examples/14_workflow_human_in_loop_resolver.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kneo_agent import AgentBuilder, Message, RunConfig
from kneo_agent.workflows import WorkflowBuilder


class DraftRuntime:
    name = "draft-runtime"

    async def run(self, messages, config):
        return type(
            "RunResultLike",
            (),
            {
                "final_message": "Draft release notes ready.",
                "messages": [
                    *messages,
                    Message(role="assistant", content="Draft release notes ready.", name="writer"),
                ],
                "iterations": 1,
                "tool_calls_performed": [],
                "duration_ms": 1.0,
                "metadata": {},
            },
        )()

    async def stream(self, messages, config):
        if False:
            yield None

    def supports_streaming(self):
        return False

    def supports_tools(self):
        return True


async def main() -> None:
    writer = AgentBuilder().with_name("writer").use_runtime(DraftRuntime()).build()

    workflow = WorkflowBuilder.sequential(
        [
            writer,
            WorkflowBuilder.human_step(
                "editor_approval",
                lambda messages, config: f"Approve this draft? {messages[-1].content}",
                resolver=lambda request: "Approved by Dana",
                description="Collect editor approval before publishing.",
            ),
            WorkflowBuilder.step(
                "publish",
                lambda messages, config: f"Publishing after review: {messages[-1].content}",
            ),
        ],
        name="release-workflow",
    )

    result = await workflow.run(
        [Message(role="user", content="Prepare release notes.")],
        RunConfig(),
    )
    print("Workflow steps:", result.metadata["workflow_steps"])
    print("Final message:", result.final_message)
    print("Conversation:")
    for message in result.messages:
        print(f"  - {message.role}: {message.content}")


if __name__ == "__main__":
    asyncio.run(main())
