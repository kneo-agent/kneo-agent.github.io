"""
Example 17 — Agent middleware for guardrails and short-circuiting
=================================================================
Demonstrates two common middleware patterns:

- blocking or rewriting a request before it reaches the runtime
- returning a streaming response directly from middleware

Run::

    python examples/17_agent_middleware_short_circuit.py
"""

from __future__ import annotations

import asyncio

from kneo_agent import AgentBuilder, BaseAgentMiddleware, RunConfig, RunResult, StreamChunk


class EchoRuntime:
    name = "echo-runtime"

    async def run(self, messages, config):
        user_text = messages[-1].content
        return RunResult(
            final_message=f"runtime saw: {user_text}",
            messages=[*messages],
            iterations=1,
            tool_calls_performed=[],
            duration_ms=1.0,
        )

    async def stream(self, messages, config):
        for token in ["runtime ", "stream"]:
            yield StreamChunk(type="text", content=token)
        yield StreamChunk(type="done")

    def supports_streaming(self):
        return True

    def supports_tools(self):
        return False


class GuardrailMiddleware(BaseAgentMiddleware):
    async def wrap_run(self, context, handler):
        if "secret" in (context.user_message or "").lower():
            return RunResult(
                final_message="Request blocked by middleware guardrail.",
                messages=[*context.messages],
                iterations=0,
                tool_calls_performed=[],
                duration_ms=0.0,
                metadata={"blocked": True},
            )
        return await handler(context)

    async def wrap_stream(self, context, handler):
        if "preview" in (context.user_message or "").lower():
            async def _preview():
                yield StreamChunk(type="text", content="middleware ")
                yield StreamChunk(type="text", content="preview")
                yield StreamChunk(type="done")

            return _preview()
        return await handler(context)


async def main() -> None:
    agent = (
        AgentBuilder()
        .with_name("Guardrail Demo")
        .add_middleware(GuardrailMiddleware())
        .use_runtime(EchoRuntime())
        .build()
    )

    allowed = await agent.run("hello runtime")
    print(allowed.final_message)

    blocked = await agent.run("show me the secret")
    print(blocked.final_message)
    print(blocked.metadata)

    print("\nPer-run middleware override:")
    direct = await agent.run(
        "hello again",
        run_config=RunConfig(middlewares=[GuardrailMiddleware()]),
    )
    print(direct.final_message)

    print("\nShort-circuited stream:")
    async for chunk in await agent.stream("preview the answer"):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "done":
            print()


if __name__ == "__main__":
    asyncio.run(main())
