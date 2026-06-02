"""
Cookbook — production middleware bundle
=======================================
Composes the four shipped production middlewares on one agent:

- ``RetryMiddleware``      — retry transient model/tool failures
- ``RateLimitMiddleware``  — token-bucket throttle
- ``TokenBudgetMiddleware``— per-run / cumulative cost caps
- ``RedactionMiddleware``  — scrub secrets from inputs / outputs / tools

**Use the Bridge pattern for this.** ``RetryMiddleware`` and
``RedactionMiddleware``'s tool-argument scrubbing ride the inner
``wrap_model_call`` / ``wrap_tool_call`` hooks, which only fire when Kneo
owns the loop (Bridge) — under an Adapter / Native runtime they are
silent no-ops. See ``docs/user/agent_middleware_guide.md``.

This example uses a tiny in-process ``RuntimeImpl`` (no provider SDK or
network) so it runs anywhere; swap it for a real Bridge impl in practice.

Run::

    python examples/cookbook/production_middleware.py
"""

from __future__ import annotations

import asyncio

from kneo_agent import AgentBuilder, ModelResponse
from kneo_agent.middleware import (
    COMMON_PATTERNS,
    RateLimitMiddleware,
    RedactionMiddleware,
    RetryMiddleware,
    TokenBudgetMiddleware,
)
from kneo_agent.runtime.bridge import SimpleAgentExecutor

# A fake leaked secret in the model's output — matches COMMON_PATTERNS
# (OpenAI/Anthropic ``sk-`` shape) so RedactionMiddleware scrubs it.
_LEAKED_SECRET = "sk-PRODabcdef0123456789ghijklmno"


class FlakyMockImpl:
    """Stand-in Bridge ``RuntimeImpl``: fails once (to exercise retry),
    then returns a response that (a) embeds a secret and (b) reports token
    usage — so redaction and the token budget have something to act on."""

    platform_name = "mock"

    def __init__(self) -> None:
        self._attempts = 0

    async def complete(self, messages, config) -> ModelResponse:
        self._attempts += 1
        if self._attempts == 1:
            print("  · model call failed (simulated transient error) — RetryMiddleware will retry")
            raise ConnectionError("transient upstream error")
        return ModelResponse(
            text=f"All set. For reference the deploy key was {_LEAKED_SECRET} — keep it safe.",
            tool_calls=[],
            usage={"input_tokens": 40, "output_tokens": 18, "total_tokens": 58},
        )

    async def execute_tool(self, call, config) -> str:  # pragma: no cover - no tools here
        return "{}"

    async def stream_tokens(self, messages, config):  # pragma: no cover - unused
        yield ""

    def supports_streaming(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return True


def build_agent(budget: TokenBudgetMiddleware):
    runtime = SimpleAgentExecutor(FlakyMockImpl())
    return (
        AgentBuilder()
        .with_name("Production Agent")
        .with_system_prompt("You are a deployment assistant.")
        # Order matters: Redaction outermost so it scrubs before anything
        # inner (e.g. an observability exporter) can see the raw value.
        .add_middleware(RedactionMiddleware(COMMON_PATTERNS))
        .add_middleware(RetryMiddleware(max_attempts=3, initial_delay=0.01))
        # Composed in for completeness; at this tiny volume it never throttles.
        # Lower `rate`/`burst` (e.g. rate=1, burst=1) to see it pace runs.
        .add_middleware(RateLimitMiddleware(rate=50.0, burst=5))
        .add_middleware(budget)
        .use_bridge(runtime)
        .build()
    )


async def main() -> None:
    # Cumulative cap across runs (e.g. one billing period); on_missing="warn"
    # surfaces any runtime that fails to report usage.
    budget = TokenBudgetMiddleware(per_run=1000, cumulative=10_000, on_missing="warn")

    print("Run 1:")
    result = await build_agent(budget).run("Finish the deployment.")
    print(f"  final message: {result.final_message}")
    print(f"  usage:         {result.metadata.get('usage')}")
    assert _LEAKED_SECRET not in result.final_message, "secret should have been redacted!"
    print("  ✓ secret redacted, ✓ transient failure retried, ✓ usage recorded")

    print("\nRun 2 (same budget instance → cumulative tracking):")
    await build_agent(budget).run("Verify the deployment.")
    print(f"  cumulative tokens used: {budget.cumulative_used}")

    budget.reset()
    print(f"  after reset (new billing period): {budget.cumulative_used}")


if __name__ == "__main__":
    asyncio.run(main())
