"""Runs the bundled worktree-audit.sh on real git repos and checks every bucket.

Upstream bugs this pins:
- cursor/plugins#449: untracked and ignored files were "scratch" or invisible, so a
  worktree holding them could be bucketed safe and removed with --force.
- cursor/plugins#470: a closed-unmerged PR, or commits that exist nowhere else, made a
  worktree safe.
The squash-pruned, reused-name, and behind-merged cases come from the open upstream fix
cursor/plugins#492, so a later re-merge cannot regress them.
From pstack-claude (MIT, worktree-audit.mjs): ignored paths under build and cache
directories (build/, node_modules/, __pycache__, ...) do not hold a worktree, but .env
still does; commits only the worktree's HEAD reflog reaches are hold-reflog; a locked
worktree is hold-locked with its reason in the LOCKED column.
The t3-* cases pin the jutsu T3 column: a worktree in a T3 worktrees folder, or bound to a
live T3 thread, is t3-managed (reported, never pruned), whatever else it holds. They run
against a fake T3 home in T3CODE_HOME, so the real ~/.t3 is never read.
"""
from __future__ import annotations

import json
import os
import sqlite3
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = Path(os.environ.get("JUTSU_PLUGIN") or ROOT / "plugin") / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh"
HAS_SQLITE3 = bool(shutil.which("sqlite3"))

# name -> (DIRTY, REMOTE, BUCKET)
EXPECTED = {
    "clean-on-main": ("clean", "no-remote", "safe"),
    "wip": ("wip:1", "no-remote", "hold-wip"),
    "untracked": ("untracked:1", "no-remote", "hold-local"),
    "ignored": ("ignored:1", "no-remote", "hold-local"),
    "disposable-only": ("clean", "no-remote", "safe"),
    "reflog-only": ("reflog:1", "detached", "hold-reflog"),
    "locked": ("clean", "no-remote", "hold-locked"),
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
    "rewound": ("clean", "no-remote", "safe"),
    "reused-name": ("clean", "pushed", "safe"),
    "t3-root": ("clean", "no-remote", "t3-managed"),
    "t3-root-wip": ("wip:1", "no-remote", "t3-managed"),
    "t3-root-locked": ("clean", "no-remote", "t3-managed"),
    "t3-custom": ("clean", "no-remote", "t3-managed"),
    "t3-previous": ("clean", "no-remote", "t3-managed"),
    "t3-deleted-thread": ("clean", "no-remote", "safe"),
}
if HAS_SQLITE3:
    EXPECTED["t3-thread"] = ("clean", "no-remote", "t3-managed")
# name -> LOCKED column; every other row is "-".
LOCKED_EXPECTED = {"locked": "agent at work", "t3-root-locked": "locked"}
# name -> T3 column; every other row is "-".
T3_EXPECTED = {"t3-root": "root", "t3-root-wip": "root", "t3-root-locked": "root", "t3-custom": "root", "t3-previous": "root"}
if HAS_SQLITE3:
    T3_EXPECTED["t3-thread"] = "thread"


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "needs jq and bash")
class WorktreeAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name).resolve()
        (base / "gitconfig").write_text("")
        (base / "claude" / "projects").mkdir(parents=True)
        (base / "bin").mkdir()
        home = base / "home"
        home.mkdir()
        t3 = base / "t3"
        (t3 / "worktrees" / "repo").mkdir(parents=True)
        (t3 / "userdata").mkdir()
        (t3 / "userdata" / "settings.json").write_text(json.dumps({
            "worktreesDirectory": "~/custom-wt",
            # "/" is a filesystem root, so T3 ignores it, and so must the audit.
            "previousWorktreesDirectories": [str(base / "old-wt"), "/", "relative/dir"],
        }))
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
            "HOME": str(home),
            "T3CODE_HOME": str(t3),
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

        def worktree(name, detach=False, parent=None):
            path = (parent or base) / name
            path.parent.mkdir(parents=True, exist_ok=True)
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
        (repo / ".gitignore").write_text(".env\nbuild/\nnode_modules/\n__pycache__/\n")
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
        # Only rebuildable build and cache output: nothing at stake.
        disposable = worktree("disposable-only")
        (disposable / "build").mkdir()
        (disposable / "build" / "out.bin").write_text("x")
        (disposable / "node_modules" / "pkg").mkdir(parents=True)
        (disposable / "node_modules" / "pkg" / "index.js").write_text("x")
        (disposable / "src" / "__pycache__").mkdir(parents=True)
        (disposable / "src" / "__pycache__" / "m.pyc").write_text("x")
        # A commit made on a detached HEAD, then left: only this worktree's HEAD reflog
        # reaches it, and `git worktree remove` deletes that reflog.
        reflog_only = worktree("reflog-only", detach=True)
        commit(reflog_only, "orphan-work")
        git(reflog_only, "checkout", "-q", "--detach", "main")
        # Rewound on its branch: the branch reflog (shared, survives removal) keeps it.
        rewound = worktree("rewound")
        commit(rewound, "rewound-work")
        git(rewound, "reset", "-q", "--hard", "HEAD~1")
        git(repo, "worktree", "lock", "--reason", "agent at work", str(worktree("locked")))
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

        worktree("t3-root", parent=t3 / "worktrees" / "repo")
        (worktree("t3-root-wip", parent=t3 / "worktrees" / "repo") / "a.txt").write_text("edited\n")
        git(repo, "worktree", "lock", str(worktree("t3-root-locked", parent=t3 / "worktrees" / "repo")))
        worktree("t3-custom", parent=home / "custom-wt" / "repo")
        worktree("t3-previous", parent=base / "old-wt" / "repo")
        thread_wt = worktree("t3-thread")
        deleted_wt = worktree("t3-deleted-thread")
        db = sqlite3.connect(str(t3 / "userdata" / "statev2.sqlite"))
        db.execute("CREATE TABLE orchestration_v2_projection_threads (thread_id TEXT, payload_json TEXT, deleted_at TEXT)")
        db.executemany("INSERT INTO orchestration_v2_projection_threads VALUES (?, ?, ?)", [
            ("a", json.dumps({"worktreePath": str(thread_wt)}), None),
            ("b", json.dumps({"worktreePath": str(deleted_wt)}), "2026-01-01T00:00:00Z"),
            ("c", json.dumps({"worktreePath": None}), None),
        ])
        db.commit()
        db.close()

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
        self.assertEqual(safe, ["behind-merged", "clean-on-main", "disposable-only", "merged-pr", "reused-name",
                                "rewound", "squash-pruned", "t3-deleted-thread"])

    def test_locked_worktrees_show_their_reason(self):
        self.assertIn("LOCKED", self.header)
        for name, row in self.rows.items():
            with self.subTest(worktree=name):
                self.assertEqual(row["LOCKED"], LOCKED_EXPECTED.get(name, "-"))

    def test_a_locked_t3_worktree_stays_t3_managed(self):
        self.assertEqual(self.rows["t3-root-locked"]["BUCKET"], "t3-managed")
        self.assertEqual(self.rows["t3-root-locked"]["LOCKED"], "locked")

    def test_t3_worktrees_are_reported_never_removable(self):
        self.assertIn("T3", self.header)
        for name, row in self.rows.items():
            with self.subTest(worktree=name):
                self.assertEqual(row["T3"], T3_EXPECTED.get(name, "-"))
                self.assertEqual(row["BUCKET"] == "t3-managed", name in T3_EXPECTED)

    @unittest.skipUnless(HAS_SQLITE3, "sqlite3 is not installed")
    def test_reads_t3_threads_without_writing_the_database(self):
        db = Path(self.env["T3CODE_HOME"]) / "userdata" / "statev2.sqlite"
        self.assertEqual(sorted(p.name for p in db.parent.iterdir()), ["settings.json", "statev2.sqlite"])
        self.assertNotIn("could not read T3 threads", self.stderr)

    def test_header_does_not_claim_read_only(self):
        head = "\n".join(AUDIT.read_text().splitlines()[:8])
        self.assertNotIn("Read-only", head)
        self.assertIn("git fetch origin main", head)


if __name__ == "__main__":
    unittest.main()
