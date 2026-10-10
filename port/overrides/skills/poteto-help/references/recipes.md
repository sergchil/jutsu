# Prompts worth copying

Swap in the real paths, skills, and done checks. Informal wording works.

## Understand

- `/p3 read <thread>. restate the underlying issue in your own words, in plain english.`
- `/p3 investigate why <symptom>. give me what we know, what data you used, and your best hypotheses. don't change any code yet.`
- `use /p3:how to understand <subsystem>. then use /p3:why to find out why it broke recently.`
- `/p3:recall my work on <topic> from last week, then read <issue>.`
- `/p3:teach me why you implemented it this way and not <other way>. what did you trade off?`
- `/p3 take over this branch. read the decision log, find what's done, and continue. don't redo finished work.`

## Build

- Bug: `/p3 <symptom>. repro first, then fix and verify.`
- Bug in an app: `/p3 repro this with /verify-<app>. if it repros on main, fix it and show me a video as proof.`
- Bug with a cheap test: `/p3 repro <bug> first. if there's a cheap test path, /p3:tdd it. then fix and rerun.`
- Feature: `/p3 add <behavior>. <current output> stays byte-identical. verify both.`
- Refactor: `/p3 move <code> into one module, zero behavior change. record the current output first and prove it's unchanged after.`
- Perf: `/p3 <operation> takes <time> on <fixture>. trace it, fix the measured cause, show me before and after.`

## Design and plan

- `/p3 prototype a few options for <feature>. take screenshots or videos for me to compare.`
- `/p3 we need <feature>. /p3:architect it first, and answer open questions with prototypes. let me review before proceeding.`
- `/p3 write a tutorial for how i would use <new package> first. then /p3:teach me why it beats the current one.`
- `ask /p3:arena for a second opinion on this thread and our approach.`
- `/p3 turn this design into a plan. small verifiable PRs, each with its own verification steps.`
- `/p3 plan the migration of <library> to <target>. small verifiable PRs. the result must match the original exactly, bugs included.`

## Review and ship

- `/p3:interrogate the whole branch, but skeptically. don't change anything yet. no nitpicks unless it's a real bug or regression.` Read the dismissals too.
- `/p3:swarm check every package under <dir> against its check script. one worker per package. one report.`
- `/p3 open the pr. small ordered commits, evidence in the description.`
- `/p3 babysit this pr. get it green.` For status only: `/p3 check on pr <number>. anything outstanding?`
- `/p3 land the stack.`

## Away and back

- `/p3 im going to bed. <goal> in a fresh worktree off <base>. done means <checks>. keep a decision log. don't ask me before committing. run until done. if you're truly stuck after a few hours, stop and write up why.`
- `/p3:show-me-your-work catch me up on what you did last night.` Read its Attention section first.
- `/p3 full autopilot on this queue. each item is independent.`
- `/p3 autopilot these changes but stack them, don't ship. i'll land the stack.`
- `/p3:reflect capture what we learned so the next run doesn't repeat it.` Approve only edits that change a future decision.
- `/p3:bro` restates the last reply in plain words.
