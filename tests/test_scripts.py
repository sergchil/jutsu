"""Runs the bundled scripts' own tests and strict type check (watch-pr, orch) on a clean copy of the build,
checks that the runtime install stays production-only, and keeps check-plan in step with the plan template.

JUTSU_PLUGIN points the tests at another build (a preview) instead of plugin/.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = Path(os.environ.get("JUTSU_PLUGIN") or ROOT / "plugin")
SCRIPTS = PLUGIN / "skills" / "poteto-mode" / "scripts"
PLAYBOOK = PLUGIN / "skills" / "poteto-mode" / "playbooks" / "multi-phase-plan.md"
# The same rule as check-plan.mjs: <text> starting with a letter, not right after an identifier.
PLACEHOLDER = re.compile(r"(?<![A-Za-z0-9_])<([A-Za-z][^<>\n]*)>")
# check-plan.mjs must run on either; the playbook says bun, with node as the fallback.
RUNTIMES = [p for p in (shutil.which("bun"), shutil.which("node")) if p]


def copy_scripts(tmp: str) -> Path:
    copy = Path(tmp) / "scripts"
    shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("node_modules"))
    return copy


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


@unittest.skipUnless(shutil.which("bun"), "bun is not installed")
class BundledScriptsTest(unittest.TestCase):
    def test_bun_suites_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_scripts(tmp)
            # The tests and the type check need the dev dependencies, so this copy gets a full install.
            install = subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=copy,
                                     capture_output=True, text=True, timeout=300)
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            # orch's tests spawn real git and fake gh processes; under load they pass bun's
            # 5 s default, which made this suite flaky. 30 s keeps a hung test visible.
            run = subprocess.run(["bun", "test", "--timeout", "30000"], cwd=copy, capture_output=True, text=True, timeout=300)
            self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-3000:])
            self.assertIn(" 0 fail", run.stdout + run.stderr)
            types = subprocess.run(["bun", "run", "typecheck"], cwd=copy, capture_output=True, text=True, timeout=300)
            self.assertEqual(types.returncode, 0, types.stdout[-3000:] + types.stderr[-3000:])

    def test_first_run_installs_only_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_scripts(tmp)
            for launcher in (["orch/orch.ts", "--help"], ["watch-pr/watch-pr", "--help"]):
                r = subprocess.run(["bun", *launcher], cwd=copy, capture_output=True, text=True, timeout=300)
                self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            modules = copy / "node_modules"
            self.assertTrue((modules / "commander" / "package.json").is_file())
            for dev in ("typescript", "bun-types", "@types"):
                self.assertFalse((modules / dev).exists(), f"{dev} was installed by the runtime bootstrap")
            self.assertLess(dir_size(modules), 2_000_000)


@unittest.skipUnless(RUNTIMES, "neither bun nor node is installed")
class CheckPlanTest(unittest.TestCase):
    def check(self, *args, runtime: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([runtime or RUNTIMES[0], str(SCRIPTS / "check-plan.mjs"), *args],
                              capture_output=True, text=True, timeout=60)

    def skeleton(self) -> str:
        m = re.search(r"^````markdown\n(.*?)^````$", PLAYBOOK.read_text(encoding="utf-8"), re.S | re.M)
        self.assertIsNotNone(m, "multi-phase-plan.md has no ````markdown skeleton")
        return m.group(1)

    def run_plan(self, text: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(text, encoding="utf-8")
            return self.check(str(plan))

    def test_help_prints_usage_on_every_runtime(self):
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime):
                r = self.check("--help", runtime=runtime)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("Usage:", r.stdout)
                self.assertNotIn("ENOENT", r.stdout + r.stderr)

    def test_no_argument_is_a_usage_error(self):
        r = self.check()
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage:", r.stderr)

    def test_the_raw_skeleton_fails_on_its_placeholders(self):
        r = self.run_plan(self.skeleton())
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertGreater(r.stderr.count("unfilled placeholder"), 20, r.stderr)

    def test_the_skeleton_passes_once_every_placeholder_is_filled(self):
        text = self.skeleton()
        while True:
            filled = PLACEHOLDER.sub("x", text)
            if filled == text:
                break
            text = filled
        r = self.run_plan(text)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 PR sections, 0 problems", r.stdout)


if __name__ == "__main__":
    unittest.main()
