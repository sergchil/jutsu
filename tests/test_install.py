"""Tests for tools/install.py, run against a throwaway HOME so no real config is touched."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "tools" / "install.py"
PLUGIN = (ROOT / "plugin").resolve()


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.default = self.home / ".claude"
        self.work = self.home / "claude-work"
        self.envdir = self.home / "claude-env"
        self.off = self.home / "claude-off"
        for d in (self.default, self.work, self.envdir, self.off):
            d.mkdir()
        self.settings = self.home / ".t3" / "userdata" / "settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"providerInstances": {
            "codex": {"driver": "codex", "config": {"homePath": "~/should-not-matter"}},
            "claude-work": {"driver": "claudeAgent", "config": {"homePath": "~/claude-work"}},
            "claude-env": {"driver": "claudeAgent",
                           "environment": [{"name": "CLAUDE_CONFIG_DIR", "value": str(self.envdir)}],
                           "config": {"homePath": ""}},
            "claude-off": {"driver": "claudeAgent", "enabled": False, "config": {"homePath": "~/claude-off"}},
            "claude-off2": {"driver": "claudeAgent", "config": {"enabled": False, "homePath": "~/claude-off"}},
            "claude-dup": {"driver": "claudeAgent", "config": {"homePath": ""}},
        }}))
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        self.env.update(HOME=str(self.home), PATH="/usr/bin:/bin")

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(INSTALL), "--t3-settings", str(self.settings), *args],
                              capture_output=True, text=True, env=self.env, timeout=30)

    def link(self, d: Path) -> Path:
        return d / "skills" / "p3"

    def test_links_every_claude_config_dir_t3_uses(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for d in (self.default, self.work, self.envdir):
            self.assertTrue(self.link(d).is_symlink(), d)
            self.assertEqual(self.link(d).resolve(), PLUGIN)
        self.assertFalse((self.home / "should-not-matter").exists())
        self.assertEqual(r.stdout.count("linked "), 3)
        self.assertFalse(self.link(self.off).exists())
        self.assertIn("skip: T3 instance claude-off is disabled", r.stdout)
        self.assertIn("skip: T3 instance claude-off2 is disabled", r.stdout)

    def test_expands_tilde_in_an_instance_config_dir(self):
        s = json.loads(self.settings.read_text())
        s["providerInstances"]["claude-tilde"] = {"driver": "claudeAgent", "environment": [
            {"name": "CLAUDE_CONFIG_DIR", "value": "~/claude-tilde"}], "config": {"homePath": ""}}
        self.settings.write_text(json.dumps(s))
        (self.home / "claude-tilde").mkdir()
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(self.link(self.home / "claude-tilde").is_symlink())

    def test_links_both_home_and_a_shell_config_dir(self):
        shell_dir = self.home / "shell-claude"
        shell_dir.mkdir()
        self.env["CLAUDE_CONFIG_DIR"] = str(shell_dir)
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(self.link(shell_dir).is_symlink())
        self.assertTrue(self.link(self.default).is_symlink())

    def test_is_idempotent(self):
        self.run_install()
        r = self.run_install()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.count("already linked"), 3)

    def test_never_writes_settings(self):
        settings = self.default / "settings.json"
        settings.write_text('{"enabledPlugins": {}}')
        before = settings.read_bytes()
        self.run_install()
        self.run_install("--uninstall", "--purge")
        self.assertEqual(settings.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.default.iterdir()), ["settings.json", "skills"])

    def test_refuses_to_replace_a_foreign_entry(self):
        (self.default / "skills" / "p3").mkdir(parents=True)
        (self.default / "skills" / "p3" / "SKILL.md").write_text("mine")
        r = self.run_install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not p3's link", r.stdout)
        self.assertEqual((self.default / "skills" / "p3" / "SKILL.md").read_text(), "mine")

    def test_refuses_a_foreign_symlink(self):
        other = self.home / "other-skill"
        other.mkdir()
        (self.default / "skills").mkdir()
        self.link(self.default).symlink_to(other)
        r = self.run_install()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.link(self.default).resolve(), other.resolve())

    def test_relinks_a_dangling_link_from_a_moved_checkout(self):
        (self.default / "skills").mkdir()
        self.link(self.default).symlink_to(self.home / "old" / ROOT.name / "plugin")
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.link(self.default).resolve(), PLUGIN)

    def test_refuses_a_dangling_link_into_another_project(self):
        (self.default / "skills").mkdir()
        foreign = self.home / "somewhere" / "plugin"
        self.link(self.default).symlink_to(foreign)
        r = self.run_install()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(os.readlink(self.link(self.default)), str(foreign))
        self.run_install("--uninstall")
        self.assertTrue(self.link(self.default).is_symlink())

    def test_reports_conflicting_pstack_ports(self):
        (self.default / "settings.json").write_text(json.dumps({"enabledPlugins": {
            "pstack@pstack-claude": True, "other@x": True, "pstack@off": False}}))
        (self.work / "skills" / "p3-mode").mkdir(parents=True)
        r = self.run_install()
        self.assertIn("plugin pstack@pstack-claude is enabled", r.stdout)
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.default.resolve()} claude plugin disable pstack@pstack-claude", r.stdout)
        self.assertNotIn("pstack@off", r.stdout)
        self.assertIn("p3-mode is installed (another pstack port)", r.stdout)

    def test_uninstall_removes_only_p3_links(self):
        self.run_install()
        (self.default / "skills" / "keep-me").mkdir()
        data = self.default / "plugins" / "data" / "p3-skills-dir"
        data.mkdir(parents=True)
        r = self.run_install("--uninstall")
        self.assertEqual(r.returncode, 0)
        for d in (self.default, self.work, self.envdir):
            self.assertFalse(self.link(d).exists() or self.link(d).is_symlink())
        self.assertTrue((self.default / "skills" / "keep-me").is_dir())
        self.assertTrue(data.is_dir())
        self.run_install("--uninstall", "--purge")
        self.assertFalse(data.exists())

    def test_dry_run_changes_nothing(self):
        r = self.run_install("--dry-run")
        self.assertEqual(r.returncode, 0)
        for d in (self.default, self.work, self.envdir):
            self.assertFalse(self.link(d).exists())

    def test_skips_config_dirs_that_do_not_exist(self):
        self.work.rmdir()
        r = self.run_install()
        self.assertIn("this config dir does not exist yet", r.stdout)
        self.assertFalse(self.work.exists())

    def test_missing_t3_settings_still_installs_the_default(self):
        self.settings.unlink()
        r = self.run_install()
        self.assertEqual(r.returncode, 0)
        self.assertTrue(self.link(self.default).is_symlink())


if __name__ == "__main__":
    unittest.main()
