# Porting guide

How jutsu turns upstream pstack (Cursor) into a Claude Code plugin that runs well inside T3 Code. Every override follows these rules.

## Layout

- `vendor/pstack/` is upstream, byte for byte. Never edit it. `tools/sync_upstream.py` refreshes it.
- `port/spec.json` maps paths, drops Cursor-only frontmatter, and sets which skills the model may invoke.
- `port/subs/*.json` hold mechanical rewrites for files that need only small changes. Every rule must match at least once, or the build fails.
- `port/overrides/<plugin path>` replaces a whole file. `port/overrides.lock.json` pins the upstream file each override was merged against. When upstream changes, `tools/sync_upstream.py` 3-way merges the override, and the build fails until a person reviews it and `tools/build.py --relock <path>` runs.
- `port/overrides.json` gives each override a reason: `kind` (`runtime`, `upstream-bug`, `lesson`, `naming`, or `other`), a one-sentence `why`, and the `upstream` issue or PR URL or `null`. The build fails on an override without an entry, an entry without an override, and an override that matches upstream.
- `port/adapter.json` records how jutsu answers each row of upstream's own Claude Code adapter (`vendor/pstack/docs/harness/claude-code.md`, not shipped). `tools/adapter_diff.py` checks it.
- Dotfiles such as `.DS_Store` are never overrides, added files, or upstream files. The build and sync skip them.
- `port/added/<plugin path>` holds files upstream does not have (the runtime, hooks, the `/jutsu` alias, the manifest).
- `plugin/` is generated. Never edit it by hand.

## Rules for an override

1. **Keep upstream's words only where they work in Claude Code and T3.** Port nothing blindly. For each sentence:
   - it works here as written: keep it;
   - Claude Code or T3 does the job natively, or a verified behavior in the [runtime](../port/added/skills/poteto-mode/references/runtime.md) makes it wrong: adapt it to the native mechanism;
   - it does nothing here (a Cursor mechanism with no counterpart, a rule no tool can act on, text that repeats T3's injected prompt): drop it, and record the drop in that file's `why` in `port/overrides.json`.
   Fidelity to upstream wording is not a reason to keep text. Never add policy of your own. Keep step numbers, because other files cite them; a dropped step keeps its number with a one-line reason.
2. **Mechanisms come from the runtime.** Name the exact tool and parameters the runtime names. Link the runtime section instead of repeating it: from a playbook, `../references/runtime.md#subagents`; from anywhere else, `{{plugin}}/skills/poteto-mode/references/runtime.md#subagents`. When a step needs a T3-only tool, say what to do without it in the same step or link the runtime row that says it.
3. **Skills and principles are files.** A jutsu skill has `disable-model-invocation: true`, so it is not in the model's skill list, unless `port/spec.json` lists it in `model_invocable` (today `tdd`, `benchmark-checklist`, and `typescript-best-practices`: cheap, no fan-out, no writes, and their trigger is real). A model-invocable skill keeps upstream's "Use when" description. A slash-only one says what it does and how to run it (`tools/check.py` enforces both). On the first mention of another skill in a file, give its path: the **how** skill (`{{plugin}}/skills/how/SKILL.md`). Principles: `{{plugin}}/principles/principle-<name>.md`. The build replaces `{{plugin}}` with the relative path from the file to the plugin root. Do not use `{{plugin}}` in `agents/*.md`.
4. **Subagents.** Cursor `Task` becomes the `Agent` tool: `subagent_type`, `model` (alias `opus`, `sonnet`, `fable`, `haiku` only), `effort` (`low` to `max`), `run_in_background`. Models come from the role names in the runtime's Roles section. Cursor's slug-fallback rules (the Task error's valid-slug list) are dropped. A `readonly: true` child becomes a read-only brief, plus `subagent_type: "Explore"` when it only reads code. Cursor's "readonly strips MCP" caveat is dropped.
5. **Names.** `/poteto-mode` becomes `/jutsu`. Other skills become `/jutsu:<name>`. `poteto-agent` becomes `jutsu:poteto-agent`. `Comment Sicko` becomes `jutsu:comment-sicko`. The models file is `rules/jutsu-models.md` in the Claude config dir, written by `/jutsu:setup-pstack`. A repo `.claude/jutsu-models.md` wins over it. Generated project skills go to `.claude/skills/`, personal ones to `$CLAUDE_CONFIG_DIR/skills/` (default `~/.claude/skills/`).
6. **Style.** Upstream's prose rules: short declarative sentences, no long dash, no colon as a mid-sentence connector, no fabricated links.

## Lessons to encode

Each one comes from a real run of a port, or from T3's source. Put each where its step lives.

1. In Claude's agent list, `completed` means notified, not exited. Stop an abandoned agent and confirm with `git status` before a fresh one takes its work.
2. Before a commit, merge, push, or deploy from a worktree, stop every child that writes there, grandchildren included.
3. A review gate stays closed when no independent reviewer could run. Record `BLOCKED: independent review` and say which reviewers ran.
4. One checkout per writer. In T3 that is `delegate_task` with `isolation: "worktree"` (from your HEAD commit, so commit first). `Agent` `isolation: "worktree"` branches from the remote default branch, so a native writer gets a hand-made worktree from your HEAD. See the runtime's [Isolation](../port/added/skills/poteto-mode/references/runtime.md#isolation).
5. A launched T3 thread never wakes its launcher. It reports with `t3_thread_send`, and the coordinator keeps a heartbeat. Launch threads only when the user asks for them or for a PR owner, which must watch its own PR.
6. A merge ends a PR watch without a wake. Waiting on a merge needs a `schedule_task` heartbeat.
7. Subagents and delegated children cannot `watch_pull_request`. Babysit and Shipping run in a top-level thread.
8. Only the checks-passed wake names the head SHA, and only its 7-character form. Read the full SHA before acting.
9. Comments that existed before the watch started never wake it. Handle them first.
10. A delegated child can finish its turn and leave its run open, so its completion wake never comes. A bounded `t3_thread_wait` or a heartbeat catches it.
11. Read back the provider, model, and effort a child actually ran at. A child on a different model without `options` runs at default effort.
12. Reviews never run below `high` effort. Medium-effort reviews missed real blockers.
13. A Claude child that leaves a background shell running can end its turn early. Children run commands in the foreground.
14. Never put `$(...)` or shell-expanding backticks in a brief a child pastes into a command.
15. A child's modes can never be broader than its parent's. An unattended program needs the coordinator in `auto` or `full-access`, or every child stalls on approvals.
16. T3's `full-access` mode approves every tool call. Its `auto` mode is Claude's own auto permission mode, which may still ask or refuse on a risky action. Neither is a pause rule, so the agent holds the Always-pause list itself.
17. `t3_thread_interrupt` does not stop async children. `task_cancel` does.
18. An unbound `schedule_task` run starts from `main` at origin. Bind runs to the coordinator.
19. `AskUserQuestion` options need non-empty descriptions.
20. Claude transcripts live under `$CLAUDE_CONFIG_DIR/projects/<dir>/`, where `<dir>` is the working directory with every character other than a letter or digit replaced by `-` (cut to 200 characters plus a hash when longer). Link the runtime's History section instead of restating the rule. Skip `isMeta` and local-command records.
21. The todo fallback is `.audit/<slug>.todo.md` in the main checkout, one file per session slug, so parallel sessions do not collide.
22. Babysit reports a behind-base gate instead of resolving it, and confirms its first status read is the PR it was asked about.
23. No subagent has `AskUserQuestion`, `ScheduleWakeup`, or `/loop`. Questions and timed wakes stay in a top-level thread. A babysitting subagent reruns the watcher in the foreground.
24. Reports into a coordinator use `t3_thread_send` with `mode: "queue"`. The default `auto` steers an active turn, and a steer interrupts Claude's running tools.
25. A launched thread is a new session where poteto mode is off. Its brief opens with the router's absolute path.
26. T3's plan mode is Claude's plan permission mode, so writes are refused. Run the read-only steps, put the plan in `ExitPlanMode`, and stop. T3 builds its plan card from that call and denies it.
27. Todo tools are off on current Claude models by default, so the `.audit/` file fallback is the normal path.
28. Keep `.jutsu/` and `.audit/` out of git through `git rev-parse --git-path info/exclude`, which every worktree shares. In a worktree `.git` is a file.
29. The default effort is `xhigh`, as upstream runs. `setup-pstack`'s example table must equal the runtime's Roles (a test checks it).
30. A launched T3 thread starts from a commit SHA. T3 names a new worktree's branch `t3/<hash>` and renames it in the background, so a branch name read from T3 can vanish before the launch runs ("Workspace preparation failed"). Read back each launched thread within a minute.
31. Keep upstream's bare `/<skill>` commands. The build rewrites them to `/jutsu:<skill>`, so new upstream skills need no edit for naming.
32. A fork (T3's thread fork) has a new session id. The mode hook restores poteto mode from the last `/jutsu` command in the transcript on `fork`, `resume`, and `compact`.
33. T3 expands only the last `$skill` mention into a slash command. The mode hook also turns the mode on from `UserPromptSubmit` text: `/jutsu` or `$jutsu` as a whole token at the start of the prompt or of a line, outside code, or a `skill://` link to jutsu. A mention inside a sentence ("what does $jutsu do?") does not count. A prompt that is only `/jutsu off` or `$jutsu off` turns it off.
34. Claude Code's `SubagentStart` hook reaches the child through `additionalContext` and carries the parent's session id (probed on 2.1.296). The mode hook gives a `jutsu:poteto-agent` child the router path when the mode is on. Briefs still open with the router path, since other child types get nothing.
35. Never call `t3_worktree_handoff`. Its queued continuation can wait minutes or never start. Use `delegate_task` with `isolation: "worktree"` instead.
36. zsh expands a word that starts with `=`, so `echo =====` kills a chained command. Quote separators, or use one `Read` per file.
37. A short `delegate_task` wave stays in the turn: async launches, then `t3_thread_wait` on each child. Several `mode: "wait"` calls run one after another. On a failed wait, end the turn.
38. Date every harness fact in the runtime with the build it was probed on, or cite its source, so the next T3 or Claude update knows what to re-probe.
39. Pass `-R <owner>/<repo>` from the PR URL to `gh pr` and `gh run` for a PR that may come from a fork, and name the PR by number or URL, not by branch.
40. T3 deletes its worktrees by its cleanup rules, and by default keeps one only for uncommitted changes (`storageCleanup.ts:330-366`), so git-ignored files in a worktree are lost. `.jutsu/` and `.audit/` live in the main checkout, found from `git rev-parse --path-format=absolute --git-common-dir` (a test runs the runtime's snippet in a real linked worktree).
41. T3 injects its own orchestration rules into Claude's system prompt (`orchestrationInstructions.ts`, `runtimeInstructions.ts`). The runtime keeps only what jutsu adds and links T3's rule by name. `tools/t3-instructions.txt` snapshots that text, and the weekly T3 workflow opens a PR when it changes, since a new parameter can make the runtime wrong while every tool name stays the same.
42. An effort change applies to a running T3 session, and a model change keeps background agents. Only a mode change may still be refused while background work runs (Not checked).
43. A read-only sandbox, not plan mode, is what limits T3's pre-approved tools to the read-only ones.
44. A review guide (`write_pull_request_guides`) explains a PR. It never replaces a verdict.
45. In T3 each worktree thread writes its transcripts under its own `projects/<dir>/`, so "this workspace's transcripts" covers about one thread. Use `t3_thread_list` and `t3_thread_read` for the rest.
46. Claude Code loads every `.md` file in the config dir's `rules/` folder into each new session ([memory docs](https://code.claude.com/docs/en/memory#user-level-rules)). The models file lives there, so role lines are in context. A skill reads the file when they are not, or when setup ran after the session started. The file keeps jutsu's own name, since upstream's adapter writes `pstack-models.md` in another format.
47. A step that needs a Cursor-only feature with no T3 or Claude Code counterpart writes exactly `Skipped in Claude Code: <step>. <reason>.` and goes on (upstream's adapter). Schedules, webhooks, PR watching, cloud workers, and Bugbot comments have counterparts here, so they are never skipped.
48. When upstream's Claude Code adapter disagrees with jutsu, record why in `port/adapter.json`. Fix jutsu only when the row shows a real gap, as with `SendMessage` resuming a finished subagent.

## Tests

`python3 -m unittest discover -s tests`, `python3 tools/build.py --check`, and `python3 tools/adapter_diff.py`.
49. Upstream's defaults (every role at `xhigh`, three-model architect and review panels) cost hours on ticket-sized work in real HoF runs: 22 minutes of three architects and a judge for one datasource contract, and a three-reviewer interrogate that ran 12 h 40 min through retries. jutsu's defaults are the `balanced` budget: Opus `high` for code, Fable only for perf and the hardest tasks, Sonnet for reading and workers, one architect runner with no judge, one reviewer. `large` in setup-pstack restores upstream's.
