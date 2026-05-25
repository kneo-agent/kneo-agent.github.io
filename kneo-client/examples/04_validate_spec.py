"""Validate, then compile, then explain a spec.

The Studio iterate-and-test loop. Each call returns server-side
diagnostics; stop on the first failure rather than chaining.

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/04_validate_spec.py path/to/spec.yaml
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from kneo_client import KneoClient


async def main(spec_path: Path) -> None:
    spec_text = spec_path.read_text(encoding="utf-8")
    payload = {"spec": spec_text}

    async with KneoClient.from_profile() as client:
        validated = await client.agent.specs.validate(payload)
        print(f"validate: valid={validated.valid}")
        if not validated.valid:
            for diag in validated.diagnostics or []:
                print(f"  {diag}")
            return

        compiled = await client.agent.specs.compile(payload)
        print(f"compile: ok={compiled.ok}")
        if not compiled.ok:
            for diag in compiled.diagnostics or []:
                print(f"  {diag}")
            return

        explained = await client.agent.specs.explain(payload)
        print(f"explain: {explained.summary}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} SPEC_PATH", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(Path(sys.argv[1])))
