---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
disable-model-invocation: true
---

# Reflect

Mine the current conversation for durable learnings, then route them into skill edits.

Invoke when the user says "reflect" or "/reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## 1. Locate the active transcript

Before fanning out, find this conversation's transcript in the `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<dir>/` directory Claude writes it to, per [the runtime's History]({{plugin}}/skills/poteto-mode/references/runtime.md#history). T3 threads write there too. Do not glob across `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/*/`. That crosses workspace boundaries and reads private chats from unrelated projects.

```bash
ls -t <transcripts>/*.jsonl <transcripts>/*/subagents/*.jsonl 2>/dev/null | head -10
```

That covers the session (`<id>.jsonl`) and subagent (`<id>/subagents/agent-<child>.jsonl`) layouts. For each candidate, find the first `user` record that is not `isMeta` and is not a local-command record (its text opens with `<command-name>`, `<local-command-stdout>`, or `<bash-input>`). Take the file whose `message.content`, a string or a list of text blocks, contains the conversation's opening user prompt. If none matches, pass a tight digest of the session instead. In T3, `t3_thread_read` with `view: "activity"` on this thread lists its tool calls for the digest. `orchestrator_capabilities` returns this thread's id as `parentThreadId`.

## 2. Spawn three reviewers in parallel

One message, three `Agent` calls, `subagent_type: "general-purpose"`. Reviewers need MCP access to look up the tickets, chat threads, and observability traces the transcript references. The templates forbid writes.

Each reviewer and the synthesizer name a role line in `jutsu-models.md` and its default in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). Set `model` and `effort` from that line, or from the default if the file or the line is missing. Reviewers and the synthesizer never run below `high` effort, so raise a lower value to `high`. Omit both when the value is `inherit`. If the `Agent` tool rejects a value, use the default and say so. A line that names a T3 target runs that spawn through `delegate_task` per [the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents). Pass `options` with `effort` on every call and a distinct `clientRequestId` per call, and read the result with `task_status` after the wake.

| Lens | Role line | Prompt template |
|---|---|---|
| Judgment | `reflect judgment, divergent, synthesizer` | `references/judgment-reviewer.md` |
| Tooling | `reflect tooling` | `references/tooling-reviewer.md` |
| Divergent | `reflect judgment, divergent, synthesizer` | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings in the `Agent` result.

## 3. Synthesize

One `Agent` call, `subagent_type: "general-purpose"`, `model` and `effort` from the `reflect judgment, divergent, synthesizer` line. It spot-verifies citations through MCP. Pass `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. It returns an Accepted / Rejected / Backlog list.

## 4. Structural enforcement check

Move any Accepted item that a lint rule, script, metadata flag, or runtime check would enforce more reliably to Backlog. See the **encode-lessons-in-structure** principle (`{{plugin}}/principles/principle-encode-lessons-in-structure.md`).

## 5. Apply

Present the synthesizer's full Accepted / Rejected / Backlog output and wait for explicit approval before applying any Accepted edit. The user picks the subset and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

File each Backlog item to your team's devex or backlog tracker without waiting. Only the Accepted list waits for approval.

Follow each approved row's Routing exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): the parent does it directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): follow the Authoring a skill playbook (`{{plugin}}/skills/poteto-mode/playbooks/authoring-a-skill.md`) and run its draft / test / iterate loop.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): follow the same playbook and run a description-optimization loop. Claude Code's `skill-creator` plugin helps with its evals when installed, per [the runtime's Missing companions]({{plugin}}/skills/poteto-mode/references/runtime.md#missing-companions).
- `new skill via authoring-a-skill: <kebab-name>`: hand creation to the Authoring a skill playbook. Do not invent the shape ad hoc.

If your environment ships a SKILL.md validator, run it on every touched skill before declaring done.

## 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
