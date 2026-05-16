"""
Cookbook — REST/HTTP service tool with per-host auth-header injection
======================================================================
Pattern for exposing an internal REST API to an agent without
embedding the auth token in the prompt or in tool arguments.

Highlights:

- An ``HTTPClient`` wrapper resolves credentials from a
  ``SecretProvider`` per host, and never logs / returns the
  resolved value.
- The tool handler accepts ``method``, ``path``, ``query``,
  ``json_body`` — but **not** an arbitrary ``url``, so a compromised
  model can't redirect requests to an external host.
- Error handling preserves the response status + a truncated body
  for the model to learn from, without dumping headers (which can
  contain re-emitted bearer tokens on some servers).

Run::

    python examples/cookbook/rest_api_tool.py

In your application, replace ``_OfflineHTTP`` with ``urllib.request``
or ``httpx.Client`` — the rest of the recipe is unchanged.
"""

import json
from typing import Any
from urllib.parse import urlencode, urljoin

from kneo_agent.utils import MappingSecretProvider, SecretProvider, ToolRegistry

# ── 1. Offline HTTP stub so the recipe smoke-tests in CI ────────────


class _OfflineHTTP:
    """Stand-in for ``urllib.request.urlopen`` / ``httpx.Client.send``.

    Real apps replace this with the real client; the rest of the recipe
    is unchanged."""

    def __init__(self, fixtures: dict[tuple[str, str], dict[str, Any]]):
        self._fixtures = fixtures

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, Any]]:
        key = (method, url)
        if key not in self._fixtures:
            return 404, {"error": "not found", "url": url, "method": method}
        return 200, self._fixtures[key]


# ── 2. Per-host HTTPClient that resolves auth from a SecretProvider ──


class HTTPClient:
    """Tiny scoped HTTP client. Build one per *trusted* host so the
    agent's REST tool can reach only that host.

    Real-world example::

        client = HTTPClient(
            base_url="https://orders.internal.corp/v1/",
            secrets=EnvSecretProvider(prefix="ORDERS_"),
            secret_name="api_token",
        )

    The secret value is fetched lazily on each request; if you rotate
    secrets via FileSecretProvider or by mutating a MappingSecretProvider
    map, the next request picks up the new value.
    """

    def __init__(
        self,
        *,
        base_url: str,
        secrets: SecretProvider,
        secret_name: str,
        transport: _OfflineHTTP,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        timeout: float = 10.0,
    ) -> None:
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        self._base = base_url
        self._secrets = secrets
        self._secret_name = secret_name
        self._transport = transport
        self._auth_header = auth_header
        self._auth_scheme = auth_scheme
        self._timeout = timeout

    def _build_url(self, path: str, query: dict[str, Any] | None) -> str:
        if path.startswith("/"):
            path = path.lstrip("/")
        url = urljoin(self._base, path)
        if query:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{urlencode(query, doseq=True)}"
        return url

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = self._build_url(path, query)
        headers = {
            self._auth_header: f"{self._auth_scheme} {self._secrets.get(self._secret_name)}",
            "Accept": "application/json",
        }
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._transport.request(method, url, headers=headers, body=body)


# ── 3. Tool definition ──────────────────────────────────────────────


def make_rest_tool(client: HTTPClient):
    def handler(args: dict[str, Any]) -> str:
        method = args["method"].upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            return json.dumps({"error": f"unsupported method {method!r}"})
        try:
            status, payload = client.request(
                method,
                args["path"],
                query=args.get("query"),
                json_body=args.get("json_body"),
            )
        except Exception as exc:
            # Surface a typed error class to the model rather than the
            # full traceback. The exception type is informative; the
            # message often is not (and can leak internal hostnames).
            return json.dumps({"error": type(exc).__name__})
        # Truncate so the model gets a useful tail without consuming
        # half its context window on a 200 KB response.
        body_str = json.dumps(payload)
        if len(body_str) > 4000:
            body_str = body_str[:4000] + "...<truncated>"
        return json.dumps({"status": status, "body": body_str})

    return handler


# ── 4. Wire it ──────────────────────────────────────────────────────


def main() -> None:
    secrets = MappingSecretProvider({"api_token": "real-token-not-shown"})
    transport = _OfflineHTTP(
        fixtures={
            ("GET", "https://orders.internal.corp/v1/orders?customer=acme"): {
                "orders": [{"id": 10, "amount": 250.0}, {"id": 11, "amount": 75.0}],
            },
            ("POST", "https://orders.internal.corp/v1/orders/refund"): {
                "ok": True,
                "refund_id": "rfd-42",
            },
        }
    )
    client = HTTPClient(
        base_url="https://orders.internal.corp/v1/",
        secrets=secrets,
        secret_name="api_token",
        transport=transport,
    )

    registry = ToolRegistry()

    @registry.tool(
        name="orders_api",
        description=(
            "Call the orders REST API. ``method`` is GET/POST/PUT/DELETE/PATCH, "
            "``path`` is appended to the configured base URL. Use ``query`` for "
            "URL params and ``json_body`` for a JSON request body."
        ),
        parameters={
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "path": {"type": "string"},
                "query": {"type": "object"},
                "json_body": {"type": "object"},
            },
            "required": ["method", "path"],
        },
    )
    def orders_api(args):
        return make_rest_tool(client)(args)

    print("GET   :", orders_api({"method": "GET", "path": "/orders", "query": {"customer": "acme"}}))
    print("POST  :", orders_api({"method": "POST", "path": "/orders/refund", "json_body": {"id": 10}}))
    print("404   :", orders_api({"method": "GET", "path": "/missing"}))
    print("guard :", orders_api({"method": "TRACE", "path": "/anything"}))


if __name__ == "__main__":
    main()
