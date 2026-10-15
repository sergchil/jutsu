"""Pins the T3 fit of the playbooks and router (see tools/check_fit_playbooks.py)."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FitPlaybooksTest(unittest.TestCase):
    def test_built_playbooks_fit_t3(self):
        run = subprocess.run([sys.executable, str(ROOT / "tools" / "check_fit_playbooks.py"), str(ROOT / "plugin")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
