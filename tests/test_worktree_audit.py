"""Runs the bundled worktree-audit.sh on real git repos and checks every bucket.

Upstream bugs this pins:
- cursor/plugins#449: untracked and ignored files were "scratch" or invisible, so a
  worktree holding them could be bucketed safe and removed with --force.
- cursor/plugins#470: a closed-unmerged PR, or commits that exist nowhere else, made a
  worktree safe.
The squash-pruned, reused-name, and behind-merged cases come from the open upstream fix
cursor/plugins#492, so a later re-merge cannot regress them.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "plugin" / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh"

# name -> (DIRTY, REMOTE, BUCKET)
EXPECTED = {
    "clean-on-main": ("clean", "no-remote", "safe"),
    "wip": ("wip:1", "no-remote", "hold-wip"),
    "untracked": ("untracked:1", "no-remote", "hold-local"),
    "ignored": ("ignored:2", "no-remote", "hold-local"),
    "corrupt-index": ("unknown", "no-remote", "hold-wip"),
    "closed-pr": ("clean", "pushed", "review"),
    "closed-pr-unpushed": ("clean", "ahead1", "hold-unpushed"),
    "local-only": ("clean", "no-remote", "hold-unpushed"),
    "detached": ("clean", "detached", "hold-unpushed"),
    "merged-pr": ("clean", "pushed", "safe"),
    "merged-then-more": ("clean", "pushed", "review"),
    "behind": ("clean", "behind", "review"),
    "behind-merged": ("clean", "behind", "safe"),
    "squash-pruned": ("clean", "no-remote", "safe"),
    "reused-name": ("clean", "pushed", "safe"),
}


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "needs jq and bash")
class WorktreeAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name).resolve()
        (base / "gitconfig").write_text("")
        (base / "claude" / "projects").mkdir(parents=True)
        (base / "bin").mkdir()
        gh = base / "bin" / "gh"
        gh.write_text('#!/bin/sh\ncat "$GH_STUB_JSON"\n')
        gh.chmod(0o755)
        cls.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
            "CLAUDE_CONFIG_DIR": str(base / "claude"),
            "GH_STUB_JSON": str(base / "prs.json"),
            "PATH": f"{base / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        }

        def git(cwd, *args):
            return subprocess.run(["git", *args], cwd=cwd, env=cls.env, check=True,
                                  capture_output=True, text=True).stdout.strip()

        def commit(path, name):
            (path / f"{name}.txt").write_text(name + "\n")
            git(path, "add", "-A")
            git(path, "commit", "-qm", name)
            return git(path, "rev-parse", "HEAD")

        def worktree(name, detach=False):
            path = base / name
            if detach:
                git(repo, "worktree", "add", "-q", "--detach", str(path), "main")
            else:
                git(repo, "worktree", "add", "-q", "-b", name, str(path), "main")
            return path

        origin = base / "origin.git"
        git(base, "init", "-q", "--bare", "-b", "main", str(origin))
        repo = base / "repo"
        git(base, "init", "-q", "-b", "main", str(repo))
        git(repo, "remote", "add", "origin", str(origin))
        (repo / ".gitignore").write_text(".env\nbuild/\n")
        (repo / "a.txt").write_text("a\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
        git(repo, "push", "-q", "origin", "main")
        # Hides untracked files from a plain `git status`; the audit must not be fooled.
        git(repo, "config", "status.showUntrackedFiles", "no")

        worktree("clean-on-main")
        (worktree("wip") / "a.txt").write_text("edited\n")
        (worktree("untracked") / "notes.txt").write_text("notes\n")
        ignored = worktree("ignored")
        (ignored / ".env").write_text("SECRET=1\n")
        (ignored / "build").mkdir()
        (ignored / "build" / "out.bin").write_text("x")
        corrupt = worktree("corrupt-index")
        Path(git(corrupt, "rev-parse", "--path-format=absolute", "--git-path", "index")).write_bytes(b"garbage")

        closed = worktree("closed-pr")
        commit(closed, "closed-work")
        git(closed, "push", "-q", "origin", "closed-pr")

        closed_unpushed = worktree("closed-pr-unpushed")
        commit(closed_unpushed, "pushed-work")
        git(closed_unpushed, "push", "-q", "origin", "closed-pr-unpushed")
        commit(closed_unpushed, "local-work")

        commit(worktree("local-only"), "local-only-work")
        commit(worktree("detached", detach=True), "detached-work")

        merged = worktree("merged-pr")
        merged_head = commit(merged, "merged-work")
        git(merged, "push", "-q", "origin", "merged-pr")

        more = worktree("merged-then-more")
        merged_earlier = commit(more, "merged-earlier")
        commit(more, "after-merge")
        git(more, "push", "-q", "origin", "merged-then-more")

        behind = worktree("behind")
        commit(behind, "first")
        commit(behind, "second")
        git(behind, "push", "-q", "origin", "behind")
        git(behind, "reset", "-q", "--hard", "HEAD~1")

        # The PR merged at the remote head; this checkout stopped one commit short.
        behind_merged = worktree("behind-merged")
        commit(behind_merged, "bm-first")
        bm_head = commit(behind_merged, "bm-second")
        git(behind_merged, "push", "-q", "origin", "behind-merged")
        git(behind_merged, "reset", "-q", "--hard", "HEAD~1")

        # Squash-merged, then the remote branch was deleted.
        pruned = worktree("squash-pruned")
        pruned_head = commit(pruned, "pruned-work")
        git(pruned, "push", "-q", "origin", "squash-pruned")
        git(pruned, "push", "-q", "origin", "--delete", "squash-pruned")

        # An old closed PR used the same branch name before the merged one.
        reused = worktree("reused-name")
        reused_head = commit(reused, "reused-work")
        git(reused, "push", "-q", "origin", "reused-name")

        (base / "prs.json").write_text(json.dumps([
            {"number": 41, "state": "CLOSED", "headRefName": "closed-pr", "headRefOid": "0" * 40},
            {"number": 42, "state": "CLOSED", "headRefName": "closed-pr-unpushed", "headRefOid": "0" * 40},
            {"number": 43, "state": "MERGED", "headRefName": "merged-pr", "headRefOid": merged_head},
            {"number": 44, "state": "MERGED", "headRefName": "merged-then-more", "headRefOid": merged_earlier},
            {"number": 45, "state": "MERGED", "headRefName": "behind-merged", "headRefOid": bm_head},
            {"number": 46, "state": "MERGED", "headRefName": "squash-pruned", "headRefOid": pruned_head},
            {"number": 47, "state": "CLOSED", "headRefName": "reused-name", "headRefOid": "1" * 40},
            {"number": 48, "state": "MERGED", "headRefName": "reused-name", "headRefOid": reused_head},
        ]))

        run = subprocess.run(["bash", str(AUDIT), str(repo)], env=cls.env, capture_output=True,
                             text=True, timeout=120)
        cls.stderr = run.stderr
        # The first line names the base ref the audit compared against.
        lines = [l for l in run.stdout.strip().splitlines() if not l.startswith("# base:")]
        cls.header = lines[0].split("\t") if lines else []
        cls.rows = {}
        for line in lines[1:]:
            cols = dict(zip(cls.header, line.split("\t")))
            cls.rows[Path(cols["WORKTREE"]).name] = cols

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_worktree_lands_in_the_right_bucket(self):
        self.assertEqual(sorted(self.rows), sorted(EXPECTED), self.stderr)
        for name, (dirty, remote, bucket) in EXPECTED.items():
            with self.subTest(worktree=name):
                row = self.rows[name]
                self.assertEqual((row["DIRTY"], row["REMOTE"], row["BUCKET"]), (dirty, remote, bucket))

    def test_only_clean_merged_work_is_safe(self):
        safe = sorted(name for name, row in self.rows.items() if row["BUCKET"] == "safe")
        self.assertEqual(safe, ["behind-merged", "clean-on-main", "merged-pr", "reused-name", "squash-pruned"])

    def test_header_does_not_claim_read_only(self):
        head = "\n".join(AUDIT.read_text().splitlines()[:8])
        self.assertNotIn("Read-only", head)
        self.assertIn("git fetch origin main", head)


if __name__ == "__main__":
    unittest.main()
