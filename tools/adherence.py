#!/usr/bin/env python3
"""Router adherence: how often sessions in jutsu mode open the router, a playbook, and a principle.

    python3 tools/adherence.py [--config-dir DIR ...] [--since YYYY-MM-DD] [--json]

Reads Claude Code transcripts under <config dir>/projects/ (default $CLAUDE_CONFIG_DIR, else
~/.claude). Read-only, and it prints counts only, never transcript text.

Method from pstack-claude issue #264. A main session counts when the jutsu mode hook's text
("jutsu poteto mode is ...") appears in one of its hook attachment records. From that record on,
it counts the session once for each kind of file it opened with the Read tool: the router
(skills/poteto-mode/SKILL.md), a playbook (skills/poteto-mode/playbooks/*.md), and a principle
(principles/principle-*.md). `prompts` counts UserPromptSubmit hook records that carry the text,
one per prompt sent while the mode was on. Subagents of those sessions
(<session>/subagents/agent-*.jsonl) are split into jutsu:poteto-agent and other types. `hook`
counts the ones the SubagentStart hook reached.

Limits: a Bash `cat` or `sed` of a file is not counted as opening it. A forked session copies its
parent's records into a new file, so it can count twice.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = "jutsu poteto mode is"
HOOK_KINDS = {"hook_success", "hook_additional_context"}
KINDS = ("router", "playbook", "principle")
ROUTER = re.compile(r"/skills/poteto-mode/SKILL\.md$")
PLAYBOOK = re.compile(r"/skills/poteto-mode/playbooks/[^/]+\.md$")
PRINCIPLE = re.compile(r"/principles/principle-[^/]+\.md$")


def kind_of(path: str):
    for kind, pattern in (("router", ROUTER), ("playbook", PLAYBOOK), ("principle", PRINCIPLE)):
        if pattern.search(path):
            return kind
    return None


def records(path: Path, stats: dict):
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                stats["skipped_lines"] += 1
                continue
            if isinstance(rec, dict):
                yield rec


def hook_text(rec: dict):
    """The hook's output when rec is a hook attachment carrying the mode text, else None."""
    if rec.get("type") != "attachment":
        return None
    att = rec.get("attachment")
    if not isinstance(att, dict) or att.get("type") not in HOOK_KINDS:
        return None
    text = " ".join(str(att.get(k) or "") for k in ("content", "stdout"))
    return att if MARKER in text else None


def opened(rec: dict):
    if rec.get("type") != "assistant":
        return
    content = (rec.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if isinstance(item, dict) and item.get("type") == "tool_use" and item.get("name") == "Read":
            kind = kind_of(str((item.get("input") or {}).get("file_path") or ""))
            if kind:
                yield kind


def scan(path: Path, stats: dict, from_marker: bool):
    """(mode seen, prompts with the mode, kinds opened). With from_marker, opens count only after the mode text."""
    on = not from_marker
    seen = False
    prompts = 0
    kinds = set()
    for rec in records(path, stats):
        att = hook_text(rec)
        if att is not None:
            on = seen = True
            if att.get("hookEvent") == "UserPromptSubmit":
                prompts += 1
        if on:
            kinds.update(opened(rec))
    return seen, prompts, kinds


def config_dirs(args) -> list[Path]:
    if args.config_dir:
        return [Path(d).expanduser() for d in args.config_dir]
    return [Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()]


def measure(dirs: list[Path], since: float | None) -> dict:
    stats = {"skipped_lines": 0}
    main = {"sessions": 0, "prompts": 0, **{k: 0 for k in KINDS}}
    subs = {t: {"agents": 0, "hook": 0, **{k: 0 for k in KINDS}} for t in ("jutsu:poteto-agent", "other")}
    for config in dirs:
        projects = config / "projects"
        if not projects.is_dir():
            continue
        for session in sorted(projects.glob("*/*.jsonl")):
            if since is not None and session.stat().st_mtime < since:
                continue
            seen, prompts, kinds = scan(session, stats, from_marker=True)
            if not seen:
                continue
            main["sessions"] += 1
            main["prompts"] += prompts
            for k in kinds:
                main[k] += 1
            for agent in sorted((session.parent / session.stem / "subagents").glob("agent-*.jsonl")):
                try:
                    meta = json.loads(agent.with_name(agent.stem + ".meta.json").read_text())
                except (OSError, ValueError):
                    meta = {}
                bucket = subs["jutsu:poteto-agent" if meta.get("agentType") == "jutsu:poteto-agent" else "other"]
                reached, _, kinds = scan(agent, stats, from_marker=False)
                bucket["agents"] += 1
                bucket["hook"] += reached
                for k in kinds:
                    bucket[k] += 1
    return {"config_dirs": len(dirs), "main": main, "subagents": subs, **stats}


def share(n: int, total: int) -> str:
    return f"{n} of {total} ({round(100 * n / total)}%)" if total else f"{n} of 0"


def report(data: dict) -> str:
    m = data["main"]
    lines = [f"Main sessions with jutsu mode on: {m['sessions']} ({m['prompts']} prompts sent while on)"]
    lines += [f"  opened the {k}: {share(m[k], m['sessions'])}" if k == "router" else
              f"  opened a {k}: {share(m[k], m['sessions'])}" for k in KINDS]
    for name, s in data["subagents"].items():
        lines.append(f"Subagents of those sessions, {name}: {s['agents']}")
        lines.append(f"  reached by the SubagentStart hook: {share(s['hook'], s['agents'])}")
        lines += [f"  opened the {k}: {share(s[k], s['agents'])}" if k == "router" else
                  f"  opened a {k}: {share(s[k], s['agents'])}" for k in KINDS]
    if data["skipped_lines"]:
        lines.append(f"Skipped {data['skipped_lines']} unreadable transcript line(s).")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--config-dir", action="append", help="a Claude config dir (repeatable); default $CLAUDE_CONFIG_DIR, else ~/.claude")
    ap.add_argument("--since", help="only transcripts modified on or after this date (YYYY-MM-DD)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    since = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    data = measure(config_dirs(args), since)
    print(json.dumps(data, indent=2) if args.json else report(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
