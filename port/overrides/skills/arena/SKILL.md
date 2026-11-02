---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
disable-model-invocation: true
---

# Arena

Open a todolist with one entry per phase (Frame, Fan out, Cross-judge, Pick, Graft, Verify) before launching anything.

## Phase A: Frame

Every candidate gets the same prompt, so the prompt is the contract.

1. State the artifact each candidate is producing.
2. Derive the rubric, 3-6 concrete gradeable criteria for what success looks like on *this* task. It is the picker's tool in Phase D. Candidates only see the task.
<<<<<<< jutsu override
3. Pick the runners. Use the `arena runners` line in `jutsu-models.md`, setting each seat's `model` and `effort` from its entry. If the file or that line is missing, run one each on the line's defaults in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). An `inherit` entry in this line or the cross-judge line means the parent model, so omit `model` and `effort` for it. An entry that names a T3 target runs through `delegate_task` per [the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents). If a T3 entry cannot run (outside T3, or its provider is off in T3's settings), run that seat on its line's Claude default and say the panel lost its cross-family seat. Spawn more runners when the arena covers multiple design directions. Use the same model N times when the work is generation-bound rather than judgment-sensitive.
4. Give each candidate its own output location (a git worktree from your HEAD where possible, created before you spawn per [the runtime's Isolation]({{plugin}}/skills/poteto-mode/references/runtime.md#isolation), otherwise `/tmp/arena-<slug>/candidate-<n>/`), per the **separate-before-serializing-shared-state** principle (`{{plugin}}/principles/principle-separate-before-serializing-shared-state.md`). Do not use `Agent` `isolation: "worktree"`. It branches from the remote default branch. A seat that runs through `delegate_task` gets `isolation: "worktree"` instead, which starts from your local commit without uncommitted edits, so commit what the seats need first.
=======
3. Pick the runners. Use the `arena runners` line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that line is missing, default to one each on `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. An `auto` or `inherit-parent` entry in this line means the parent model, so omit `model` for it. If the Task tool rejects a configured entry, run that seat on its family's default and say so. Families go by prefix: `claude-*`, and `grok-*` with `cursor-grok-*` and `composer-*`. A refused `composer-*` entry runs on `grok-4.7-xhigh-fast`. If the family has no default, or the Task tool rejects that default, use the closest valid slug of the same family from its error message, or drop the seat and say so when there is none. If dropped seats leave fewer than two runners, add runners until there are two, or one when the line has one entry. Run each added runner on a remaining runner's model, or omit `model` so it runs on the parent model when none remain, and say so. Spawn more runners when the arena covers multiple design directions. Use the same model N times when the work is generation-bound rather than judgment-sensitive. Pick each subagent's reasoning level and fast or standard speed for the job, per the Subagents section of the **poteto-mode** skill.
4. Give each candidate its own output location (a git worktree where possible, otherwise `/tmp/arena-<slug>/candidate-<n>/`), per the **separate-before-serializing-shared-state** principle skill.
>>>>>>> upstream ae5650febf43

## Phase B: Fan out

Spawn all N subagents in one message with `run_in_background: true` and each seat's `model` and `effort`, each with the task, the path to the shared grounding, its own output path, and instructions to produce the artifact and a short rationale naming the alternatives it considered and what it rejected. Never put `$(...)` or shell-expanding backticks in a brief a candidate pastes into a command.

If a candidate produces no output, proceed with N-1 and note the dropout.

## Phase C: Cross-judge

<<<<<<< jutsu override
With one runner there is nothing to compare. Skip Phase C and Phase E, read the one candidate yourself against the rubric in Phase D, and verify it in Phase F. This is the default for `architect`, which runs one runner.

After all Phase B candidates complete, choose one model from the `arena cross-judge pool` line in `jutsu-models.md`. If the file or that line is missing, choose from the line's defaults in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). Prefer a non-Claude T3 target when the pool has one, else a different model family from the parent's. When the judge and the parent are both Claude models, as with the defaults, record in the synthesis note that they share one vendor, per the Model diversity note in the runtime's Roles. Spawn one judge subagent on that model with a read-only brief, at `high` effort or above. It sees the rubric and the candidates by path label, scores each criterion, and recommends a base with rationale. It runs in parallel with your reading in Phase D. Don't spawn it while candidates are still writing.
=======
After all Phase B candidates complete, choose one model from the `arena cross-judge pool` line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that line is missing, choose from `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. Spawn one readonly judge subagent. The judge is never from the parent's family, as Phase A step 3 defines families. Try only the entries from another family, in pool order. An `auto` or `inherit-parent` entry is the parent model, so it never judges. With the default pool, a Claude parent gets `grok-4.7-xhigh-fast`. A parent from any other family gets `claude-opus-5-5-xhigh` first. If the Task tool rejects an entry, use a valid slug of the same model at the closest level or speed from the error message, or move to the next entry when there is none. If no entry from another family runs, try the default pool's entries from another family the same way. If none of those runs, skip the judge, pick the base alone in Phase D, and say so. If you do not know the parent's model, try the pool's real slugs in pool order and say that the family check did not run. The judge sees the rubric and the candidates by path label, scores each criterion, and recommends a base with rationale. It runs in parallel with your reading in Phase D. Don't spawn it while candidates are still writing.
>>>>>>> upstream ae5650febf43

## Phase D: Pick a base

Read every candidate end to end before picking. Score each against the rubric criterion by criterion, not on holistic feel, and compare with the cross-judge when Phase C ran one. Agreement on the base confirms the pick. Disagreement means one of you is biased or the rubric was ambiguous. Read both rationales before deciding.

Pick the base a future maintainer can extend most easily without breaking invariants. When two feel tied, prefer the cleaner boundary or smaller API, per the Laziness Protocol (`{{plugin}}/principles/principle-laziness-protocol.md`).

## Phase E: Graft

Walk each losing candidate once more for what is worth porting into the base, usually one or two things per candidate, not most of it. Fold each graft in by hand, per the **redesign-from-first-principles** principle (`{{plugin}}/principles/principle-redesign-from-first-principles.md`), so the result stays coherent under one mental model. Don't paste mechanically.

If the candidates converge on one shape, that is strong agreement. Note it, and whether the runners shared one vendor, and ship the consensus shape. No graft is needed. If they wildly diverge, Phase A was under-specified. Reframe and re-run rather than averaging the divergence.

## Phase F: Verify

Verify the synthesized artifact like any other output, per the **prove-it-works** principle (`{{plugin}}/principles/principle-prove-it-works.md`). If verification finds a problem the arena missed, either Phase A was wrong (re-frame and re-run) or a candidate caught it and you missed the graft (go back to Phase E). Don't paper over it.

## Outputs

<<<<<<< jutsu override
One synthesized artifact, with a short synthesis note alongside naming the base and why, the cross-judge's verdict, each graft with its source candidate, what was rejected and why, any convergence or dropouts, the model and effort each seat and the judge actually ran at, and the verification result.
=======
One synthesized artifact, with a short synthesis note alongside naming the base and why, the cross-judge's verdict or that Phase C skipped the judge, each graft with its source candidate, what was rejected and why, any convergence or dropouts, and the verification result.
>>>>>>> upstream ae5650febf43
