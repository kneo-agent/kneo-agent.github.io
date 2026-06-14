"""Worked example: a custom tool middleware + the two adapter-hop fixes.

A service middleware wraps the SDK runtime through an adapter. Two 0.10.0
MEDIUM fixes keep that adapter hop faithful, and this script exercises both
offline, with no provider or network:

1. **Tool-result metadata reaches the SDK.** A custom `ToolMiddleware` can
   stamp `ToolResult.metadata` (audit annotations, guardrail notes).
   `SDKToolResult` has no metadata field, so before the fix
   `tool_result_to_sdk` dropped it on the floor. `ServiceToolMiddlewareAdapter`
   now folds that metadata into the SDK `ToolCallContext.metadata`, which the
   SDK pipeline preserves.

2. **OTel trace context survives the sync/async thread hop.**
   `run_awaitable_sync` runs an SDK coroutine on a worker thread, which
   starts with an empty context. It now carries the OpenTelemetry context
   across the hop, so spans emitted inside the awaitable nest under the run
   span instead of becoming orphan roots. The demo proves it by reading a
   marker set on the parent context from inside the awaitable. (Only the OTel
   context is propagated — not a full `contextvars.copy_context()`, which
   would carry sniffio's marker and break `anyio.run` on the worker.)

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


def otel_context_survives_hop() -> Any:
    """Set a marker on the OTel context, then read it back from inside an
    awaitable executed via `run_awaitable_sync` (which hops to a worker
    thread). Returns what the worker saw — the parent value if the context
    crossed the hop, `None` if it was lost (the pre-fix behaviour)."""
    from opentelemetry import context as otel_context

    from kneo_serv.sdk import run_awaitable_sync

    key = otel_context.create_key("custom_middleware_demo_marker")
    token = otel_context.attach(otel_context.set_value(key, "parent-context"))
    try:

        async def _read_on_worker() -> Any:
            return otel_context.get_value(key)

        return run_awaitable_sync(_read_on_worker())
    finally:
        otel_context.detach(token)


def main() -> None:
    """Exercise both adapter-hop fixes and print the results."""
    sdk_metadata = metadata_passthrough()
    seen = otel_context_survives_hop()

    print("== Tool-result metadata pass-through ==")
    print(
        "  SDK ToolCallContext.metadata['audited_by'] ->",
        sdk_metadata.get("audited_by"),
    )
    print()
    print("== OTel context survives the run_awaitable_sync thread hop ==")
    print("  marker seen on the worker thread ->", repr(seen))

    assert sdk_metadata.get("audited_by") == "custom-middleware-demo", (
        "tool-result metadata was dropped at the SDK adapter hop"
    )
    assert seen == "parent-context", (
        "OTel context did not survive the run_awaitable_sync thread hop"
    )
    print()
    print("Both adapter-hop fixes hold: metadata preserved, OTel context propagated.")


if __name__ == "__main__":
    main()
