"""
Cookbook — Workflow conditional branching + retry-on-failure
=============================================================
Build a graph workflow that:

1. Classifies an incoming message into a category.
2. Routes to one of two specialist steps based on the classification —
   using ``WorkflowBuilder.add_edge(..., condition=...)``.
3. Wraps the specialist step with ``RetryStep`` so transient failures
   (a flaky internal service, a model hiccup) don't fail the whole
   workflow.

The shapes ``WorkflowBuilder`` (graph), ``WorkflowEdge.condition``
(routing), and ``RetryStep`` (resilience) are all part of the public
``kneo_agent.workflows`` surface; you do **not** need a separate
``WorkflowGraphBuilder`` — ``WorkflowBuilder`` is the graph builder.

Run::

    python examples/cookbook/workflow_branching_and_retry.py
"""

import asyncio
import itertools

from kneo_agent import Message, RunConfig
from kneo_agent.workflows import (
    FunctionStep,
    RetryStep,
    WorkflowBuilder,
)

# ── 1. Steps ─────────────────────────────────────────────────────────


def classify(messages, config):
    """Tag the latest user message as 'billing' or 'tech'."""
    last = messages[-1].content.lower()
    label = "billing" if any(w in last for w in ("invoice", "refund", "charge")) else "tech"
    return Message(role="assistant", content=f"[label={label}]")


# A flaky tech-support step — fails twice, succeeds on the third call.
_tech_attempts = itertools.count(1)


def tech_support(messages, config):
    n = next(_tech_attempts)
    if n < 3:
        raise ConnectionError("internal ticketing API timed out")
    return "Tech support: please clear your cache and retry."


def billing_support(messages, config):
    return "Billing support: refund processed."


# ── 2. Routing predicates over WorkflowEdge.condition ────────────────


def is_label(label: str):
    """Build a predicate that fires when the most recent step output
    contains ``[label=<x>]``."""

    def _pred(result, current_messages, config):
        return f"[label={label}]" in result.final_message

    return _pred


# ── 3. Wire the graph ────────────────────────────────────────────────


async def main() -> None:
    classifier = FunctionStep("classify", classify)
    tech = RetryStep(
        FunctionStep("tech_support", tech_support),
        max_attempts=5,
        initial_delay=0,    # zero for the example; production would use 0.5s+
        jitter=0,
    )
    billing = FunctionStep("billing_support", billing_support)

    builder = WorkflowBuilder(classifier, name="support-router")
    builder.add_executor(tech)
    builder.add_executor(billing)
    builder.add_edge("classify", "tech_support", condition=is_label("tech"), label="route:tech")
    builder.add_edge("classify", "billing_support", condition=is_label("billing"), label="route:billing")
    workflow = builder.build()

    for query in [
        "My invoice is wrong, please refund.",
        "My laptop won't connect to wifi.",
    ]:
        print(f"\n→ {query!r}")
        result = await workflow.run(
            [Message(role="user", content=query)],
            RunConfig(max_iterations=4),
        )
        print(f"  steps : {result.metadata['workflow_steps']}")
        print(f"  reply : {result.final_message}")


if __name__ == "__main__":
    asyncio.run(main())
