"""Minimal MCP stdio server backing `examples/mcp_stdio_workflow.yaml`.

Runs over stdio with no network and no credentials — the platform spawns
it as a subprocess when the spec's `tool.mcp` is first called, which
makes it both a runnable walkthrough and the CI runtime-transport proof
for the declarative-MCP stdio path (the 0.8.0 feature whose session
lifecycle was fixed in 0.9.0).

Requires the `mcp` package, which ships with `kneo-agent` — nothing
extra to install. Run it standalone to poke at it:

    python examples/mcp_stdio_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

server = FastMCP("kneo-example-tools")


@server.tool()
def word_count(text: str) -> str:
    """Count the words in `text`."""
    return str(len(text.split()))


@server.tool()
def shout(text: str) -> str:
    """Upper-case `text` — proof the round trip carries content."""
    return text.upper()


if __name__ == "__main__":
    server.run("stdio")
