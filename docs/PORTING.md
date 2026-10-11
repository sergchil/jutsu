# Porting guide

How p3-stack turns upstream pstack (Cursor) into a Claude Code plugin that runs well inside T3 Code. Every override follows these rules.

## Layout

- `vendor/pstack/` is upstream, byte for byte. Never edit it. `tools/sync_upstream.py` refreshes it.
- `port/spec.json` maps paths, drops Cursor-only frontmatter, and sets which skills the model may invoke.
- `port/substitutions.json` holds mechanical rewrites for files that need only small changes. Every rule must match at least once, or the build fails.
- `port/overrides/<plugin path>` replaces a whole file. `port/overrides.lock.json` pins the upstream file each override was merged against. When upstream changes, the build fails until the override is re-merged and `tools/build.py --relock` runs.
- `port/added/<plugin path>` holds files upstream does not have (the runtime, hooks, the `/p3` alias, the manifest).
- `plugin/` is generated. Never edit it by hand.

## Rules for an override

1. **Fidelity first.** Keep upstream's words. Change a sentence only when one of these forces it:
   - the Cursor mechanism it names does not exist in Claude Code or T3;
   - a verified Claude Code or T3 behavior in `plugin/skills/poteto-mode/references/runtime.md` makes it wrong;
   - a lesson in the list below.
   Never add policy of your own. Never drop a step. Keep step numbers, because other files cite them.
2. **Mechanisms come from the runtime.** Name the exact tool and parameters the runtime names. Link the runtime section instead of repeating it: from a playbook, `../references/runtime.md#subagents`; from anywhere else, `{{p3}}/skills/poteto-mode/references/runtime.md#subagents`. When a step needs a T3-only tool, say what to do without it in the same step or link the runtime row that says it.
3. **Skills and principles are files.** Every p3 skill has `disable-model-invocation: true`, so it is not in the model's skill list. On the first mention of another skill in a file, give its path: the **how** skill (`{{p3}}/skills/how/SKILL.md`). Principles: `{{p3}}/principles/principle-<name>.md`. The build replaces `{{p3}}` with the relative path from the file to the plugin root. Do not use `{{p3}}` in `agents/*.md`.
4. **Subagents.** Cursor `Task` becomes the `Agent` tool: `subagent_type`, `model` (alias `opus`, `sonnet`, `fable`, `haiku` only), `effort` (`low` to `max`), `run_in_background`. Models come from the role names in the runtime's Roles section. Cursor's slug-fallback rules (the Task error's valid-slug list) are dropped. A `readonly: true` child becomes a read-only brief, plus `subagent_type: "Explore"` when it only reads code. Cursor's "readonly strips MCP" caveat is dropped.
5. **Names.** `/poteto-mode` becomes `/p3`. Other skills become `/p3:<name>`. `poteto-agent` becomes `p3:poteto-agent`. `Comment Sicko` becomes `p3:comment-sicko`. The models file is `p3-models.md`, written by `/p3:setup-pstack`. Generated project skills go to `.claude/skills/`, personal ones to `$CLAUDE_CONFIG_DIR/skills/` (default `~/.claude/skills/`).
6. **Style.** Upstream's prose rules: short declarative sentences, no long dash, no colon as a mid-sentence connector, no fabricated links.

## Lessons to encode

Each one comes from a real run of a port, or from T3's source. Put each where its step lives.

1. In Claude's agent list, `completed` means notified, not exited. Stop an abandoned agent and confirm with `git status` before a fresh one takes its work.
2. Before a commit, merge, push, or deploy from a worktree, stop every child that writes there, grandchildren included.
3. A review gate stays closed when no independent reviewer could run. Record `BLOCKED: independent review` and say which reviewers ran.
4. One worktree per writer, from your HEAD. `Agent` `isolation: "worktree"` branches from the remote default branch.
5. A launched T3 thread never wakes its launcher. It reports with `t3_thread_send`. The coordinator also watches its PR and keeps a heartbeat.
6. A merge ends a PR watch without a wake. Waiting on a merge needs a `schedule_task` heartbeat.
7. Subagents and delegated children cannot `watch_pull_request`. Babysit and Shipping run in a top-level thread.
8. A watch wake does not name the head SHA. Read it before acting.
9. Comments that existed before the watch started never wake it. Handle them first.
10. A delegated child can finish its turn and leave its run open, so its completion wake never comes. A bounded `t3_thread_wait` or a heartbeat catches it.
11. Read back the provider, model, and effort a child actually ran at. A child on a different model without `options` runs at default effort.
12. Reviews never run below `high` effort. Medium-effort reviews missed real blockers.
13. A Claude child that leaves a background shell running can end its turn early. Children run commands in the foreground.
14. Never put `$(...)` or shell-expanding backticks in a brief a child pastes into a command.
15. A child's modes can never be broader than its parent's. An unattended program needs the coordinator in `auto` or `full-access`, or every child stalls on approvals.
16. T3's `auto` and `full-access` modes approve tool calls silently. The agent holds the Always-pause list itself.
17. `t3_thread_interrupt` does not stop async children. `task_cancel` does.
18. An unbound `schedule_task` run starts from `main` at origin. Bind runs to the coordinator.
19. `AskUserQuestion` options need non-empty descriptions.
20. Claude transcripts live under `$CLAUDE_CONFIG_DIR/projects/<dir>/`, where `<dir>` is the working directory with every character other than a letter or digit replaced by `-` (cut to 200 characters plus a hash when longer). Link the runtime's History section instead of restating the rule. Skip `isMeta` and local-command records.
21. The todo fallback is `.audit/<slug>.todo.md`, one file per session slug, so parallel sessions do not collide.
22. Babysit reports a behind-base gate instead of resolving it, and confirms its first status read is the PR it was asked about.
23. No subagent has `AskUserQuestion`, `ScheduleWakeup`, or `/loop`. Questions and timed wakes stay in a top-level thread. A babysitting subagent reruns the watcher in the foreground.
24. Reports into a coordinator use `t3_thread_send` with `mode: "queue"`. The default `auto` steers an active turn, and a steer interrupts Claude's running tools.
25. A launched thread is a new session where poteto mode is off. Its brief opens with the router's absolute path.
26. In plan mode, Claude calls `ExitPlanMode`. T3 builds its plan card from that call and denies it.
27. Todo tools are off on current Claude models by default, so the `.audit/` file fallback is the normal path.
28. Keep `.p3/` and `.audit/` out of git through `git rev-parse --git-path info/exclude`. In a worktree `.git` is a file.
29. The default effort is `xhigh`, as upstream runs. `setup-pstack`'s example table must equal the runtime's Roles (a test checks it).
30. A launched T3 thread starts from a commit SHA. T3 names a new worktree's branch `t3/<hash>` and renames it in the background, so a branch name read from T3 can vanish before the launch runs ("Workspace preparation failed"). Read back each launched thread within a minute.
31. Keep upstream's bare `/<skill>` commands. The build rewrites them to `/p3:<skill>`, so new upstream skills need no edit for naming.
32. A fork (T3's thread fork) has a new session id. The mode hook restores poteto mode from the last `/p3` command in the transcript on `fork`, `resume`, and `compact`.

## Tests

`python3 -m unittest discover -s tests` and `python3 tools/build.py --check`.
