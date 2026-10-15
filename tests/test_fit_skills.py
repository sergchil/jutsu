"""Fit-audit checks for the skills and agents area, run against a built plugin dir.

Usage: JUTSU_PLUGIN=<built plugin dir> python3 -m unittest test_fit_skills -v
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

PLUGIN = Path(os.environ.get("JUTSU_PLUGIN", Path(__file__).resolve().parent.parent / "plugin"))
OWNED = sorted(p for p in (PLUGIN / "skills").glob("*/SKILL.md") if p.parent.name != "poteto-mode")


def read(rel: str) -> str:
    return (PLUGIN / rel).read_text()


class FitSkillsTest(unittest.TestCase):
    def test_s1_no_speed_in_skills(self):
        hits = [p.parent.name for p in OWNED if re.search(r"fast or standard speed|standard speed", p.read_text())]
        self.assertEqual(hits, [])

    def test_s10_delegate_boilerplate_once_in_runtime(self):
        hits = [p.parent.name for p in OWNED
                if "Pass `options` with `effort` on every call" in p.read_text()
                or "If the `Agent` tool rejects" in p.read_text()]
        self.assertEqual(hits, [])

    def test_s11_no_restated_transcript_path_or_glob_warning(self):
        hits = [p.parent.name for p in OWNED
                if "projects/<dir>/" in p.read_text() or "projects/*/" in p.read_text()]
        self.assertEqual(hits, [])

    def test_s14_skill_creator_note_only_in_authoring(self):
        hits = [p.parent.name for p in OWNED if "`skill-creator` plugin" in p.read_text()]
        self.assertEqual(hits, [])

    def test_d3_recall_has_no_role_sentence(self):
        self.assertNotIn("Pick each subagent's", read("skills/recall/SKILL.md"))

    def test_setup_offers_every_provider_and_its_own_efforts(self):
        t = read("skills/setup-pstack/SKILL.md")
        self.assertNotIn("applies to new sessions", t)
        self.assertNotIn("Another Claude instance with `canRunChildTask: true` is another Claude account", t)
        self.assertIn("canRunCrossProviderChildTask", t)
        self.assertIn("Codex", t)
        self.assertNotRegex(t, r"Every effort is one of `low`")
        self.assertIn(".claude/skills/verify/", t)

    def test_verify_skill_named_verify(self):
        t = read("skills/create-verification-skill/SKILL.md")
        self.assertNotIn("verify-<app>", t)
        self.assertIn(".claude/skills/verify/SKILL.md", t)
        self.assertIn("name: verify", t)
        self.assertNotIn("(no placeholders left): Commit", t)
        self.assertIn(".claude/skills/verify/", read("skills/maintain-verification-skill/SKILL.md"))

    def test_history_covers_every_worktree(self):
        for s in ("recall", "automate-me"):
            self.assertIn("git worktree list", read(f"skills/{s}/SKILL.md"), s)

    def test_automate_me_pr_only_inside_a_repo(self):
        t = read("skills/automate-me/SKILL.md")
        self.assertNotIn("Work in a worktree off main. Commit and open a PR.", t)
        self.assertIn("not in a repo", t)

    def test_ketchup_visuals(self):
        t = read("skills/ketchup/SKILL.md")
        self.assertNotIn("No screenshot yet", t)
        self.assertNotIn("A Markdown table is not a visual", t)
        self.assertIn("Mermaid", t)
        self.assertIn("html_render", t)

    def test_teach_has_no_generated_images(self):
        t = read("skills/teach/SKILL.md")
        self.assertNotIn("generated image", t)
        self.assertIn("mermaid", t.lower())

    def test_poteto_agent_router_path(self):
        t = read("agents/poteto-agent.md")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/poteto-mode/SKILL.md", t)
        self.assertNotIn("highest `version`", t)
        self.assertIn("description: Delegate", t)

    def test_principle_names_ts_skill_by_path(self):
        t = read("principles/principle-type-system-discipline.md")
        self.assertIn("skills/typescript-best-practices/SKILL.md", t)

    def test_model_invocable_descriptions_route(self):
        for s in ("typescript-best-practices", "tdd", "benchmark-checklist"):
            desc = re.search(r"^description: (.*)$", read(f"skills/{s}/SKILL.md"), re.M).group(1)
            self.assertNotRegex(desc, r"[Rr]un it with /", s)
            self.assertRegex(desc, r"Use (only )?when", s)

    def test_poteto_help(self):
        t = read("skills/poteto-help/SKILL.md")
        self.assertNotIn("cursor/plugins/blob/main/pstack/docs/guide", t)
        self.assertNotIn("written for Cursor", t)
        self.assertNotIn("Other tools that read the Agent Skills format", t)
        self.assertNotIn("Cursor's `/deslop`", t)
        self.assertNotIn("Cursor's `/create-skill`", t)
        self.assertNotIn("/make-bot-ui", t)
        self.assertNotIn("applies to new sessions", t)
        self.assertIn("`$jutsu:", t)
        self.assertNotIn("verify-<app>", read("skills/poteto-help/references/recipes.md"))


if __name__ == "__main__":
    unittest.main()
