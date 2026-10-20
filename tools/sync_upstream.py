#!/usr/bin/env python3
"""Refresh vendor/pstack from cursor/plugins and 3-way merge the overrides it touches.

    python3 tools/sync_upstream.py                    # latest main
    python3 tools/sync_upstream.py --ref <sha>        # a specific commit
    python3 tools/sync_upstream.py --dry-run          # report only, write nothing
    python3 tools/sync_upstream.py --summary FILE     # also write a Markdown summary

For each override whose upstream file changed, the sync runs `git merge-file` with
base = the old vendor file (only when its sha256 equals the lock value), ours = the
override, theirs = the new vendor file. Both upstream sides first get the same
frontmatter transform the build applies, so the port's frontmatter is not a conflict.

- A clean merge is written and listed as "merged cleanly, review then relock".
- A conflict is written with git's markers. The build refuses marker lines.
- An old vendor file that does not match the lock is not merged; port it by hand.

The lock is never refreshed here. Upstream's new lines can still hold a Cursor
mechanism, so a person reviews each merged override and runs
`python3 tools/build.py --relock <plugin path>`. Until then the build, and the
weekly update PR, stay red. Substitution rules that no longer match also fail the
build, so silent drift is not possible.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "port" / "upstream.json"
VENDOR = ROOT / "vendor" / "pstack"
LOCK = ROOT / "port" / "overrides.lock.json"
REASONS = ROOT / "port" / "overrides.json"
OVERRIDES = ROOT / "port" / "overrides"
WEB = "https://github.com/cursor/plugins"

LABELS = {
    "clean": "merged cleanly, review then relock",
    "same": "upstream's change is already in the override, review then relock",
    "matches-upstream": "merged into a copy of upstream; delete the override and its lock entry",
    "conflict": "conflict, resolve the markers then relock",
    "no-base": "not merged: the old vendor file does not match the lock; re-merge by hand",
    "binary": "not merged: not a text file; re-merge by hand",
    "removed": "upstream removed its file; delete the override, its lock entry, and its overrides.json entry",
}
WRITES = ("clean", "matches-upstream", "conflict")


def run(*cmd: str, cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def tree_files(root: Path) -> set[str]:
    """Files under root, without dotfiles such as Finder's .DS_Store (see build.junk)."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def merge_file(ours: bytes, base: bytes, theirs: bytes, labels: tuple[str, str, str]) -> tuple[int, bytes]:
    """git merge-file -p. Returns (number of conflicts, merged bytes)."""
    with tempfile.TemporaryDirectory(prefix="jutsu-merge-") as tmp:
        paths = []
        for name, data in (("ours", ours), ("base", base), ("theirs", theirs)):
            p = Path(tmp) / name
            p.write_bytes(data)
            paths.append(str(p))
        r = subprocess.run(["git", "merge-file", "-p", "-L", labels[0], "-L", labels[1], "-L", labels[2], *paths],
                           capture_output=True)
    if r.returncode < 0 or r.returncode > 127:
        raise RuntimeError(f"git merge-file failed: {r.stderr.decode(errors='replace')}")
    return r.returncode, r.stdout


def plan_merges(old_root: Path, new_root: Path, build, labels: tuple[str, str, str]) -> list[dict]:
    """One item per override whose upstream file changed or went away."""
    spec = build.load_json(build.SPEC)
    lock = json.loads(LOCK.read_text()) if LOCK.exists() else {}

    def mapped(root: Path) -> dict:
        out = {}
        for rel in tree_files(root):
            out_rel = build.map_path(rel, spec)
            if out_rel is not None:
                out[out_rel] = rel
        return out

    old_map, new_map = mapped(old_root), mapped(new_root)
    items = []
    for ov in sorted(OVERRIDES.rglob("*")):
        if not ov.is_file() or build.junk(ov):
            continue
        out_rel = ov.relative_to(OVERRIDES).as_posix()
        old_rel, new_rel = old_map.get(out_rel), new_map.get(out_rel)
        if old_rel is None:
            continue  # the build reports an override with no upstream file
        if new_rel is None:
            items.append({"path": out_rel, "kind": "removed"})
            continue
        old_src, new_src = old_root / old_rel, new_root / new_rel
        if old_src.read_bytes() == new_src.read_bytes():
            continue
        item = {"path": out_rel, "upstream_file": new_rel}
        items.append(item)
        if sha256(old_src.read_bytes()) != lock.get(out_rel):
            item["kind"] = "no-base"
            continue
        if not (build.is_text(old_src) and build.is_text(new_src) and build.is_text(ov)):
            item["kind"] = "binary"
            continue
        base = build.transform_frontmatter(out_rel, old_src.read_text(encoding="utf-8"), spec).encode()
        theirs = build.transform_frontmatter(out_rel, new_src.read_text(encoding="utf-8"), spec).encode()
        ours = ov.read_bytes()
        conflicts, merged = merge_file(ours, base, theirs, labels)
        item["content"] = merged
        if conflicts:
            item["kind"], item["conflicts"] = "conflict", conflicts
        elif merged == ours:
            item["kind"] = "same"
        elif merged == theirs:
            item["kind"] = "matches-upstream"
        else:
            item["kind"] = "clean"
    return items


GITHUB_ISSUE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)")


def upstream_state(url: str) -> str | None:
    """open or closed, from `gh api`. None when gh is missing, offline, or the URL is not a GitHub issue."""
    m = GITHUB_ISSUE.match(url or "")
    if not m or not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(["gh", "api", f"repos/{m.group(1)}/{m.group(2)}/issues/{m.group(3)}", "--jq", ".state"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    state = r.stdout.strip()
    return state if r.returncode == 0 and state in ("open", "closed") else None


def describe(items: list[dict], reasons: dict) -> list[str]:
    """Report lines per item, plus the upstream link for upstream-bug overrides."""
    lines = []
    for it in items:
        label = LABELS[it["kind"]]
        if it["kind"] == "conflict":
            label = f"conflict ({it['conflicts']}), resolve the markers then relock"
        lines.append(f"  {label}: port/overrides/{it['path']}")
        reason = reasons.get(it["path"]) or {}
        if reason.get("kind") == "upstream-bug" and reason.get("upstream"):
            url = reason["upstream"]
            it["upstream"] = url
            note = f"    fixes upstream bug {url}"
            if upstream_state(url) == "closed":
                note += " (closed: upstream may have fixed this; drop our copy if so)"
                it["upstream_closed"] = True
            lines.append(note)
    return lines


def commit_log(clone: Path, old: str, new: str, path: str) -> list[tuple] | None:
    """(full sha, short sha, subject) per upstream commit that touched path, newest first."""
    try:
        run("git", "cat-file", "-e", f"{old}^{{commit}}", cwd=clone)
        out = run("git", "log", "--format=%H%x09%h%x09%s", f"{old}..{new}", "--", path, cwd=clone)
    except subprocess.CalledProcessError:
        return None
    return [tuple(line.split("\t", 2)) for line in out.splitlines() if line]


def web_base(repository: str) -> str:
    m = re.match(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repository)
    return f"https://github.com/{m.group(1)}" if m else WEB


ADAPTER = "docs/harness/claude-code.md"


def adapter_report(fresh: Path, touched: list[str]) -> list[str]:
    """When upstream's Claude Code adapter changed, each row that now disagrees with port/adapter.json."""
    if ADAPTER not in touched or not (fresh / ADAPTER).is_file():
        return []
    import adapter_diff  # same folder
    record = json.loads(adapter_diff.RECORD.read_text()) if adapter_diff.RECORD.exists() else {}
    _, problems = adapter_diff.diff((fresh / ADAPTER).read_text(encoding="utf-8"), record, ROOT / "plugin")
    lines = [f"upstream's Claude Code adapter changed ({ADAPTER}); review with python3 tools/adapter_diff.py:"]
    lines += [f"  {p}" for p in problems] or ["  every row still matches port/adapter.json"]
    return lines


def summary_markdown(meta: dict, commit: str, version: str, commits, items: list[dict],
                     adapter: list[str] | None = None) -> str:
    web = web_base(meta["repository"])
    out = [f"### Upstream commits, {meta['commit'][:12]} ({meta['version']}) to {commit[:12]} ({version})", ""]
    if commits is None:
        out.append(f"The old pin {meta['commit'][:12]} is not in upstream's history, so there is no commit list.")
    elif not commits:
        out.append(f"No commit touched `{meta['path']}`.")
    for full, short, subject in commits or []:
        out.append(f"- [{short}]({web}/commit/{full}) {subject}")
    out += ["", "### 3-way merge per override", ""]
    if not items:
        out.append("No override's upstream file changed.")
    else:
        out += ["| Override | Result | Upstream bug |", "|---|---|---|"]
        for it in items:
            label = LABELS[it["kind"]]
            if it["kind"] == "conflict":
                n = it["conflicts"]
                label = f"conflict ({n} hunk{'' if n == 1 else 's'}), resolve the markers then relock"
            bug = it.get("upstream", "")
            if it.get("upstream_closed"):
                bug += " (closed: upstream may have fixed this; drop our copy if so)"
            out.append(f"| `port/overrides/{it['path']}` | {label} | {bug} |")
    if adapter:
        out += ["", "### Upstream's Claude Code adapter", "", "```", *adapter, "```"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="main")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    ap.add_argument("--summary", metavar="FILE", help="write a Markdown summary (commits, merge results) here")
    args = ap.parse_args()
    meta = json.loads(UPSTREAM.read_text())
    reasons = json.loads(REASONS.read_text()) if REASONS.exists() else {}
    sys.path.insert(0, str(ROOT / "tools"))
    import build  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="jutsu-sync-") as tmp:
        clone = Path(tmp) / "plugins"
        run("git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", meta["repository"], str(clone))
        run("git", "sparse-checkout", "set", meta["path"], cwd=clone)
        run("git", "checkout", "--quiet", args.ref, cwd=clone)
        commit = run("git", "rev-parse", "HEAD", cwd=clone)
        fresh = clone / meta["path"]
        version = json.loads((fresh / ".cursor-plugin" / "plugin.json").read_text()).get("version", "?")

        old, new = tree_files(VENDOR), tree_files(fresh)
        added = sorted(new - old)
        removed = sorted(old - new)
        changed = sorted(f for f in old & new if not filecmp.cmp(VENDOR / f, fresh / f, shallow=False))
        print(f"upstream {meta['commit'][:12]} ({meta['version']}) -> {commit[:12]} ({version})")
        commits = commit_log(clone, meta["commit"], commit, meta["path"])
        if commits:
            print("upstream commits:")
            for full, short, subject in commits:
                print(f"  {short} {subject}")
        for label, files in (("added", added), ("removed", removed), ("changed", changed)):
            for f in files:
                print(f"  {label}: {f}")
        if not (added or removed or changed):
            print("  no changes")
        adapter = adapter_report(fresh, added + changed)
        for line in adapter:
            print(line)

        labels = ("jutsu override", f"upstream {meta['commit'][:12]}", f"upstream {commit[:12]}")
        items = plan_merges(VENDOR, fresh, build, labels)
        if items:
            print("3-way merge of the overrides upstream touched" + (" (dry run, nothing written):" if args.dry_run else ":"))
            for line in describe(items, reasons):
                print(line)
            relock = [it["path"] for it in items if it["kind"] not in ("removed", "matches-upstream")]
            if relock:
                print("after review, relock each one: python3 tools/build.py --relock " + " ".join(relock))

        if args.dry_run:
            return 0
        shutil.rmtree(VENDOR)
        shutil.copytree(fresh, VENDOR)
        for it in items:
            if it["kind"] in WRITES:
                (OVERRIDES / it["path"]).write_bytes(it["content"])
        meta_old = dict(meta)
        meta.update(commit=commit, version=version)
        UPSTREAM.write_text(json.dumps(meta, indent=2) + "\n")
        if args.summary:
            Path(args.summary).write_text(summary_markdown(meta_old, commit, version, commits, items, adapter))
        print(f"vendor/pstack updated to {version} ({commit[:12]}).")
        with tempfile.TemporaryDirectory(prefix="jutsu-sync-build-") as out:
            try:
                build.build(Path(out), relock=False, check_lock=True)
                print("Nothing to port: the build passes as is. Run the tests, then commit.")
            except build.BuildError as exc:
                print(exc)
                print("Port each item, relock it, then: python3 tools/check.py "
                      "&& python3 -m unittest discover -s tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
