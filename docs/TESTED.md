# Live tests

Run by hand in T3 Code nightly 0.0.46 (build 20261009.2861) with Claude Code 2.1.295 on macOS, 2026-10-10 and 2026-10-11. Each result was read from the Claude transcript, git, GitHub, or a screenshot, not from the agent's own summary.

| What | Result |
|---|---|
| `./install.sh` from a fresh GitHub clone into an empty Claude setup | Tests pass and the link is created |
| `./uninstall.sh`, then `./install.sh`, on a real setup | `claude plugin list` showed `jutsu@skills-dir`, then nothing, then `jutsu@skills-dir` again |
| `$jutsu` in T3's skill picker, `/jutsu:…` in the `/` menu | Both listed and both start the skill |
| Mode across turns and `/jutsu off` | Reminder on every turn while on, none after `/jutsu off` |
| A forked session | Checked by replaying a real T3 transcript through the mode hook: the fork keeps the mode (not forked live) |
| Bug fix playbook (replayed through T3's own Agent SDK launch path, twice) | Reproduced first, failing test committed before the fix, tests pass, todo list holds the playbook's steps |
| Feature with an independent review subagent | `jutsu:poteto-agent` review on a second model; 5 of 5 tests pass |
| `/jutsu:setup-pstack` | Called `orchestrator_capabilities`, wrote the role table |
| `/jutsu:arena` | Three runners (opus, fable, sonnet) in their own worktrees, then a judge; 8 of 8 tests pass on the pick |
| Parallel work as separate T3 threads | `t3_thread_launch` ×3 from a commit SHA, each in its own worktree; reports back by `t3_thread_send`; a `schedule_task` heartbeat; a `delegate_task` review that found the one merge conflict |
| PR babysitting on a real PR | `watch_pull_request` woke the thread on a new comment, on a failing check, and on close; it called `unwatch_pull_request` at the end |
| Browser and simulator proof | `preview_open`, `preview_evaluate`, `preview_snapshot`; `device_open`, `device_screenshot` on an iPhone simulator |
| Upstream update | The weekly workflow found pstack 0.15.17, opened a pull request listing the 13 items to port; ported and merged with CI green |

**Renamed from p3 to jutsu on 2026-10-11.** The rows above ran under the old name; the rename changed names only. Rerun after the rename: `$jutsu` shows in T3's picker (the README screenshot); `claude plugin list` shows `jutsu@skills-dir`, then nothing after `./uninstall.sh`, then `jutsu@skills-dir` again after `./install.sh`; Claude lists `/jutsu` and 27 `/jutsu:<skill>` commands, the agents `jutsu:poteto-agent` and `jutsu:comment-sicko`, and no `p3` command; `/jutsu` picked the Bug fix playbook in a headless run and `/jutsu off` cleared the mode. A Claude session that is already running picks up an installed or removed plugin on its next message, checked with a throwaway plugin in the same stream-json mode T3 uses.

Not run live: a real PR merge. T3 sends no wake on a merge, so the playbooks keep a `schedule_task` heartbeat for it.
