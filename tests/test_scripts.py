"""Runs the bundled bun scripts' own tests and strict type check (watch-pr, orch) on a clean copy of the build."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugin" / "skills" / "poteto-mode" / "scripts"


@unittest.skipUnless(shutil.which("bun"), "bun is not installed")
class BundledScriptsTest(unittest.TestCase):
    def test_bun_suites_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "scripts"
            shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("node_modules"))
            install = subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=copy,
                                     capture_output=True, text=True, timeout=300)
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            run = subprocess.run(["bun", "test"], cwd=copy, capture_output=True, text=True, timeout=300)
            self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-3000:])
            self.assertIn(" 0 fail", run.stdout + run.stderr)
            types = subprocess.run(["bun", "run", "typecheck"], cwd=copy, capture_output=True, text=True, timeout=300)
            self.assertEqual(types.returncode, 0, types.stdout[-3000:] + types.stderr[-3000:])

    def test_check_plan_runs_on_plain_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        r = subprocess.run([node, str(SCRIPTS / "check-plan.mjs"), "--help"], capture_output=True, text=True, timeout=60)
        self.assertNotIn("Cannot find", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
