"""List audit events using the new ``Page`` wrapper.

``AuditClient.list`` returns a :class:`kneo_client.core.results.Page`.
Iteration yields the events directly; ``page.count`` gives the number
of items on this fetch.

A note on the audit endpoint specifically: the platform's ``/v1/audit-events``
spec accepts ``limit`` only (no ``offset``), and the response echoes
only ``count`` + ``events`` — not ``total`` or sort metadata. The
wrapper surfaces this honestly: ``page.total``, ``page.limit``,
``page.offset``, ``page.sort_by``, and ``page.sort_order`` are all
``None``, and ``page.has_more`` is ``False`` because the server doesn't
tell us whether more events exist. You get the first N events the
server returned for the requested ``limit``, and that's the whole
visible window. Use the ``event_type`` / ``run_id`` filters to narrow
the result set.

For *fully* paginating endpoints (``runs.list``, ``runs.checkpoints``,
``runs.trace``, ``human_tasks.list``), the same ``Page`` returned by
the wrapper carries full metadata and supports page-walking via
:func:`kneo_client.core.results.iterate_all`.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/03_paginate_audit.py [event_type]
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient

PAGE_LIMIT = 200


async def main(event_type: str | None) -> None:
    async with KneoClient.from_profile() as client:
        page = await client.platform.audit.list(event_type=event_type, limit=PAGE_LIMIT)
        print(
            f"fetched {page.count} audit events "
            f"(limit={PAGE_LIMIT}; server doesn't echo total)",
            file=sys.stderr,
        )
        for event in page:
            print(event)


if __name__ == "__main__":
    filter_type = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(filter_type))
