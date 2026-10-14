#!/usr/bin/env python3
"""Static checks on a built jutsu plugin tree.

    python3 tools/check.py [PLUGIN_DIR]     # default: plugin/

Each check encodes a bug found in an earlier pstack port or in T3's source:
frontmatter that Claude Code rejects or misreads, links that do not resolve,
unresolved {{plugin}} tokens, Cursor-only mechanisms left in prose, T3 tool names
that do not exist, hooks that point at missing or non-executable files, and
unresolved merge conflict markers. The Cursor-only rules test themselves first.
Python 3.9+, stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T3_TOOLS = {l.strip() for l in (ROOT / "tools" / "t3-tools.txt").read_text().splitlines() if l.strip()}
# Tool names T3 accepts but that are not separate MCP tools, or older names that other
# ports used. Listing them here keeps the typo check strict for everything else.
T3_TOOL_LIKE = re.compile(
    r"`((?:t3_[a-z_]+)|(?:preview_[a-z_]+)|(?:device_[a-z_]+)|delegate_task|task_status|task_cancel|"
    r"orchestrator_capabilities|create_threads|schedule_task|list_scheduled_tasks|update_scheduled_task|"
    r"delete_scheduled_task|run_scheduled_task_now|request_secret|watch_pull_request|unwatch_pull_request|"
    r"link_pull_request|unlink_pull_request|list_thread_pull_requests|html_preview|html_render)`")
PLUGIN_AGENT_IGNORED_KEYS = {"permissionMode", "hooks", "mcpServers", "initialPrompt"}

# Cursor-only mechanisms and unsafe text that must not survive in prose.
#
# Each rule proves itself (self_test): `bad` is a line the pattern must match, and
# `good` is the line a port writes instead, which must match no rule. So a pattern
# cannot rot without its examples failing.
#
# `allow` excuses hits line by line: (file, text on the line, reason). The runtime
# maps each Cursor term, so its vocabulary rows may name them. An allowance that
# excuses no hit fails the check, so it goes away with the line it was for.
#
# `outside` limits a rule to every file but the ones named. Only the
# t3_worktree_handoff rule uses it: the runtime is the one place that may name the
# tool, to say not to use it.
RUNTIME = "skills/poteto-mode/references/runtime.md"


def rule(pattern: str, bad: str, good: str, allow=(), outside=()) -> dict:
    return {"pattern": pattern, "re": re.compile(pattern), "bad": bad, "good": good,
            "allow": tuple(allow), "outside": tuple(outside)}


VOCAB = "the vocabulary table maps the Cursor term"
DENY = [
    rule(r"\bgeneralPurpose\b",
         "Spawn a subagent with `subagent_type: generalPurpose`.",
         'Spawn an `Agent` with `subagent_type: "general-purpose"`.',
         allow=[(RUNTIME, "| `generalPurpose` |", VOCAB)]),
    rule(r"\bAskQuestion\b",
         "Use the `AskQuestion` tool.",
         "Use the `AskUserQuestion` tool.",
         allow=[(RUNTIME, "| `AskQuestion` |", VOCAB)]),
    rule(r"cursor-team-kit",
         "Run `/deslop` from `cursor-team-kit` over the diff.",
         "Deslop the diff per the runtime's Missing companions."),
    rule(r"\bcontrol-(?:ui|cli)\b",
         "Browser UIs use `control-ui`.",
         "Browser UIs use T3's `preview_*` tools.",
         allow=[(RUNTIME, "| `control-ui`, `control-cli`, a simulator skill |", VOCAB)]),
    rule(r"agent-transcripts",
         "Read the `agent-transcripts/` directory the system prompt names.",
         "Read the transcript per the runtime's History.",
         allow=[(RUNTIME, "| transcripts, `agent-transcripts/` |", VOCAB)]),
    rule(r"~/\.cursor|\.cursor/",
         "Write `.cursor/skills/verify-<app>/SKILL.md`.",
         "Write `.claude/skills/verify-<app>/SKILL.md`."),
    rule(r"\bCustom Mode\b",
         "Mention once that a Custom Mode keeps it on.",
         "Mention once that `/jutsu` keeps it on for the session."),
    rule(r"\bgrok-\d",
         "Use your configured bug-fix model (default `grok-4.7-xhigh-fast`).",
         "Use the `bug-fix` role in the runtime's Roles."),
    rule(r"claude-opus-\d-\d-(?:x?high|max|medium)",
         "Reviewer A runs on `claude-opus-5-5-xhigh`.",
         'Reviewer A runs with `model: "opus"` and `effort: "xhigh"`.'),
    rule(r"subagent_type: \"poteto-agent\"",
         'Explore in subagents with `subagent_type: "poteto-agent"`.',
         'Explore in subagents with `subagent_type: "jutsu:poteto-agent"`.',
         allow=[(RUNTIME, '| `subagent_type: "poteto-agent"` |', VOCAB)]),
    rule(r"Comment Sicko\"",
         'Spawn it with `subagent_type: "Comment Sicko"`.',
         'Spawn it with `subagent_type: "jutsu:comment-sicko"`.'),
    rule(r"(?<![\w/.-])/poteto-mode\b",
         "Start the task with /poteto-mode.",
         "Start the task with /jutsu."),
    rule(r"pstack-models\.mdc",
         "Read the `pstack-models.mdc` rule.",
         "Read `jutsu-models.md`."),
    rule(r"\bcloud[- ]agents?\b",
         "Hand each slice to a cloud agent.",
         "Hand each slice to a worker in its own worktree.",
         allow=[(RUNTIME, "| cloud agent, own VM |", VOCAB)]),
    rule(r"command -v origin|\borigin pr |\bOrigin CLI\b",
         "If `command -v origin` succeeds, use `origin pr merge <pr>`.",
         "Merge with `gh pr merge <pr> --squash`."),
    rule(r"`Task`|\bTask tool\b|\bTask call",
         "Launch all reviewers in one message with the Task tool.",
         "Launch all reviewers in one message with the `Agent` tool.",
         allow=[(RUNTIME, '| `Task`, subagent, "spawn" |', VOCAB),
                (RUNTIME, "under its old name, `Task`", "says some tool lists still show the old name")]),
    rule(r"readonly strips MCP",
         "Do not use readonly, because readonly strips MCP access.",
         "An `Agent` child keeps its MCP tools."),
    rule(r"readonly: true",
         "Each reviewer gets `readonly: true`.",
         "Each reviewer gets a read-only brief.",
         allow=[(RUNTIME, "| `readonly: true` |", VOCAB)]),
    rule(r"\{\{plugin\}\}",
         "Read `{{plugin}}/skills/how/SKILL.md`.",
         "Read `../../skills/how/SKILL.md`."),
    # Deleting a worktree by force or by hand loses untracked and ignored files
    # (cursor/plugins#449). A plain `git worktree remove` that refuses is the stop.
    rule(r"worktree remove (?:--force|-f)\b|\brm -rf\b",
         "Run `git worktree remove --force <path>`, then `rm -rf` what is left.",
         "Run a plain `git worktree remove <path>`. It refuses when work is at stake."),
    # T3's handoff waited up to nine minutes for the continuation, or never started
    # it (pmwoz/t3-pstack PR #2). The runtime says not to use it.
    rule(r"\bt3_worktree_handoff\b",
         "Hand the thread to a new worktree with `t3_worktree_handoff`.",
         "Create the worktree from your HEAD per the runtime's Isolation.",
         outside=[RUNTIME]),
]


def self_test(rules=None) -> list[str]:
    """Each rule's `bad` line must hit it, and its `good` line must hit no rule."""
    rules = DENY if rules is None else rules
    problems = []
    for r in rules:
        if not r["re"].search(r["bad"]):
            problems.append(f"DENY rule {r['pattern']!r}: does not match its own bad example {r['bad']!r}")
        for other in rules:
            if other["re"].search(r["good"]):
                problems.append(f"DENY rule {r['pattern']!r}: its good example {r['good']!r} "
                                f"matches rule {other['pattern']!r}")
    return problems


# A line git writes for an unresolved merge. `=======` counts only alone on its
# line, so a longer Markdown heading underline does not.
CONFLICT_MARKER = re.compile(r"^(?:<{7}|>{7})(?: |$)|^={7}$", re.M)


def conflict_markers(root: Path, label: str = "") -> list[str]:
    """Each conflict-marker line in the text files under root, as `path:line`."""
    found = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "node_modules" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for hit in CONFLICT_MARKER.finditer(text):
            line = text.count("\n", 0, hit.start()) + 1
            found.append(f"{label}{p.relative_to(root).as_posix()}:{line}: unresolved merge conflict marker "
                         f"{hit.group(0).rstrip()!r}; resolve it, then relock")
    return found

LINK = re.compile(r"\]\(([^)\s#]+)(#[^)]*)?\)")
CODE_PATH = re.compile(r"`((?:\.\./|\./)?(?:\.\./)*(?:skills|playbooks|references|principles|scripts|agents|hooks)/[A-Za-z0-9_./<>-]+\.(?:md|sh|mjs|ts))`")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(text: str) -> dict:
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def check(plugin: Path) -> list[str]:
    errors: list[str] = []
    rel = lambda p: p.relative_to(plugin).as_posix()

    manifest = plugin / ".claude-plugin" / "plugin.json"
    try:
        m = json.loads(manifest.read_text())
        if m.get("name") != "jutsu":
            errors.append("plugin.json: name must be jutsu")
        for a in m.get("agents", []):
            if not (plugin / a).is_file():
                errors.append(f"plugin.json: agent {a} does not exist")
    except (OSError, ValueError) as exc:
        errors.append(f"plugin.json: {exc}")

    for skill in sorted(plugin.glob("skills/*/SKILL.md")):
        fm = frontmatter(skill.read_text())
        name = skill.parent.name
        if fm.get("name") != name:
            errors.append(f"{rel(skill)}: name must equal its directory ({name})")
        desc = fm.get("description", "")
        if not desc:
            errors.append(f"{rel(skill)}: missing description")
        if len(desc) > 1024:
            errors.append(f"{rel(skill)}: description is {len(desc)} chars (max 1024)")
        if desc.startswith("`"):
            errors.append(f"{rel(skill)}: a description starting with a backtick must be quoted")
        if fm.get("disable-model-invocation") != "true":
            errors.append(f"{rel(skill)}: jutsu skills are user-invoked (disable-model-invocation: true)")
    root = frontmatter((plugin / "SKILL.md").read_text()) if (plugin / "SKILL.md").exists() else {}
    if root.get("name") != "jutsu":
        errors.append("SKILL.md: the root alias must be named jutsu")

    for agent in sorted(plugin.glob("agents/*.md")):
        fm = frontmatter(agent.read_text())
        if fm.get("name") != agent.stem:
            errors.append(f"{rel(agent)}: name must equal the file name ({agent.stem})")
        bad = PLUGIN_AGENT_IGNORED_KEYS & set(fm)
        if bad:
            errors.append(f"{rel(agent)}: plugin agents ignore {sorted(bad)}")

    errors += self_test()
    errors += conflict_markers(plugin)
    excused = {(id(d), a): 0 for d in DENY for a in d["allow"]}
    for md in sorted(p for p in plugin.rglob("*.md") if "node_modules" not in p.parts):
        text = md.read_text()
        lines = text.splitlines()
        r = rel(md)
        for d in DENY:
            if r in d["outside"]:
                continue
            for hit in d["re"].finditer(text):
                line = text.count("\n", 0, hit.start()) + 1
                allowance = next((a for a in d["allow"] if a[0] == r and a[1] in lines[line - 1]), None)
                if allowance:
                    excused[(id(d), allowance)] += 1
                    continue
                errors.append(f"{r}:{line}: Cursor-only, unresolved, or unsafe text: {hit.group(0)!r}")
        for hit in LINK.finditer(text):
            target = hit.group(1)
            if re.match(r"[a-z]+:", target):
                continue
            if not (md.parent / target).exists():
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{r}:{line}: link does not resolve: {target}")
        for hit in CODE_PATH.finditer(text):
            target = hit.group(1)
            if "<" in target or ">" in target:
                continue
            bases = [md.parent]
            if not target.startswith("."):
                bases += [plugin, plugin / "skills" / "poteto-mode"]
                bases += [p for p in md.parents if p.parent.name == "skills"]
            if not any((b / target).exists() for b in bases):
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{r}:{line}: path does not resolve: {target}")
        for hit in T3_TOOL_LIKE.finditer(text):
            name = hit.group(1)
            if name not in T3_TOOLS:
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{r}:{line}: not a T3 tool: {name}")

    for d in DENY:
        for a in d["allow"]:
            if not excused[(id(d), a)]:
                errors.append(f"allowance for {d['pattern']!r} in {a[0]} on the line with {a[1]!r} excuses nothing; "
                              "delete it from DENY in tools/check.py")

    # Skill commands are /jutsu:<name> in this plugin. A bare /<name> is upstream's Cursor
    # naming and does not run here.
    names = sorted(d.name for d in plugin.glob("skills/*") if d.is_dir())
    bare = re.compile(r"(?<![\w:/.\-~$])/(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
                      + r")(?![\w/-]|\.\w)") if names else None
    if bare:
        for md in sorted(p for p in plugin.rglob("*.md") if "node_modules" not in p.parts):
            text = md.read_text()
            for hit in bare.finditer(text):
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{rel(md)}:{line}: bare skill command /{hit.group(1)}; use /jutsu:{hit.group(1)}")

    hooks = plugin / "hooks" / "hooks.json"
    try:
        spec = json.loads(hooks.read_text())["hooks"]
        for event, groups in spec.items():
            for group in groups:
                for h in group["hooks"]:
                    cmd = h["command"]
                    m = re.match(r'"\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)"', cmd)
                    if not m:
                        errors.append(f"hooks.json {event}: command must start with a quoted ${{CLAUDE_PLUGIN_ROOT}} path")
                        continue
                    target = plugin / m.group(1)
                    if not target.is_file() or not os.access(target, os.X_OK):
                        errors.append(f"hooks.json {event}: {m.group(1)} is missing or not executable")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"hooks/hooks.json: {exc}")

    for script in [p for p in plugin.rglob("*.sh") if "node_modules" not in p.parts] + [plugin / "hooks" / "jutsu-mode"]:
        if script.exists() and not os.access(script, os.X_OK):
            errors.append(f"{rel(script)}: not executable")
    return errors


def main() -> int:
    plugin = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "plugin"
    errors = check(plugin)
    for e in errors:
        print(e)
    print(f"{len(errors)} problem(s) in {plugin}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
