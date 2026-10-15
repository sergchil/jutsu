### Eval

**You own the experiment design. Plan, blind, run, synthesize.**

**Non-negotiables for blinding:**

- No `eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`, `benchmark`, `candidate`, or `arena` in any directory, file, or prompt the candidate sees.
- The candidate prompt looks like an organic user request. State the goal, not the meta.
- No chain-eliciting cues. Don't ask the candidate to list which skills, principles, or files they applied. Ask for design notes generally and grade chain-following from code shape, not self-report.
- Sanitize directory and slug names. Use project-shaped names a user might pick.
- Don't tell the candidate other candidates exist.
- The judge can know it's judging but sees outputs by sanitized label only, never by model name.
- Comparing two variants: one judge scores both sets in a single pass on one scale, blind to which set each came from.

**Steps:**

1. **Frame.** State what variant is under test and what behavior counts as success. Write the rubric (3-6 concrete criteria) for the judge only. Hold it back from candidates.
2. **Set up sanitized environments.** Per-candidate working dir with the variant in place. Plant any context an organic task would have: a project skeleton, the skills the candidate would naturally read.
3. **Author one organic prompt.** What a user would type. No leakage of what's being measured.
4. **Spawn N parallel candidates** on different models per the **arena** skill's Phase B (`../../../skills/arena/SKILL.md`). Each works in its own sanitized dir. Same prompt to each. When the variant is a skill, the router, a hook, or a plugin description, run each candidate as its own session from its sanitized dir, as `claude -p --plugin-dir <variant>` with the prompt, because a native `Agent` child loads the installed jutsu and tests the wrong variant. Native `Agent` candidates fit only a prompt-only variant. Pick each subagent's `effort` for the job, per the Subagents section.
5. **Spawn one blinded judge** on a different model family per the **arena** skill's Phase C. Judge sees outputs by sanitized label and the rubric, never a model name.
6. **Verify the chain from transcripts, not self-report.** Read each candidate's own transcript per [the runtime's History](../references/runtime.md#history). An `Agent` candidate's sits beside its parent session's as `<session>/subagents/agent-<id>.jsonl`. A `claude -p` candidate's sits under its sanitized dir's own project directory, so read it by that exact path. A `delegate_task` candidate's T3 thread reads with `t3_thread_read` and `view: "activity"`. A `claude -p` candidate that read the installed jutsu instead of the variant is void. Look at which files each candidate actually opened. Grade chain-following from the files it really read plus the shape of the code, never from the candidate's own claims.
7. **Read every candidate output yourself** end to end. Compare to the judge's verdict. Disagreement means a model is biased or the rubric is ambiguous. Synthesize.

**Reply:** variant under test, rubric, per-candidate notes, judge's verdict, your synthesis, and a recommendation for whether to promote the variant.
