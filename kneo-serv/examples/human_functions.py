"""Placeholder step implementations for the human-approval example spec.

These back the `implementation:` references in `human_approval_workflow.yaml`.
They return canned strings so the example runs end-to-end without a real
provider — retarget them before any real use.
"""


def draft_report(text: str) -> str:
    """Return a canned draft for the given input."""
    return f"Draft report for: {text}"


def publish_report(text: str) -> str:
    """Return a canned published result for the given input."""
    return f"Published: {text}"


def archive_rejected(text: str) -> str:
    """Return a canned archived result for a rejected draft (graph reject branch)."""
    return f"Archived rejected draft: {text}"
