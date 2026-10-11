# p3 runtime: Claude Code inside T3 Code

pstack was written for Cursor. This file says how each Cursor mechanism runs here. Every playbook and skill that spawns, waits, schedules, watches, or proves work on a UI points at a section of this file. Read the section before the step that needs it.

## Host

- **T3.** Tools named `mcp__t3-code__*` are present, and the system prompt has a "T3 Code orchestration" section. This file calls them by their short names (`delegate_task`, `watch_pull_request`).
- **Plain Claude Code.** No `mcp__t3-code__*` tools. Use the fallback named in each section.
- **Partial T3.** T3 stable (v0.0.45) ships only `preview_*`, `device_*`, and the pull request link tools. The orchestration tools (`delegate_task`, `t3_thread_*`, `watch_pull_request`, `schedule_task`) need a T3 nightly from 2026-10-03 or later. `html_render` and `request_secret` need 2026-10-05 or later. All 80 tools are always listed, so a tool that is listed can still fail at call time. When a T3 call fails with an unknown-tool or capability error, take the fallback for that step and say so in the reply.

## Vocabulary

Playbooks keep upstream's words. Read them this way.

| Playbook says | Here |
|---|---|
| `Task`, subagent, "spawn" | The `Agent` tool. See [Subagents](#subagents). |
| `subagent_type: "poteto-agent"` | `subagent_type: "p3:poteto-agent"`. |
| `generalPurpose` | `subagent_type: "general-purpose"`. |
| `readonly: true` | A read-only brief, plus `subagent_type: "Explore"` when the child only reads code. |
| `run_in_background: true` | Same parameter on `Agent`. Background is the default. |
| model slug per role | `model` and `effort` on `Agent`, from [Roles](#roles). |
| cloud agent, own VM | A worktree. See [Isolation](#isolation). In T3 a long-lived owner is a launched thread. |
| `AskQuestion` | `AskUserQuestion`. See [Questions](#questions). |
| todolist | The task tools when present, else a file. See [Todo list](#todo-list). |
| `/loop`, an hourly tick, a wake | See [Waking](#waking). |
| `scripts/watch-pr` polling | `watch_pull_request` to wake, `watch-pr --status-only` to judge. See [Pull requests](#pull-requests). |
| transcripts, `agent-transcripts/` | See [History](#history). |
| `control-ui`, `control-cli`, a simulator skill | See [Proof surfaces](#proof-surfaces). |
| the agent store | `.p3/<slug>/` in the repo. See [Store](#store). |
| Cursor restart | A T3 restart, a Claude session restart, or compaction. |
| `/deslop`, `create-skill` | The `deslop` and `skill-authoring` notes in [Missing companions](#missing-companions). |
| Bugbot, agentic security review | Any review bot. Triage per `bugbot-triage.md`. |

## Subagents

**Default: the native `Agent` tool.** Some tool lists still show it under its old name, `Task`. T3's own system prompt says to prefer native subagents for same-provider work when they support the model. Every Claude model and effort level is reachable natively, so a Claude child is an `Agent` call. T3 shows each one as a child thread.

- `subagent_type`: `p3:poteto-agent` for every child inside a playbook step. Routed skills name their own type, usually `general-purpose` or `Explore`. Keep what the skill names.
- `model`: an alias only: `opus`, `sonnet`, `fable`, or `haiku`. The tool rejects full model ids.
- `effort`: `low`, `medium`, `high`, `xhigh`, or `max`. Pass it on every call that has a role. Without it the child inherits the session effort.
- `run_in_background`: true unless you need the result before your next step.
- `name`: set it for any child you may message or stop. `SendMessage` continues a live child.
- **Brief.** A child gets only its brief. Open every `p3:poteto-agent` brief with the absolute path of the router (`skills/poteto-mode/SKILL.md`, which you know because you read it) and the line `Read it in full before any work.` Then the goal, file pointers instead of pasted context, constraints, and the report format. Never put `$(...)` or backticks that a shell would expand into a brief that a child will paste into a command. Tell every child to run each command in the foreground and never end its turn with a background shell or agent still running, since a Claude child that does can report early. A deadline orders the work; it never waives a step.
- **Stop what you abandon.** In the agent list `completed` means the completion was notified, not that the process exited. A child with live background work reports completed and keeps writing. Stop it with `TaskStop` (it may be deferred, so load it with `ToolSearch` first) and confirm with `git status` before you give its work to a fresh child.
- **Drain before landing.** Before a commit, merge, push, or deploy from a worktree, every child that writes there has stopped.
- **No subagent** has `AskUserQuestion` or `ScheduleWakeup`, so questions and `/loop` stay in this thread. Background children also cannot call `delegate_task` after your turn ends. In T3 (the Agent SDK), a subagent does not wait for its own background children, so their reports arrive in this thread. Drain them here.

**When to use `delegate_task` instead (T3 only).**

- The role in [Roles](#roles) names a T3 target (`t3:<providerInstanceId>/<model>`), such as a second Claude account or another provider.
- The child must outlive this session's process, for example a reviewer you will read after a T3 restart.

Rules for `delegate_task`:

- `target`: `{providerInstanceId, model, options}`. Always pass `options` with `effort`. A child on a different model without `options` runs at that provider's default effort, not yours.
- `mode: "async"`, then end your turn or keep working. T3 wakes you with "Delegated task X reached a terminal state". Read the result with `task_status`. Reading it earlier cancels the wake. `t3_thread_wait` waits without cancelling it.
- `clientRequestId`: a distinct, stable id per call, reused only on a retry of the same call. Each review round is a new call with the original brief, prior findings, the responses, and open objections. Never send a new round to `childThreadId` with `t3_thread_send`.
- Do not set `role` to anything but `general`. T3 prepends a line for other roles.
- A child's runtime and interaction modes must be equal to or narrower than yours. A broader request fails. It is never clamped.
- `task_cancel` stops a child and its children. `t3_thread_interrupt` does not.
- Children share your checkout. See [Isolation](#isolation).
- Open a `delegate_task` brief for a code or judgment role with the router's absolute path and `Read it in full before any work.`, as for `p3:poteto-agent`. The child is a new session where poteto mode is off.
- Children never call `watch_pull_request`. T3 refuses a delegated child's watch, and a native subagent's watch lands on your thread.

## Roles

Role defaults. A role line in `p3-models.md` overrides one. Look for `.claude/p3-models.md` in the repo, then `p3-models.md` in the Claude config dir (`$CLAUDE_CONFIG_DIR`, else `~/.claude`). `/p3:setup-pstack` writes it.

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

Upstream runs every role at its model's highest reasoning setting, and so do these defaults. `/p3:setup-pstack` lowers them for a smaller budget.

A value is `<alias> @<effort>`, `inherit` (omit `model` and `effort`), or `t3:<providerInstanceId>/<modelId> @<effort>` for a `delegate_task` target. A value without `@` uses the session effort. An effort a model does not offer falls back to its default, so report the effort the child ran at, not the one you asked for.

**Model diversity.** Upstream's panels pair two vendors. Claude models share one vendor, so a disagreement between opus, fable, and sonnet is real but weaker evidence than upstream's. Say so when a verdict rests on agreement. A T3 role line can add another provider when the user has one.

## Isolation

Two writers never share a checkout (principle-separate-before-serializing-shared-state).

- Read-only children share your checkout.
- Worktrees you create are invisible to T3's diff and checkpoint views, which show only the thread's own checkout. Report each one's branch and head SHA. In T3's approval-required mode, writes to a worktree outside the project ask for approval each time, so run fan-out playbooks in `auto` or `full-access`.
- **A child that writes while another writer may overlap** gets its own worktree, created by you before you spawn it, from your current HEAD: `git worktree add <path> -b <branch> HEAD`. Commit first, because uncommitted changes do not reach it. The brief says: work only under the absolute path, prefix every command with `cd <path> &&`, report the branch and head SHA. Check that the diff landed there before you integrate. Remove the worktree after.
- Do not use `Agent` `isolation: "worktree"` for stacked or branch-based work. It branches from the remote default branch unless the user set `worktree.baseRef: "head"`.
- **A long-lived owner** (a PR owner in Autopilot or Orchestrate) in T3 is a launched thread: `t3_thread_launch` with a `title` and `workspaceStrategy: {"type":"worktree","baseRef":"<commit SHA>","branch":"<branch>","startFromOrigin":false}`. Commit first, then set `baseRef` to `git rev-parse HEAD`. Never pass a branch name that T3 created: it names a new worktree's branch `t3/<hash>` and renames it in the background, so that name can vanish before the launch runs and the thread fails with "Workspace preparation failed" and the brief in `message`. Open the brief with the router's absolute path and the line `Read it in full before any work.`, since a launched thread is a new session where poteto mode is off. Pass `modelSelection: {instanceId, model, options:[{"id":"effort","value":"<level>"}]}`. Leave out `runtimeMode` and `interactionMode`, so the thread runs in your modes. Keep the returned `threadId`. Within a minute, read each launched thread (`t3_thread_list` or `t3_thread_read`) and confirm it is running, not failed. On "Workspace preparation failed", fix the cause and launch again. Launch has no retry key, so after a lost response check `t3_thread_list` before you launch again. Invoking one of those playbooks is the user's request for separate threads.
  - A launched thread never wakes its launcher. Its brief says to report each milestone with `t3_thread_send` and `mode: "queue"` to the coordinator's thread id (the default `auto` steers an active turn, which interrupts Claude's running tools), and to stop when that call is refused. The coordinator also watches the owner's PR and keeps a heartbeat ([Waking](#waking)).
  - Outside T3 a long-lived owner is a background `Agent` in its own worktree.

## Waking

| Need | T3 | Plain Claude Code |
|---|---|---|
| Wake on a PR event | `watch_pull_request`, then end the turn | `/loop` dynamic mode with `watch-pr` |
| Recurring tick (hourly audit, overnight cadence) | `schedule_task` with `schedule: {"type":"interval","everyMs":3600000}` and the default `bindToCurrentThread` | `/loop 1h` |
| Wall-clock tick | `schedule_task` with `{"type":"fixed_time","timeOfDay":"09:00"}` | `/loop` or cron |
| Drive one task to a predicate | a `schedule_task` heartbeat bound to this thread, deleted when the predicate holds. The user may also start Claude's `/goal <condition>`, which T3 tracks. Only the user can start it. | `/loop` until the predicate, or the user's `/goal` |
| Wait for a child | its completion wake, `task_status`, or `t3_thread_wait` (at most 60 min) | the Agent completion notice |

- `schedule_task` takes `schedule` as an object, never as JSON text. The minimum interval is 60 seconds. A run bound to a busy thread queues behind the active turn. Report the returned cadence and next run time. Delete the task (`delete_scheduled_task`) when its predicate holds.
- An unbound scheduled run starts a fresh thread from `main` at origin. Bind runs to the coordinator unless the user asked for fresh threads.
- A `fixed_time` slot missed while T3 was closed is skipped, not caught up. Check for missed work on the next run.
- These survive a T3 restart. `/loop` and background Bash do not.

## Pull requests

- Open with `gh`. After opening or adopting a PR, register it on the thread with `link_pull_request` (T3), one call per stack layer.
- **Wake** with `watch_pull_request` from a top-level thread, never from a child ([Subagents](#subagents)). It wakes on a newly failed check, all required checks passing, a new comment or review from someone else posted after the watch began, a conflict, a close, or repeated read failures. Handle existing comments first, since they will not wake you. Wakes queue behind an active turn. A wake does not name the head SHA, so read it.
- **A merge does not wake you.** The watch ends silently. When you wait on a merge, also keep a `schedule_task` heartbeat (every 10 to 30 minutes) that checks the PR state, and delete it after.
- Ten comment-only wakes in a row end the watch. Settling or archiving the thread, or the user pressing Stop, ends it too. Unsettle a settled thread (`t3_thread_update`) before a new watch. Call `unwatch_pull_request` before handing the thread back to the user.
- **Read state** with the bundled watcher (bun): `scripts/watch-pr/watch-pr --status-only` under this file's skill directory prints one status table (checks, review state, `mergeStateStatus`, head SHA) and exits. **Judge** by running it once without `--status-only` when no check is pending. It returns the verdict at once. A green check list is not a verdict, and the watcher reports `READY` on a branch that is `BEHIND` its base, so read `mergeStateStatus` yourself.

## Questions

- `AskUserQuestion` renders as a T3 question card. Give every option a non-empty description. A blank one can stall the thread.
- T3's `auto` and `full-access` runtime modes approve tool calls without asking. Permission prompts do not guard the Always-pause list in poteto-mode's Autonomy section. You do. Ask before each item on it.
- In plan mode, call `ExitPlanMode` with the plan. T3 shows it as a plan card, denies the call, and you stop. The user approves and sends the next message.
- When `AskUserQuestion` is not in your tools, ask in plain text and end the turn.
- T3 refuses a model, effort, or mode change while background agents or shells run. Ask for any mode switch before the first background child starts.
- In plan mode T3 does not pre-approve `task_status` or `t3_thread_read`, so each read asks for approval.

## Todo list

Claude Code offers no todo tools on current models (Opus 4.8 and later, Sonnet 5, Fable 5) unless the user sets `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`. When `TaskCreate` and `TaskUpdate` (or `TodoWrite`) are in your tools, use them. Otherwise keep the list in `.audit/<slug>.todo.md` in the working tree, where `<slug>` is a short kebab-case name for the task. One line per item, `- [ ]` or `- [x]`, updated at each step. Keep `.audit/` out of git as [Store](#store) says.

## History

- **T3:** `t3_thread_list` (one project per call, `titleContains` for titles), `t3_thread_read` (any thread, paged, `view: "activity"` for tool calls), `t3_thread_search` (message text only, one hit per thread, at most 50, no titles). Reading a direct child's finished result acknowledges its wake.
- **Claude transcripts:** `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<dir>/<session>.jsonl`, where `<dir>` is the working directory with every character other than a letter or digit replaced by `-`. A `<dir>` longer than 200 characters is cut to 200 and gets a hash suffix, so for a long path list `projects/` and match the prefix. Subagent transcripts are `<dir>/<session>/subagents/agent-<id>.jsonl`. T3 threads write them too, with the thread's worktree as the working directory. Skip records with `isMeta` and local-command records.

## Proof surfaces

- **Browser and web UIs (T3):** call `preview_status`, then `preview_open` if nothing is attached, then `preview_navigate`, `preview_snapshot`, and the focused tools. Prefer snapshot locators to coordinates. Record proof with `preview_recording_start` and `preview_recording_stop`, or `preview_snapshot` with `save: true`. A tab owned by `human` is read-only for you. Parallel children open their own tab with `reuseExistingTab: false` and pass its `tabId`. If preview fails twice on the same step, quote the error and use another browser tool.
- **Simulators (T3):** `device_list`, `device_open` (it returns an `agent-device` command for taps and typing), `device_screenshot`, `device_close`. Device access is off until the user enables it in T3 settings. Say so if a call is refused.
- **CLIs and TUIs:** drive them in the terminal. For a TUI, use `tmux` with `send-keys` and `capture-pane`.
- **Visual reports (T3):** check a self-contained HTML page with `html_preview`, then publish it with `html_render` before the final reply. Do not restate it.
- **Plain Claude Code:** a browser MCP server or Playwright when installed. Otherwise say which surface you could not drive.
- **Secrets (T3):** `request_secret`. Never ask for a secret in chat.

## Store

Durable files for a program (Orchestrate's tables, decision logs, resume notes) go under `.p3/<slug>/` at the repo root. The first time, append `.p3/` and `.audit/` to the file that `git rev-parse --git-path info/exclude` prints. In a worktree `.git` is a file, so never write `.git/info/exclude` by hand. Worktree threads see only committed files, so pass a coordinator's store path as an absolute path.

## Missing companions

- **deslop.** Before a commit, reread the diff and remove slop per the unslop skill and poteto-mode's Comments section: narrating comments, dead code, needless wrappers, defensive checks on trusted internal values, and debug output.
- **skill-authoring.** Follow the Authoring a skill playbook. Claude Code's `skill-creator` plugin helps with evals when installed.
- **babysit collisions.** Claude Code's `/autofix-pr` and T3's own PR watching match the same words as Babysit. The Babysit playbook wins.
