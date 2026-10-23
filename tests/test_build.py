"""Tests for tools/build.py and tools/check.py."""
from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertTrue((vendor / "skills" / "poteto-mode" / "SKILL.md").read_text().startswith("---\nname: poteto-mode\n"))

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

    def test_model_invocable_skills_keep_auto_invocation(self):
        spec = build.load_json(build.SPEC)
        self.assertEqual(sorted(spec["frontmatter"]["model_invocable"]),
                         ["benchmark-checklist", "tdd", "typescript-best-practices"])
        src = "---\nname: tdd\ndescription: Use when asked for TDD.\ndisable-model-invocation: true\n---\nbody\n"
        out = build.transform_frontmatter("skills/tdd/SKILL.md", src, spec)
        self.assertEqual(out, "---\nname: tdd\ndescription: Use when asked for TDD.\n---\nbody\n")

    def test_substitutions_come_only_from_port_subs(self):
        self.assertFalse((ROOT / "port" / "substitutions.json").exists())
        ids = [s["id"] for s in build.load_substitutions()]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))


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

    def test_the_runtime_is_checked_like_any_other_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = mini_plugin(tmp)
            runtime = plugin / check.RUNTIME
            runtime.write_text("| `AskQuestion` | `AskUserQuestion` |\n| cloud agent | a worktree |\n")
            text = "\n".join(check.check(plugin))
            self.assertIn(f"{check.RUNTIME}:1: Cursor-only, unresolved, or unsafe text: 'AskQuestion'", text)
            self.assertIn(f"{check.RUNTIME}:2: Cursor-only, unresolved, or unsafe text: 'cloud agent'", text)

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


def mini_plugin(tmp: str) -> Path:
    """The smallest plugin tree check.check accepts, so a test sees only its own problem."""
    plugin = Path(tmp) / "mini"
    files = {
        ".claude-plugin/plugin.json": json.dumps({"name": "jutsu", "agents": []}),
        "SKILL.md": "---\nname: jutsu\ndescription: Turn on poteto mode.\ndisable-model-invocation: true\n---\n",
        "skills/how/SKILL.md": "---\nname: how\ndescription: Explain how code works.\n"
                               "disable-model-invocation: true\n---\nbody\n",
        "skills/poteto-mode/SKILL.md": "---\nname: poteto-mode\ndescription: The router.\n"
                                       "disable-model-invocation: true\n---\n",
        check.RUNTIME: "# runtime\n",
        "hooks/hooks.json": json.dumps({"hooks": {}}),
        "hooks/jutsu-mode": "#!/bin/sh\nexit 0\n",
    }
    for rel, text in files.items():
        (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
        (plugin / rel).write_text(text)
    (plugin / "hooks/jutsu-mode").chmod(0o755)
    return plugin


def skill(plugin: Path, name: str, description: str, user_only: bool) -> None:
    flag = "disable-model-invocation: true\n" if user_only else ""
    path = plugin / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n{flag}---\nbody\n")


class SkillTextTest(unittest.TestCase):
    """Text Claude Code shows people, and which skills Claude may invoke on its own."""

    def problems(self, plugin: Path, invocable=()) -> str:
        with mock.patch.object(check, "model_invocable", return_value=set(invocable)):
            return "\n".join(check.check(plugin))

    def test_the_mini_plugin_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.problems(mini_plugin(tmp)), "")

    def test_a_slash_only_description_must_not_read_as_a_routing_rule(self):
        # cursor/plugins#367: "Use when the user says reflect" in the / menu reads as if
        # the skill fires on its own.
        with tempfile.TemporaryDirectory() as tmp:
            plugin = mini_plugin(tmp)
            skill(plugin, "reflect", "Use when the user says reflect.", user_only=True)
            self.assertIn("skills/reflect/SKILL.md: a slash-only description must not read as a routing rule",
                          self.problems(plugin))

    def test_a_model_invocable_skill_may_route_and_must_not_be_user_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = mini_plugin(tmp)
            skill(plugin, "tdd", "Use when asked for TDD.", user_only=False)
            self.assertEqual(self.problems(plugin, {"tdd"}), "")
            skill(plugin, "tdd", "Run TDD.", user_only=True)
            self.assertIn("skills/tdd/SKILL.md: port/spec.json lists it as model_invocable",
                          self.problems(plugin, {"tdd"}))
            skill(plugin, "tdd", "Run TDD.", user_only=False)
            self.assertIn("skills/tdd/SKILL.md: jutsu skills are user-invoked", self.problems(plugin))

    def test_spec_names_the_invocable_skills(self):
        self.assertEqual(check.model_invocable(), {"benchmark-checklist", "tdd", "typescript-best-practices"})

    def test_cursor_visualize_command_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = mini_plugin(tmp)
            how = plugin / "skills/how/SKILL.md"
            how.write_text(how.read_text() + "Build the chart with `/visualize`.\n")
            self.assertIn("'/visualize'", self.problems(plugin))


class T3ToolNameTest(unittest.TestCase):
    """T3 tool names come from tools/t3-tools.txt, not from a pattern kept in check.py."""

    def test_header_lines_are_not_tool_names(self):
        self.assertFalse(any(n.startswith("#") or " " in n for n in check.T3_TOOLS))
        self.assertIn("write_pull_request_guides", check.T3_TOOLS)

    def test_typos_of_listed_tools_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = mini_plugin(tmp)
            how = plugin / "skills/how/SKILL.md"
            how.write_text(how.read_text() + "Call `write_pull_request_guide`, then `read_pull_request_guide`, "
                           "`t3_thread_create`, and `run_scheduled_tasks_now`. Keep `run_in_background`.\n")
            text = "\n".join(check.check(plugin))
            for bad in ("write_pull_request_guide", "t3_thread_create", "run_scheduled_tasks_now"):
                self.assertIn(f"not a T3 tool: {bad}\n", text + "\n")
            self.assertNotIn("not a T3 tool: read_pull_request_guide\n", text + "\n")
            self.assertNotIn("run_in_background", text)

    def test_every_listed_tool_passes(self):
        self.assertFalse([t for t in check.T3_TOOLS if check.unknown_t3_tool(t)])
        self.assertEqual(check.self_test_other(), [])


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


class JunkFileTest(unittest.TestCase):
    """Finder's .DS_Store and other dotfiles are never read as overrides, added files, or upstream files."""

    def test_dotfiles_are_skipped_by_build_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            junk = b"\x00\x00\x00\x01Bud1\x00"
            for d in ("port/overrides", "port/overrides/skills/how", "port/added", "port/added/hooks",
                      "vendor/pstack", "vendor/pstack/skills/teach"):
                (repo / d / ".DS_Store").write_bytes(junk)
            (repo / "port/overrides/skills/how/._SKILL.md").write_bytes(junk)
            r = build_copy(repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = repo.parent / "out"
            dotfiles = [p for p in out.rglob(".*") if p.is_file()]
            self.assertEqual(dotfiles, [])
            self.assertTrue((out / ".claude-plugin" / "plugin.json").is_file())
            shutil.copytree(out, repo / "plugin")
            (repo / "plugin/skills/.DS_Store").write_bytes(junk)
            r = subprocess.run([sys.executable, str(repo / "tools/build.py"), "--check"],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


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


class StoreTest(unittest.TestCase):
    """The runtime's Store snippet must put .jutsu/ in the main checkout, even when run
    from a linked worktree, because T3's cleanup deletes worktrees whose only local files
    are git-ignored (apps/server/src/storageCleanup.ts:330-366)."""

    def snippet(self) -> str:
        runtime = (ROOT / "port/added/skills/poteto-mode/references/runtime.md").read_text()
        store = runtime.split("## Store", 1)[1].split("\n## ", 1)[0]
        m = re.search(r"```sh\n(.*?)```", store, re.S)
        self.assertIsNotNone(m, "the Store section has no sh block")
        return m.group(1)

    def git(self, *args, cwd):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_store_lives_in_the_main_checkout_from_a_linked_worktree(self):
        shells = [s for s in ("sh", "zsh", "bash") if shutil.which(s)]
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp).resolve() / "repo"
            main.mkdir()
            self.git("init", "-q", cwd=main)
            (main / "README.md").write_text("x\n")
            self.git("add", "-A", cwd=main)
            self.git("commit", "-qm", "init", cwd=main)
            wt = Path(tmp).resolve() / "t3-worktrees" / "repo" / "t3-abc"
            self.git("worktree", "add", "-q", "-b", "t3/abc", str(wt), cwd=main)
            # The old rule ("at the repo root") resolves to the worktree, which T3 may delete.
            self.assertEqual(self.git("rev-parse", "--show-toplevel", cwd=wt), str(wt))
            for shell in shells:
                for where in (wt, main, wt):  # twice from the worktree: the exclude lines stay single
                    with self.subTest(shell=shell, where=where.name):
                        r = subprocess.run([shell, "-c", self.snippet()], cwd=where, capture_output=True, text=True,
                                           env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1"))
                        self.assertEqual(r.returncode, 0, r.stderr)
                        self.assertEqual(r.stdout.strip(), str(main / ".jutsu"))
            exclude = (main / ".git" / "info" / "exclude").read_text().splitlines()
            self.assertEqual([l for l in exclude if not l.startswith("#")], [".jutsu/", ".audit/"])
            (main / ".jutsu" / "plan").mkdir(parents=True)
            (main / ".jutsu" / "plan" / "resume.md").write_text("note\n")
            (main / ".audit").mkdir()
            (main / ".audit" / "plan.todo.md").write_text("- [ ] x\n")
            (wt / ".jutsu").mkdir()
            self.assertEqual(self.git("status", "--porcelain", cwd=main), "")
            self.assertEqual(self.git("status", "--porcelain", cwd=wt), "")


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
        block = setup.split("# budget: balanced (defaults)\n", 1)[1].split("```", 1)[0]
        example = dict(line.split(": ", 1) for line in block.strip().splitlines())
        self.assertEqual(len(defaults), 17)
        self.assertEqual(example, defaults)


if __name__ == "__main__":
    unittest.main()
