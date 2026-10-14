#!/usr/bin/env python3
"""Generate tools/t3-tools.txt from a pinned snapshot of T3 Code's own source.

    python3 tools/t3_tools.py                    # regenerate at the pin in port/t3.json
    python3 tools/t3_tools.py --ref main         # move the pin to a ref and regenerate
    python3 tools/t3_tools.py --ref main --dry-run   # print the diff only, write nothing
    python3 tools/t3_tools.py --check            # fail when the committed list differs from the pin
    python3 tools/t3_tools.py --source DIR ...   # read an existing T3 checkout, no clone

T3 registers each MCP tool with `Tool.make(<name>, ...)` in
apps/server/src/mcp/toolkits/<toolkit>/*.ts. The name is a string literal or a
constant such as HTML_RENDER_TOOL_NAME that lives in another package, so constants
are resolved across every file of the snapshot. As an independent count, the tools
named in `Toolkit.make(...)` must match the `Tool.make` calls one for one.
tools/check.py reads the list to reject T3 tool names that do not exist.
Python 3.9+, stdlib only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "port" / "t3.json"
LIST = ROOT / "tools" / "t3-tools.txt"
# Where jutsu text lives. A removed T3 tool named here needs a port change.
MENTION_DIRS = ("plugin", "port/added", "port/overrides", "port/subs", "docs")

IDENT = r"[A-Za-z_$][\w$]*"
TOOL_MAKE = re.compile(r"\bTool\s*\.\s*make\s*\(")
TOOLKIT_MAKE = re.compile(r"\bToolkit\s*\.\s*make\s*\(")
STRING = r"(?:\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|`[^`$\\]*`)"
CONST = re.compile(
    rf"\bconst\s+({IDENT})\s*(?::[^=;]+)?=\s*({STRING})\s*(?:as\s+const\s*)?[;\n]")


class ExtractError(Exception):
    pass


def strip_comments(src: str) -> str:
    """Blank out // and /* */ comments, keeping strings and line numbers intact."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def unquote(lit: str) -> str:
    return lit[1:-1]


def balanced_args(code: str, start: int) -> str:
    """Text between the paren that ends at `start` - 1 and its closing paren."""
    depth, i = 1, start
    while i < len(code) and depth:
        c = code[i]
        if c in "\"'`":
            j = i + 1
            while j < len(code) and code[j] != c:
                j += 2 if code[j] == "\\" else 1
            i = j
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return code[start:i - 1]


def split_top(args: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for c in args:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def constants(files: dict[str, str]) -> dict[str, set[str]]:
    """Every `const NAME = "literal"` in the snapshot, by name."""
    found: dict[str, set[str]] = {}
    for code in files.values():
        for m in CONST.finditer(code):
            found.setdefault(m.group(1), set()).add(unquote(m.group(2)))
    return found


def extract(toolkit_files: dict[str, str], other_files: dict[str, str] | None = None) -> list[str]:
    """Tool names registered in the toolkit sources. Raises ExtractError on anything unresolved.

    toolkit_files: path -> TypeScript source under the toolkits directory.
    other_files: path -> source of the rest of the snapshot, searched for constants.
    """
    tk = {p: strip_comments(s) for p, s in toolkit_files.items()}
    every = dict(tk)
    every.update({p: strip_comments(s) for p, s in (other_files or {}).items()})
    global_consts = constants(every)

    names: dict[str, str] = {}
    registered: set[str] = set()
    inline = 0
    for path, code in sorted(tk.items()):
        local = constants({path: code})
        for m in TOOL_MAKE.finditer(code):
            first = split_top(balanced_args(code, m.end()))[:1]
            arg = first[0] if first else ""
            line = code.count("\n", 0, m.start()) + 1
            if re.fullmatch(STRING, arg):
                name = unquote(arg)
            elif re.fullmatch(IDENT, arg):
                values = local.get(arg) or global_consts.get(arg) or set()
                if len(values) != 1:
                    why = "no string constant" if not values else f"conflicting values {sorted(values)}"
                    raise ExtractError(
                        f"{path}:{line}: Tool.make({arg}): {why} found in the snapshot. "
                        f"Add the file that defines {arg} to `paths` in port/t3.json.")
                name = next(iter(values))
            else:
                raise ExtractError(f"{path}:{line}: cannot read the tool name in Tool.make({arg[:60]})")
            if name in names:
                raise ExtractError(f"{path}:{line}: tool {name} is also made at {names[name]}")
            names[name] = f"{path}:{line}"
        for m in TOOLKIT_MAKE.finditer(code):
            for arg in split_top(balanced_args(code, m.end())):
                if re.fullmatch(IDENT, arg):
                    registered.add(f"{path}:{arg}")
                elif TOOL_MAKE.search(arg):
                    inline += 1
                else:
                    raise ExtractError(f"{path}: cannot read Toolkit.make argument {arg[:60]}")
    if len(registered) + inline != len(names):
        raise ExtractError(
            f"{len(names)} Tool.make calls but {len(registered) + inline} distinct tools in "
            "Toolkit.make. A tool is made but not registered, or the reader missed one.")
    return sorted(names)


def git(*cmd: str, cwd: Path | None = None) -> str:
    return subprocess.run(("git",) + cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def clone(pin: dict, ref: str, dest: Path) -> tuple[str, str]:
    git("clone", "--quiet", "--filter=blob:none", "--no-checkout", pin["repository"], str(dest))
    git("sparse-checkout", "set", *pin["paths"], cwd=dest)
    git("checkout", "--quiet", ref, cwd=dest)
    return git("rev-parse", "HEAD", cwd=dest), git("log", "-1", "--format=%cs", "HEAD", cwd=dest)


def read_tree(source: Path, pin: dict) -> tuple[dict[str, str], dict[str, str]]:
    toolkits, others = {}, {}
    base = source / pin["toolkits"]
    if not base.is_dir():
        raise ExtractError(f"{pin['toolkits']} is missing in the T3 checkout")
    for p in pin["paths"]:
        for f in sorted((source / p).rglob("*.ts")):
            if f.name.endswith((".test.ts", ".testkit.ts", ".d.ts")):
                continue
            rel = f.relative_to(source).as_posix()
            text = f.read_text(encoding="utf-8")
            # Toolkits live one directory down: toolkits/<toolkit>/<file>.ts
            if f.parent.parent == base:
                toolkits[rel] = text
            else:
                others[rel] = text
    if not toolkits:
        raise ExtractError(f"no toolkit sources under {pin['toolkits']}")
    return toolkits, others


def render(names: list[str], pin: dict) -> str:
    head = [
        "# Generated by tools/t3_tools.py from T3 Code's toolkit sources. Do not edit.",
        f"# {pin['repo']} {pin['commit']} ({pin['date']}), {pin['toolkits']}/*/",
        f"# {len(names)} tools",
    ]
    return "\n".join(head + names) + "\n"


def names_in(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]


def mentions(name: str) -> list[str]:
    word = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
    hits = []
    for d in MENTION_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.is_file():
                try:
                    if word.search(f.read_text(encoding="utf-8")):
                        hits.append(f.relative_to(ROOT).as_posix())
                except UnicodeDecodeError:
                    pass
    return hits


def report(old: list[str], new: list[str]) -> str:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    lines = [f"{len(old)} -> {len(new)} tools"]
    lines += [f"added: {n}" for n in added]
    for n in removed:
        files = mentions(n)
        lines.append(f"removed: {n}" + (f" (mentioned in {', '.join(files)})" if files else ""))
    if not added and not removed:
        lines.append("no tool names changed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="T3 commit, tag or branch (default: the pinned commit)")
    ap.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    ap.add_argument("--check", action="store_true", help="fail when the committed list differs from the pin")
    ap.add_argument("--source", type=Path, help="existing T3 checkout to read instead of cloning")
    args = ap.parse_args(argv)
    pin = json.loads(PIN.read_text())

    with tempfile.TemporaryDirectory(prefix="jutsu-t3-") as tmp:
        try:
            if args.source:
                src = args.source
                commit = git("rev-parse", "HEAD", cwd=src)
                date = git("log", "-1", "--format=%cs", "HEAD", cwd=src)
            else:
                src = Path(tmp) / "t3code"
                commit, date = clone(pin, args.ref or pin["commit"], src)
            names = extract(*read_tree(src, pin))
        except (ExtractError, subprocess.CalledProcessError) as e:
            detail = getattr(e, "stderr", None) or ""
            print(f"t3_tools: {e} {detail}".strip(), file=sys.stderr)
            return 2

    new_pin = dict(pin, commit=commit, date=date)
    text = render(names, new_pin)
    current = LIST.read_text() if LIST.exists() else ""

    if args.check:
        if commit != pin["commit"]:
            print(f"t3_tools: checked out {commit}, but port/t3.json pins {pin['commit']}", file=sys.stderr)
            return 1
        if current != text:
            sys.stdout.writelines(difflib.unified_diff(
                current.splitlines(True), text.splitlines(True), "tools/t3-tools.txt (committed)",
                "tools/t3-tools.txt (from pin)"))
            print("t3_tools: tools/t3-tools.txt differs from the pinned T3 source. "
                  "Run python3 tools/t3_tools.py", file=sys.stderr)
            return 1
        print(f"t3_tools: {len(names)} tools match {pin['repo']} {commit[:12]}")
        return 0

    print(f"T3 {pin['commit'][:12]} ({pin.get('date', '?')}) -> {commit[:12]} ({date})")
    print(report(names_in(current), names))
    if args.dry_run:
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(True), text.splitlines(True), "tools/t3-tools.txt", "tools/t3-tools.txt (new)"))
        return 0
    LIST.write_text(text)
    PIN.write_text(json.dumps(new_pin, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
