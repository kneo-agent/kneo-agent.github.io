"""Create a run, wait for it to complete, then print its trace.

Demonstrates the bread-and-butter operational flow: submit work to the
platform, poll until done, inspect what happened. Uses
:meth:`RunsClient.wait_for_completion` for the polling loop.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/01_basic_run.py SPEC_REFERENCE

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
        created = await client.platform.runs.create({"spec_id": spec_reference})
        run_id = created.run_id
        print(f"created run {run_id!r} (status={created.status!r})")
        if run_id is None:
            print("server did not return a run_id; nothing more to do")
            return

        terminal = await client.platform.runs.wait_for_completion(
            run_id, poll_interval=2.0, timeout=600
        )
        print(f"terminal status: {terminal.status!r}")

        trace = await client.platform.runs.trace(run_id, limit=20)
        for event in trace.events:
            print(f"  {event}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_REFERENCE", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
