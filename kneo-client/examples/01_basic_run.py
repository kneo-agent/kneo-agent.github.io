"""Create a run and stream its trace events as they arrive.

Demonstrates the bread-and-butter operational flow: submit work to the
platform, watch what happens live, see the final status. Uses
:meth:`RunsClient.tail_trace` to interleave the polling loop and the
event stream into one async iterator — no separate wait + fetch pass.

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

        # tail_trace yields each event as it lands on the server, then
        # one final drain pass after the run reaches a terminal status.
        async for event in client.platform.runs.tail_trace(
            run_id, poll_interval=2.0, timeout=600
        ):
            print(f"  {event}")

        terminal = await client.platform.runs.get(run_id)
        print(f"terminal status: {terminal.status!r}")

        # The pre-helper pattern, kept for reference:
        #
        # await client.platform.runs.wait_for_completion(run_id, poll_interval=2.0)
        # trace = await client.platform.runs.trace(run_id, limit=200)
        # for event in trace:
        #     print(event)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_REFERENCE", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
