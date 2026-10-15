"""Tests for tools/sync_upstream.py: 3-way merge of overrides against a real upstream git repo."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HOW = "skills/how/SKILL.md"
SICKO = "agents/comment-sicko.md"
REMOVED = "skills/poteto-mode/scripts/check-plan.test.ts"
NEW_SKILL = "skills/brand-new/SKILL.md"
FAR_PARAGRAPH = "A new upstream paragraph, far from every line jutsu changed."


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


def tree_hashes(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


class SyncFixture(unittest.TestCase):
    """A temp copy of vendor/ port/ tools/, and an upstream git repo that starts at the vendored tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="jutsu-sync-test-")
        self.tmp = Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        for part in ("vendor", "port", "tools"):
            shutil.copytree(ROOT / part, self.repo / part, ignore=shutil.ignore_patterns("__pycache__"))
        self.up = self.tmp / "upstream"
        shutil.copytree(self.repo / "vendor" / "pstack", self.up / "pstack")
        git("init", "--quiet", cwd=self.up)
        git("add", "-A", cwd=self.up)
        git("commit", "--quiet", "-m", "base", cwd=self.up)
        self.base = git("rev-parse", "HEAD", cwd=self.up)
        meta_path = self.repo / "port" / "upstream.json"
        meta = json.loads(meta_path.read_text())
        meta.update(repository=str(self.up), commit=self.base)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        # A gh that is not on the network: tests that need an answer replace it.
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.fake_gh("exit 1")

    def tearDown(self):
        self._tmp.cleanup()

    def fake_gh(self, body: str):
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\n" + body + "\n")
        gh.chmod(0o755)

    def upstream_update(self) -> str:
        """Five kinds of upstream change in one commit."""
        pstack = self.up / "pstack"
        # 1. A far-away paragraph in an override's file: merges cleanly.
        how = pstack / HOW
        how.write_text(how.read_text() + "\n" + FAR_PARAGRAPH + "\n")
        # 2. The same line jutsu rewrote: conflicts.
        sicko = pstack / SICKO
        text = sicko.read_text()
        self.assertIn("`/how`, `/why`, or both", text)
        sicko.write_text(text.replace("`/how`, `/why`, or both", "`/how`, `/why`, `/recall`, or all three"))
        # 3. Text a substitution rule rewrites: the rule no longer matches.
        rule = json.loads((self.repo / "port/subs/lead.json").read_text())["substitutions"][0]
        target = pstack / "skills/poteto-mode/playbooks/investigation.md"
        target.write_text(target.read_text().replace(rule["pattern"], "the how-to skill"))
        # 4. A new upstream skill.
        new = pstack / NEW_SKILL
        new.parent.mkdir(parents=True)
        new.write_text("---\nname: Brand New\ndescription: d\ndisable-model-invocation: true\n---\nUse the Task tool.\n")
        # 5. A removed upstream file that jutsu overrides.
        (pstack / REMOVED).unlink()
        git("add", "-A", cwd=self.up)
        git("commit", "--quiet", "-m", "upstream: tweak how, comment-sicko, and investigation", cwd=self.up)
        return git("rev-parse", "HEAD", cwd=self.up)

    def sync(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        r = subprocess.run([sys.executable, str(self.repo / "tools/sync_upstream.py"), *args],
                           capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r


class SyncMergeTest(SyncFixture):
    def test_sync_merges_overrides_three_ways_and_keeps_the_lock(self):
        new = self.upstream_update()
        lock_before = (self.repo / "port/overrides.lock.json").read_bytes()
        ours_how = (self.repo / "port/overrides" / HOW).read_text()
        summary = self.tmp / "summary.md"
        out = self.sync("--ref", new, "--summary", str(summary)).stdout

        self.assertIn("upstream: tweak how, comment-sicko, and investigation", out)
        self.assertIn(f"merged cleanly, review then relock: port/overrides/{HOW}", out)
        self.assertIn(f"conflict (1), resolve the markers then relock: port/overrides/{SICKO}", out)
        self.assertIn(f"upstream removed its file; delete the override, its lock entry, and its overrides.json "
                      f"entry: port/overrides/{REMOVED}", out)
        self.assertIn(f"added: {NEW_SKILL}", out)
        self.assertIn(f"python3 tools/build.py --relock {SICKO} {HOW}", out)
        # The build after the sync stays red until a person relocks.
        self.assertIn(f"re-merge port/overrides/{HOW}", out)
        self.assertIn(f"port/overrides/{SICKO}:", out)
        self.assertIn("unresolved merge conflict marker", out)
        self.assertIn("substitution lead-1 matched nothing", out)
        self.assertIn(f"upstream removed the file behind port/overrides/{REMOVED}", out)

        merged = (self.repo / "port/overrides" / HOW).read_text()
        self.assertTrue(merged.startswith(ours_how.rstrip("\n")), "our override text is kept")
        self.assertIn(FAR_PARAGRAPH, merged)
        self.assertNotIn("<<<<<<<", merged)
        conflicted = (self.repo / "port/overrides" / SICKO).read_text()
        self.assertIn("<<<<<<< jutsu override", conflicted)
        self.assertIn(f">>>>>>> upstream {new[:12]}", conflicted)
        self.assertIn("`/recall`, or all three", conflicted)
        self.assertTrue((self.repo / "port/overrides" / REMOVED).exists(), "a person deletes it after reading why")

        self.assertEqual((self.repo / "port/overrides.lock.json").read_bytes(), lock_before)
        self.assertEqual(json.loads((self.repo / "port/upstream.json").read_text())["commit"], new)
        self.assertTrue((self.repo / "vendor/pstack" / NEW_SKILL).exists())
        self.assertFalse((self.repo / "vendor/pstack" / REMOVED).exists())

        body = summary.read_text()
        self.assertIn(f"- [{new[:7]}](https://github.com/cursor/plugins/commit/{new}) upstream: tweak how", body)
        self.assertIn(f"| `port/overrides/{HOW}` | merged cleanly, review then relock |", body)
        self.assertIn(f"| `port/overrides/{SICKO}` | conflict (1 hunk)", body)

        # Relocking the reviewed clean merge clears it; the conflict still fails the build.
        r = subprocess.run([sys.executable, str(self.repo / "tools/build.py"), "--relock", HOW],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn(f"re-merge port/overrides/{HOW}", r.stderr)
        self.assertIn("unresolved merge conflict marker", r.stderr)

    def test_dry_run_writes_nothing(self):
        new = self.upstream_update()
        before = tree_hashes(self.repo)
        out = self.sync("--ref", new, "--dry-run", "--summary", str(self.tmp / "summary.md")).stdout
        self.assertIn("dry run, nothing written", out)
        self.assertIn(f"merged cleanly, review then relock: port/overrides/{HOW}", out)
        self.assertIn(f"conflict (1), resolve the markers then relock: port/overrides/{SICKO}", out)
        self.assertEqual(tree_hashes(self.repo), before)
        self.assertFalse((self.tmp / "summary.md").exists())

    def test_no_merge_when_the_old_vendor_file_does_not_match_the_lock(self):
        new = self.upstream_update()
        lock_path = self.repo / "port/overrides.lock.json"
        lock = json.loads(lock_path.read_text())
        lock[HOW] = "0" * 64
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        ours = (self.repo / "port/overrides" / HOW).read_bytes()
        out = self.sync("--ref", new).stdout
        self.assertIn(f"not merged: the old vendor file does not match the lock; re-merge by hand: "
                      f"port/overrides/{HOW}", out)
        self.assertEqual((self.repo / "port/overrides" / HOW).read_bytes(), ours)

    def test_upstream_bug_override_names_its_link_and_a_closed_issue(self):
        new = self.upstream_update()
        reasons_path = self.repo / "port/overrides.json"
        reasons = json.loads(reasons_path.read_text())
        url = "https://github.com/cursor/plugins/issues/999"
        reasons[SICKO] = {"kind": "upstream-bug", "why": "w.", "upstream": url}
        reasons_path.write_text(json.dumps(reasons, indent=2) + "\n")

        out = self.sync("--ref", new, "--dry-run").stdout  # gh fails, as offline
        self.assertIn(f"fixes upstream bug {url}\n", out)
        self.assertNotIn("may have fixed", out)

        self.fake_gh('[ "$1 $2" = "api repos/cursor/plugins/issues/999" ] && echo closed || exit 1')
        out = self.sync("--ref", new, "--dry-run").stdout
        self.assertIn(f"fixes upstream bug {url} (closed: upstream may have fixed this; drop our copy if so)", out)


if __name__ == "__main__":
    unittest.main()
