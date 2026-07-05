"""Safely retry a POST by reusing the same Idempotency-Key.

The platform short-circuits a duplicate ``POST /v1/runs`` with the same
``Idempotency-Key`` and identical payload, returning the original
response. If the payload differs, it returns 409 (mapped here to
:class:`KneoIdempotencyMismatchError`). The transport will *also* retry
transient failures automatically when a key is set, so most callers
don't need to write a loop — this script shows the manual pattern for
visibility.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/02_idempotent_retry.py SPEC_PATH
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient
from kneo_client.core.errors import (
    KneoIdempotencyMismatchError,
    KneoNetworkError,
    KneoServerError,
)
from kneo_client.core.idempotency import new_idempotency_key

# The run's task input — replace with your own. A run needs an ``input``
# plus a spec (server-side ``spec_path`` here); there is no ``spec_id``.
RUN_INPUT = "Summarize the latest activity."


async def main(spec_path: str) -> None:
    async with KneoClient.from_profile() as client:
        key = new_idempotency_key()
        body = {"input": RUN_INPUT, "spec_path": spec_path}

        for attempt in range(1, 4):
            try:
                run = await client.platform.runs.create(body, idempotency_key=key)
                print(f"attempt {attempt}: success run_id={run.run_id!r}")
                return
            except KneoIdempotencyMismatchError as exc:
                # Body changed between attempts — fatal at our layer.
                print(
                    f"attempt {attempt}: idempotency mismatch ({exc})", file=sys.stderr
                )
                return
            except (KneoNetworkError, KneoServerError) as exc:
                # Safe to retry with the same key; the transport already
                # retries within its policy, but we add an outer guard
                # to illustrate the pattern.
                print(f"attempt {attempt}: transient failure ({exc})", file=sys.stderr)
                if attempt == 3:
                    raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_PATH", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
