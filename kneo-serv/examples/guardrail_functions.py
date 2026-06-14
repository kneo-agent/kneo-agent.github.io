"""Placeholder tool implementation for `guardrails_complete.yaml`.

Backs the `lookup_account` tool. It deliberately returns a record
containing PII (a social-security number) so the declared tool-stage
guardrail has something to catch — the offline test proves the guardrail
redacts it. Retarget before any real use.
"""


def lookup_account(args: dict) -> str:
    """Return a canned account record that contains PII (an SSN)."""
    return f"Account for {args.get('q')}: name=Dana Lee, SSN=123-45-6789"
