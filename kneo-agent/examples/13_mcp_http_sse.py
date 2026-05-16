"""
Example 13 — MCP HTTP / SSE integration
=======================================
Connects to an MCP server exposed over HTTP or SSE, imports its tools, and
packages them for normal agent execution.

Set one of these before running:

- ``MCP_HTTP_URL`` for direct JSON-RPC over HTTP
- ``MCP_SSE_URL`` and optionally ``MCP_MESSAGE_URL`` for SSE + message endpoint

Run::

    python examples/13_mcp_http_sse.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kneo_agent import AgentBuilder, MCPServerConfig
from kneo_agent.patterns import NativeRuntimeFactory
from kneo_agent.utils import ToolRegistry


def _server_config() -> MCPServerConfig:
    http_url = os.getenv("MCP_HTTP_URL")
    sse_url = os.getenv("MCP_SSE_URL")
    message_url = os.getenv("MCP_MESSAGE_URL")

    if http_url:
        return MCPServerConfig.http(name="remote-http", url=http_url)
    if sse_url:
        return MCPServerConfig.sse(
            name="remote-sse",
            sse_url=sse_url,
            message_url=message_url,
        )

    raise SystemExit(
        "Set MCP_HTTP_URL or MCP_SSE_URL before running this example."
    )


async def main() -> None:
    registry = ToolRegistry()
    try:
        config = _server_config()
        tools = await registry.register_mcp_server(config, prefix="remote_")

        print(f"Connected to {config.transport} MCP server {config.name!r}")
        print("Discovered tools:")
        for tool in tools:
            print(f"  - {tool.name}")

        runtime = NativeRuntimeFactory.for_openai(model="gpt-4o", strategy="react")
        agent = (
            AgentBuilder()
            .with_name("Remote MCP Demo")
            .with_system_prompt(
                "Use remote MCP tools when they are relevant and summarize clearly."
            )
            .with_tool_registry(registry, skill_name="remote-mcp")
            .use_runtime(runtime)
            .build()
        )

        reply = await agent.chat("What MCP tools do you have available?")
        print("\nAgent reply:\n")
        print(reply)
    finally:
        await registry.aclose()


if __name__ == "__main__":
    asyncio.run(main())
