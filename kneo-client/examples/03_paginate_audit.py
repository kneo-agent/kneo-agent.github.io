"""List audit events using the ``Page`` wrapper and ``iterate_all``.

``AuditClient.list`` returns a :class:`kneo_client.core.results.Page`.
Iteration yields the events directly; ``page.count`` gives the number
of items on this fetch.

Audit has been fully paginated since ``kneo_serv`` 0.6.0 / client
0.6.0: the endpoint accepts ``limit`` / ``offset`` / ``sort_by`` /
``sort_order``, the response echoes ``total`` / ``offset`` and sort
metadata, and :func:`kneo_client.core.results.iterate_all` walks it
like any other fully paginating endpoint (``runs.list``,
``runs.checkpoints``, ``runs.trace``, ``human_tasks.list``,
``agent.skills.list``). Since ``kneo_serv`` 0.9.0 the response also
discloses ``window`` — the deepest reachable paging offset; ``total``
is the true store count and can exceed it, and ``page.has_more``
reports whether more events are *fetchable*, so the walk stops
honestly at the window edge.

Against a pre-0.6.0 server the metadata degrades to ``None``,
``has_more`` is ``False``, and the walk fetches once and exits.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/03_paginate_audit.py [event_type]
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient
from kneo_client.core.results import Page, iterate_all

PAGE_LIMIT = 200


async def main(event_type: str | None) -> None:
    async with KneoClient.from_profile() as client:
        # First page by hand — shows the pagination metadata.
        page = await client.platform.audit.list(event_type=event_type, limit=PAGE_LIMIT)
        print(
            f"first page: {page.count} of total={page.total} audit events "
            f"(offset={page.offset}, window={page.window}, has_more={page.has_more})",
            file=sys.stderr,
        )
        for event in page:
            print(event)

        # Remaining pages via iterate_all — offset-walks until has_more
        # is False (end of data, or the paging window edge).
        async def fetch(limit: int, offset: int) -> Page:
            return await client.platform.audit.list(
                event_type=event_type, limit=limit, offset=offset
            )

        walked = page.count
        if page.has_more:
            async for event in iterate_all(
                fetch, page_size=PAGE_LIMIT, start_offset=page.count
            ):
                print(event)
                walked += 1
        print(f"walked {walked} audit events in total", file=sys.stderr)


if __name__ == "__main__":
    filter_type = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(filter_type))
