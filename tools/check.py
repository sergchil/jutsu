#!/usr/bin/env python3
"""Static checks on a built p3 plugin tree.

    python3 tools/check.py [PLUGIN_DIR]     # default: plugin/

Each check encodes a bug found in an earlier pstack port or in T3's source:
frontmatter that Claude Code rejects or misreads, links that do not resolve,
unresolved {{p3}} tokens, Cursor-only mechanisms left in prose, T3 tool names
that do not exist, and hooks that point at missing or non-executable files.
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

# Cursor-only mechanisms that must not survive in prose. (pattern, allowed files)
# The runtime maps each Cursor term, so its vocabulary table may name them.
RUNTIME = "skills/poteto-mode/references/runtime.md"
DENY = [
    (r"\bgeneralPurpose\b", (RUNTIME,)),
    (r"\bAskQuestion\b", (RUNTIME,)),
    (r"cursor-team-kit", ()),
    (r"\bcontrol-(?:ui|cli)\b", (RUNTIME,)),
    (r"agent-transcripts", (RUNTIME,)),
    (r"~/\.cursor|\.cursor/", ()),
    (r"\bCustom Mode\b", ()),
    (r"\bgrok-\d", ()),
    (r"claude-opus-\d-\d-(?:x?high|max|medium)", ()),
    (r"subagent_type: \"poteto-agent\"", (RUNTIME,)),
    (r"Comment Sicko\"", ()),
    (r"(?<![\w/.-])/poteto-mode\b", ()),
    (r"pstack-models\.mdc", ()),
    (r"\bcloud[- ]agents?\b", (RUNTIME,)),
    (r"command -v origin|\borigin pr |\bOrigin CLI\b", ()),
    (r"`Task`|\bTask tool\b|\bTask call", (RUNTIME,)),
    (r"readonly strips MCP", ()),
    (r"\{\{p3\}\}", ()),
]

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
        if m.get("name") != "p3":
            errors.append("plugin.json: name must be p3")
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
            errors.append(f"{rel(skill)}: p3 skills are user-invoked (disable-model-invocation: true)")
    root = frontmatter((plugin / "SKILL.md").read_text()) if (plugin / "SKILL.md").exists() else {}
    if root.get("name") != "p3":
        errors.append("SKILL.md: the root alias must be named p3")

    for agent in sorted(plugin.glob("agents/*.md")):
        fm = frontmatter(agent.read_text())
        if fm.get("name") != agent.stem:
            errors.append(f"{rel(agent)}: name must equal the file name ({agent.stem})")
        bad = PLUGIN_AGENT_IGNORED_KEYS & set(fm)
        if bad:
            errors.append(f"{rel(agent)}: plugin agents ignore {sorted(bad)}")

    for md in sorted(p for p in plugin.rglob("*.md") if "node_modules" not in p.parts):
        text = md.read_text()
        r = rel(md)
        for pattern, allowed in DENY:
            if r in allowed:
                continue
            for hit in re.finditer(pattern, text):
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{r}:{line}: Cursor-only or unresolved text: {hit.group(0)!r}")
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

    # Skill commands are /p3:<name> in this plugin. A bare /<name> is upstream's Cursor
    # naming and does not run here.
    names = sorted(d.name for d in plugin.glob("skills/*") if d.is_dir())
    bare = re.compile(r"(?<![\w:/.\-~$])/(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True)))
                      + r")(?![\w/-]|\.\w)") if names else None
    if bare:
        for md in sorted(p for p in plugin.rglob("*.md") if "node_modules" not in p.parts):
            text = md.read_text()
            for hit in bare.finditer(text):
                line = text.count("\n", 0, hit.start()) + 1
                errors.append(f"{rel(md)}:{line}: bare skill command /{hit.group(1)}; use /p3:{hit.group(1)}")

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

    for script in [p for p in plugin.rglob("*.sh") if "node_modules" not in p.parts] + [plugin / "hooks" / "p3-mode"]:
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
