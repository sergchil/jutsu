#!/usr/bin/env python3
"""Refresh vendor/pstack from cursor/plugins and report what the port must re-merge.

    python3 tools/sync_upstream.py              # latest main
    python3 tools/sync_upstream.py --ref <sha>  # a specific commit
    python3 tools/sync_upstream.py --dry-run    # report only

After a sync, `python3 tools/build.py` fails on every override whose upstream file
changed. Re-merge each one against the new upstream (vendor/ diff shows what moved),
then run `python3 tools/build.py --relock` and the tests. Substitution rules that no
longer match also fail the build, so silent drift is not possible.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "port" / "upstream.json"
VENDOR = ROOT / "vendor" / "pstack"
LOCK = ROOT / "port" / "overrides.lock.json"


def run(*cmd: str, cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def tree_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="main")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    meta = json.loads(UPSTREAM.read_text())

    with tempfile.TemporaryDirectory(prefix="p3sync-") as tmp:
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
        for label, files in (("added", added), ("removed", removed), ("changed", changed)):
            for f in files:
                print(f"  {label}: {f}")
        if not (added or removed or changed):
            print("  no changes")

        lock = json.loads(LOCK.read_text()) if LOCK.exists() else {}
        sys.path.insert(0, str(ROOT / "tools"))
        import build  # noqa: E402

        spec = build.load_json(build.SPEC)
        touched = set(changed) | set(removed)
        remerge = sorted(out for out in lock
                         if any(build.map_path(f, spec) == out for f in touched))
        if remerge:
            print("overrides to re-merge before `build.py --relock`:")
            for out in remerge:
                print(f"  port/overrides/{out}")

        if args.dry_run:
            return 0
        shutil.rmtree(VENDOR)
        shutil.copytree(fresh, VENDOR)
        meta.update(commit=commit, version=version)
        UPSTREAM.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"vendor/pstack updated. Next: python3 tools/build.py, re-merge, --relock, run the tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
