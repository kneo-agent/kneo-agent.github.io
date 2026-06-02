"""
Example 12 — MCP stdio server integration
=========================================
Registers tools from an MCP stdio server and exposes them to a Kneo agent.

This example uses the popular filesystem MCP server via ``npx``. You can
swap the command out for any MCP-compatible stdio server.

Run::

    python examples/12_mcp_stdio_filesystem.py

Requirements:

- Node.js + ``npx``
- ``OPENAI_API_KEY`` if you keep the OpenAI runtime below
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


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "Set OPENAI_API_KEY before running this example (it drives the "
            "OpenAI runtime below). Guarding here avoids spawning the MCP "
            "subprocess only to fail mid-run with a noisy teardown."
        )

    registry = ToolRegistry()
    try:
        tools = await registry.register_mcp_server(
            MCPServerConfig.stdio(
                name="filesystem",
                command="npx",
                args=[
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    str(PROJECT_ROOT),
                ],
            ),
            prefix="fs_",
        )

        print("Discovered MCP tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

        runtime = NativeRuntimeFactory.for_openai(model="gpt-4o", strategy="react")
        agent = (
            AgentBuilder()
            .with_name("Filesystem MCP Demo")
            .with_system_prompt(
                "You can inspect the project directory with MCP filesystem tools. "
                "Use them when the user asks about local files."
            )
            .with_tool_registry(registry, skill_name="filesystem-mcp")
            .use_runtime(runtime)
            .build()
        )

        reply = await agent.chat("List a few top-level files in this project.")
        print("\nAgent reply:\n")
        print(reply)
    finally:
        await registry.aclose()


if __name__ == "__main__":
    asyncio.run(main())
