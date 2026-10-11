# Changelog

Notable changes to jutsu. Versions follow the plugin version in `plugin/.claude-plugin/plugin.json`.

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
