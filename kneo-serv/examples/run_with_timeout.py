"""Worked example: run-level deadlines + the prune_timed_out_runs sweep.

Demonstrates the 0.3.0 run-level timeout surface end-to-end:

1. `start_run_from_spec(..., timeout_seconds=N)` schedules a run with a
   wall-clock deadline written to `RunState.deadline_at`.
2. `prune_timed_out_runs()` is an operator-callable sweep that
   force-cancels every `running` or `blocked` run past its deadline,
   transitions the state to `timed_out`, deletes the continuation if
   the run was paused on a human task, and emits a `run.timed_out`
   audit event.

Run with:

    python examples/run_with_timeout.py

Reads no external secrets — the example uses the `dummy` runtime via
the bundled smoke spec.

See [`docs/user/human_in_the_loop.md § 9.5`](../docs/user/human_in_the_loop.md)
for the dispatch matrix between run-level and human-task timeouts.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from kneo_serv.service.factory import create_default_platform_manager


def main() -> None:
    """Schedule a run with a short deadline, then run the prune sweep."""
    state_dir = Path(tempfile.mkdtemp(prefix="kneo-timeout-example-"))
    manager = create_default_platform_manager(
        state_path=state_dir / "kneo_runs.sqlite",
        include_example_tools=False,
    )

    # Schedule a run with a 2-second deadline. The spec is the bundled
    # human-approval workflow; the worker will pause on the human step
    # (no reviewer is around to resume it) and the run will sit in
    # `blocked` until the deadline elapses.
    run_state = manager.start_run_from_spec(
        input_text="Approve the Q3 budget revision.",
        spec_path="examples/human_approval_workflow.yaml",
        target="workflow",
        timeout_seconds=2,
    )
    print(f"Run created: id={run_state.id} deadline_at={run_state.deadline_at}")

    # Wait past the deadline. In production this happens asynchronously
    # — the prune sweep is driven by cron / a scheduled run / a manual
    # operator action.
    time.sleep(3)

    # Force-cancel every run past its deadline. Returns the count of
    # runs transitioned to `timed_out` on this call.
    transitioned = manager.prune_timed_out_runs()
    print(f"prune_timed_out_runs() -> {transitioned} run(s) timed out")

    final = manager.run_state_store.get_run(run_state.id)
    print(f"Final status: {final.status}")
    if final.error:
        print(f"Error envelope: {final.error}")

    # Audit trail picks up the lifecycle transition.
    events = manager.run_state_store.list_audit_events(
        run_id=run_state.id, event_type="run.timed_out"
    )
    print(f"run.timed_out audit events: {len(events)}")


if __name__ == "__main__":
    main()
