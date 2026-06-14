"""Placeholder step implementations for `nested_workflow_human_approval.yaml`.

These back the `implementation:` references in the nested drafting
sub-workflow and the top-level publish step. They return canned strings so
the example runs end-to-end without a real provider — retarget them before
any real use.
"""


def outline_section(text: str) -> str:
    """First step of the nested drafting sub-workflow: produce an outline."""
    return f"Outline for: {text}"


def expand_draft(text: str) -> str:
    """Second step of the nested drafting sub-workflow: expand the outline
    into a draft. Receives the previous step's output as its input."""
    return f"Draft ({text})"


def publish_report(text: str) -> str:
    """Top-level publish step: runs only after the human approval resumes,
    so its input is the approved draft."""
    return f"Published: {text}"
