#!/usr/bin/env python3
"""Build the p3 plugin from the vendored upstream pstack plus the port overlay.

    python3 tools/build.py            # write plugin/
    python3 tools/build.py --check    # exit 1 if plugin/ is stale
    python3 tools/build.py --relock   # record current upstream hashes for overrides

Pipeline per upstream file: map path -> transform frontmatter -> apply substitutions
-> replace with an override when one exists. Then copy port/added/ and generate the
root router alias. Python 3.9+, stdlib only.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "port" / "spec.json"
SUBS = ROOT / "port" / "substitutions.json"
OVERRIDES = ROOT / "port" / "overrides"
LOCK = ROOT / "port" / "overrides.lock.json"
ADDED = ROOT / "port" / "added"
OUT = ROOT / "plugin"

TEXT_SUFFIXES = {".md", ".ts", ".mjs", ".js", ".json", ".sh", ".tsv", ".yaml", ".yml", ".txt", ""}


class BuildError(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def is_text(path: Path) -> bool:
    if path.suffix not in TEXT_SUFFIXES:
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False


def map_path(rel: str, spec: dict) -> str | None:
    """Map an upstream path (relative to vendor/pstack) to a plugin path, or None to drop it."""
    for prefix in spec["exclude"]:
        if rel == prefix or rel.startswith(prefix):
            return None
    m = re.match(r"skills/(principle-[a-z0-9-]+)/SKILL\.md$", rel)
    if m:
        return f"principles/{m.group(1)}.md"
    for old, new in spec.get("rename", {}).items():
        if rel == old:
            return new
    return rel


FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def transform_frontmatter(out_rel: str, text: str, spec: dict) -> str:
    m = FRONTMATTER.match(text)
    if not m:
        return text
    lines = m.group(1).split("\n")
    fm = spec["frontmatter"]
    drop = set(fm["drop"])
    kept = []
    for line in lines:
        key = line.split(":", 1)[0].strip() if ":" in line and not line.startswith(" ") else None
        if key in drop:
            continue
        kept.append(line)

    skill = re.match(r"skills/([^/]+)/SKILL\.md$", out_rel)
    agent = re.match(r"agents/([^/]+)\.md$", out_rel)
    principle = re.match(r"principles/([^/]+)\.md$", out_rel)
    if skill:
        name = skill.group(1)
        kept = [f"name: {name}" if l.startswith("name:") else l for l in kept]
        if name not in fm.get("model_invocable", []):
            kept.append("disable-model-invocation: true")
    elif agent:
        name = agent.group(1)
        kept = [f"name: {name}" if l.startswith("name:") else l for l in kept]
        if any(l.startswith("is_background:") for l in lines):
            kept.append("background: true")
    elif principle:
        pass
    return "---\n" + "\n".join(kept) + "\n---\n" + text[m.end():]


def compile_subs(subs: list) -> list:
    compiled = []
    for i, s in enumerate(subs):
        flags = re.M
        pat = s["pattern"] if s.get("regex") else re.escape(s["pattern"])
        repl = s["replacement"] if s.get("regex") else s["replacement"].replace("\\", "\\\\")
        compiled.append({
            "id": s.get("id", f"#{i}"),
            "re": re.compile(pat, flags),
            "repl": repl,
            "files": re.compile(s["files"]) if s.get("files") else None,
            "hits": 0,
        })
    return compiled


def apply_subs(out_rel: str, text: str, compiled: list) -> str:
    for s in compiled:
        if s["files"] and not s["files"].search(out_rel):
            continue
        text, n = s["re"].subn(s["repl"], text)
        s["hits"] += n
    return text


P3_TOKEN = re.compile(r"\{\{p3\}\}")


def resolve_p3_token(out_rel: str, text: str) -> str:
    """Replace {{p3}} with the relative path from this file's directory to the plugin root.

    Content files are read by the model by path, so links stay relative to the file
    being read, the way upstream writes them. Agent bodies are system prompts, not
    files, so they must not use the token (checked in tools/check.py).
    """
    depth = out_rel.count("/")
    rel = "/".join([".."] * depth) if depth else "."
    return P3_TOKEN.sub(rel, text)


def build(out_dir: Path, relock: bool = False) -> list[str]:
    spec = load_json(SPEC)
    compiled = compile_subs(load_json(SUBS)["substitutions"])
    lock = load_json(LOCK) if LOCK.exists() else {}
    vendor = ROOT / spec["vendor"]
    notes: list[str] = []
    produced: dict[str, str] = {}

    for src in sorted(vendor.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(vendor).as_posix()
        out_rel = map_path(rel, spec)
        if out_rel is None:
            continue
        dest = out_dir / out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        override = OVERRIDES / out_rel
        if override.exists():
            want = lock.get(out_rel)
            have = sha256(src)
            if relock:
                lock[out_rel] = have
            elif want != have:
                raise BuildError(
                    f"override {out_rel}: upstream {rel} changed (lock {str(want)[:12]} != {have[:12]}). "
                    "Re-merge the override against the new upstream, then run build.py --relock.")
            shutil.copyfile(override, dest)
            produced[out_rel] = "override"
        elif is_text(src):
            text = src.read_text(encoding="utf-8")
            text = transform_frontmatter(out_rel, text, spec)
            text = apply_subs(out_rel, text, compiled)
            dest.write_text(text, encoding="utf-8")
            produced[out_rel] = "upstream"
        else:
            shutil.copyfile(src, dest)
            produced[out_rel] = "binary"
        shutil.copymode(src, dest)

    for out_rel in sorted(lock):
        if out_rel not in produced and not relock:
            raise BuildError(f"lock entry {out_rel} has no upstream file any more; remove it")
    for ov in sorted(OVERRIDES.rglob("*")):
        if ov.is_file():
            out_rel = ov.relative_to(OVERRIDES).as_posix()
            if out_rel not in produced:
                raise BuildError(f"override {out_rel} matches no upstream file; move it to port/added/")
    if relock:
        lock = {k: v for k, v in lock.items() if (OVERRIDES / k).exists()}
        LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for src in sorted(ADDED.rglob("*")):
        if not src.is_file() or src.name == ".DS_Store":
            continue
        out_rel = src.relative_to(ADDED).as_posix()
        if out_rel in produced:
            raise BuildError(f"added file {out_rel} collides with an upstream file; use port/overrides/")
        dest = out_dir / out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        shutil.copymode(src, dest)
        produced[out_rel] = "added"

    for out_rel, kind in produced.items():
        if kind == "binary":
            continue
        path = out_dir / out_rel
        text = path.read_text(encoding="utf-8")
        resolved = resolve_p3_token(out_rel, text)
        if resolved != text:
            path.write_text(resolved, encoding="utf-8")

    stale = [s["id"] for s in compiled if s["hits"] == 0]
    if stale:
        raise BuildError("substitutions matched nothing (stale or misspelled): " + ", ".join(stale))
    notes.append(f"{len(produced)} files: " + ", ".join(
        f"{k}={sum(1 for v in produced.values() if v == k)}" for k in ("upstream", "override", "added", "binary")))
    return notes


def trees_equal(a: Path, b: Path) -> list[str]:
    diffs = []
    files_a = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()} if b.exists() else set()
    for rel in sorted(files_a ^ files_b):
        diffs.append(f"only in {'build' if rel in files_a else 'plugin/'}: {rel}")
    for rel in sorted(files_a & files_b):
        pa, pb = a / rel, b / rel
        if not filecmp.cmp(pa, pb, shallow=False):
            diffs.append(f"differs: {rel}")
        elif stat.S_IMODE(pa.stat().st_mode) & 0o111 != stat.S_IMODE(pb.stat().st_mode) & 0o111:
            diffs.append(f"exec bit differs: {rel}")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--relock", action="store_true")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="p3build-") as tmp:
        tmp_out = Path(tmp) / "plugin"
        tmp_out.mkdir()
        try:
            notes = build(tmp_out, relock=args.relock)
        except BuildError as exc:
            print(f"build failed: {exc}", file=sys.stderr)
            return 1
        if args.check:
            diffs = trees_equal(tmp_out, OUT)
            if diffs:
                print("plugin/ is stale; run python3 tools/build.py", file=sys.stderr)
                print("\n".join(diffs[:40]), file=sys.stderr)
                return 1
            print("plugin/ is current. " + " ".join(notes))
            return 0
        staging = ROOT / ".plugin.new"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(tmp_out, staging, symlinks=True)
        if OUT.exists():
            old = ROOT / ".plugin.old"
            if old.exists():
                shutil.rmtree(old)
            OUT.rename(old)
            staging.rename(OUT)
            shutil.rmtree(old)
        else:
            staging.rename(OUT)
    print("built plugin/. " + " ".join(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
