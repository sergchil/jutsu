"""Tests for tools/build.py and tools/check.py."""
from __future__ import annotations

import filecmp
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build  # noqa: E402
import check  # noqa: E402


def build_to(tmp: str) -> Path:
    out = Path(tmp) / "plugin"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--out", str(out)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return out


class BuildTest(unittest.TestCase):
    def test_committed_plugin_is_current(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            pa, pb = build_to(a), build_to(b)
            self.assertEqual(build.trees_equal(pa, pb), [])

    def test_built_plugin_passes_the_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = check.check(build_to(tmp))
            self.assertEqual(errors, [], "\n".join(errors[:30]))

    def test_vendor_is_untouched_upstream(self):
        vendor = ROOT / "vendor" / "pstack"
        self.assertTrue((vendor / ".cursor-plugin" / "plugin.json").exists())
        self.assertTrue((vendor / "skills" / "poteto-mode" / "SKILL.md").read_text().startswith("---\nname: Poteto Mode"))

    def test_p3_token_resolves_relative_to_each_file(self):
        self.assertEqual(build.resolve_p3_token("SKILL.md", "{{p3}}/x"), "./x")
        self.assertEqual(build.resolve_p3_token("skills/how/SKILL.md", "{{p3}}/x"), "../../x")
        self.assertEqual(build.resolve_p3_token("skills/poteto-mode/playbooks/a.md", "{{p3}}/x"), "../../../x")

    def test_principles_move_out_of_the_skill_list(self):
        spec = build.load_json(build.SPEC)
        self.assertEqual(build.map_path("skills/principle-prove-it-works/SKILL.md", spec),
                         "principles/principle-prove-it-works.md")
        self.assertIsNone(build.map_path("automations/benny/README.md", spec))
        self.assertIsNone(build.map_path(".cursor-plugin/plugin.json", spec))

    def test_frontmatter_drops_cursor_keys_and_hides_skills_from_the_model(self):
        spec = build.load_json(build.SPEC)
        src = ("---\nname: Poteto Mode\ndescription: d\ndisable-model-invocation: true\nmode: true\n"
               "icon: crown\ncolor: yellow\nreminder: r\n---\nbody\n")
        out = build.transform_frontmatter("skills/poteto-mode/SKILL.md", src, spec)
        self.assertEqual(out, "---\nname: poteto-mode\ndescription: d\ndisable-model-invocation: true\n---\nbody\n")
        agent = build.transform_frontmatter("agents/comment-sicko.md",
                                            "---\nname: Comment Sicko\ndescription: d\nis_background: true\n---\n", spec)
        self.assertEqual(agent, "---\nname: comment-sicko\ndescription: d\n---\n")


class CheckerTest(unittest.TestCase):
    def test_flags_each_class_of_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = build_to(tmp)
            bad = plugin / "skills" / "how" / "SKILL.md"
            bad.write_text(bad.read_text() + "\nUse `Task` with generalPurpose. See [x](missing.md) and `t3_thread_create`. {{p3}}\n")
            (plugin / "hooks" / "p3-mode").chmod(0o644)
            text = "\n".join(check.check(plugin))
            for needle in ("'`Task`'", "'generalPurpose'", "link does not resolve: missing.md",
                           "not a T3 tool: t3_thread_create", "'{{p3}}'", "missing or not executable"):
                self.assertIn(needle, text)


class UpstreamUpdateTest(unittest.TestCase):
    """An upstream change must surface every override and rule that needs porting, in one run."""

    def test_upstream_change_lists_everything_to_port(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            for part in ("vendor", "port", "tools"):
                shutil.copytree(ROOT / part, repo / part)
            vendor = repo / "vendor" / "pstack"
            babysit = vendor / "skills/poteto-mode/playbooks/babysit.md"
            babysit.write_text(babysit.read_text() + "\nA new upstream rule.\n")
            subs = json.loads((repo / "port/subs/lead.json").read_text())["substitutions"]
            target = vendor / "skills/poteto-mode/playbooks/investigation.md"
            target.write_text(target.read_text().replace(subs[0]["pattern"], "the how-to skill"))
            new_skill = vendor / "skills/brand-new/SKILL.md"
            new_skill.parent.mkdir(parents=True)
            new_skill.write_text("---\nname: Brand New\ndescription: d\ndisable-model-invocation: true\n---\nUse the Task tool.\n")
            r = subprocess.run([sys.executable, str(repo / "tools/build.py"), "--out", str(Path(tmp) / "out")],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("2 thing(s) to port", r.stderr)
            self.assertIn("re-merge port/overrides/skills/poteto-mode/playbooks/babysit.md", r.stderr)
            self.assertIn("substitution lead-1 matched nothing", r.stderr)
            r = subprocess.run([sys.executable, str(repo / "tools/build.py"), "--out", str(Path(tmp) / "out"), "--no-lock"],
                               capture_output=True, text=True, timeout=120)
            self.assertIn("substitution lead-1 matched nothing", r.stderr)
            self.assertNotIn("babysit.md", r.stderr)


    def test_partial_relock_still_names_the_other_drifted_overrides(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            for part in ("vendor", "port", "tools"):
                shutil.copytree(ROOT / part, repo / part)
            vendor = repo / "vendor" / "pstack" / "skills/poteto-mode/playbooks"
            for name in ("babysit.md", "shipping.md"):
                (vendor / name).write_text((vendor / name).read_text() + "\nA new upstream rule.\n")
            r = subprocess.run([sys.executable, str(repo / "tools/build.py"), "--relock",
                                "skills/poteto-mode/playbooks/babysit.md"], capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("shipping.md", r.stderr)
            self.assertNotIn("babysit.md", r.stderr)
            lock = json.loads((repo / "port/overrides.lock.json").read_text())
            old = json.loads((ROOT / "port/overrides.lock.json").read_text())
            self.assertNotEqual(lock["skills/poteto-mode/playbooks/babysit.md"], old["skills/poteto-mode/playbooks/babysit.md"])
            self.assertEqual(lock["skills/poteto-mode/playbooks/shipping.md"], old["skills/poteto-mode/playbooks/shipping.md"])


class PortRulesTest(unittest.TestCase):
    def test_bare_skill_commands_become_plugin_commands(self):
        pattern = build.bare_command_pattern(["how", "bro", "figure-it-out"])
        cases = {
            "Use /how or /figure-it-out.": "Use /p3:how or /p3:figure-it-out.",
            "the voice of [`/bro`](../bro/SKILL.md)": "the voice of [`/p3:bro`](../bro/SKILL.md)",
            "/p3:how stays": "/p3:how stays",
            "path skills/how/SKILL.md and ~/x/how and https://a.b/how stay": "path skills/how/SKILL.md and ~/x/how and https://a.b/how stay",
            "/how.md and /howl stay": "/how.md and /howl stay",
        }
        for src, want in cases.items():
            self.assertEqual(build.name_commands(src, pattern), want, src)

    def test_launched_threads_start_from_a_commit_sha(self):
        runtime = (ROOT / "plugin/skills/poteto-mode/references/runtime.md").read_text()
        self.assertIn('"baseRef":"<commit SHA>"', runtime)
        self.assertIn("Workspace preparation failed", runtime)
        self.assertNotIn('"baseRef":"<parent branch>"', runtime)


class DocsTest(unittest.TestCase):
    def test_repo_docs_links_resolve(self):
        import re
        link = re.compile(r"\]\(([^)\s#]+)(#[^)]*)?\)")
        for doc in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
            text = doc.read_text()
            for m in link.finditer(text):
                target = m.group(1)
                if re.match(r"[a-z]+:", target):
                    continue
                self.assertTrue((doc.parent / target).exists(), f"{doc.name}: {target}")

    def test_readme_stays_short(self):
        lines = (ROOT / "README.md").read_text().splitlines()
        self.assertLessEqual(len(lines), 90, "keep the README scannable; move detail to docs/")


class RoleTableTest(unittest.TestCase):
    """setup-pstack's example table must equal the runtime's Roles defaults."""

    def test_setup_example_matches_runtime_defaults(self):
        import re
        runtime = (ROOT / "port/added/skills/poteto-mode/references/runtime.md").read_text()
        section = runtime.split("## Roles", 1)[1].split("\n## ", 1)[0]
        defaults = {}
        for line in section.splitlines():
            m = re.match(r"- ([a-z ,-]+): (`.+`)$", line)
            if m:
                defaults[m.group(1)] = ", ".join(v.strip("`") for v in m.group(2).split(", "))
        setup = (ROOT / "port/overrides/skills/setup-pstack/SKILL.md").read_text()
        block = setup.split("# budget: large (xhigh)\n", 1)[1].split("```", 1)[0]
        example = dict(line.split(": ", 1) for line in block.strip().splitlines())
        self.assertEqual(len(defaults), 17)
        self.assertEqual(example, defaults)


if __name__ == "__main__":
    unittest.main()
