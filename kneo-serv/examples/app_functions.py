"""Placeholder tool implementations for the example specs.

These back the `implementation:` references in `research_agent.yaml` (and its
overlays). They return canned strings so the examples run end-to-end without a
real provider — retarget them before any real use.
"""


def compress_history(text: str) -> str:
    """Return a stand-in compressed view of conversation history."""
    return f"[compressed] {text}"


def web_search(args: dict) -> str:
    """Return a canned web-search result for the given query."""
    return f"Search result for: {args.get('query')}"


def webpage_reader(args: dict) -> str:
    """Return canned page content for the given URL."""
    return f"Page content from: {args.get('url')}"


def summarize(args: dict) -> str:
    """Return a canned summary of the given text."""
    return f"Summary: {args.get('text')}"
