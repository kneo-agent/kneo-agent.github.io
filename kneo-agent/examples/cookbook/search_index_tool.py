"""
Cookbook — Search index tool against Elasticsearch / OpenSearch
================================================================
Pattern for letting an agent run search queries against a corporate
search index without giving it write access or letting it pivot to a
different index.

Highlights:

- The handler is **bound to a single index** at registry-time. The
  agent picks the *query*, never the index name.
- A whitelist of allowed query types (``match``, ``match_phrase``,
  ``term``, ``range``, ``bool``) keeps the agent on the documented
  search surface — no scripts, no aggregations that can scan the
  whole cluster, no DSL trickery.
- Results are normalized to ``{"hits": [{"id", "score", "source"}]}``
  so the agent doesn't see whatever 200 KB of raw response a real
  cluster returns.
- The recipe ships with an in-memory mock matching the Elasticsearch
  Python client's surface (``es.search(index=..., body=...)``); to
  run against a real cluster, drop in ``elasticsearch.Elasticsearch(
  hosts=["https://es.internal.corp:9200"], ca_certs="/etc/ssl/corp/ca.pem",
  basic_auth=(user, secrets.get("es_password")))``.

Run::

    python examples/cookbook/search_index_tool.py
"""

import json
from typing import Any

from kneo_agent import ToolDefinition
from kneo_agent.utils import MappingSecretProvider, ToolRegistry

# ── 1. Offline mock matching the elasticsearch-py surface ───────────


class _FakeES:
    """Subset of the Elasticsearch Python client used by this recipe.

    Replace with::

        from elasticsearch import Elasticsearch
        es = Elasticsearch(
            hosts=["https://es.internal.corp:9200"],
            ca_certs="/etc/ssl/corp/ca.pem",
            basic_auth=("agent", secrets.get("es_password")),
        )
    """

    def __init__(self, indexed: dict[str, list[dict[str, Any]]]):
        self._docs = indexed

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        docs = self._docs.get(index, [])
        size = body.get("size", 10)
        from_ = body.get("from", 0)
        query = body.get("query", {"match_all": {}})

        def matches(doc: dict[str, Any], q: dict[str, Any]) -> bool:
            if "match_all" in q:
                return True
            if "match" in q:
                field, value = next(iter(q["match"].items()))
                return value.lower() in str(doc.get(field, "")).lower()
            if "match_phrase" in q:
                field, value = next(iter(q["match_phrase"].items()))
                return value in str(doc.get(field, ""))
            if "term" in q:
                field, value = next(iter(q["term"].items()))
                return doc.get(field) == value
            if "range" in q:
                field, spec = next(iter(q["range"].items()))
                v = doc.get(field)
                if v is None:
                    return False
                if "gte" in spec and v < spec["gte"]:
                    return False
                return not ("lte" in spec and v > spec["lte"])
            if "bool" in q:
                must = q["bool"].get("must", [])
                return all(matches(doc, sub) for sub in must)
            return False

        hits = [
            {"_id": str(i), "_score": 1.0, "_source": d}
            for i, d in enumerate(docs)
            if matches(d, query)
        ]
        sliced = hits[from_:from_ + size]
        return {"hits": {"total": {"value": len(hits)}, "hits": sliced}}


# ── 2. Allowed query shapes ─────────────────────────────────────────


_ALLOWED_QUERY_KEYS = {"match", "match_phrase", "term", "range", "bool"}


def _validate_query(query: Any, depth: int = 0) -> str | None:
    """Return ``None`` if ``query`` only uses whitelisted shapes;
    return an error string otherwise.

    Recurses into ``bool.must`` so the model can build composite
    AND queries but cannot smuggle in ``script`` / ``script_score``
    / ``percolate`` / ``regexp`` (regex search is denial-of-service
    bait against a real cluster)."""
    if depth > 5:
        return "query nested too deeply"
    if not isinstance(query, dict) or len(query) != 1:
        return "query must be a single-key object"
    (key,) = query.keys()
    if key not in _ALLOWED_QUERY_KEYS:
        return f"query type {key!r} is not allowed"
    if key == "bool":
        for sub in query["bool"].get("must", []):
            err = _validate_query(sub, depth + 1)
            if err:
                return err
    return None


# ── 3. Tool factory bound to (client, index) ────────────────────────


def make_search_tool(es: Any, index: str):
    def handler(args: dict[str, Any]) -> str:
        query = args["query"]
        size = min(int(args.get("size", 10)), 100)
        from_ = max(int(args.get("from", 0)), 0)

        err = _validate_query(query)
        if err:
            return json.dumps({"error": err})

        try:
            response = es.search(index=index, body={"query": query, "size": size, "from": from_})
        except Exception as exc:
            return json.dumps({"error": type(exc).__name__})

        hits = [
            {"id": h["_id"], "score": h["_score"], "source": h["_source"]}
            for h in response.get("hits", {}).get("hits", [])
        ]
        return json.dumps({
            "total": response.get("hits", {}).get("total", {}).get("value", len(hits)),
            "hits": hits,
        })

    return handler


# ── 4. Wire it ──────────────────────────────────────────────────────


def main() -> None:
    # In real use, pass this provider into the Elasticsearch client
    # (basic_auth=(user, secrets.get("es_password"))). The fake here
    # ignores credentials, but the variable stays so the recipe matches
    # the production wiring shape.
    _secrets = MappingSecretProvider({"es_password": "REDACTED-PASSWORD"})
    _ = _secrets
    es = _FakeES({
        "tickets": [
            {"ticket_id": 1, "title": "Wifi down on floor 3", "priority": 5, "status": "open"},
            {"ticket_id": 2, "title": "Refund for invoice 42", "priority": 2, "status": "closed"},
            {"ticket_id": 3, "title": "Wifi unstable in cafeteria", "priority": 4, "status": "open"},
        ]
    })
    handler = make_search_tool(es, index="tickets")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="search_tickets",
            description=(
                "Search the support-tickets index. ``query`` is an Elasticsearch query "
                "DSL clause restricted to match / match_phrase / term / range / bool.must."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "object"},
                    "size": {"type": "integer"},
                    "from": {"type": "integer"},
                },
                "required": ["query"],
            },
        ),
        handler,
    )

    print("match  :", handler({"query": {"match": {"title": "wifi"}}}))
    print("range  :", handler({"query": {"range": {"priority": {"gte": 3}}}, "size": 5}))
    print("guard  :", handler({"query": {"script": {"source": "ctx._source.delete()"}}}))

    # Confirm the password never landed in any tool result.
    out = handler({"query": {"match_all": {}}})
    assert "REDACTED-PASSWORD" not in out


if __name__ == "__main__":
    main()
