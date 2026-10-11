# How jutsu works

## Packaging

jutsu is a Claude Code "skills-dir plugin". `install.sh` puts one symlink, `<claude config dir>/skills/jutsu -> <checkout>/plugin`, into each Claude config dir that T3 uses (it reads them from T3's provider settings). Claude Code then loads the folder as `jutsu@skills-dir`: 27 user-invoked skills, two agents (`jutsu:poteto-agent`, `jutsu:comment-sicko`), and a mode hook. The root `SKILL.md` is the `/jutsu` command, which also appears in T3's `$` skill picker.

- Every skill sets `disable-model-invocation: true`, so none of them crowd Claude's skill list. The router reads the other skills and the 24 principles as files, by path.
- `plugin/hooks/jutsu-mode` keeps the mode on: `/jutsu` writes a per-session flag, each later prompt gets pstack's one-line reminder, and a compaction, resume, or fork re-points Claude at the router. It never blocks a prompt.

## Install details

`install.sh` reads T3's provider settings and finds the Claude config dir of every enabled Claude instance, the way T3 does: `homePath`, else the instance's `CLAUDE_CONFIG_DIR`, else `~/.claude`. It also links a `CLAUDE_CONFIG_DIR` exported in your shell, which the T3 desktop app does not pass on. It writes nothing else: no `settings.json` edits, no marketplace records. `./install.sh --status` shows what is linked.

**Another pstack port installed?** Two routers in one session fight. The installer names any enabled `pstack@…` plugin and any `poteto-mode` or `jutsu-mode` skill, with the command to turn it off (`claude plugin disable pstack@pstack-claude`). To keep it everywhere except one repo, commit `{ "enabledPlugins": { "pstack@pstack-claude": false } }` to that repo's `.claude/settings.json`.

**T3 runtime modes.** *Approval required* asks before every write. *Auto* and *Full access* approve tool calls without asking; jutsu still pauses on its own before force-pushes, deploys, data deletion, and messages to customers. An unattended run needs one of those two, because a child never gets more access than its parent. *Plan* suits read-only playbooks: T3 keeps Claude's plan and stops, so approve it and send the next message.

**Requirements in detail.** Claude Code 2.1.292 added the per-subagent `effort` the role table needs. T3 nightly from 2026-10-03 has the orchestration tools (`delegate_task`, `t3_thread_*`, `watch_pull_request`, `schedule_task`); T3 stable 0.0.45 has only the preview, device, and PR link tools, and jutsu says which fallback it took. `gh` is for pull requests, `bun` for the bundled `watch-pr` and `orch` scripts.

## Cursor to Claude Code and T3

`plugin/skills/poteto-mode/references/runtime.md` is the one map from each Cursor mechanism to its Claude Code and T3 equivalent. Playbooks link to its sections.

| pstack in Cursor | jutsu in Claude Code + T3 |
|---|---|
| Custom Mode keeps `/poteto-mode` on | `/jutsu` plus the mode hook |
| `Task` subagents with model slugs | `Agent` with a model alias and `effort`, from one role table (`/jutsu:setup-pstack` overrides it) |
| Cloud agents on their own VM | A git worktree from your HEAD per writer; long-lived owners are T3 threads (`t3_thread_launch`) |
| `/loop` polling a PR | `watch_pull_request`, plus a `schedule_task` heartbeat for merges, which do not wake a watch |
| `/loop 1h` | `schedule_task` |
| Browser and simulator control skills | `preview_*` and `device_*` |
| Cursor transcripts | `t3_thread_read`, `t3_thread_search`, Claude transcripts |

Plain Claude Code (no T3) gets a fallback for every T3 step.

## Layout

```text
vendor/pstack/      upstream pstack, byte for byte (version in port/upstream.json)
port/spec.json      path moves and frontmatter rules
port/subs/*.json    small rewrites; each rule must match, or the build fails
port/overrides/     files rewritten for Claude + T3, pinned to the upstream file they came from
port/added/         runtime map, mode hook, /jutsu alias, manifest
plugin/             the built plugin (committed, so install needs no build)
tools/              build, check, install, sync
tests/              hook, installer, build, checker, and the bundled bun scripts
```

```sh
python3 tools/build.py            # rebuild plugin/ (it runs the checks too)
python3 tools/build.py --check    # fail if plugin/ is stale
python3 -m unittest discover -s tests
```

Updating from upstream: [UPDATING.md](UPDATING.md). Porting rules and lessons: [PORTING.md](PORTING.md).
