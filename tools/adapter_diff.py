#!/usr/bin/env python3
"""Cross-check upstream's own Claude Code adapter against jutsu.

    python3 tools/adapter_diff.py            # report; exit 1 on an unreviewed or broken row
    python3 tools/adapter_diff.py --quiet    # print only problems

Upstream pstack ships docs/harness/claude-code.md: tables that map each Cursor name to
Claude Code. jutsu does the same job in its runtime map and overrides. port/adapter.json
records, per adapter row, how jutsu answers it:

    "<section> | <Cursor cell>": {
      "theirs": "<their Claude Code cell, as reviewed>",
      "verdict": "same" | "different",
      "jutsu": "<jutsu's answer, one sentence>",
      "why": "<for different: why jutsu differs on purpose>",
      "where": "<plugin path>", "expect": "<regex that file must match>"
    }

The tool reports each row whose verdict is `different` (a deliberate difference), and
fails on a row with no entry (upstream added it), a row whose Claude Code cell changed
since review, an entry whose row is gone, and an entry whose `expect` no longer matches
jutsu's built plugin. For an unreviewed row it names each code span in their cell that
jutsu's runtime map forbids or never names, to speed up the review. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "vendor" / "pstack" / "docs" / "harness" / "claude-code.md"
RECORD = ROOT / "port" / "adapter.json"
PLUGIN = ROOT / "plugin"
RUNTIME = "skills/poteto-mode/references/runtime.md"
NEGATION = re.compile(r"\b(?:never|do not|don't|not|no)\b", re.I)


def parse_rows(text: str) -> list[tuple[str, str, str]]:
    """(section, Cursor cell, Claude Code cell) for each body row of each two-column table."""
    rows, section, in_table = [], "", False
    for line in text.splitlines():
        if line.startswith("## "):
            section, in_table = line[3:].strip(), False
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        if not in_table:
            in_table = True  # header row
            continue
        if set(cells[0]) <= set("-: "):
            continue  # separator row
        rows.append((section, cells[0], cells[1]))
    return rows


def key(section: str, cursor: str) -> str:
    return f"{section} | {cursor}"


def spans(cell: str) -> list[str]:
    return [s for s in re.findall(r"`([^`]+)`", cell) if len(s) > 2]


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+|\n", text)


def hints(cell: str, jutsu_text: str) -> list[str]:
    """For a row nobody reviewed: code spans jutsu forbids or never names."""
    out = []
    for s in spans(cell):
        hits = [x for x in sentences(jutsu_text) if s in x]
        if not hits:
            out.append(f"jutsu never names `{s}`")
        elif any(NEGATION.search(x) for x in hits):
            neg = next(x for x in hits if NEGATION.search(x))
            out.append(f"jutsu limits `{s}`: \"{neg.strip()[:140]}\"")
    return out


def diff(adapter_text: str, record: dict, plugin: Path) -> tuple[list[str], list[str]]:
    """(differences, problems)."""
    runtime = plugin / RUNTIME
    jutsu_text = runtime.read_text(encoding="utf-8") if runtime.is_file() else ""
    rows = parse_rows(adapter_text)
    differences, problems, seen = [], [], set()
    for section, cursor, theirs in rows:
        k = key(section, cursor)
        seen.add(k)
        entry = record.get(k)
        if entry is None:
            problems.append(f"new adapter row, review it and add it to port/adapter.json: {k} -> {theirs}")
            for h in hints(theirs, jutsu_text):
                problems.append(f"    {h}")
            continue
        if entry.get("theirs") != theirs:
            problems.append(f"adapter row changed, re-review it and update port/adapter.json: {k}\n"
                            f"    was: {entry.get('theirs')}\n    now: {theirs}")
        where = plugin / entry.get("where", RUNTIME)
        expect = entry.get("expect")
        if not where.is_file():
            problems.append(f"{k}: port/adapter.json names {entry.get('where')}, which the plugin lacks")
        elif expect and not re.search(expect, where.read_text(encoding="utf-8")):
            problems.append(f"{k}: jutsu's {entry.get('where', RUNTIME)} no longer matches /{expect}/; "
                            "fix jutsu or the entry")
        if entry.get("verdict") == "different":
            differences.append(f"{k}\n    upstream: {theirs}\n    jutsu:    {entry.get('jutsu')}\n"
                               f"    why:      {entry.get('why')}")
        elif entry.get("verdict") != "same":
            problems.append(f"{k}: verdict must be same or different")
    for k in sorted(set(record) - seen):
        problems.append(f"port/adapter.json names a row the adapter no longer has: {k}")
    return differences, problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-check upstream's Claude Code adapter against jutsu.")
    ap.add_argument("--quiet", action="store_true", help="print only problems")
    args = ap.parse_args()
    if not ADAPTER.is_file():
        print(f"upstream has no Claude Code adapter at {ADAPTER.relative_to(ROOT)}; nothing to compare")
        return 0
    record = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else {}
    differences, problems = diff(ADAPTER.read_text(encoding="utf-8"), record, PLUGIN)
    if not args.quiet:
        print(f"{len(parse_rows(ADAPTER.read_text(encoding='utf-8')))} adapter rows, "
              f"{len(differences)} deliberate difference(s), {sum(1 for p in problems if not p.startswith('    '))} problem(s)")
        for d in differences:
            print(f"different: {d}")
    for p in problems:
        print(p if p.startswith("    ") else f"problem: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
