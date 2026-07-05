"""Validate, then compile a spec — one call via the combined helper.

The Studio iterate-and-test loop. ``validate_then_compile`` runs both
calls and returns a single result; ``compile`` is skipped automatically
when validation fails so you don't waste a round-trip on a known-bad
spec.

For a fuller preview that also surfaces the explain summary and policy
report in one call, see ``client.agent.specs.dry_run(payload)`` —
mentioned at the bottom of this example.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/04_validate_spec.py path/to/spec.yaml
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient


async def main(spec_path: str) -> None:
    # ``spec_path`` is resolved server-side (under the instance's spec root).
    # To validate an inline spec instead, parse it to a dict and pass
    # ``{"spec": <dict>}`` — the ``spec`` field is an object, not raw text.
    payload = {"spec_path": spec_path}

    async with KneoClient.from_profile() as client:
        result = await client.agent.specs.validate_then_compile(payload)
        print(f"validate: valid={result.validate.valid}")
        if not result.validate.valid:
            for diag in result.validate.diagnostics or []:
                print(f"  {diag}")
            return

        # validate succeeded → compile ran.
        assert result.compile is not None
        print(f"compile: ok={result.compile.ok}")
        if not result.compile.ok:
            for compile_diag in result.compile.diagnostics or []:
                print(f"  {compile_diag}")
            return

        # Optional: get a human-readable summary too.
        explained = await client.agent.specs.explain(payload)
        print(f"explain: {explained.summary}")

        # Alternative one-call path that bundles validate + explain +
        # policy_report into a DryRunResult:
        #
        # dry = await client.agent.specs.dry_run(payload)
        # if dry.ok:
        #     print(dry.explain.summary, dry.policy_report.report)

        # Pre-helper pattern, kept for reference:
        #
        # validated = await client.agent.specs.validate(payload)
        # if not validated.valid: ...
        # compiled = await client.agent.specs.compile(payload)
        # if not compiled.ok: ...


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_PATH", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
