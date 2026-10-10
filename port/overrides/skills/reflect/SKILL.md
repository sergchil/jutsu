---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
disable-model-invocation: true
---

# Reflect

Mine the current conversation for durable learnings, then route them into skill edits.

## When to invoke

Invoke when the user says "reflect" or "/reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## Process

### 1. Locate the active transcript

The parent finds its own transcript file before fanning out. Claude writes it under `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<dir>/`, per [the runtime's History]({{p3}}/skills/poteto-mode/references/runtime.md#history). T3 threads write there too. Use that directory. Do not glob across `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/*/`. That crosses workspace boundaries and reads private chats from unrelated projects.

```bash
ls -t <transcripts>/*.jsonl <transcripts>/*/subagents/*.jsonl 2>/dev/null | head -10
```

Two transcript layouts: session (`<id>.jsonl`) and subagent (`<id>/subagents/agent-<child>.jsonl`).

For each candidate, find the first `user` record that is not `isMeta` and is not a local-command record (its text opens with `<command-name>`, `<local-command-stdout>`, or `<bash-input>`). Check that its `message.content`, a string or a list of text blocks, contains the conversation's opening user prompt. Take the matching path. If no path resolves, write a tight digest of the session and pass that instead. In T3, `t3_thread_read` with `view: "activity"` on this thread lists its tool calls for the digest. `orchestrator_capabilities` returns this thread's id as `parentThreadId`.

### 2. Spawn three reviewers in parallel

One message, three `Agent` calls, `subagent_type: "general-purpose"`, with `model` and `effort` set as below. Reviewers need MCP access for context lookups (tickets, chat threads, observability traces referenced in the transcript). The templates forbid writes.

Each reviewer and the synthesizer name a role line in `p3-models.md` and its default in [the runtime's Roles]({{p3}}/skills/poteto-mode/references/runtime.md#roles). Set `model` and `effort` from that line, or from the default if the file or the line is missing. Reviewers and the synthesizer never run below `high` effort, so raise a lower value to `high`. Omit both when the value is `inherit`. If the `Agent` tool rejects a value, use the default and say so. A line that names a T3 target runs that spawn through `delegate_task` per [the runtime's Subagents]({{p3}}/skills/poteto-mode/references/runtime.md#subagents). Pass `options` with `effort` on every call and a distinct `clientRequestId` per call, and read the result with `task_status` after the wake.

| Lens | Role line | Prompt template |
|---|---|---|
| Judgment | `reflect judgment, divergent, synthesizer` | `references/judgment-reviewer.md` |
| Tooling | `reflect tooling` | `references/tooling-reviewer.md` |
| Divergent | `reflect judgment, divergent, synthesizer` | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings in the `Agent` result.

### 3. Synthesize

One `Agent` call, `subagent_type: "general-purpose"`, with `model` and `effort` from the `reflect judgment, divergent, synthesizer` line. The synthesizer's quality check includes spot-verifying citations, which can require MCP access. Use `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. The synthesizer returns a structured Accepted / Rejected / Backlog list.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. For any item that would be enforced more reliably by a lint rule, script, metadata flag, or runtime check, move it from Accepted to Backlog. See the **encode-lessons-in-structure** principle (`{{p3}}/principles/principle-encode-lessons-in-structure.md`).

### 5. Apply

Before applying any Accepted edit, present the synthesizer's full Accepted/Rejected/Backlog output to the user and wait for explicit approval. The user picks which subset to apply and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

Backlog items file to whatever devex / backlog tracker your team uses automatically. Only the Accepted list waits for approval.

For each approved Accepted item, follow the Routing field exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): parent does directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): follow the Authoring a skill playbook (`{{p3}}/skills/poteto-mode/playbooks/authoring-a-skill.md`) and run its draft / test / iterate loop.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): follow the same playbook and run a description-optimization loop. Claude Code's `skill-creator` plugin helps with its evals when installed, per [the runtime's Missing companions]({{p3}}/skills/poteto-mode/references/runtime.md#missing-companions).
- `new skill via authoring-a-skill: <kebab-name>`: hand creation to the Authoring a skill playbook. Do not invent the shape ad hoc.

If your environment ships a SKILL.md validator, run it on every touched skill before declaring done. Skip this step if it doesn't.

### 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
