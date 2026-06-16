"""Worked example: a custom tool middleware through the async-native adapter.

A service middleware wraps the SDK runtime through an adapter. This script
exercises two adapter properties offline, with no provider or network:

1. **Tool-result metadata reaches the SDK.** A custom `ToolMiddleware` can
   stamp `ToolResult.metadata` (audit annotations, guardrail notes).
   `SDKToolResult` has no metadata field, so `tool_result_to_sdk` would drop it
   on the floor. `ServiceToolMiddlewareAdapter` folds that metadata into the
   SDK `ToolCallContext.metadata`, which the SDK pipeline preserves.

2. **OTel trace context propagates across the sync↔async boundary.**
   `run_awaitable_sync` is how sync service code drives an SDK coroutine. The
   demo sets a marker on the OTel context and reads it back from inside the
   awaitable, proving spans nest under the run span rather than orphaning.

   *(0.11.0: the adapter itself is now async-native — `ServiceMiddlewareAdapter`
   bridges via anyio `to_thread`/`from_thread` on the host loop, so it no longer
   spins a fresh `anyio.run` loop per nested middleware. That dropped the
   per-call fresh-loop "hop" the 0.10.0 OTel-carrier patch existed to repair;
   `run_awaitable_sync` now runs only at the sync→async boundary, where context
   propagates in-thread.)*

Run with:

    python examples/custom_middleware_demo.py

See [`docs/dev/design.md`](../docs/dev/design.md) for the middleware
adapter model.
"""

from __future__ import annotations

from typing import Any


def metadata_passthrough() -> dict[str, Any]:
    """Drive a custom tool middleware through the SDK adapter and return the
    SDK-side metadata, proving the stamp is preserved rather than dropped."""
    import anyio
    from kneo_agent import ToolCall
    from kneo_agent import ToolResult as SDKToolResult
    from kneo_agent.core.middleware import ToolCallContext as SDKToolCallContext

    from kneo_serv.middleware.sdk import ServiceToolMiddlewareAdapter
    from kneo_serv.sdk import run_config_to_sdk

    class AuditStampMiddleware:
        """A custom middleware that annotates every tool result."""

        def wrap_tool_call(self, ctx, next_call):
            result = next_call(ctx)
            result.metadata["audited_by"] = "custom-middleware-demo"
            return result

    async def _handler(ctx):
        return SDKToolResult(tool_call_id="t1", name="lookup", result="ok")

    ctx = SDKToolCallContext(
        executor_name="x",
        runtime_name="r",
        iteration=1,
        messages=[],
        run_config=run_config_to_sdk(None),
        tool_call=ToolCall(id="t1", name="lookup", arguments={}),
        metadata={},
    )
    anyio.run(
        ServiceToolMiddlewareAdapter(AuditStampMiddleware()).wrap_tool_call,
        ctx,
        _handler,
    )
    return dict(ctx.metadata)


def otel_context_propagates() -> Any:
    """Set a marker on the OTel context, then read it back from inside an
    awaitable driven via `run_awaitable_sync` (the sync→async boundary).
    Returns what the awaitable saw — the parent value if the context
    propagated, `None` if it was lost."""
    from opentelemetry import context as otel_context

    from kneo_serv.sdk import run_awaitable_sync

    key = otel_context.create_key("custom_middleware_demo_marker")
    token = otel_context.attach(otel_context.set_value(key, "parent-context"))
    try:

        async def _read_inside() -> Any:
            return otel_context.get_value(key)

        return run_awaitable_sync(_read_inside())
    finally:
        otel_context.detach(token)


def main() -> None:
    """Exercise both adapter-hop fixes and print the results."""
    sdk_metadata = metadata_passthrough()
    seen = otel_context_propagates()

    print("== Tool-result metadata pass-through ==")
    print(
        "  SDK ToolCallContext.metadata['audited_by'] ->",
        sdk_metadata.get("audited_by"),
    )
    print()
    print("== OTel context propagates across the sync↔async boundary ==")
    print("  marker seen inside the awaitable ->", repr(seen))

    assert sdk_metadata.get("audited_by") == "custom-middleware-demo", (
        "tool-result metadata was dropped at the SDK adapter"
    )
    assert seen == "parent-context", "OTel context did not propagate"
    print()
    print("Both adapter properties hold: metadata preserved, OTel context propagated.")


if __name__ == "__main__":
    main()
