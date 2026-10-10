---
name: interrogate
description: "Use for \"interrogate\", \"adversarial review\", \"multi-model review\", \"challenge this\", \"stress test this code\", \"find blind spots\", or \"tear this apart\". Multiple LLM reviewers challenge changes from independent angles."
disable-model-invocation: true
---

# Interrogate

Spawn one reviewer per configured model to adversarially review code changes. Each model gets the same prompt and rubric. The adversarial signal comes from model diversity, not assigned personas.

The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Determine Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that
- If on a feature branch, run `git diff main...HEAD` (or the appropriate base branch) for the full changeset
- If the user's message references recent work, gather the relevant files

Package the diff (or file contents) plus any surrounding context files the reviewers need to understand the code.

## Step 2, State the Intent

Before spawning reviewers, state the intent explicitly. Derive this from:

- The user's message
- Commit messages
- PR description if one exists
- The code itself

Write one clear paragraph. If you're unsure about the intent, ask the user before proceeding.

## Step 3, Spawn Reviewers

Launch all reviewers in a single message using the `Agent` tool. Use the `interrogate reviewers` line in `p3-models.md`, one reviewer per entry, extending or shrinking the Reviewer A/B/C labels to the configured entry count. If the file or that line is missing, use the line's defaults in [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles), Reviewer A on the first.

For each reviewer:
- `subagent_type`: `general-purpose`
- `model` and `effort`: the configured `interrogate reviewers` entry, or the default with no configured line. For an `inherit` entry, omit `model` so that reviewer runs on the parent model.
- `effort` never below `high`. Pass `high` for an entry that names a lower effort or none, `inherit` included.
- a read-only brief, which the reviewer prompt carries

If the `Agent` tool rejects a configured entry, run that reviewer on a default and say so. Do not block the review on it. An entry that names a T3 target runs that reviewer through `delegate_task` per [the runtime's Subagents](../../skills/poteto-mode/references/runtime.md#subagents). Pass `options` with `effort` on every call and a distinct `clientRequestId` per reviewer and per round, and read each result with `task_status` after the wake.

Record the provider, model, and effort each reviewer actually ran at, not the ones you asked for. A `delegate_task` reviewer's `task_status` names its provider and model, and `t3_thread_configuration` on its `childThreadId` names its effort. An `Agent` reviewer runs at the `model` and `effort` you passed, unless its model does not offer that effort and falls back to its default.

Read `references/reviewer-prompt.md` and fill in the template with:
1. The stated intent
2. The diff or file contents
3. The review rubric from `references/rubric.md`
4. The code-quality lens from `references/code-quality-review.md`

The same filled template goes to all reviewers, so every model applies the code-quality lens.

## Step 4, Synthesize

If no independent reviewer could run, the review gate stays closed. Report `BLOCKED: independent review` and say which reviewers ran.

As results come back, build a unified picture:

1. **Parse all findings** from the reviewers
2. **Identify consensus**. Findings raised by 2+ models independently are highest signal.
3. **Identify lone-model findings**. Still worth reading, but weight accordingly.
4. **Deduplicate**. Different models may describe the same issue differently. Merge these and note which models raised it.
5. **Note disagreements**. If one model flags something and another explicitly says the opposite, that's useful context for the verdict.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator.

Read `references/lead-judgment.md` for the full framework.

Categorize every finding using these buckets:

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. These would block a real PR.
- **Consider**. Legitimate points, but you're not sure they outweigh the cost of addressing them right now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact given the current stage.
- **Dismissed**. Wrong, nitpicky, or missing context. Brief explanation why.

For each finding, include:
- Which model(s) raised it
- The category (act on / consider / noted / dismissed)
- A one-line rationale for the categorization

## Output Format

Present the verdict in this structure:

### Intent
> [The stated intent paragraph from Step 2]

### Reviewers
- Reviewer [label]: [provider, model, and effort it ran at], [N findings] (one bullet per reviewer)

### Act On
[Findings that should be addressed. For each: description, which models raised it, why it matters.]

### Consider
[Findings worth thinking about. For each: description, which models raised it, tradeoff involved.]

### Noted
[Valid but low-priority. Brief list.]

### Dismissed
[Rejected findings with brief rationale.]

### Agreement Map
[Where did models agree, where did they diverge, and what does the pattern of agreement/disagreement tell us? When every reviewer is a Claude model, say that the agreement is same-vendor, per the Model diversity note in [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles).]
