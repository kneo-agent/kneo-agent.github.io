"""
Example 15 — workflow human-in-the-loop pause and resume
========================================================
Demonstrates how a workflow can pause for explicit human input by raising
``HumanInterventionRequiredError`` when no inline resolver is provided.

Run::

    python examples/15_workflow_human_in_loop_pause.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kneo_agent import AgentBuilder, HumanInterventionRequiredError, Message, RunConfig
from kneo_agent.workflows import WorkflowBuilder


class DraftRuntime:
    name = "draft-runtime"

    async def run(self, messages, config):
        return type(
            "RunResultLike",
            (),
            {
                "final_message": "Draft proposal ready.",
                "messages": [
                    *messages,
                    Message(role="assistant", content="Draft proposal ready.", name="writer"),
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

    review_step = WorkflowBuilder.human_step(
        "manager_review",
        lambda messages, config: f"Manager approval required for: {messages[-1].content}",
        description="Pause until a manager approves the draft.",
    )

    workflow = WorkflowBuilder.sequential([writer, review_step], name="approval-workflow")

    try:
        await workflow.run([Message(role="user", content="Draft a proposal.")], RunConfig())
    except HumanInterventionRequiredError as exc:
        print("Workflow paused.")
        print("Step:", exc.step_name)
        print("Prompt:", exc.prompt)
        print("Metadata:", exc.request["metadata"])
        print()
        print("To resume, provide the human response in your host app and re-enter the workflow")
        print("with a resolver or with a message such as:")
        print('  Message(role="user", content="Approved by manager")')


if __name__ == "__main__":
    asyncio.run(main())
