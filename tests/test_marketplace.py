"""The repo root is a Claude Code marketplace that lists jutsu (docs: code.claude.com/docs/en/plugin-marketplaces)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

    def test_required_fields_and_names(self):
        self.assertEqual(self.data["name"], "jutsu")
        self.assertTrue(self.data["owner"]["name"])
        self.assertRegex(self.data["name"], NAME)
        self.assertNotIn("..", self.data["name"])

    def test_lists_the_built_plugin_under_its_manifest_name(self):
        [entry] = self.data["plugins"]
        self.assertEqual(entry["source"], "./plugin")
        manifest = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        # The entry name is the install id; a different manifest name breaks installs by that name.
        self.assertEqual(entry["name"], manifest["name"])
        # plugin.json's version wins over the entry's, and validate warns when both are set.
        self.assertNotIn("version", entry)
        self.assertTrue(manifest.get("version"))

    @unittest.skipUnless(shutil.which("claude"), "claude is not installed")
    def test_claude_plugin_validate_passes(self):
        # A throwaway config dir, so the check never writes to the user's Claude config.
        with tempfile.TemporaryDirectory() as config:
            r = subprocess.run(["claude", "plugin", "validate", str(ROOT)], capture_output=True, text=True, timeout=120,
                               env={**os.environ, "CLAUDE_CONFIG_DIR": config})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Validation passed", r.stdout)


if __name__ == "__main__":
    unittest.main()
