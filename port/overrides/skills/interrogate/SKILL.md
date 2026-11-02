---
name: interrogate
description: "Use for \"interrogate\", \"adversarial review\", \"multi-model review\", \"challenge this\", \"stress test this code\", \"find blind spots\", or \"tear this apart\". Adversaries try to break a change or design, and only findings proven by a run survive."
disable-model-invocation: true
---

# Interrogate

Adversaries try to break a change or a design. A finding survives only when a run proves it. Report the findings. Do not apply fixes.

## Frame

The scope is what the user names. Otherwise it is the branch diff from its merge base with the base branch, through the working tree. State the intent with the **in-your-own-words** skill, from the user's message, the commits, and the PR description. Ask the user when the intent is unclear.

## Fan out

Run Phase A steps 3 and 4 and Phase B of the **arena** skill, with four changes. Read the `interrogate reviewers` line in place of `arena runners`. Copy the scope's uncommitted changes into each worktree. Spawn each adversary as `generalPurpose`. In place of the arena task and rationale, give each adversary the scope, the intent, and this brief:

> Break this change. Prove each finding with a run against the real code, such as a failing test, a repro script, or command output that shows the wrong behavior. For a design or plan, run a prototype or probe the current tree. Keep repros in your own worktree. Report each finding with a title, the exact command, the output it printed, and the output the intent requires. Leave out anything you did not run. That covers style, naming, structure, and risks that need a future change to matter. No findings is a valid result.

## Verify

Verify each finding per arena Phase F by rerunning its command. Keep a finding when the output shows the failure and the failure breaks the intent. Drop the rest. Merge findings that share a root cause.

<<<<<<< jutsu override
Launch all reviewers in a single message with the `Agent` tool, one per entry on the `interrogate reviewers` line in `jutsu-models.md`, labeled Reviewer A, B, and so on to match the entry count. If the file or that line is missing, use the line's defaults in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles), Reviewer A on the first.

Each reviewer gets `subagent_type: general-purpose`, a read-only brief, which the reviewer prompt carries, and `model` and `effort` set from its configured entry, or its default when there is no configured line. Omit `model` for an `inherit` entry, so that reviewer runs on the parent model. `effort` is never below `high`. Pass `high` for an entry that names a lower effort or none, `inherit` included.

An entry that names a T3 target runs through `delegate_task` per [the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents). If a T3 entry cannot run (outside T3, or its provider is off in T3's settings), run that reviewer on its line's Claude default and say the panel lost its cross-family seat.

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
[Where models agreed and diverged, and what that pattern tells us. When every reviewer is a Claude model, say that the agreement is same-vendor, per the Model diversity note in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles).]
=======
Skip arena Phases C, D, and E. Adversaries find different failures, so the verdict keeps every verified finding, not one adversary's list.

## Output

- **Intent**: the restatement.
- **Findings**: for each verified finding, the command, its output, how it breaks the intent, and the adversaries that found it. Say "no verified findings" when none survive.
- **Dropped**: for each adversary, the count of dropped findings and why.
>>>>>>> upstream ae5650febf43
