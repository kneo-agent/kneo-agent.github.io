"""Submit a run in async mode and poll it to completion.

Demonstrates the ``async_mode=true`` create path. Since ``kneo_serv``
0.11.0 the server accepts an async create with **HTTP 202 Accepted**
(was ``200``) and dispatches the run in the background; the client
treats any ``2xx`` as success, so ``create()`` returns the same
:class:`RunCreateResponse` carrying the ``run_id``. You then poll with
:meth:`RunsClient.wait_for_completion` until the run reaches a terminal
status. Contrast with ``01_basic_run.py``, which streams the trace live.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/06_async_run.py SPEC_REFERENCE

Replace ``SPEC_REFERENCE`` with a spec ID known to your kneo_serv
instance, or pre-configure a profile at ``~/.config/kneo/client.toml``
and drop the env vars.
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient


async def main(spec_reference: str) -> None:
    async with KneoClient.from_profile() as client:
        # async_mode=true: the server returns 202 and runs in the
        # background. The wrapper parses the 202 body exactly like the
        # old 200, so we still get the run_id back here.
        created = await client.platform.runs.create(
            {"spec_id": spec_reference, "async_mode": True}
        )
        run_id = created.run_id
        print(f"accepted async run {run_id!r} (status={created.status!r})")
        if run_id is None:
            print("server did not return a run_id; nothing more to do")
            return

        # Poll until terminal (succeeded / failed / cancelled / …). A
        # guardrail-blocked run terminalizes as "failed" since 0.11.0.
        terminal = await client.platform.runs.wait_for_completion(
            run_id, poll_interval=2.0, timeout=600
        )
        print(f"terminal status: {terminal.status!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_REFERENCE", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
