#!/usr/bin/env python3
"""Install p3 into every Claude Code config dir that T3 Code uses.

p3 ships as a Claude Code "skills-dir plugin": one symlink, <config>/skills/p3 -> plugin/.
Claude Code then loads it as p3@skills-dir with its skills, agents, and hooks. Nothing
else in the config dir is written: no settings.json edits, no marketplace records.

    ./install.sh                 link p3 into each config dir
    ./install.sh --status        show what is linked and what conflicts
    ./install.sh --uninstall     remove p3's links (add --purge to drop its session state)
    ./install.sh --dry-run ...   print the actions only

Config dirs come from T3's provider settings, resolved the way T3 resolves them
(apps/server/src/provider/Drivers/ClaudeHome.ts): an instance's homePath, else
CLAUDE_CONFIG_DIR from the instance's environment, else the inherited
CLAUDE_CONFIG_DIR, else ~/.claude. Python 3.9+, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugin"
LINK_NAME = "p3"
PLUGIN_NAME = "p3"
DATA_DIR_NAME = "p3-skills-dir"
CLAUDE_DRIVER = "claudeAgent"
MIN_CLAUDE = (2, 1, 292)
CONFLICT_PLUGIN_PREFIXES = ("pstack@",)
CONFLICT_SKILL_DIRS = ("poteto-mode", "p3-mode", "pstack-runtime")


def expand_home(value: str) -> str:
    if value == "~":
        return str(Path.home())
    if value.startswith("~/"):
        return str(Path.home() / value[2:])
    return value


def default_config_dir(env: dict) -> Path:
    inherited = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
    return Path(inherited).resolve() if inherited else (Path.home() / ".claude").resolve()


def t3_settings_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    home = os.environ.get("T3CODE_HOME") or os.environ.get("T3_HOME") or str(Path.home() / ".t3")
    return Path(home).expanduser() / "userdata" / "settings.json"


def claude_config_dirs(settings_path: Path, env: dict) -> list[tuple[Path, str]]:
    """(config dir, why) for every Claude instance T3 knows, plus the default instance."""
    found: dict[Path, str] = {default_config_dir(env): "default Claude instance (claudeAgent)"}
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(found.items())
    for instance_id, instance in (settings.get("providerInstances") or {}).items():
        if not isinstance(instance, dict) or instance.get("driver") != CLAUDE_DRIVER:
            continue
        config = instance.get("config") or {}
        if not isinstance(config, dict):
            config = {}
        home_path = str(config.get("homePath") or "").strip()
        instance_env = {
            str(item.get("name")): str(item.get("value") or "")
            for item in instance.get("environment") or []
            if isinstance(item, dict) and item.get("name")
        }
        if home_path:
            path = Path(expand_home(home_path)).resolve()
        elif instance_env.get("CLAUDE_CONFIG_DIR", "").strip():
            path = Path(instance_env["CLAUDE_CONFIG_DIR"].strip()).resolve()
        else:
            path = default_config_dir(env)
        found.setdefault(path, f"T3 instance {instance_id}")
    return list(found.items())


def is_our_plugin(path: Path) -> bool:
    manifest = path / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("name") == PLUGIN_NAME
    except (OSError, ValueError):
        return False


def link_state(link: Path) -> str:
    if link.is_symlink():
        target = Path(os.readlink(link))
        target = target if target.is_absolute() else (link.parent / target)
        if target.resolve() == PLUGIN.resolve():
            return "ours"
        dangling_checkout = not target.exists() and target.name == "plugin"
        return "stale-ours" if (is_our_plugin(target) or dangling_checkout) else "foreign-link"
    if link.exists():
        return "foreign"
    return "absent"


def conflicts(config_dir: Path) -> list[str]:
    found = []
    try:
        settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    for plugin_id, enabled in (settings.get("enabledPlugins") or {}).items():
        if enabled and plugin_id.startswith(CONFLICT_PLUGIN_PREFIXES):
            found.append(f"plugin {plugin_id} is enabled (a second poteto-mode router and session hook)")
    for name in CONFLICT_SKILL_DIRS:
        if (config_dir / "skills" / name).exists():
            found.append(f"skill {config_dir / 'skills' / name} is installed (another pstack port)")
    return found


def claude_version() -> tuple[int, ...] | None:
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Install p3 into each Claude Code config dir T3 uses.")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--purge", action="store_true", help="with --uninstall, also remove p3's session state")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", action="append", default=[], help="add a Claude config dir (repeatable)")
    ap.add_argument("--t3-settings", help="path to T3's settings.json (default ~/.t3/userdata/settings.json)")
    args = ap.parse_args()

    if not (PLUGIN / ".claude-plugin" / "plugin.json").exists():
        print(f"error: {PLUGIN} is missing. Run python3 tools/build.py first.", file=sys.stderr)
        return 1

    targets = claude_config_dirs(t3_settings_path(args.t3_settings), dict(os.environ))
    for extra in args.config_dir:
        targets.append((Path(expand_home(extra)).resolve(), "--config-dir"))
    seen: set[Path] = set()
    targets = [(p, why) for p, why in targets if not (p in seen or seen.add(p))]

    version = claude_version()
    if version is None:
        print("note: `claude` is not on PATH, so its version was not checked.")
    elif version < MIN_CLAUDE:
        print(f"warning: Claude Code {'.'.join(map(str, version))} is older than "
              f"{'.'.join(map(str, MIN_CLAUDE))}. Update it with `claude update`.")

    status = 0
    for config_dir, why in targets:
        link = config_dir / "skills" / LINK_NAME
        state = link_state(link)
        print(f"{config_dir}  ({why})")
        if not config_dir.is_dir():
            print("  skip: this config dir does not exist yet. Start Claude once with it, then rerun.")
            continue
        if args.status:
            print(f"  p3 link: {state}")
            for c in conflicts(config_dir):
                print(f"  conflict: {c}")
            continue
        if args.uninstall:
            if state in ("ours", "stale-ours"):
                if not args.dry_run:
                    link.unlink()
                print(f"  removed {link}")
            else:
                print(f"  nothing to remove ({state})")
            data = config_dir / "plugins" / "data" / DATA_DIR_NAME
            if args.purge and data.is_dir():
                if not args.dry_run:
                    shutil.rmtree(data)
                print(f"  removed {data}")
            continue
        if state == "ours":
            print("  already linked")
        elif state in ("absent", "stale-ours"):
            if not args.dry_run:
                link.parent.mkdir(parents=True, exist_ok=True)
                if state == "stale-ours":
                    link.unlink()
                link.symlink_to(PLUGIN.resolve(), target_is_directory=True)
            print(f"  linked {link} -> {PLUGIN.resolve()}")
        else:
            print(f"  error: {link} exists and is not p3's link. Move it away, then rerun.")
            status = 1
            continue
        for c in conflicts(config_dir):
            print(f"  conflict: {c}")
            if c.startswith("plugin "):
                plugin_id = c.split()[1]
                print(f"    fix: CLAUDE_CONFIG_DIR={config_dir} claude plugin disable {plugin_id}")
    if not args.status and not args.uninstall:
        print("Start a new Claude thread in T3 (or run /reload-plugins) and type $p3 or /p3 <task>.")
    return status


if __name__ == "__main__":
    sys.exit(main())
