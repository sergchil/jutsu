# Prompts worth copying

Swap in the real paths, skills, and done checks. Informal wording works.

## Understand

- `/jutsu read <thread>. restate the underlying issue in your own words, in plain english.`
- `/jutsu:in-your-own-words <long or messy ask>`
- `/jutsu:sharpen <the prompt you're about to send>`
- `/jutsu investigate why <symptom>. give me what we know, what data you used, and your best hypotheses. don't change any code yet.`
- `use /jutsu:how to understand <subsystem>. then use /jutsu:why to find out why it broke recently.`
- `/jutsu:recall my work on <topic> from last week, then read <issue>.`
- `/jutsu:teach me why you implemented it this way and not <other way>. what did you trade off?`
- `/jutsu take over this branch. read the decision log, find what's done, and continue. don't redo finished work.`

## Build

- Bug: `/jutsu <symptom>. repro first, then fix and verify.`
- Bug in an app: `/jutsu repro this with /verify. if it repros on main, fix it and show me a video as proof.`
- Bug with a cheap test: `/jutsu repro <bug> first. if there's a cheap test path, /jutsu:tdd it. then fix and rerun.`
- Feature: `/jutsu add <behavior>. <current output> stays byte-identical. verify both.`
- Refactor: `/jutsu move <code> into one module, zero behavior change. record the current output first and prove it's unchanged after.`
- Perf: `/jutsu <operation> takes <time> on <fixture>. trace it, fix the measured cause, show me before and after.`

## Design and plan

- `/jutsu prototype a few options for <feature>. take screenshots or videos for me to compare.`
- `/jutsu we need <feature>. /jutsu:architect it first, and answer open questions with prototypes. let me review before proceeding.`
- `/jutsu write a tutorial for how i would use <new package> first. then /jutsu:teach me why it beats the current one.`
- `ask /jutsu:arena for a second opinion on this thread and our approach.`
- `/jutsu turn this design into a plan. small verifiable PRs, each with its own verification steps.`
- `/jutsu plan the migration of <library> to <target>. small verifiable PRs. the result must match the original exactly, bugs included.`

## Review and ship

- `/jutsu:interrogate the whole branch, but skeptically. don't change anything yet. no nitpicks unless it's a real bug or regression.` Read the dismissals too.
- `/jutsu:create-formal-verification-skill prove <property> holds in <module>, even when <steps> interleave or retry.` After merges or refactors in that code: `/jutsu:maintain-formal-verification-skill`.
- `/jutsu:swarm check every package under <dir> against its check script. one worker per package. one report.`
- `/jutsu open the pr. small ordered commits, evidence in the description.`
- `/jutsu babysit this pr. get it green.` For status only: `/jutsu check on pr <number>. anything outstanding?`
- `/jutsu land the stack.`

## Away and back

- `/jutsu im going to bed. <goal> in a fresh worktree off <base>. done means <checks>. keep a decision log. don't ask me before committing. run until done. if you're truly stuck after a few hours, stop and write up why.`
- `/jutsu:show-me-your-work catch me up on what you did last night.` Read its Attention section first.
- `/jutsu:ketchup` catches you up on this chat since your last message and lists every call that waits on you.
- `/jutsu full autopilot on this queue. each item is independent.`
- `/jutsu autopilot these changes but stack them, don't ship. i'll land the stack.`
- `/jutsu:reflect capture what we learned so the next run doesn't repeat it.` Approve only edits that change a future decision.
- `/jutsu:bro` restates the last reply in plain words.
