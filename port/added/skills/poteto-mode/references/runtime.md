# jutsu runtime: Claude Code inside T3 Code

pstack was written for Cursor. This file says how each Cursor mechanism runs here. Every playbook and skill that spawns, waits, schedules, watches, or proves work on a UI points at a section of this file. Read the section before the step that needs it. T3 already puts its own orchestration rules in your system prompt. This file adds only what jutsu needs on top of them.

## Host

- **T3.** Tools named `mcp__t3-code__*` are present, and the system prompt has a "T3 Code orchestration" section. This file calls them by their short names (`delegate_task`, `watch_pull_request`). Probed 2026-10-14 on T3 nightly 0.0.46 (build 20261014.3105, commit 3417bc385) with Claude Code 2.1.299, unless a fact names another probe.
- **Plain Claude Code.** No `mcp__t3-code__*` tools. Use the fallback named in each section.
- **Partial T3.** T3 stable (v0.0.45) ships only `preview_*`, `device_*`, and the pull request link tools. The orchestration tools (`delegate_task`, `t3_thread_*`, `watch_pull_request`, `schedule_task`) need a T3 nightly from 2026-10-03 or later. `html_render` and `request_secret` need 2026-10-05, the review guide tools 2026-10-11, and `delegate_task` `isolation` 2026-10-14. All 83 tools are always listed, so a tool that is listed can still fail at call time. When a T3 call fails with an unknown-tool or capability error, take the fallback for that step and say so in the reply.
- A fact here that names a probe date held on that build. Re-probe it after a T3 or Claude Code update before you change a rule that rests on it.

## Vocabulary

Playbooks keep a few of upstream's words. Read them this way.

| Playbook says | Here |
|---|---|
| todolist | The task tools when present, else a file. See [Todo list](#todo-list). |
| `/loop`, an hourly tick, a wake | See [Waking](#waking). |
| `scripts/watch-pr` polling | `watch_pull_request` to wake, `watch-pr --status-only` to judge. See [Pull requests](#pull-requests). |
| Bugbot, agentic security review | Any review bot. Triage per `bugbot-triage.md`. |

## Cursor-only steps

When a step needs a Cursor feature that has no counterpart in T3 or Claude Code, write exactly `Skipped in Claude Code: <step>. <reason>.` in your reply and go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, such as a URL or a key, leave a placeholder and name it in the line. The line comes from upstream's own Claude Code adapter (`docs/harness/claude-code.md`, cursor/plugins#637).

Skip only when nothing here does the job. These are not skips: a schedule, tick, or webhook (`schedule_task`, [Waking](#waking)), PR watching (`watch_pull_request`, [Pull requests](#pull-requests)), a cloud worker (a worktree, [Isolation](#isolation)), Bugbot comments (review threads, triaged per `bugbot-triage.md`), and opening a PR (`gh`). What is left: Cursor Automations' own routines and `update_state` calls, the dashboard or machine of a Cursor-hosted worker, and starting or configuring Bugbot itself.

## Subagents

**Default: the native `Agent` tool** for a child that only reads, or that writes where no other writer can overlap. Every Claude model and effort level is reachable natively, so such a Claude child is an `Agent` call. T3 shows each one as a child thread.

- `subagent_type`: `jutsu:poteto-agent` for every child inside a playbook step. Routed skills name their own type, usually `general-purpose` or `Explore`. Keep what the skill names.
- `model`: an alias only: `opus`, `sonnet`, `fable`, or `haiku`. The tool rejects full model ids.
- `effort`: `low`, `medium`, `high`, `xhigh`, or `max`. Pick it for the job and pass it on every call that has a role. Without it the child inherits the session effort. There is no per-child speed setting.
- `run_in_background`: true unless you need the result before your next step.
- `name`: set it for any child you may message or stop. `SendMessage` to its name or id resumes a child, live or finished, with its full history, so continue one that way instead of spawning a new one with pasted results. `Explore` children are one-shot and cannot be resumed ([sub-agents docs](https://code.claude.com/docs/en/sub-agents#resume-subagents), read 2026-10-20).
- **Brief.** A child gets only its brief. Open every `jutsu:poteto-agent` brief with the absolute path of the router (`skills/poteto-mode/SKILL.md`, which you know because you read it) and the line `Read it in full before any work.` Then the goal, file pointers instead of pasted context, constraints, and the report format. Never put `$(...)` or backticks that a shell would expand into a brief that a child will paste into a command. Tell every child to run each command in the foreground and never end its turn with a background shell or agent still running, since a Claude child that does can report early. A deadline orders the work; it never waives a step.
- **zsh.** T3 runs commands in the user's shell, often zsh. zsh expands a word that starts with `=`, so `echo =====` fails and the rest of a chained command never runs. Quote a separator (`echo '====='`). Tell every child the same. Source: pmwoz/t3-pstack PR #1. Probed 2026-10-14 on zsh 5.9.
- **Router path from the hook.** When poteto mode is on, the mode hook gives each new `jutsu:poteto-agent` child the router path (`SubagentStart`). Other types get nothing, so the brief still opens with the router path. Probed 2026-10-14 on Claude Code 2.1.296 with `claude -p`; inside T3 Not checked.
- **Stop what you abandon.** `completed` in the agent list means the completion was notified, not that the process exited, so a child with live background work keeps writing. Stop it with `TaskStop` (load it with `ToolSearch` if it is deferred) and confirm with `git status` before you give its work to a fresh child.
- **Drain before landing.** Before a commit, merge, push, or deploy from a worktree, every child that writes there has stopped.
- **No subagent** has `AskUserQuestion` or `ScheduleWakeup`, so questions and `/loop` stay in this thread. Background children cannot call `delegate_task` after your turn ends. A subagent does not wait for its own background children, so their reports arrive here. Drain them here.

**When to use `delegate_task` instead (T3 only).**

- The child writes and needs its own checkout. See [Isolation](#isolation).
- The role in [Roles](#roles) names a T3 target (`t3:<providerInstanceId>/<model>`), such as a second Claude account or another provider.
- The child must outlive this session's process, for example a reviewer you will read after a T3 restart.

Rules for `delegate_task` beyond T3's own:

- `target`: `{providerInstanceId, model, options}`. Always pass `options` with `effort`. A child on a different model without `options` runs at that provider's default effort, not yours.
- `mode: "async"` for every call, a single child included. Sent together, `mode: "wait"` calls run one after another.
- **A short wave** (read-only children the next step needs at once, such as reviewers or a panel) stays in the turn. Launch each child async, set one deadline at most 10 minutes away, then call `t3_thread_wait` on each `childThreadId` with the time left as `timeoutMs`. When a wait times out or fails, end the turn and let the rest arrive on wakes. Source: osmelmora/p3-executor PR #2.
- **Long work** (writers, anything past 10 minutes): end your turn or keep working, and read the result with `task_status` after the wake. Reading it earlier cancels the wake. `t3_thread_wait` does not.
- Set `role` to `general`. T3 prepends a line for any other role.
- Leave `runtimeMode` and `interactionMode` unset. A broader one than yours fails.
- `task_cancel` stops a child and its children. `t3_thread_interrupt` does not.
- Open the brief for a code or judgment role with the router's absolute path and `Read it in full before any work.` The child is a new session where poteto mode is off.
- Children never call `watch_pull_request`. T3 refuses a delegated child's watch, and a native subagent's watch lands on your thread.

**A coordinator's other tools (T3).** `t3_pending_request_list` and `t3_pending_request_respond` answer a child's `AskUserQuestion` (not a permission request). `t3_queue_list` shows messages queued for a thread. `t3_thread_organize` with `settle` settles a thread; on your own thread it takes effect when the turn ends. `t3_workflow_stop` stops a Claude dynamic workflow by its `subagentId` from `t3_thread_read` with `view: "activity"`.

## Roles

Role defaults. A role line in `jutsu-models.md` overrides one. `/jutsu:setup-pstack` writes it. Find the lines in this order:

1. `.claude/jutsu-models.md` in the repo. When it exists, read it. Its lines win.
2. `rules/jutsu-models.md` in the Claude config dir (`${CLAUDE_CONFIG_DIR:-~/.claude}/rules/`). Claude Code loads every `.md` file in that folder into each new session ([memory docs](https://code.claude.com/docs/en/memory#user-level-rules), read 2026-10-20), so its role lines are usually already in your context. When they are not, or setup ran after this session started, read the file. Claude Code 2.1.304's bundle builds this folder from the same config dir as the user `CLAUDE.md`, so a set `CLAUDE_CONFIG_DIR` moves it (read in the bundle, not run).
3. `jutsu-models.md` directly in the config dir, where jutsu 0.2 wrote it.

Ignore `pstack-models.md`. Upstream pstack's own Claude Code adapter writes it in another format.

- feature, refactoring: `opus @xhigh`
- bug-fix: `fable @xhigh`
- perf-issue: `fable @xhigh`
- hillclimb: `fable @xhigh`
- judgment and prose: `opus @xhigh`
- hardest tasks: `opus @xhigh`
- how explorer: `sonnet @xhigh`
- how explainer: `opus @xhigh`
- why investigators: `sonnet @xhigh`
- why synthesizer: `opus @xhigh`
- reflect tooling: `sonnet @xhigh`
- reflect judgment, divergent, synthesizer: `opus @xhigh`
- swarm workers: `opus @xhigh`
- arena runners: `opus @xhigh`, `fable @xhigh`, `sonnet @xhigh`
- arena cross-judge pool: `opus @xhigh`, `fable @xhigh`, `sonnet @xhigh`
- architect runners: `opus @xhigh`, `fable @xhigh`, `sonnet @xhigh`
- interrogate reviewers: `opus @xhigh`, `fable @xhigh`, `sonnet @xhigh`

Upstream runs every role at its model's highest reasoning setting, and so do these defaults. `/jutsu:setup-pstack` lowers them for a smaller budget. Per spawn, the router's "Match the model to the job" moves a role's effort up or down from its value here, and a review never goes below `high`.

A value is `<alias> @<effort>`, `inherit` (omit `model` and `effort`), or `t3:<providerInstanceId>/<modelId> @<effort>` for a `delegate_task` target. A value without `@` uses the session effort. An effort a model does not offer falls back to its default, so report the effort the child ran at, not the one you asked for.

**Model diversity.** Upstream's panels pair two vendors. Claude models share one vendor, so a disagreement between opus, fable, and sonnet is real but weaker evidence than upstream's. Say so when a verdict rests on agreement. A T3 role line can add another provider when the user has one.

## Isolation

Two writers never share a checkout (principle-separate-before-serializing-shared-state). Read-only children share your checkout.

- **In T3, a child that writes while another writer may overlap** is a `delegate_task` call with `isolation: "worktree"`. T3 makes the worktree from your HEAD commit, runs project setup, and binds the child, so T3's diff and checkpoint views show its work. Commit first. The brief says to commit on its branch and report the branch and head SHA. Check that the diff landed there before you integrate. Read in T3's source at 3417bc385 (#19102); not run live.
- `isolation: "worktree"` always starts from your HEAD. For a lane that must check out another commit, such as a PR head, and for an `Agent` writer outside T3, create the worktree yourself: `git worktree add <path> -b <branch> <commit>`. The brief says: work only under the absolute path, prefix every command with `cd <path> &&`, report the branch and head SHA. Remove it with a plain `git worktree remove <path>` once its work has landed. In T3's approval-required mode, each write outside the project asks for approval, so run fan-out playbooks in `auto` or `full-access`.
- **Cleanup.** T3 removes its own worktrees under `~/.t3/worktrees` by its cleanup settings (age, merged, thread deleted, unchanged). It never sweeps a worktree you made outside that folder, so remove yours.
- Never call `t3_worktree_handoff`, even though T3 lists it. It detaches the provider session, and its queued continuation waited up to 9 minutes or never started. Source: pmwoz/t3-pstack `plugins/pstack/skills/poteto-mode/references/t3-adapter.md:68` and its PR #2.
- Do not use `Agent` `isolation: "worktree"` for stacked or branch-based work. It branches from the remote default branch unless the user set `worktree.baseRef: "head"`.
- **Separate threads** only when the user asks for them, or for a PR owner. A PR owner (Autopilot full, Orchestrate) must watch and merge its own PR, and a delegated child cannot watch, so it is a launched thread: `t3_thread_launch` with a `title` and `workspaceStrategy: {"type":"worktree","baseRef":"<commit SHA>","branch":"<branch>","startFromOrigin":false}`.
  - Commit first, then set `baseRef` to `git rev-parse HEAD`. Never pass a branch name T3 created (`t3/<hash>`): T3 renames it in the background, and the launch fails with "Workspace preparation failed" (probed 2026-10-11 on build 20261009.2861).
  - Open the brief in `message` with the router's absolute path and `Read it in full before any work.` Pass `modelSelection: {instanceId, model, options:[{"id":"effort","value":"<level>"}]}`. Leave out `runtimeMode` and `interactionMode`.
  - Within a minute, read each launched thread and confirm it is running, not failed. On a failed preparation, fix the cause and launch again.
  - A launched thread never wakes its launcher. Its brief says to report each milestone with `t3_thread_send` and `mode: "queue"` to the coordinator's thread id (the default `auto` steers an active turn, which interrupts Claude's running tools), and to stop when that call is refused. The coordinator keeps a heartbeat ([Waking](#waking)).
  - Outside T3 a PR owner is a background `Agent` in its own worktree.

## Waking

| Need | T3 | Plain Claude Code |
|---|---|---|
| Wake on a PR event | `watch_pull_request`, then end the turn | `/loop` dynamic mode with `watch-pr` |
| Recurring tick (hourly audit, overnight cadence) | `schedule_task` with `{"type":"interval","everyMs":3600000}`, bound to this thread | `/loop 1h` |
| Wall-clock tick | `schedule_task` with `{"type":"fixed_time","timeOfDay":"09:00"}` | `/loop` or cron |
| Wake on an outside event (CI, a deploy hook) | `schedule_task` with `{"type":"webhook"}`. The `webhookUrl` needs T3 Connect, and a signing secret comes from `request_secret`. | `/loop` polling |
| Drive one task to a predicate | a `schedule_task` heartbeat bound to this thread, deleted when the predicate holds. The user may also start Claude's `/goal <condition>`; T3 shows its status. Only the user can start it. | `/loop` until the predicate, or the user's `/goal` |
| Wait for a child | its completion wake, `task_status`, or `t3_thread_wait` (at most 60 min) | the Agent completion notice |

- The minimum interval is 60 seconds. A run bound to a busy thread queues behind the active turn. Delete the task (`delete_scheduled_task`) when its predicate holds. `run_scheduled_task_now` starts a run at once; T3 requires a full-access or default-mode caller.
- An unbound scheduled run starts a fresh thread from `main` at origin. Keep runs bound to the coordinator unless the user asked for fresh threads.
- A `fixed_time` slot missed while T3 was closed is skipped, not caught up. Check for missed work on the next run.
- These survive a T3 restart. `/loop` and background Bash do not.

## Pull requests

- **Fork-safe `gh`.** For a PR that may come from a fork, resolve `<owner>/<repo>` from the PR URL and pass `-R <owner>/<repo>` on every `gh pr` and `gh run` call. Name the PR by number or URL, never by branch: `gh pr view <branch>` on a `gh pr checkout` branch of a cross-repo PR returns the wrong PR. Source: mdsmithaustin/pstack issues #169 and #210.
- Open with `gh`, then link it as T3's prompt says. Write the title and body in the user's style: `t3_environment_read` returns it as `sourceControlWritingStyle`.
- **Wake** with `watch_pull_request` from a top-level thread, never from a child ([Subagents](#subagents)). It polls every 2 minutes. It wakes on a newly failed check, all required checks passing, a new comment or review from someone else posted after the watch began, a conflict, or 8 failed reads in a row (rate limits only delay it). Handle existing comments first, since they will not wake you. Wakes queue behind an active turn. Only the checks-passed wake names the head SHA, and only its short form, so read the full SHA yourself before you act.
- **A merge or close does not wake you.** The watch ends silently. When you wait on a merge, also keep a `schedule_task` heartbeat (every 10 to 30 minutes) that checks the PR state, and delete it after.
- Ten comment-only wakes in a row end the watch. Settling or archiving the thread, or the user pressing Stop, ends it too. Unsettle a settled thread (`t3_thread_organize`) before a new watch. Call `unwatch_pull_request` before handing the thread back to the user.
- **Review guides.** `write_pull_request_guides` starts a maintainer's tour of a PR (minutes per PR) and `read_pull_request_guide` reads it. A guide explains; it does not judge. Use it as a cheap first read before an interrogate panel, never as the verdict. It fails when the user turned guides off.
- **Read state** with the bundled watcher (bun): `scripts/watch-pr/watch-pr --status-only` under this file's skill directory prints one status table (checks, review state, `mergeStateStatus`, head SHA) and exits. **Judge** by running it once without `--status-only` when no check is pending. It returns the verdict at once. A green check list is not a verdict, and the watcher reports `READY` on a branch that is `BEHIND` its base, so read `mergeStateStatus` yourself.

## Questions

- `AskUserQuestion` renders as a T3 question card. Give every option a non-empty description. A blank one can stall the thread.
- Permission prompts do not guard the Always-pause list in poteto-mode's Autonomy section. You do. Ask before each item on it. T3's `full-access` mode approves every tool call. Its `auto` mode is Claude's own auto permission mode, which may still ask or refuse on a risky action; that is not a pause rule either.
- When `AskUserQuestion` is not in your tools, ask in plain text and end the turn.
- An effort change applies to a running session, and a model change keeps background agents (T3 #19341, #14726). Whether T3 refuses a runtime or interaction mode change while background agents or shells run is Not checked, so ask for any mode switch before the first background child starts.
- In a read-only sandbox T3 pre-approves only its read-only tools, which leave out `task_status` and `t3_thread_read`, so each of those calls asks for approval.

## Plan mode

T3's plan mode is Claude's own plan permission mode, so file writes are refused. Run only the read-only steps of the playbook. Put the plan in the `ExitPlanMode` call instead of a file. T3 shows it as a plan card and denies the call, and you stop. The user approves and sends the next message, and you write the plan file and continue then.

## Todo list

Claude Code offers no todo tools on current models (Opus 4.8 and later, Sonnet 5, Fable 5) unless the user sets `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`. When `TaskCreate` and `TaskUpdate` (or `TodoWrite`) are in your tools, use them. Otherwise keep the list in `.audit/<slug>.todo.md` in the main checkout ([Store](#store)), where `<slug>` is a short kebab-case name for the task. One line per item, `- [ ]` or `- [x]`, updated at each step.

## History

- **T3:** `t3_thread_list` (one project per call, `titleContains` for titles; it also returns this thread's id as `currentThreadId`), `t3_thread_read` (any thread, paged, `view: "activity"` for tool calls), `t3_thread_search` (message text only, one hit per thread, at most 50, no titles, and it skips archived threads). Reading a direct child's finished result acknowledges its wake.
- **Claude transcripts:** `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<dir>/<session>.jsonl`, where `<dir>` is the working directory with every character other than a letter or digit replaced by `-`. A `<dir>` longer than 200 characters is cut to 200 and gets a hash suffix, so for a long path list `projects/` and match the prefix. Subagent transcripts are `<dir>/<session>/subagents/agent-<id>.jsonl`. Skip records with `isMeta` and local-command records.
- In T3 each worktree thread has its own `<dir>`, so this workspace's transcripts cover about one thread. For the project's other threads, use `t3_thread_list` and `t3_thread_read`.
- Read only this project's transcripts. Never glob across `projects/*/`: other directories hold the user's private chats in other projects.

## Proof surfaces

- **Browser and web UIs (T3):** the `preview_*` tools, in the order their descriptions give. Record proof with `preview_recording_start` and `preview_recording_stop`, or `preview_snapshot` with `save: true`. Parallel children open their own tab with `reuseExistingTab: false` and pass its `tabId`.
- **Simulators (T3):** `device_list`, `device_open` (it returns an `agent-device` command for taps and typing), `device_screenshot`, `device_close`. Device access is off until the user enables it in T3 settings. Say so if a call is refused.
- **CLIs and TUIs:** drive them in the terminal. For a TUI, use `tmux` with `send-keys` and `capture-pane`.
- **Visual reports (T3):** a plain flow or sequence is a ` ```mermaid ` fence, which T3 renders. A chart, collage, or mockup is an `html_render` page, as T3's prompt says: no background on `html`, `body`, or the outer element, no outer padding, card, or title, fixed pixel heights for charts, no `100vh`, and a `height` of 80 to 2000. T3 on desktop does not render math, so write a formula as code.
- **Plain Claude Code:** a browser MCP server or Playwright when installed. Otherwise say which surface you could not drive.

## Store

Durable files for a program (Orchestrate's tables, decision logs, plans, resume notes) go under `.jutsu/<slug>/`, and todo files under `.audit/`, in the **main checkout** of the repo, never inside a worktree. T3 deletes its worktrees by its cleanup rules and by default keeps one only for uncommitted changes, so git-ignored files there are lost. It never deletes the main checkout. The main checkout is the parent of git's common directory, from any worktree. The first time, run this from the repo or any of its worktrees. It prints the store root and keeps `.jutsu/` and `.audit/` out of git for every worktree:

```sh
main="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
exclude="$(git rev-parse --path-format=absolute --git-path info/exclude)"
mkdir -p "$(dirname "$exclude")"
for p in .jutsu/ .audit/; do grep -qxF "$p" "$exclude" 2>/dev/null || printf '%s\n' "$p" >> "$exclude"; done
printf '%s\n' "$main/.jutsu"
```

Use the printed absolute path in every brief, and never `.git/info/exclude` by hand (in a worktree `.git` is a file).

## Missing companions

- **deslop.** Before a commit, reread the diff and remove slop per the unslop skill and poteto-mode's Comments section: narrating comments, dead code, needless wrappers, defensive checks on trusted internal values, and debug output.
- **skill-authoring.** Follow the Authoring a skill playbook.
