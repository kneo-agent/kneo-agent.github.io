"""Walk every audit event across all pages.

The platform uses ``limit`` / ``offset`` pagination. ``AuditClient.list``
returns one page; this script walks pages manually. (A future revision
will integrate :func:`kneo_client.core.pagination.iterate_all`.)

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/03_paginate_audit.py [event_type]
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient

PAGE_SIZE = 200


async def main(event_type: str | None) -> None:
    async with KneoClient.from_profile() as client:
        offset = 0
        seen = 0
        while True:
            page = await client.platform.audit.list(
                event_type=event_type, limit=PAGE_SIZE, offset=offset
            )
            for event in page.events:
                seen += 1
                print(event)
            # The platform sets `count` = items on this page; when count
            # is less than the requested limit, there's nothing more.
            if page.count < PAGE_SIZE:
                break
            offset += page.count
        print(f"total events seen: {seen}", file=sys.stderr)


if __name__ == "__main__":
    filter_type = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(filter_type))
