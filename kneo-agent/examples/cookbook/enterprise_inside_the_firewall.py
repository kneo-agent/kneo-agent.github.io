"""
Cookbook — Enterprise agent that stays inside the firewall
==========================================================
A single agent that never leaves your network, composed from the
pieces an on-prem deployment usually already has:

- **Local LLM** — an OpenAI-compatible endpoint (Ollama / vLLM /
  llama.cpp / LocalAI) via ``NativeRuntimeFactory.for_openai(base_url=...)``.
  No tokens leave the building.
- **Internal MCP server** — an ``MCPServerConfig`` pointed at a tool
  server running on the LAN (stdio subprocess here; swap to ``http`` /
  ``sse`` for a networked one).
- **Read-only SQL** — a parameter-bound query tool over an internal
  database (SQLite stdlib so this runs offline; the docstring shows the
  psycopg2 / pymysql swap).
- **Object store** — a list/get tool over MinIO / on-prem S3 (stubbed
  here; real wiring uses boto3 with ``endpoint_url=``).
- **`SecretProvider`** — every credential is resolved through a
  ``FileSecretProvider`` (think mounted Kubernetes/Vault secrets), never
  hardcoded or baked into the prompt.

The goal is to show the *composition* — how these wire into one
``ToolRegistry`` + ``RunConfig`` — not any single integration. The other
cookbook recipes (``sql_query_tool``, ``object_store_tool``,
``rest_api_tool``, ``mcp_server_catalog``, ``local_ollama``) drill into
each piece.

Like ``local_ollama.py``, this uses an offline stand-in runner so it
executes in CI without a live model. Point ``base_url`` at your server
and drop the ``runner=`` argument to run for real.

Run::

    python examples/cookbook/enterprise_inside_the_firewall.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from kneo_agent import AgentBuilder, MCPServerConfig, RunConfig, ToolDefinition
from kneo_agent.patterns import NativeRuntimeFactory
from kneo_agent.utils import FileSecretProvider, SecretProvider, ToolRegistry

# ── 1. Credentials via a SecretProvider (mounted secrets, not literals) ──

def _make_secret_provider() -> SecretProvider:
    """A ``FileSecretProvider`` over a directory of one-secret-per-file.

    In production this points at a mounted secrets volume
    (Kubernetes ``Secret`` / Vault agent / Docker secret). Traversal is
    confined to the base dir, so ``get("../../etc/passwd")`` raises.
    """
    secrets_dir = Path(tempfile.mkdtemp(prefix="kneo-secrets-"))
    (secrets_dir / "db_dsn").write_text("file:internal.db?mode=ro", encoding="utf-8")
    (secrets_dir / "object_store_key").write_text("REDACTED-ACCESS-KEY", encoding="utf-8")
    return FileSecretProvider(secrets_dir)


# ── 2. Read-only SQL tool over an internal database ──

def _seed_internal_db() -> Path:
    db_path = Path(tempfile.mkdtemp(prefix="kneo-db-")) / "internal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, status TEXT, owner TEXT)")
    conn.executemany(
        "INSERT INTO tickets (status, owner) VALUES (?, ?)",
        [("open", "alice"), ("open", "bob"), ("closed", "alice")],
    )
    conn.commit()
    conn.close()
    return db_path


def _make_sql_tool(db_path: Path) -> Any:
    """A read-only, row-capped query handler.

    For a real backend, open the connection read-only against your driver
    instead of SQLite (`psycopg2.connect(..., options='-c default_transaction_read_only=on')`,
    `pymysql` against a read-only replica, etc.) — the registry contract
    is identical.
    """

    def handler(args: dict[str, Any]) -> str:
        sql = str(args.get("sql", ""))
        if not sql.lower().lstrip().startswith("select"):
            return '{"error": "only SELECT statements are allowed"}'
        if ";" in sql.rstrip().rstrip(";"):
            return '{"error": "statement chaining is not allowed"}'
        # Read-only connection: a compromised query still can't write.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.execute(f"SELECT * FROM ({sql}) LIMIT 50")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return f'{{"error": "{exc}"}}'
        finally:
            conn.close()
        return json.dumps(rows)

    return handler


# ── 3. Object-store tool (stubbed; real wiring = boto3 endpoint_url=) ──

def _make_object_store_tool(secrets: SecretProvider) -> Any:
    # Resolve the credential through the provider; never inline it.
    _access_key = secrets.get("object_store_key")
    _bucket = {"policy.txt": "retention: 7y", "runbook.md": "step 1: ..."}

    def handler(args: dict[str, Any]) -> str:
        key = str(args.get("key", ""))
        if key not in _bucket:
            return '{"error": "not found"}'
        return f'{{"key": "{key}", "body": "{_bucket[key]}"}}'

    return handler


# ── 4. Compose everything onto one agent ──

class _OfflineRunner:
    """Offline stand-in for the OpenAI Agents runner so this runs in CI.
    Drop the ``runner=`` argument to talk to your live local server."""

    async def run(self, starting_agent: Any, input: Any, max_turns: int = 10) -> Any:
        return SimpleNamespace(
            final_output="3 tickets are open; owners: alice, bob.",
            new_items=[],
            raw_responses=[object()],
        )


def main() -> None:
    secrets = _make_secret_provider()
    db_path = _seed_internal_db()

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sql_query",
            description="Run a read-only SELECT against the internal ticket DB.",
            parameters={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        ),
        _make_sql_tool(db_path),
    )
    registry.register(
        ToolDefinition(
            name="object_get",
            description="Fetch a document from the internal object store by key.",
            parameters={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        ),
        _make_object_store_tool(secrets),
    )

    # An internal MCP server on the LAN contributes more tools. Config only —
    # not connected in this offline demo. Swap to MCPServerConfig.http(
    # name=..., url="http://mcp.internal.corp:8080/rpc") for a networked one.
    internal_mcp = MCPServerConfig.stdio(
        name="internal-tools",
        command="python",
        args=["-m", "company_internal_mcp_server"],
    )

    # The local LLM — nothing leaves the firewall. base_url points at your
    # on-prem OpenAI-compatible server; the offline runner stands in for CI.
    runtime = NativeRuntimeFactory.for_openai(
        base_url="http://llm.internal.corp:11434/v1",
        api_key=secrets.get("object_store_key"),  # any non-empty value for most local servers
        model="llama3.1",
        runner=_OfflineRunner(),
    )
    agent = (
        AgentBuilder()
        .with_name("Inside-the-Firewall Agent")
        .with_system_prompt(
            "You are an internal operations assistant. Use the SQL and "
            "object-store tools to answer; never invent data."
        )
        .with_tools(registry.definitions)
        .use_runtime(runtime)
        .build()
    )

    # Hand the tool handlers to the run via extra["tool_handlers"] (the public
    # registry.handlers mapping).
    run_config = RunConfig(extra={"tool_handlers": registry.handlers})

    print("Runtime        :", agent.runtime_name)
    print("Tools          :", [t.name for t in registry.definitions])
    print("Internal MCP   :", internal_mcp.name, f"({internal_mcp.transport})")
    print("Secrets source : FileSecretProvider (mounted volume)")

    # Exercise a tool handler directly to prove the wiring (offline).
    print("SQL result     :", registry.handlers["sql_query"]({"sql": "SELECT owner FROM tickets WHERE status='open'"}))
    print("Doc result     :", registry.handlers["object_get"]({"key": "policy.txt"}))

    result = asyncio.run(agent.run("How many tickets are open and who owns them?", run_config=run_config))
    print("Agent answer   :", result.final_message)

    # The credential is never echoed into a tool result or the answer.
    assert "REDACTED-ACCESS-KEY" not in result.final_message


if __name__ == "__main__":
    main()
