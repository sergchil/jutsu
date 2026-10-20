"""Runs the bundled checkpoint.sh on real git repos: Pause safely saves a checkpoint, Session pickup verifies it.

The checkpoint records the branch, head commit, worktree, and the hashes of the resume note and todo file in
the main checkout's store, so it survives T3 deleting the worktree. The idea comes from pstack-claude's
resume.mjs (MIT), which verifies a checkpoint before a pickup trusts it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(os.environ.get("JUTSU_PLUGIN") or ROOT / "plugin") / "skills" / "poteto-mode" / "scripts" / "checkpoint.sh"


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name).resolve()
        (base / "gitconfig").write_text("")
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        self.main = base / "repo"
        self.git(base, "init", "-q", "-b", "main", str(self.main))
        (self.main / "a.txt").write_text("a\n")
        self.git(self.main, "add", "-A")
        self.git(self.main, "commit", "-qm", "init")
        self.wt = base / "t3" / "worktrees" / "repo" / "feature"
        self.git(self.main, "worktree", "add", "-q", "-b", "feature", str(self.wt), "main")
        (self.wt / "b.txt").write_text("b\n")
        self.git(self.wt, "add", "-A")
        self.git(self.wt, "commit", "-qm", "wip: feature")
        self.head = self.git(self.wt, "rev-parse", "HEAD")
        self.store = self.main / ".jutsu" / "feat"
        self.store.mkdir(parents=True)
        (self.store / "resume.md").write_text("# Resume\nNext: write the test.\n")
        (self.main / ".audit").mkdir()
        (self.main / ".audit" / "feat.todo.md").write_text("- [x] one\n- [ ] two\n")
        # The store is excluded in every checkout, as the runtime's Store snippet does.
        exclude = Path(self.git(self.wt, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(".jutsu/\n.audit/\n")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def run_script(self, cwd, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd, env=self.env, capture_output=True,
                              text=True, timeout=60)

    def test_save_writes_the_checkpoint_in_the_main_checkout(self):
        r = self.run_script(self.wt, "save", "feat")
        self.assertEqual(r.returncode, 0, r.stderr)
        path = self.store / "checkpoint"
        self.assertEqual(r.stdout.strip(), str(path))
        text = path.read_text()
        self.assertIn(f"head: {self.head}", text)
        self.assertIn("branch: feature", text)
        self.assertIn(f"worktree: {self.wt}", text)
        self.assertIn("dirty: 0", text)
        self.assertIn("note: resume.md ", text)
        self.assertIn(f"todo: {self.main / '.audit' / 'feat.todo.md'} ", text)

    def test_save_refuses_uncommitted_work(self):
        (self.wt / "c.txt").write_text("untracked\n")
        r = self.run_script(self.wt, "save", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commit", r.stderr)
        self.assertFalse((self.store / "checkpoint").exists())

    def test_save_refuses_a_detached_head(self):
        self.git(self.wt, "checkout", "-q", "--detach")
        r = self.run_script(self.wt, "save", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("detached", r.stderr)

    def test_save_needs_the_resume_note(self):
        (self.store / "resume.md").unlink()
        r = self.run_script(self.wt, "save", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("resume.md", r.stderr)

    def test_verify_passes_on_an_untouched_checkpoint(self):
        self.assertEqual(self.run_script(self.wt, "save", "feat").returncode, 0)
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"ok: feature is at {self.head[:12]}", r.stdout)

    def test_verify_with_no_checkpoint_is_missing(self):
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 2)
        self.assertIn("missing", r.stdout + r.stderr)

    def test_verify_survives_the_worktree_being_deleted(self):
        self.assertEqual(self.run_script(self.wt, "save", "feat").returncode, 0)
        # T3's cleanup removes the worktree folder; the branch and the main checkout remain.
        self.git(self.main, "worktree", "remove", str(self.wt))
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("gone: worktree", r.stdout)
        self.assertIn(f"ok: feature is at {self.head[:12]}", r.stdout)

    def test_verify_reports_a_branch_that_moved_or_was_rewritten(self):
        self.assertEqual(self.run_script(self.wt, "save", "feat").returncode, 0)
        (self.wt / "d.txt").write_text("d\n")
        self.git(self.wt, "add", "-A")
        self.git(self.wt, "commit", "-qm", "more")
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed: feature is 1 commit(s) ahead", r.stdout)
        self.git(self.wt, "reset", "-q", "--hard", "main")
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed: feature no longer contains", r.stdout)

    def test_verify_reports_edited_notes_and_dirty_trees(self):
        self.assertEqual(self.run_script(self.wt, "save", "feat").returncode, 0)
        (self.main / ".audit" / "feat.todo.md").write_text("- [x] one\n- [x] two\n")
        (self.wt / "a.txt").write_text("edited\n")
        r = self.run_script(self.main, "verify", "feat")
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed: todo", r.stdout)
        self.assertIn("changed: worktree has 1 uncommitted path(s)", r.stdout)


if __name__ == "__main__":
    unittest.main()
