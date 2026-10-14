"""Checks the built skill text that Claude Code shows people.

- Every jutsu skill is slash-only (`disable-model-invocation: true`), so its description
  shows in the `/` menu and is never used for routing. A routing rule such as "Use when
  the user says reflect" reads there as if the skill fires on its own
  (cursor/plugins#367, fix PR cursor/plugins#519).
- Upstream's ketchup builds its charts with Cursor's `/visualize`, which Claude Code
  and T3 do not have.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
ROUTING = re.compile(r"(?i)\buse (only )?when\b")


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    block = text.split("---", 2)[1]
    out = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            out[key.strip()] = value.strip().strip('"')
    return out


class SkillTextTest(unittest.TestCase):
    def test_slash_only_descriptions_do_not_read_as_routing_rules(self):
        bad = []
        for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
            meta = frontmatter(skill)
            if meta.get("disable-model-invocation") == "true" and ROUTING.search(meta.get("description", "")):
                bad.append(f"{skill.parent.name}: {meta['description']}")
        self.assertEqual(bad, [])

    def test_no_cursor_only_visualize_command(self):
        hits = [str(p.relative_to(PLUGIN)) for p in PLUGIN.rglob("*.md") if "/visualize" in p.read_text()]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
