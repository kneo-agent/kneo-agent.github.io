"""Worked example: secret redaction across structured data, free text, and traces.

The platform scrubs secrets out of everything it persists or emits —
structured payloads (checkpoints, audit events, error envelopes), free
text (log lines, error messages), and trace events. This demo exercises
all three surfaces offline, with no provider or network.

It doubles as the executable regression for the 0.10.0 redaction MEDIUMs,
especially the *pluralized-key* fix: keys like ``api_keys``,
``refresh_tokens``, and ``KNEO_SERV_API_KEYS`` are credentials and must be
redacted, while single-segment *usage* keys like ``input_tokens`` /
``max_tokens`` are counting nouns and must survive untouched (over-redacting
them corrupted token-usage accounting before the fix).

Run with:

    python examples/redaction_demo.py

See [`docs/user/security_hardening.md`](../docs/user/security_hardening.md)
for the full redaction surface.
"""

from __future__ import annotations

from typing import Any

from kneo_serv.observability.context import TraceContext
from kneo_serv.observability.tracer import Tracer
from kneo_serv.security.redaction import (
    REDACTED,
    redact_data,
    redact_text,
)


def redaction_report() -> dict[str, Any]:
    """Redact representative secrets across all three surfaces and return the
    results, so a caller (or the offline test) can confirm enforcement."""

    # 1. Structured payload — the checkpoint / audit / error-envelope shape.
    #    Pluralized credential keys must be redacted; usage keys must survive.
    structured = redact_data(
        {
            "api_keys": ["sk-secretvalue123456", "sk-anothersecret7890"],
            "refresh_token": "rt-supersecretrefresh",
            "client_secret": "cs-topsecret",
            "nested": {
                "ssn": "123-45-6789",
                "note": "reach alice@example.com password=hunter2 token=abc123",
            },
            # Usage accounting — NOT secrets, must pass through unchanged.
            "input_tokens": 1280,
            "max_tokens": 4096,
        }
    )

    # 2. Free text — a log line / error message with inline credentials.
    free_text = redact_text(
        "provider failed with api_key=sk-secretvalue123456 "
        "and authorization=Bearer abc.def.ghi"
    )

    # 3. Trace event — previews, metadata, and errors are scrubbed on emit.
    ctx = TraceContext(run_id="run-redaction-demo")
    Tracer(ctx).emit(
        "run_started",
        input="contact alice@example.com password=supersecret ssn 123-45-6789",
        metadata={"authorization": "Bearer abc.def.ghi"},
        error="provider failed with api_key=sk-secretvalue123456",
    )
    trace_event = ctx.collector.to_dict_list()[0]

    return {
        "structured": structured,
        "free_text": free_text,
        "trace_event": trace_event,
    }


def main() -> None:
    """Print the before/after for each redaction surface."""
    report = redaction_report()

    print("== Structured payload (redact_data) ==")
    print("  api_keys (plural credential) ->", report["structured"]["api_keys"])
    print("  refresh_token              ->", report["structured"]["refresh_token"])
    print("  client_secret              ->", report["structured"]["client_secret"])
    print("  nested.ssn                 ->", report["structured"]["nested"]["ssn"])
    print("  nested.note                ->", report["structured"]["nested"]["note"])
    print("  input_tokens (usage, kept) ->", report["structured"]["input_tokens"])
    print("  max_tokens   (usage, kept) ->", report["structured"]["max_tokens"])
    print()
    print("== Free text (redact_text) ==")
    print(" ", report["free_text"])
    print()
    print("== Trace event (Tracer.emit) ==")
    print(
        "  metadata.authorization ->",
        report["trace_event"]["metadata"]["authorization"],
    )
    print("  error                  ->", report["trace_event"]["error"])

    # The whole report must be free of every secret literal.
    import json

    serialized = json.dumps(report, sort_keys=True, default=str)
    for secret in (
        "sk-secretvalue123456",
        "rt-supersecretrefresh",
        "cs-topsecret",
        "hunter2",
        "abc123",
        "123-45-6789",
        "alice@example.com",
    ):
        assert secret not in serialized, f"leaked secret: {secret}"
    # Usage accounting survived.
    assert report["structured"]["input_tokens"] == 1280
    assert report["structured"]["max_tokens"] == 4096
    print()
    print(f"All secrets redacted ({REDACTED}); token-usage counts preserved.")


if __name__ == "__main__":
    main()
