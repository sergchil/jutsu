"""Tests for tools/adapter_diff.py: upstream's Claude Code adapter against jutsu's runtime map."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adapter_diff  # noqa: E402


def record() -> dict:
    return json.loads(adapter_diff.RECORD.read_text())


class AdapterDiffTest(unittest.TestCase):
    def setUp(self):
        self.text = adapter_diff.ADAPTER.read_text()

    def test_every_row_is_reviewed_and_still_true(self):
        differences, problems = adapter_diff.diff(self.text, record(), ROOT / "plugin")
        self.assertEqual(problems, [])
        self.assertTrue(differences)
        r = subprocess.run([sys.executable, str(ROOT / "tools/adapter_diff.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_parses_each_table_row(self):
        rows = adapter_diff.parse_rows(self.text)
        self.assertEqual(len(rows), len(record()))
        self.assertIn(("Tools", "`Task`", "`Agent`"), rows)
        sections = {s for s, _, _ in rows}
        self.assertEqual(sections, {"Tools", "Subagent fields", "Models", "Paths", "Cursor-only features"})

    def test_known_differences_are_recorded(self):
        rec = record()
        for cursor in ('`environment: "cloud"`', "A `grok-*`, `gpt-*`, or other non-Claude slug", "Transcripts in"):
            k = next(k for k in rec if cursor in k)
            self.assertEqual(rec[k]["verdict"], "different", k)
            self.assertTrue(rec[k]["why"], k)

    def test_upstream_changes_are_reported(self):
        changed = self.text.replace("| `Task` | `Agent` |", "| `Task` | `Agent` with `isolation: \"worktree\"` |")
        changed = changed.replace("| `file_attachments` | List the paths in the brief. |\n", "")
        changed = changed.replace("## Paths\n\n| Cursor | Claude Code |\n| --- | --- |\n",
                                  "## Paths\n\n| Cursor | Claude Code |\n| --- | --- |\n| `.cursorignore` | `isolation: \"worktree\"` |\n")
        self.assertNotEqual(changed, self.text)
        _, problems = adapter_diff.diff(changed, record(), ROOT / "plugin")
        text = "\n".join(problems)
        self.assertIn("adapter row changed, re-review it and update port/adapter.json: Tools | `Task`", text)
        self.assertIn("names a row the adapter no longer has: Subagent fields | `file_attachments`", text)
        self.assertIn("new adapter row, review it and add it to port/adapter.json: Paths | `.cursorignore`", text)
        self.assertIn('jutsu limits `isolation: "worktree"`', text)

    def test_a_jutsu_change_that_breaks_a_recorded_answer_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "plugin"
            shutil.copytree(ROOT / "plugin", plugin, ignore=shutil.ignore_patterns("node_modules"))
            runtime = plugin / adapter_diff.RUNTIME
            runtime.write_text(runtime.read_text().replace("Do not use `Agent` `isolation: \"worktree\"`", "Use it"))
            _, problems = adapter_diff.diff(self.text, record(), plugin)
            self.assertTrue(any('Subagent fields | `environment: "cloud"`' in p and "no longer matches" in p
                                for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
