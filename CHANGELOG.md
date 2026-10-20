# Changelog

Notable changes to jutsu. Versions follow the plugin version in `plugin/.claude-plugin/plugin.json`.

## 0.3.0 (2026-10-20)

- Tracks pstack 0.15.29. New skills `/jutsu:sharpen`, `/jutsu:create-formal-verification-skill`, and `/jutsu:maintain-formal-verification-skill`, now 31 skills. `/jutsu:setup-pstack` also offers a formal verification skill. `/jutsu:ketchup` lists every call waiting on you, and the autopilots catch you up with it. A formal verification skill goes to `.claude/skills/<name>/` and never takes the name `verify`.
- `/jutsu:setup-pstack` writes `jutsu-models.md` to the `rules/` folder of the Claude config dir (`$CLAUDE_CONFIG_DIR`, else `~/.claude`). Claude Code loads it into each new session, so role lines are in context. A repo `.claude/jutsu-models.md` still wins, and the 0.2 file still counts until setup runs again. `./uninstall.sh` removes both.
- A step that needs a Cursor-only feature with no T3 or Claude Code counterpart writes `Skipped in Claude Code: <step>. <reason>.` and goes on. Schedules, webhooks, and PR watching are not skips.
- Both ideas come from upstream's own Claude Code adapter ([#637](https://github.com/cursor/plugins/pull/637), [#705](https://github.com/cursor/plugins/pull/705)). `tools/adapter_diff.py` checks each of its rows against jutsu, the sync lists a changed row, and [docs/COMPARISON.md](docs/COMPARISON.md) lists the deliberate differences. The check found that `SendMessage` resumes a finished subagent, now in the runtime.
- `watch-pr` no longer says READY when a required review is missing, or when GitHub reports BLOCKED with clean CI (another branch rule, such as signed commits). BLOCKED while required checks still run stays a wait. Taken from [pstack-claude](https://github.com/michael-denyer/pstack-claude).
- The build and sync skip dotfiles such as `.DS_Store`, which were read as overrides and upstream files.
- [#449](https://github.com/cursor/plugins/issues/449), [#470](https://github.com/cursor/plugins/issues/470), and [PR #510](https://github.com/cursor/plugins/pull/510) are still open upstream on 2026-10-20, and 0.15.29 does not touch those files. jutsu keeps its fixes.

## 0.2.0 (2026-10-14)

- Tracks pstack 0.15.23. New skill `/jutsu:in-your-own-words`, and per-job subagent effort from upstream. Now 23 playbooks, 24 principles, and 28 skills as `/jutsu:<skill>` commands.
- Fixes `watch-pr` on a repo with no CI, which never reached a verdict (upstream [PR #510](https://github.com/cursor/plugins/pull/510)). A PR with no checks counts as no CI only after the same head stays check-less for 60 s, so a fresh push is not called READY early.
- [#471](https://github.com/cursor/plugins/issues/471) is fixed upstream ([PR #484](https://github.com/cursor/plugins/pull/484)). jutsu now uses upstream's code and keeps two extra cursor guards. [#449](https://github.com/cursor/plugins/issues/449) and [#470](https://github.com/cursor/plugins/issues/470) stay fixed here, and the worktree audit now also covers the cases from [PR #492](https://github.com/cursor/plugins/pull/492).
- The mode also turns on from a line that starts with `$jutsu` or `/jutsu` and from a `skill://` link to jutsu, since T3 expands only the last `$skill` mention. A `SubagentStart` hook gives each `jutsu:poteto-agent` child the router path.
- Runtime rules: never use `t3_worktree_handoff`; quote separators in zsh; launch short `delegate_task` waves async and wait with `t3_thread_wait`; pass `gh -R <owner>/<repo>` for PRs from forks; host facts carry the date they were checked.
- Slash-only skills describe what they do instead of when to use them (upstream #367).
- Updates: the sync now 3-way merges each override upstream touched, and the build fails on conflict markers. Each override has a reason in `port/overrides.json`. The build fails on an override that matches upstream. Checker rules test themselves. The T3 tool list is generated from pinned T3 source, and a weekly workflow opens a PR when T3 changes. CI runs on the bot's update PRs.
- Ideas and fixes from other ports, credited in [NOTICE.md](NOTICE.md) and [docs/COMPARISON.md](docs/COMPARISON.md).

### Fit audit (T3 nightly 20261014.3105, Claude Code 2.1.299)

Every unit was checked against what Claude Code and T3 do natively. Upstream text stays only where it works here; the rest is adapted or dropped, and each drop is recorded in `port/overrides.json`.

- Isolation: a writing child in T3 is `delegate_task` with `isolation: "worktree"`, which T3 creates from your HEAD, sets up, shows in its diff views, and cleans up. Separate threads only when the user asks, or for a PR owner, which must watch its own PR.
- The store moves to the main checkout. `.jutsu/` and `.audit/` inside a T3 worktree were git-ignored, and T3's cleanup deletes a worktree whose only local files are ignored. A test runs the runtime's snippet in a real linked worktree.
- Runtime facts corrected: effort changes apply live; `auto` is Claude's auto permission mode, not bypass; the checks-passed wake names the short SHA; a read-only sandbox, not plan mode, limits T3's pre-approved tools; a watch stops after 8 failed reads. New: review guides, webhook schedules, `run_scheduled_task_now`, the coordinator's pending-request, queue, settle, and workflow-stop tools, T3's worktree cleanup, `html_render` layout rules, Mermaid, and a Plan mode section. Text that repeated T3's injected prompt, the speed bullet, and unused Vocabulary rows are gone.
- The mode hook no longer turns on from a mention inside a sentence ("what does $jutsu do?"), and a long prompt is read in linear time.
- `tdd`, `benchmark-checklist`, and `typescript-best-practices` are model-invocable again, with upstream's "Use when" descriptions.
- The weekly T3 workflow also snapshots T3's injected instructions and the `delegate_task` schema, so a new parameter or prompt rule opens a pull request, not only a renamed tool. Pinned to T3 3417bc385.
- `tools/check.py` takes T3 tool names only from `tools/t3-tools.txt`, catches typos of them, and absorbs the two checks from `tests/test_skill_text.py`. The empty `port/substitutions.json` is gone.

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
