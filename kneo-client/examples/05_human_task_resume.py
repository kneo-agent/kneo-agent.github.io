"""Resume the first pending human-review task with a decision.

Uses ``resume_first_pending`` — the list-then-resume dance collapsed
into one call. Returns ``None`` if no matching pending task exists.

The actual ``HumanResumeRequest`` schema depends on the run that
produced the task; adjust the payload to match.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/05_human_task_resume.py [approve|reject]
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient


async def main(decision: str) -> None:
    if decision not in {"approve", "reject"}:
        print(
            f"decision must be 'approve' or 'reject', got {decision!r}",
            file=sys.stderr,
        )
        sys.exit(2)

    async with KneoClient.from_profile() as client:
        response = await client.platform.human_tasks.resume_first_pending(
            {"decision": decision},
        )
        if response is None:
            print("no pending human tasks")
            return
        print(f"resumed -> status={response.status!r}")

        # To loop over multiple pending tasks, fall back to the manual
        # list-then-resume pattern (the helper only claims one). Task
        # items are continuation records keyed by "id":
        #
        # page = await client.platform.human_tasks.list(status="pending", limit=10)
        # for task in page:
        #     await client.platform.human_tasks.resume(
        #         task["id"], {"decision": decision}
        #     )


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "approve"
    asyncio.run(main(arg))
