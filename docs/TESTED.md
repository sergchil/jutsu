# Live tests

Each result was read from the Claude transcript, git, GitHub, or a screenshot, not from the agent's own summary.

## 0.4.0 (2026-10-20)

Automated, plus a marketplace install into a throwaway Claude config dir. Not run live in a Claude Code or T3 session.

| Suite | Result |
|---|---|
| `python3 -m unittest discover -s tests` | 165 pass, including the worktree audit on 26 real worktrees (build and cache folders, reflog-only commits, locked worktrees), `checkpoint.sh` on a real linked worktree that is then removed, the adherence count on fixture transcripts, and the installer skipping a config dir with the marketplace copy |
| `bun test --timeout 30000` in `poteto-mode/scripts`, on a clean copy | 95 pass |
| `python3 tools/build.py --check`, `python3 tools/check.py`, `python3 tools/adapter_diff.py` | clean |
| `claude plugin validate .` and `claude plugin validate ./plugin` (Claude Code 2.1.304) | Validation passed |
| Marketplace install with `CLAUDE_CONFIG_DIR` set to a scratch dir: `claude plugin marketplace add <copy of this repo>`, `claude plugin install jutsu@jutsu` | Installed and enabled as `jutsu@jutsu`. A `git-subdir` source, which copies `plugin/` into the plugin cache as a GitHub install does, listed 32 skills and 4 hooks in `claude plugin details`, with no root `/jutsu` skill. The cached `hooks/jutsu-mode`, run with that copy's `CLAUDE_PLUGIN_ROOT` and a data dir, turned the mode on from `$jutsu` and named the cached router path |
| GraphQL read for pending merges on a real PR (`sergchil/jutsu#7`) | Returned `autoMergeRequest: null` and `isInMergeQueue: false`. `dequeuePullRequest` takes `id`, checked by schema introspection. No mutation was run |

**Router adherence** (`python3 tools/adherence.py`, read-only, on this machine's `~/.claude/projects` on 2026-10-20; counts only):

| Population | Count | Opened the router | A playbook | A principle |
|---|---|---|---|---|
| Main sessions with jutsu mode on (323 prompts sent while on) | 10 | 7 (70%) | 1 (10%) | 0 |
| `jutsu:poteto-agent` subagents of those sessions | 24 (12 reached by the `SubagentStart` hook) | 23 (96%) | 2 (8%) | 1 (4%) |
| Other subagents of those sessions | 21 (0 reached) | 0 | 0 | 0 |

pstack-claude's issue #264 reported 19% router, 3% playbook, and 3% principle over 1,725 sessions, and 76%, 5%, 14% for its poteto-agent. jutsu's sample is one user and 10 sessions, and it counts only `Read` calls, so treat it as a first reading. The low playbook rate is the gap to look at next.

Not checked: `/plugin marketplace add sergchil/jutsu` from GitHub (the branch is not pushed), the marketplace install inside a T3 thread or T3's `$` picker, `checkpoint.sh` and the merge-queue steps in a live run, and `/jutsu:thermo-nuclear-review` on a real diff.

## 0.3.0 (2026-10-20)

Automated only. Not run live in Claude Code or the T3 app.

| Suite | Result |
|---|---|
| `python3 -m unittest discover -s tests` | 143 pass, including the adapter cross-check, dotfile skipping in build and sync, and the models file under `rules/` |
| `bun test --timeout 30000` in `poteto-mode/scripts`, on a clean copy | 93 pass |
| `python3 tools/build.py --check`, `python3 tools/check.py`, `python3 tools/adapter_diff.py` | clean |

Not checked: that a session started with `CLAUDE_CONFIG_DIR` set loads `rules/` from that dir (read in Claude Code 2.1.304's bundle, not run), whether subagents get user rules in context, and T3 rendering an embedded screenshot in a `/jutsu:ketchup` reply.

## 0.2.0 (2026-10-14)

**Headless, not in the T3 app.** Claude Code 2.1.296 on macOS, run headless with stream-json output, the mode T3 uses to drive Claude, with jutsu linked at `~/.claude/skills/jutsu`. 0.2.0 has not been rerun in the T3 desktop app yet.

| What | Result |
|---|---|
| `$jutsu` as plain text mid-sentence: "Fix the bug in calc.py, $jutsu. Do not change code yet: say which playbook you matched, then spawn exactly one jutsu:poteto-agent…" | The `UserPromptSubmit` hook turned the mode on: it wrote the session flag (`sessions/<id>` holds `on`) and added "jutsu poteto mode is now on in this session…" to the turn, as the transcript shows |
| Router and playbook | The model read `poteto-mode/SKILL.md` and `references/runtime.md`, matched the Bug fix playbook, and changed no code |
| `SubagentStart` hook | It spawned one `Agent` with `subagent_type: jutsu:poteto-agent`, `model: haiku`, `effort: low`. Asked to quote the first context it got before its brief, the child replied "jutsu poteto mode is on in the parent session.", the hook's text |
| Commands Claude lists | `/jutsu` and 28 `/jutsu:<skill>` commands, including the new `/jutsu:in-your-own-words`; agents `jutsu:poteto-agent` and `jutsu:comment-sicko` (stream-json `init` event) |

Automated, on the 0.2.0 tree:

| Suite | Result |
|---|---|
| `python3 -m unittest discover -s tests` | 95 pass: build, checker (rules test themselves), mode and subagent hooks, installer, upstream 3-way sync on real git repos, T3 tool list from T3 source, worktree audit on 15 real worktrees |
| `bun test` in `poteto-mode/scripts` (watch-pr, orch, check-plan), on a clean copy | 85 pass, including the no-CI `watch-pr` cases and the 60 s guard against an early READY |

Not run for 0.2.0: the T3 desktop app, a real PR in a repo with no CI, and the `t3.yml` weekly workflow.

## 0.1.0 (2026-10-10 and 2026-10-11)

Run by hand in T3 Code nightly 0.0.46 (build 20261009.2861) with Claude Code 2.1.295 on macOS.

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
