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

    def test_plugin_token_resolves_relative_to_each_file(self):
        self.assertEqual(build.resolve_plugin_token("SKILL.md", "{{plugin}}/x"), "./x")
        self.assertEqual(build.resolve_plugin_token("skills/how/SKILL.md", "{{plugin}}/x"), "../../x")
        self.assertEqual(build.resolve_plugin_token("skills/poteto-mode/playbooks/a.md", "{{plugin}}/x"), "../../../x")

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
            bad.write_text(bad.read_text() + "\nUse `Task` with generalPurpose. See [x](missing.md) and `t3_thread_create`. {{plugin}}\n"
                           "Then `git worktree remove --force <path>` and `rm -rf` what is left.\n")
            (plugin / "hooks" / "jutsu-mode").chmod(0o644)
            text = "\n".join(check.check(plugin))
            for needle in ("'`Task`'", "'generalPurpose'", "link does not resolve: missing.md",
                           "not a T3 tool: t3_thread_create", "'{{plugin}}'", "missing or not executable",
                           "'worktree remove --force'", "'rm -rf'"):
                self.assertIn(needle, text)

    def test_conflict_markers_in_the_plugin_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = build_to(tmp)
            how = plugin / "skills" / "how" / "SKILL.md"
            how.write_text(how.read_text() + "<<<<<<< jutsu override\nours\n=======\ntheirs\n>>>>>>> upstream abc\n")
            text = "\n".join(check.check(plugin))
            for marker in ("'<<<<<<<'", "'======='", "'>>>>>>>'"):
                self.assertIn(f"unresolved merge conflict marker {marker}", text)

    def test_allowances_are_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = build_to(tmp)
            runtime = plugin / check.RUNTIME
            runtime.write_text(runtime.read_text() + "\nUse the `AskQuestion` tool.\n")
            text = "\n".join(check.check(plugin))
            self.assertIn(f"{check.RUNTIME}:", text)
            self.assertIn("'AskQuestion'", text)

    def test_an_allowance_that_excuses_nothing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = build_to(tmp)
            runtime = plugin / check.RUNTIME
            lines = [l for l in runtime.read_text().splitlines(True) if "| `AskQuestion` |" not in l]
            runtime.write_text("".join(lines))
            text = "\n".join(check.check(plugin))
            self.assertIn("on the line with '| `AskQuestion` |' excuses nothing", text)

    def test_worktree_handoff_is_named_only_in_the_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = build_to(tmp)
            how = plugin / "skills" / "how" / "SKILL.md"
            how.write_text(how.read_text() + "\nThen call `t3_worktree_handoff` to move the thread.\n")
            runtime = plugin / check.RUNTIME
            runtime.write_text(runtime.read_text() + "\nDo not call `t3_worktree_handoff`. It stalls the session.\n")
            text = "\n".join(check.check(plugin))
            self.assertIn("skills/how/SKILL.md", text)
            self.assertIn("'t3_worktree_handoff'", text)
            self.assertNotIn(f"{check.RUNTIME}:", text)


class DenyRulesTest(unittest.TestCase):
    """Every DENY rule proves itself: its bad line hits it, its good line hits no rule."""

    def test_every_rule_has_examples_that_pass(self):
        self.assertTrue(all(r["bad"] and r["good"] for r in check.DENY))
        self.assertEqual(check.self_test(), [])

    def test_a_dead_or_over_wide_rule_fails_its_self_test(self):
        dead = check.rule(r"\bTaskk\b", "Use the Task tool.", "Use the `Agent` tool.")
        wide = check.rule(r"Agent", "Use the Agent tool.", "Use the `Agent` tool.")
        problems = "\n".join(check.self_test([dead, wide]))
        self.assertIn("does not match its own bad example 'Use the Task tool.'", problems)
        self.assertIn("its good example 'Use the `Agent` tool.' matches rule 'Agent'", problems)


def copy_repo(tmp: str) -> Path:
    import shutil
    repo = Path(tmp) / "repo"
    for part in ("vendor", "port", "tools"):
        shutil.copytree(ROOT / part, repo / part, ignore=shutil.ignore_patterns("__pycache__"))
    return repo


def build_copy(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(repo / "tools/build.py"), "--out", str(repo.parent / "out"), *args],
                          capture_output=True, text=True, timeout=120)


class OverrideRulesTest(unittest.TestCase):
    def test_conflict_marker_in_port_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            ov = repo / "port/overrides/skills/how/SKILL.md"
            n = len(ov.read_text().splitlines())
            ov.write_text(ov.read_text() + "<<<<<<< jutsu override\nx\n=======\ny\n>>>>>>> upstream z\n")
            r = build_copy(repo, "--no-lock")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(f"port/overrides/skills/how/SKILL.md:{n + 1}: unresolved merge conflict marker", r.stderr)
            self.assertIn(f"port/overrides/skills/how/SKILL.md:{n + 3}: unresolved merge conflict marker '======='",
                          r.stderr)

    def test_an_override_that_matches_upstream_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            vendor = repo / "vendor/pstack"
            raw = "skills/poteto-mode/scripts/check-plan.mjs"
            (repo / "port/overrides" / raw).write_bytes((vendor / raw).read_bytes())
            # The same holds for an override equal to what the build makes of upstream.
            teach = "skills/teach/SKILL.md"
            spec = build.load_json(build.SPEC)
            made = build.apply_subs(teach, build.transform_frontmatter(teach, (vendor / teach).read_text(), spec),
                                    build.compile_subs(build.load_substitutions()))
            (repo / "port/overrides" / teach).write_text(made)
            r = build_copy(repo, "--no-lock")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            for path in (raw, teach):
                self.assertIn(f"port/overrides/{path} matches upstream; delete the override and its lock entry",
                              r.stderr)

    def test_every_override_needs_a_reason_and_every_reason_an_override(self):
        reasons = json.loads((ROOT / "port/overrides.json").read_text())
        overrides = {p.relative_to(ROOT / "port/overrides").as_posix()
                     for p in (ROOT / "port/overrides").rglob("*") if p.is_file() and p.name != ".DS_Store"}
        self.assertEqual(build.reason_problems(reasons, overrides), [])
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            path = repo / "port/overrides.json"
            reasons = json.loads(path.read_text())
            del reasons["skills/how/SKILL.md"]
            reasons["skills/gone/SKILL.md"] = {"kind": "runtime", "why": "w.", "upstream": None}
            reasons["skills/teach/SKILL.md"] = {"kind": "whim", "why": "", "upstream": "#12"}
            path.write_text(json.dumps(reasons))
            r = build_copy(repo, "--no-lock")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            for needle in ("port/overrides/skills/how/SKILL.md has no entry in port/overrides.json",
                           "port/overrides.json names skills/gone/SKILL.md, which has no override",
                           "skills/teach/SKILL.md: kind must be one of",
                           "skills/teach/SKILL.md: why must be one short sentence",
                           "skills/teach/SKILL.md: upstream must be an issue or PR URL, or null"):
                self.assertIn(needle, r.stderr)


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
            "Use /how or /figure-it-out.": "Use /jutsu:how or /jutsu:figure-it-out.",
            "the voice of [`/bro`](../bro/SKILL.md)": "the voice of [`/jutsu:bro`](../bro/SKILL.md)",
            "/jutsu:how stays": "/jutsu:how stays",
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
        for doc in [*sorted(ROOT.glob("*.md")), *sorted((ROOT / "docs").glob("*.md")),
                    ROOT / ".github" / "pull_request_template.md"]:
            text = doc.read_text()
            for m in link.finditer(text):
                target = m.group(1)
                if re.match(r"[a-z]+:", target):
                    continue
                self.assertTrue((doc.parent / target).exists(), f"{doc.name}: {target}")

    def test_readme_stays_short(self):
        lines = (ROOT / "README.md").read_text().splitlines()
        self.assertLessEqual(len(lines), 90, "keep the README scannable; move detail to docs/")

    def test_website_files_exist(self):
        import re
        page = (ROOT / "docs" / "index.html").read_text()
        local = [m for m in re.findall(r'(?:src|href)="([^"#:]+)"', page)]
        self.assertTrue(local)
        for path in local:
            self.assertTrue((ROOT / "docs" / path).is_file(), f"docs/index.html: {path}")
        self.assertTrue((ROOT / "docs" / ".nojekyll").is_file(), "docs/.nojekyll keeps GitHub Pages from running Jekyll")


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
