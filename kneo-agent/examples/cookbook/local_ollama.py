"""
Cookbook — Local LLM via Ollama (or any OpenAI-compatible server)
=================================================================
Point Kneo Agent at an OpenAI-compatible HTTP endpoint to run an
agent fully on-prem. The same pattern works for vLLM, llama.cpp's
``llama-server``, LocalAI, or any other server that speaks the
OpenAI chat-completions API.

The SDK does not start a local server for you — bring up Ollama (or
your equivalent) yourself first::

    ollama pull llama3.1
    ollama serve

Real-world usage — one call::

    from kneo_agent import build_sync_agent

    agent = build_sync_agent(
        "openai",
        base_url="http://localhost:11434/v1",
        model="llama3.1",
        system_prompt="You are a concise assistant.",
    )
    print(agent.chat("What is 2 + 2?"))

Or against the explicit factory if you want fine-grained control::

    from kneo_agent import AgentBuilder
    from kneo_agent.patterns import NativeRuntimeFactory

    runtime = NativeRuntimeFactory.for_openai(
        base_url="http://localhost:11434/v1",
        model="llama3.1",
    )
    agent = (
        AgentBuilder()
        .with_name("Local LLM Agent")
        .with_system_prompt("You are a concise assistant.")
        .use_runtime(runtime)
        .build()
    )

This script uses a mock OpenAI-Agents runner so it runs offline in CI.
Replace the mock with no ``runner=`` argument to talk to your live
local server.

Run::

    python examples/cookbook/local_ollama.py
"""

import asyncio
from types import SimpleNamespace

from kneo_agent import AgentBuilder
from kneo_agent.patterns import NativeRuntimeFactory


class _OfflineRunner:
    """Stand-in for the OpenAI Agents SDK runner so this example runs
    in CI without a live local model. In your own code you don't need
    this — drop the ``runner=`` argument and the SDK provides one."""

    async def run(self, starting_agent, input, max_turns=10):
        return SimpleNamespace(
            final_output="2 + 2 = 4.",
            new_items=[],
            raw_responses=[object()],
        )


async def main() -> None:
    runtime = NativeRuntimeFactory.for_openai(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # most local servers ignore this
        model="llama3.1",
        runner=_OfflineRunner(),
    )
    agent = (
        AgentBuilder()
        .with_name("Local LLM Agent")
        .with_system_prompt("You are a concise assistant.")
        .use_runtime(runtime)
        .build()
    )
    result = await agent.run("What is 2 + 2?")
    print(f"Runtime:   {agent.runtime_name}")
    print(f"Answer:    {result.final_message}")


if __name__ == "__main__":
    asyncio.run(main())
