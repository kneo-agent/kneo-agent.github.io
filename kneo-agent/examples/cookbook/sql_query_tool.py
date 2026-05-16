"""
Cookbook — SQL query tool with parameter binding + schema introspection
========================================================================
Pattern for exposing a SQL database (PostgreSQL / MySQL / SQL Server)
to an agent as a *read-only*, parameter-bound query tool. Three
sub-tools land in the registry:

- ``schema`` — return the list of tables and columns so the agent
  can compose its own query without you embedding the schema in the
  system prompt.
- ``query`` — run a parameterized SELECT with a row cap and an
  optional offset.
- ``count`` — `SELECT COUNT(*)` against a table for cheap
  cardinality checks.

Critical design choices:

1. **Parameter binding**, never f-string interpolation. The handler
   refuses any query that contains ``;`` outside string literals so a
   compromised model can't chain into a destructive statement.
2. **Read-only enforcement** at the connection layer (SQLite uses
   ``mode=ro``; psycopg2 / pymysql equivalents are noted inline).
3. **Pagination** via ``LIMIT`` / ``OFFSET`` on every result so a
   "find me all customers" request can't OOM the agent loop.
4. **No vendored client.** This recipe uses ``sqlite3`` from stdlib
   so it runs offline; the docstring shows how the handler swaps to
   psycopg2 / pymysql / pyodbc for a real backend.

Run::

    python examples/cookbook/sql_query_tool.py
"""

import json
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from kneo_agent.utils import ToolRegistry

# ── 1. Toy database (replace with a real connection in your app) ────


def open_readonly_db(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection in read-only mode.

    For PostgreSQL with psycopg2:
        conn = psycopg2.connect(dsn, options="-c default_transaction_read_only=on")
    For MySQL with pymysql:
        conn = pymysql.connect(..., autocommit=True); conn.cursor().execute("SET SESSION TRANSACTION READ ONLY")
    For SQL Server (pyodbc):
        conn = pyodbc.connect(..., readonly=True)
    """
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def build_demo_db() -> Path:
    """Build a tiny customer-orders DB for the example."""
    db = Path(tempfile.mkdtemp()) / "demo.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, region TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL);
        INSERT INTO customers VALUES (1, 'Acme', 'EU');
        INSERT INTO customers VALUES (2, 'Globex', 'US');
        INSERT INTO customers VALUES (3, 'Initech', 'EU');
        INSERT INTO orders VALUES (10, 1, 250.00);
        INSERT INTO orders VALUES (11, 1, 75.00);
        INSERT INTO orders VALUES (12, 2, 1200.00);
        INSERT INTO orders VALUES (13, 3, 99.99);
    """)
    conn.commit()
    conn.close()
    return db


# ── 2. Tool handlers ─────────────────────────────────────────────────


_FORBIDDEN_TOKENS = re.compile(r";|\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH)\b", re.IGNORECASE)


def make_handlers(db_path: str | Path):
    def schema_handler(args: dict[str, Any]) -> str:
        with open_readonly_db(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            schema: dict[str, list[dict[str, str]]] = {}
            for (table,) in tables:
                cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
                schema[table] = [
                    {"name": c[1], "type": c[2], "nullable": not c[3]} for c in cols
                ]
        return json.dumps(schema)

    def query_handler(args: dict[str, Any]) -> str:
        sql = args["sql"]
        params = args.get("params") or []
        limit = min(int(args.get("limit", 100)), 1000)
        offset = max(int(args.get("offset", 0)), 0)

        if _FORBIDDEN_TOKENS.search(sql):
            return json.dumps({"error": "only single SELECT statements are allowed"})

        # Wrap so even a "SELECT ... LIMIT 10" the model wrote is bounded.
        wrapped = f"SELECT * FROM ({sql}) AS _q LIMIT ? OFFSET ?"
        with open_readonly_db(db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(wrapped, [*params, limit, offset]).fetchall()
            except sqlite3.Error as exc:
                return json.dumps({"error": str(exc)})
        return json.dumps([dict(r) for r in rows])

    def count_handler(args: dict[str, Any]) -> str:
        table = args["table"]
        # Whitelist table names against the actual schema so a user-
        # provided string can't escape the parameter slot.
        with open_readonly_db(db_path) as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if table not in tables:
                return json.dumps({"error": f"unknown table {table!r}"})
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return json.dumps({"table": table, "count": n})

    return schema_handler, query_handler, count_handler


# ── 3. Wire into a ToolRegistry ──────────────────────────────────────


def main() -> None:
    db = build_demo_db()
    schema, query, count = make_handlers(db)

    registry = ToolRegistry()

    @registry.tool(
        name="schema",
        description="Return the list of tables and columns in the database.",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    def _schema(args):
        return schema(args)

    @registry.tool(
        name="query",
        description=(
            "Run a parameterized read-only SELECT query. "
            "Pass ``sql`` and a list of ``params``; results are capped by "
            "``limit`` (default 100, max 1000) and offset by ``offset``."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "params": {"type": "array", "items": {"type": ["string", "number", "boolean", "null"]}},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": ["sql"],
        },
    )
    def _query(args):
        return query(args)

    @registry.tool(
        name="count",
        description="Return the row count for a table.",
        parameters={
            "type": "object",
            "properties": {"table": {"type": "string"}},
            "required": ["table"],
        },
    )
    def _count(args):
        return count(args)

    # Direct dispatch — same shape an agent would take.
    print("schema:", _schema({}))
    print("count :", _count({"table": "customers"}))
    print("query :", _query({
        "sql": "SELECT name, region FROM customers WHERE region = ?",
        "params": ["EU"],
        "limit": 10,
    }))
    print("guard :", _query({"sql": "DROP TABLE customers"}))


if __name__ == "__main__":
    main()
