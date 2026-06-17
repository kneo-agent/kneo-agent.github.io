"""List the skill catalog and start a run with a per-request skills overlay.

Demonstrates the Studio-facing skills surface (``kneo_serv >= 0.9.0``):
read the catalog via :meth:`SkillsClient.list` (a ``Page`` of open
mappings carrying at least ``name`` / ``description`` / ``path``), then
narrow what a single run may use by passing a per-request
``SkillsOverlay`` to ``runs.create``. The overlay is
``{"add": [...], "disable": [...]}``; ``add`` names must be declared in
the spec's skills block (the catalog here lists the valid targets).

Run with::

    KNEO_URL=https://kneo.example.com \\
    KNEO_API_KEY=... \\
    python examples/07_skills_overlay.py SPEC_REFERENCE [SKILL_NAME ...]

With no ``SKILL_NAME`` args the script just prints the catalog. Pass one
or more skill names to overlay them onto the run's ``add`` list.
"""

from __future__ import annotations

import asyncio
import sys

from kneo_client import KneoClient


async def main(spec_reference: str, overlay_add: list[str]) -> None:
    async with KneoClient.from_profile() as client:
        # The catalog: valid targets for a SkillsOverlay "add" list.
        catalog = await client.agent.skills.list(limit=50)
        # Catalog items are "open" generated models: bracket lookup and
        # membership tests, not dict conveniences like .get().
        print("skill catalog:")
        for skill in catalog:
            desc = skill["description"] if "description" in skill else ""
            print(f"  - {skill['name']}: {desc}")

        if not overlay_add:
            print("\nno SKILL_NAME args given; not starting a run")
            return

        body = {
            "spec_id": spec_reference,
            "skills": {"add": overlay_add, "disable": []},
        }
        created = await client.platform.runs.create(body)
        print(
            f"\ncreated run {created.run_id!r} with skills overlay "
            f"add={overlay_add} (status={created.status!r})"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"usage: python {sys.argv[0]} SPEC_REFERENCE [SKILL_NAME ...]",
            file=sys.stderr,
        )
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
