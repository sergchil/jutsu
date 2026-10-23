---
name: interrogate
description: "Use for \"interrogate\", \"adversarial review\", \"multi-model review\", \"challenge this\", \"stress test this code\", \"find blind spots\", or \"tear this apart\". Multiple LLM reviewers challenge changes from independent angles."
disable-model-invocation: true
---

# Interrogate

Spawn one reviewer per configured model to adversarially review code changes. The adversarial signal comes from model diversity, not assigned personas. The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that.
- If on a feature branch, run `git diff main...HEAD` (or the appropriate base branch) for the full changeset.
- If the user's message references recent work, gather the relevant files.

Package the diff or file contents with any surrounding context files the reviewers need to understand the code.

## Step 2, Intent

Before spawning reviewers, state the intent in one clear paragraph from the user's message, commit messages, the PR description if one exists, and the code. If you're unsure about the intent, ask the user before proceeding.

## Step 3, Spawn Reviewers

Launch all reviewers in a single message with the `Agent` tool, one per entry on the `interrogate reviewers` line in `jutsu-models.md`, labeled Reviewer A, B, and so on to match the entry count. If the file or that line is missing, use the line's defaults in [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles), Reviewer A on the first.

Each reviewer gets `subagent_type: general-purpose`, a read-only brief, which the reviewer prompt carries, and `model` and `effort` set from its configured entry, or its default when there is no configured line. Omit `model` for an `inherit` entry, so that reviewer runs on the parent model. `effort` is never below `high`. Pass `high` for an entry that names a lower effort or none, `inherit` included.

An entry that names a T3 target runs through `delegate_task` per [the runtime's Subagents](../../skills/poteto-mode/references/runtime.md#subagents). If a T3 entry cannot run (outside T3, or its provider is off in T3's settings), run that reviewer on its line's Claude default and say the panel lost its cross-family seat.

Record the provider, model, and effort each reviewer actually ran at, not the ones you asked for. A `delegate_task` reviewer's `task_status` names its provider and model, and `t3_thread_configuration` on its `childThreadId` names its effort. An `Agent` reviewer runs at the `model` and `effort` you passed, unless its model does not offer that effort and falls back to its default.

Read `references/reviewer-prompt.md` and fill in the same template for every reviewer with the stated intent, the diff or file contents, the rubric from `references/rubric.md`, and the code-quality lens from `references/code-quality-review.md`.

## Step 4, Synthesize

If no independent reviewer could run, the review gate stays closed. Report `BLOCKED: independent review` and say which reviewers ran.

As results come back, build a unified picture. Parse every reviewer's findings. Merge findings that describe the same issue differently, and note which models raised each one. Findings two or more models raised independently are the highest signal. Read a lone model's finding, but weight it accordingly. Note disagreements. If one model flags something and another explicitly says the opposite, that is context for the verdict.

With one reviewer, which is jutsu's default, there is nothing to merge across models. Take its findings as they are, skip the agreement analysis and the Model Diversity section of the report, and go to lead judgment. Add a second entry to the `interrogate reviewers` line only for big or risky changes.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator. Read `references/lead-judgment.md` for the full framework. Put every finding in one of four buckets, with the model(s) that raised it and a one-line rationale.

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. They would block a real PR.
- **Consider**. Legitimate, but you're not sure they outweigh the cost of addressing them now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact at this stage.
- **Dismissed**. Wrong, nitpicky, or missing context, with a brief reason.

## Output Format

### Intent
> [The stated intent paragraph from Step 2]

### Reviewers
- Reviewer [label]: [provider, model, and effort it ran at], [N findings] (one bullet per reviewer)

### Act On
[Each: description, which models raised it, why it matters.]

### Consider
[Each: description, which models raised it, the tradeoff.]

### Noted
[Brief list.]

### Dismissed
[Each with a brief rationale.]

### Agreement Map
[Where models agreed and diverged, and what that pattern tells us. When every reviewer is a Claude model, say that the agreement is same-vendor, per the Model diversity note in [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles).]
