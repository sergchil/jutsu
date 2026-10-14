---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
---

# Swarm

Fan out N parallel workers. They may cover separate slices, race the same brief, or mix both. The parent waits, aggregates, and returns one report.

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers, not how many run at once.
4. Pick the worker `model` and `effort` from the `swarm workers` line in `jutsu-models.md`. If the file or that line is missing, use its default in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). For `inherit`, omit both so the workers run on the parent model. If the `Agent` tool rejects a value, use the default and say so. A line that names a T3 target runs the workers through `delegate_task` per [the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents). Pass `options` with `effort` on every call and a distinct `clientRequestId` per worker and per respawn, and read each result with `task_status` after the wake. A worker that reviews never runs below `high` effort. For a model race, name each arm's model and effort up front, and report the ones each arm actually ran at. Pick each subagent's reasoning level and fast or standard speed for the job, per the Subagents section of the **poteto-mode** skill (`{{plugin}}/skills/poteto-mode/SKILL.md`) and [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles).
5. Give each worker its own writable output when it writes. A worker that writes to the repo gets its own worktree, created from your HEAD before you spawn it, per [the runtime's Isolation]({{plugin}}/skills/poteto-mode/references/runtime.md#isolation). Do not use `Agent` `isolation: "worktree"` for it, since that branches from the remote default branch. When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method (sample count, what one sample is, order). The worker records both in its result.

## Phase B: Fan out

Spawn all N workers in one message with `subagent_type: "general-purpose"`, `run_in_background: true`, and the step 4 `model` and `effort`, left unset for `inherit`. Workers run on this machine, so each writer works only in its own worktree. Launch workers as separate T3 threads (`t3_thread_launch`) only when the user asked for separate threads, and then follow the launched-thread rules in [the runtime's Isolation]({{plugin}}/skills/poteto-mode/references/runtime.md#isolation).

When a worker must start from a branch other than your HEAD, create its worktree from that branch.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Never put `$(...)` or shell-expanding backticks in a brief a worker pastes into a command. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that can prove a defect reports `ISSUES` and lists every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and method its brief names, and respawn that worker once. After a second miss, record a gap. A gap does not count as a pass. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
