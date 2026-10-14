# Changelog

Notable changes to jutsu. Versions follow the plugin version in `plugin/.claude-plugin/plugin.json`.

## 0.2.0 (2026-10-14)

- Tracks pstack 0.15.23. New skill `/jutsu:in-your-own-words`, and per-job subagent effort from upstream. Now 23 playbooks, 24 principles, and 28 skills as `/jutsu:<skill>` commands.
- Fixes `watch-pr` on a repo with no CI, which never reached a verdict (upstream [PR #510](https://github.com/cursor/plugins/pull/510)). A PR with no checks counts as no CI only after the same head stays check-less for 60 s, so a fresh push is not called READY early.
- [#471](https://github.com/cursor/plugins/issues/471) is fixed upstream ([PR #484](https://github.com/cursor/plugins/pull/484)). jutsu now uses upstream's code and keeps two extra cursor guards. [#449](https://github.com/cursor/plugins/issues/449) and [#470](https://github.com/cursor/plugins/issues/470) stay fixed here, and the worktree audit now also covers the cases from [PR #492](https://github.com/cursor/plugins/pull/492).
- The mode also turns on from `$jutsu` or `/jutsu` anywhere in the prompt text and from a `skill://` link to jutsu, since T3 expands only the last `$skill` mention. A `SubagentStart` hook gives each `jutsu:poteto-agent` child the router path.
- Runtime rules: never use `t3_worktree_handoff`; quote separators in zsh; launch short `delegate_task` waves async and wait with `t3_thread_wait`; pass `gh -R <owner>/<repo>` for PRs from forks; host facts carry the date they were checked.
- Slash-only skills describe what they do instead of when to use them (upstream #367).
- Updates: the sync now 3-way merges each override upstream touched, and the build fails on conflict markers. Each override has a reason in `port/overrides.json`. The build fails on an override that matches upstream. Checker rules test themselves. The T3 tool list is generated from pinned T3 source, and a weekly workflow opens a PR when T3 changes. CI runs on the bot's update PRs.
- Ideas and fixes from other ports, credited in [NOTICE.md](NOTICE.md) and [docs/COMPARISON.md](docs/COMPARISON.md).

## 0.1.0 (2026-10-11)

The first public release.

- Lauren Tan's pstack 0.15.17, ported to Claude Code inside T3 Code: 23 playbooks, 24 principles, and 27 skills as `/jutsu:<skill>` commands. `make-bot-ui` is left out, because it builds Cursor automations.
- `/jutsu` turns on poteto mode, and `$jutsu` starts it from T3's skill picker. A hook keeps the mode on across turns, compaction, resume, and forks, until `/jutsu off`.
- jutsu uses T3's own tools: threads in their own worktrees started from a commit SHA, delegated tasks with retry keys, PR watching with a heartbeat for merges, schedules, and the browser and simulator tools. Without T3, each step falls back to plain Claude Code.
- `/jutsu:setup-pstack` picks the model and effort for each role.
- `./install.sh` links jutsu into every Claude Code config folder that T3 uses. `./uninstall.sh` removes everything it added.
- Fixes three bugs that are still open upstream: [#449](https://github.com/cursor/plugins/issues/449) (worktree cleanup could delete untracked and ignored files), [#470](https://github.com/cursor/plugins/issues/470) (closed or unpushed work was called safe to delete), and [#471](https://github.com/cursor/plugins/issues/471) (only the first 100 review threads were read).
- A weekly workflow opens a pull request for each new pstack release and lists what to port.
- Website: https://sergchil.github.io/jutsu/
