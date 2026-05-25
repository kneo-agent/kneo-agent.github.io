"""List pending human-review tasks and resume them with a decision.

Only resumes the first pending task; the same pattern extends to a
batch. The actual ``HumanResumeRequest`` schema depends on the run that
produced the task — adjust the payload to match.

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
            f"decision must be 'approve' or 'reject', got {decision!r}", file=sys.stderr
        )
        sys.exit(2)

    async with KneoClient.from_profile() as client:
        pending = await client.platform.human_tasks.list(status="pending", limit=10)
        print(f"{pending.count} pending tasks")
        if pending.count == 0:
            return

        for task in pending.tasks:
            print(f"resuming {task.continuation_id!r} with decision={decision!r}")
            response = await client.platform.human_tasks.resume(
                task.continuation_id,
                {"decision": decision},
            )
            print(f"  -> status={response.status!r}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "approve"
    asyncio.run(main(arg))
