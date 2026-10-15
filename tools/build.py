#!/usr/bin/env python3
"""Build the jutsu plugin from the vendored upstream pstack plus the port overlay.

    python3 tools/build.py            # write plugin/
    python3 tools/build.py --check    # exit 1 if plugin/ is stale
    python3 tools/build.py --relock   # record current upstream hashes for overrides

Pipeline per upstream file: map path -> transform frontmatter -> apply substitutions
-> replace with an override when one exists. Then copy port/added/ and generate the
root router alias. Python 3.9+, stdlib only.

The build fails on an override with no reason in port/overrides.json (or a reason
with no override), on an override that matches upstream, and on any merge
conflict marker line under port/.
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
OVERRIDES = ROOT / "port" / "overrides"
LOCK = ROOT / "port" / "overrides.lock.json"
REASONS = ROOT / "port" / "overrides.json"
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
    elif principle:
        pass
    return "---\n" + "\n".join(kept) + "\n---\n" + text[m.end():]


def load_substitutions() -> list:
    """The rules in port/subs/*.json, in file name order."""
    subs = []
    for extra in sorted((ROOT / "port" / "subs").glob("*.json")):
        for rule in load_json(extra)["substitutions"]:
            rule = dict(rule)
            rule.setdefault("id", f"{extra.stem}:{rule['pattern'][:40]}")
            subs.append(rule)
    return subs


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


def apply_subs(out_rel: str, text: str, compiled: list, count: bool = True) -> str:
    for s in compiled:
        if s["files"] and not s["files"].search(out_rel):
            continue
        text, n = s["re"].subn(s["repl"], text)
        if count:
            s["hits"] += n
    return text


REASON_KINDS = ("runtime", "upstream-bug", "lesson", "naming", "other")


def reason_problems(reasons: dict, overrides: set) -> list[str]:
    """Every override needs a reason in port/overrides.json, and every reason a file."""
    problems = []
    for out_rel in sorted(overrides - set(reasons)):
        problems.append(f"port/overrides/{out_rel} has no entry in port/overrides.json; "
                        "add its kind, why, and upstream link")
    for out_rel in sorted(set(reasons) - overrides):
        problems.append(f"port/overrides.json names {out_rel}, which has no override; delete the entry")
    for out_rel in sorted(set(reasons) & overrides):
        r = reasons[out_rel]
        if not isinstance(r, dict) or set(r) != {"kind", "why", "upstream"}:
            problems.append(f"port/overrides.json {out_rel}: needs exactly kind, why, and upstream")
            continue
        if r["kind"] not in REASON_KINDS:
            problems.append(f"port/overrides.json {out_rel}: kind must be one of {', '.join(REASON_KINDS)}")
        if not isinstance(r["why"], str) or not r["why"].strip():
            problems.append(f"port/overrides.json {out_rel}: why must be one short sentence")
        if r["upstream"] is not None and not str(r["upstream"]).startswith("https://"):
            problems.append(f"port/overrides.json {out_rel}: upstream must be an issue or PR URL, or null")
    return problems


def bare_command_pattern(names) -> "re.Pattern[str]":
    """A /<skill> command written the upstream (Cursor) way. Not a path, URL, or /jutsu:<skill>."""
    return re.compile(r"(?<![\w:/.\-~$])/(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
                      + r")(?![\w/-]|\.\w)")


def name_commands(text: str, pattern) -> str:
    """Skill commands run as /jutsu:<name> in this plugin."""
    return pattern.sub(r"/jutsu:\1", text)


PLUGIN_TOKEN = re.compile(r"\{\{plugin\}\}")


def resolve_plugin_token(out_rel: str, text: str) -> str:
    """Replace {{plugin}} with the relative path from this file's directory to the plugin root.

    Content files are read by the model by path, so links stay relative to the file
    being read, the way upstream writes them. Agent bodies are system prompts, not
    files, so they must not use the token (checked in tools/check.py).
    """
    depth = out_rel.count("/")
    rel = "/".join([".."] * depth) if depth else "."
    return PLUGIN_TOKEN.sub(rel, text)


def build(out_dir: Path, relock=False, check_lock: bool = True) -> list[str]:
    """relock: False, True (every override), or a set of plugin paths to relock."""
    spec = load_json(SPEC)
    compiled = compile_subs(load_substitutions())
    lock = load_json(LOCK) if LOCK.exists() else {}
    vendor = ROOT / spec["vendor"]
    notes: list[str] = []
    problems: list[str] = []
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
            ours = override.read_bytes()
            if ours == src.read_bytes() or (is_text(src) and ours.decode("utf-8", "replace") == apply_subs(
                    out_rel, transform_frontmatter(out_rel, src.read_text(encoding="utf-8"), spec),
                    compiled, count=False)):
                problems.append(f"port/overrides/{out_rel} matches upstream; delete the override and its lock entry")
            if relock is True or (relock and out_rel in relock):
                lock[out_rel] = have
            elif relock and want != have:
                problems.append(f"re-merge port/overrides/{out_rel}: upstream {rel} changed (not in --relock list)")
            elif check_lock and want != have:
                problems.append(
                    f"re-merge port/overrides/{out_rel}: upstream {rel} changed "
                    f"(see `git diff HEAD -- vendor/pstack/{rel}`)")
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
        if out_rel not in produced and not relock and check_lock:
            problems.append(f"upstream removed the file behind port/overrides/{out_rel}; delete the override and its lock entry")
    override_files = set()
    for ov in sorted(OVERRIDES.rglob("*")):
        if ov.is_file() and ov.name != ".DS_Store":
            out_rel = ov.relative_to(OVERRIDES).as_posix()
            override_files.add(out_rel)
            if out_rel not in produced:
                problems.append(f"port/overrides/{out_rel} matches no upstream file; move it to port/added/ or delete it")
    problems += reason_problems(load_json(REASONS) if REASONS.exists() else {}, override_files)
    import check as checker  # same folder; static checks the plugin must pass
    problems += checker.conflict_markers(ROOT / "port", "port/")
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

    commands = bare_command_pattern([d.name for d in (out_dir / "skills").iterdir() if d.is_dir()])
    for out_rel, kind in list(produced.items()):
        if kind == "binary" or not out_rel.endswith(".md"):
            continue
        path = out_dir / out_rel
        text = path.read_text(encoding="utf-8")
        resolved = name_commands(resolve_plugin_token(out_rel, text), commands)
        if resolved != text:
            path.write_text(resolved, encoding="utf-8")

    for s in compiled:
        if s["hits"] == 0:
            problems.append(f"substitution {s['id']} matched nothing; upstream text moved, so update or delete the rule")
    if problems:
        raise BuildError(f"{len(problems)} thing(s) to port after the upstream change:\n  - " + "\n  - ".join(problems))
    found = checker.check(out_dir)
    if found:
        raise BuildError(f"{len(found)} check problem(s) in the built plugin:\n  - " + "\n  - ".join(found[:40]))
    notes.append(f"{len(produced)} files: " + ", ".join(
        f"{k}={sum(1 for v in produced.values() if v == k)}" for k in ("upstream", "override", "added", "binary")))
    return notes


RUNTIME_ONLY = ("node_modules",)


def tree_files(root: Path) -> set[str]:
    """Files in a plugin tree, without dependencies the bundled scripts install at runtime."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and not any(part in RUNTIME_ONLY for part in p.relative_to(root).parts)}


def trees_equal(a: Path, b: Path) -> list[str]:
    diffs = []
    files_a = tree_files(a)
    files_b = tree_files(b) if b.exists() else set()
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
    ap.add_argument("--relock", nargs="*", metavar="PLUGIN_PATH",
                    help="record current upstream hashes: for every override, or only for the given plugin paths")
    ap.add_argument("--out", help="write the build here instead of plugin/ (for previews)")
    ap.add_argument("--no-lock", action="store_true", help="skip the override lock check (previews only)")
    args = ap.parse_args()
    if args.out:
        out = Path(args.out).resolve()
        if out == OUT or OUT in out.parents or out in OUT.parents:
            print("--out must be outside plugin/", file=sys.stderr)
            return 2
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        try:
            notes = build(out, relock=False, check_lock=not args.no_lock)
        except BuildError as exc:
            print(f"build failed: {exc}", file=sys.stderr)
            return 1
        print(f"built {out}. " + " ".join(notes))
        return 0
    with tempfile.TemporaryDirectory(prefix="jutsu-build-") as tmp:
        tmp_out = Path(tmp) / "plugin"
        tmp_out.mkdir()
        try:
            notes = build(tmp_out, relock=(True if args.relock == [] else set(args.relock) if args.relock else False))
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
