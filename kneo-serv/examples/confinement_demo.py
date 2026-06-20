"""Demonstrate 1.0.0 spec-path confinement (default-on).

Run:

    python examples/confinement_demo.py

Caller-supplied ``spec_path`` / ``overlays`` / ``skills[].source`` are confined to
the **spec root** — ``KNEO_SERV_SPEC_ROOT`` when set, otherwise the process
working directory. A read resolving outside the root raises
``SpecPathConfinementError``, which the service maps to ``422 spec_path_confined``.
Through ``0.12.x`` this was opt-in (an out-of-root absolute path only warned);
``1.0.0`` flips it default-on and extends it to the ``skills[].source`` sibling
read path (closing the authenticated arbitrary-file-read oracle).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from kneo_serv.security.spec_root import SpecPathConfinementError, confine_spec_path
from kneo_serv.spec.skill_loader import SkillLoader


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kneo-spec-root-"))
    os.environ["KNEO_SERV_SPEC_ROOT"] = str(root)
    print(f"KNEO_SERV_SPEC_ROOT = {root}\n")

    # 1. An in-root spec path resolves and is allowed.
    in_root = root / "agent.yaml"
    in_root.write_text("version: v1\nagent: {name: demo}\n", encoding="utf-8")
    print("in-root  spec_path    -> allowed:", confine_spec_path(in_root))

    # 2. An out-of-root spec path / overlay is rejected.
    try:
        confine_spec_path("/etc/passwd", label="spec_path")
    except SpecPathConfinementError as exc:
        print("out-of-root spec_path -> rejected (422 spec_path_confined):", exc)

    # 3. An out-of-root skill source is rejected at load time (the closed sibling
    #    oracle): a declared skills[].source can no longer read arbitrary files.
    try:
        SkillLoader().load("leak", "/etc/passwd")
    except SpecPathConfinementError as exc:
        print("out-of-root skill src -> rejected (422 spec_path_confined):", exc)

    # 4. An in-root skill bundle loads normally.
    skill = root / "demo.md"
    skill.write_text("Demo skill instructions.", encoding="utf-8")
    loaded = SkillLoader().load("demo", skill)
    print("in-root  skill source -> loaded:", loaded.name)


if __name__ == "__main__":
    main()
