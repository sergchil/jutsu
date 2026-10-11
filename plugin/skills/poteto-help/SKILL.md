---
name: poteto-help
description: Guides users through p3 setup, /p3, and picking the skill, playbook, or principle for a task. Type /p3:poteto-help with a question.
disable-model-invocation: true
---

# Poteto help

Answer the user's question about p3, hand them a prompt they can send, and link the file the answer came from. For a help question, don't start the work. The user asked how, and a p3 run spends real tokens, so let them send the prompt.

A message that asks for work, such as "use p3 to fix this bug", is not a help question. Read [`poteto-mode`](../../skills/poteto-mode/SKILL.md), do the work under it, and mention once that `/p3` keeps it on for the rest of the session.

This file maps questions to the skills and pages that hold the answers. Those files own the details. Read the file you route to before you quote it, and trust it when it disagrees with this map. The links here point into the installed plugin, which the user may not be able to open, so give the user the file's public copy: `https://github.com/sergchil/p3-stack/blob/main/plugin/` followed by its path. The guide pages linked below are upstream pstack's guide, written for Cursor. Say so when you link one, and read its Cursor terms through [the runtime's Vocabulary](../../skills/poteto-mode/references/runtime.md#vocabulary).

## Find out what they need

Infer the need from the message and the conversation. A named situation, such as "which skill reviews a PR?", goes straight to its section. If the need is still unclear, ask one `AskUserQuestion` with these options, then answer only the section they pick. Give each option a one-line description, because a blank one can stall a T3 thread. The tool takes at most four options and adds an Other field, so offer the first four and say in the question that Other covers the fifth.

- Get set up
- Start a task with `/p3`
- Pick a skill for a situation
- Fix a run that went wrong
- Make p3 my own

Check the state that changes the answer, and mention it only when it does:

- No `.claude/p3-models.md` in the repo and no `p3-models.md` in the Claude config dir (`$CLAUDE_CONFIG_DIR`, else `~/.claude`) means `/p3:setup-pstack` hasn't run for this user, so every role uses its default from [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles).
- No `verify-*` skill in `.claude/skills/` or other app harness in the project means agents have no scripted way to drive the app. Mention `/p3:create-verification-skill` when the question is about proving a change works.

When the models file is missing and it matters, ask whether the user wants to pick a model for each role and a reasoning budget now. It matters when the user is new, the question is about setup or cost, or the answer depends on which models run. Ask at most once per chat. If the need is also unclear, ask both questions in the same `AskUserQuestion` call. Offer two choices:

- Now: give them `/p3:setup-pstack` to type, and answer their question too.
- Later: answer their question, and add one line saying every role keeps its default model until they run `/p3:setup-pstack`.

## Get set up

1. Install p3 per the [p3-stack README](https://github.com/sergchil/p3-stack#readme). It is a Claude Code plugin, and T3 Code runs the user's own `claude`, so one install serves both.
2. Run [`/p3:setup-pstack`](../../skills/setup-pstack/SKILL.md). It asks for a reasoning budget, maps a Claude model and effort to each role, and writes `p3-models.md`. In T3 it reads the live model catalog and can add a second Claude account as a target. The file applies to new sessions.
3. Start a real task with `/p3`, a goal, and a check that can pass or fail.

Installing changes nothing until the user types `/p3` or another p3 skill. No p3 skill loads from the user's words alone, because every one is user-invoked. The README has the details, including how to uninstall. Offer to word their first prompt with them, per [`references/prompting.md`](references/prompting.md).

If cost is the worry, say where the tokens go and how to spend fewer. p3 spends extra tokens on subagents and review panels. Rerun `/p3:setup-pstack` and pick a smaller budget or cheaper models such as `sonnet` or `haiku`. A role set to `inherit` runs on the session's model and effort, which saves tokens when the session runs on a cheaper model or a lower effort. A shorter panel list runs fewer subagents, one for each entry. Save `/p3` for work that needs rigor.

p3 is pstack ported to Claude Code, built to run inside T3 Code. Plain Claude Code works too. Each step that needs a T3 tool names its fallback in [the runtime](../../skills/poteto-mode/references/runtime.md#host). Other tools that read the Agent Skills format can read the files, but the workflow skills spawn Claude subagents with the `Agent` tool and the mode hook is a Claude Code plugin hook, so those parts need Claude Code.

In T3, p3 uses T3's own tools where Claude Code has none. `watch_pull_request` and `schedule_task` wake it on PR events and timed ticks. `t3_thread_launch` gives a long-lived PR owner its own thread and worktree. `delegate_task` runs a role on another Claude account. `preview_*` drives web UIs, `device_*` drives simulators, `html_render` publishes visual reports, and `t3_thread_list`, `t3_thread_read`, and `t3_thread_search` read past threads. [The runtime](../../skills/poteto-mode/references/runtime.md) maps each one and its fallback.

## Start a task with `/p3`

`/p3` matches the task to a playbook, copies the playbook's steps into the todo list, and runs the other skills as the steps need them. A step it skips stays in the list as `skip: <reason>`. A good prompt states the goal and how to tell it's done. It doesn't list skills, because a hand-written sequence tends to drop or reorder steps the playbook would keep. Read [`references/prompting.md`](references/prompting.md) before you help word one. [Guide page 2](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/02-poteto-mode.md) has examples.

How `/p3` stays on:

- `/p3 <task>` at the start of a message, or `$p3` from T3's skill picker, turns poteto mode on for the rest of the session. `/p3:poteto-mode` does the same.
- While it is on, a plugin hook adds a one-line reminder to every turn. The reminder says to apply the mode to a new task that matches a playbook or needs rigor, and to skip it on a casual turn or when the user opts out. So the mode stays on without taking over casual turns. After a compaction or a resume, the hook also tells the model to reread the router.
- `/p3 off` turns it off. A new session starts with it off.

Link [Claude Code's skills docs](https://code.claude.com/docs/en/skills) when this comes up. Mid-chat, "new task" makes the mode match a fresh playbook. `/p3` already uses `p3:poteto-agent` for the subagents its playbook steps spawn. To get the same style from a subagent of your own, spawn it with `subagent_type: "p3:poteto-agent"`.

## Pick a skill

The default answer is `/p3`, which runs most of the others when its steps need them. Name a skill directly when the user wants more or less of something than the playbook gives. Read the skill before you recommend it, and give one example prompt.

| The user wants to | Skill |
|---|---|
| Do any non-trivial task with rigor | [`/p3`](../../skills/poteto-mode/SKILL.md) |
| Know how code works now, or where new code should live | [`/p3:how`](../../skills/how/SKILL.md) |
| Know why code is shaped this way, or where a number came from | [`/p3:why`](../../skills/why/SKILL.md) |
| Understand a change or subsystem, explained plainly | [`/p3:teach`](../../skills/teach/SKILL.md) |
| Catch up on their own recent work on a topic | [`/p3:recall`](../../skills/recall/SKILL.md) |
| Catch up on everything in this chat since their last message, with enough context to decide each action item | [`/p3:ketchup`](../../skills/ketchup/SKILL.md) |
| Know what a small diff could break outside itself | [`/p3:blast-radius`](../../skills/blast-radius/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [`/p3:architect`](../../skills/architect/SKILL.md) |
| Get several attempts at one brief, merged into the best one | [`/p3:arena`](../../skills/arena/SKILL.md) |
| Run parallel checks over slices, or race workers, each in its own worktree | [`/p3:swarm`](../../skills/swarm/SKILL.md) |
| Have different models review a diff and try to break it | [`/p3:interrogate`](../../skills/interrogate/SKILL.md) |
| Fix a bug test-first when a cheap local test exists | [`/p3:tdd`](../../skills/tdd/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [`/p3:typescript-best-practices`](../../skills/typescript-best-practices/SKILL.md) |
| Strip comments before review, using a reviewer that didn't write them | [`/p3:no-comments`](../../skills/no-comments/SKILL.md) |
| Clean AI tells out of prose | [`/p3:unslop`](../../skills/unslop/SKILL.md) |
| Write docs, an RFC, a README, a PR description, or a commit message to a standard | [`/p3:technical-writing`](../../skills/technical-writing/SKILL.md) |
| Hear the last reply again in plain words | [`/p3:bro`](../../skills/bro/SKILL.md) |
| Give agents a scripted way to drive the app and prove behavior | [`/p3:create-verification-skill`](../../skills/create-verification-skill/SKILL.md) |
| Bring a verification skill and its feature map back in line with the app | [`/p3:maintain-verification-skill`](../../skills/maintain-verification-skill/SKILL.md) |
| Vet a performance number before reporting or acting on it | [`/p3:benchmark-checklist`](../../skills/benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [`/p3:figure-it-out`](../../skills/figure-it-out/SKILL.md) |
| Keep a decision log during a run, and review it afterward | [`/p3:show-me-your-work`](../../skills/show-me-your-work/SKILL.md) |
| Pick a model for each role and a reasoning budget | [`/p3:setup-pstack`](../../skills/setup-pstack/SKILL.md) |
| Turn their own working habits into a personal mode skill | [`/p3:automate-me`](../../skills/automate-me/SKILL.md) |
| Turn what a finished task taught into skill edits | [`/p3:reflect`](../../skills/reflect/SKILL.md) |
| Stop agents from repeating the same mistakes in this repo | [`/p3:correct`](../../skills/correct/SKILL.md) |
| Find their way around p3 | `/p3:poteto-help` |

If a skill directory next to this one is missing from the table, read its frontmatter and route by its description. Principles live in `../../principles/` and are covered under principles below.

Close calls:

- `/p3:how` explains what the code does. `/p3:why` explains the reasons. `/p3:teach` runs one or both and explains the result plainly.
- `/p3:arena` gives every worker the same brief and merges the best parts. `/p3:swarm` splits work into slices or a race and returns one report.
- `/p3:architect` implements right after it settles the design. Add "with checkpoint" to review the design before it writes code.
- `/p3:interrogate` reviews the diff. `/p3:blast-radius` looks for breakage outside the diff and proves the one fact that makes the change safe.
- `/p3:recall` rebuilds context across recent chats. `/p3:ketchup` covers only this chat since the user's last message. Resuming one specific chat or branch is the Session pickup playbook.
- `/p3:figure-it-out` designs one rigorous run. The Orchestrate playbook runs a program that spans days and many PRs. The Autonomous run playbook drives one task to a finish condition.

Not in p3:

- Cursor's `/deslop` and its UI and CLI drivers. p3 deslops a diff before commit per [the runtime's Missing companions](../../skills/poteto-mode/references/runtime.md#missing-companions), and drives the real app per [its Proof surfaces](../../skills/poteto-mode/references/runtime.md#proof-surfaces): T3's `preview_*` tools for web UIs, `device_*` for simulators, and the terminal for CLIs.
- Cursor's `/create-skill` and its wake loop. Writing a skill follows the [Authoring a skill playbook](../../skills/poteto-mode/playbooks/authoring-a-skill.md), and Claude Code's `skill-creator` plugin helps with evals when installed. Waking on a tick or a PR event follows [the runtime's Waking](../../skills/poteto-mode/references/runtime.md#waking).
- `/make-bot-ui`, upstream's page whose buttons wake a Grok Bot over a webhook. p3 does not ship it.
- p3 has no `/orchestrate` skill. Orchestrate is a `/p3` playbook. If the slash menu shows `/orchestrate`, another plugin provides it.

## Playbooks and principles

Playbooks are step lists inside `/p3`, not skills, so they have no slash command. Inside `/p3`, describing the task picks one, and these phrases name one directly:

- "babysit this pr" or "check on pr 123" runs Babysit. It drives the PR to merge-ready and stops there. It doesn't merge unless the user asks to merge, land, or ship.
- "land the stack" runs Shipping.
- "take over this branch" runs Session pickup.
- "pause safely" runs Pause safely.
- "full autopilot on this queue" runs Autopilot-full. "stack them, don't ship" runs Autopilot-stack.
- "run the eval playbook" runs Eval.

Without `/p3`, a phrase such as "babysit this pr" can start Claude Code's `/autofix-pr` or T3's own PR watching for the same job instead. With `/p3` on, the Babysit playbook wins. The Playbooks section of [`poteto-mode`](../../skills/poteto-mode/SKILL.md) lists every playbook and when it applies. [Guide page 6](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/06-verify-and-ship.md) covers opening, babysitting, and landing a PR.

p3 has no planning skill. Plan mode in T3 or Claude Code works alongside it. For work that spans phases or stacked PRs, asking `/p3` for a plan runs the [Multi-phase plan playbook](../../skills/poteto-mode/playbooks/multi-phase-plan.md), which writes the plan and doesn't implement it. For a design question, the Prototype playbook or `/p3:architect` settles it in code first.

Principles are one-rule files in `../../principles/` that `/p3` reads and cites in its replies. The user rarely asks for one. They steer with the names instead, as in "apply prove it works. show me the real output." A principle has no slash command. Naming it, as in "read the prove-it-works principle", loads it on demand from [`principle-prove-it-works.md`](../../principles/principle-prove-it-works.md) and its siblings. [Guide page 8](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/08-principles.md) lists them.

## Fix a run that went wrong

| Symptom | Fix |
|---|---|
| The mode stopped applying after a few turns | It is a new session, or `/p3 off` ran, or the task was started without `/p3` at the start of a message. Start the task with `/p3`. If the turn reminder never appears, check that p3 is enabled with `claude plugin list`. |
| Every turn shows two routers or two reminders | Another pstack plugin is enabled next to p3, such as `pstack@pstack-claude`. Disable it with `claude plugin disable pstack@pstack-claude`, once in each Claude config dir that T3 or the user runs. |
| A question got treated as the next step of the last task | Say "new task", or say the turn doesn't need the mode. |
| A new model choice had no effect | `p3-models.md` applies to new sessions. Start one. A repo `.claude/p3-models.md` also wins over the one in the Claude config dir. |
| Runs cost more than expected | See the cost paragraph under Get set up. |
| A skill didn't load on its own | Every p3 skill is user-invoked. It loads when the user types it, or when `/p3` reads its file, and `/p3` doesn't run every skill. |
| A T3 tool failed as unknown, or no PR watch or delegation ran | T3 stable ships only the preview, device, and PR link tools. The orchestration tools need a T3 nightly. p3 takes the fallback in [the runtime's Host](../../skills/poteto-mode/references/runtime.md#host) and says so. |
| A `device_*` call was refused | Device access is off by default. Turn on agent device access in T3's settings. |
| "babysit this pr" ran another PR watcher | Claude Code's `/autofix-pr` or T3's own PR watching matched the words. Start the request with `/p3`. |
| Parallel agents overwrote each other | Give each writer its own worktree from your HEAD, per [the runtime's Isolation](../../skills/poteto-mode/references/runtime.md#isolation). |
| An overnight run moved but finished nothing | The run needs a check that can pass or fail, not a duration. See [guide page 7](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/07-overnight.md). |
| The reply claims success from a green build | Ask for the real command, flow, stored value, or profile. That's the prove-it-works principle. |

For a run that drifts, [`references/prompting.md`](references/prompting.md) has one-line steers. [Guide page 10](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/10-recipes-and-pitfalls.md) has more pitfalls and the recipes worth copying.

## Make p3 my own

- [`/p3:automate-me`](../../skills/automate-me/SKILL.md) drafts a personal mode skill from the user's own history, to use alongside `/p3`.
- [`/p3:reflect`](../../skills/reflect/SKILL.md) after a session turns its lessons into skill edits the user approves.
- `/p3 write a skill for <workflow>` runs the authoring playbook. The eval playbook tests a skill change blind.
- Fix a misbehaving skill in its own PR, not inside the feature work where it went wrong.

[Guide page 9](https://github.com/cursor/plugins/blob/main/pstack/docs/guide/09-make-it-yours.md) covers each of these.

## Reply

Lead with the answer. Give at most one example prompt in a code block, adapted from [`references/recipes.md`](references/recipes.md) when one fits, then the link to that file. Keep it short unless the user asked for the whole map.
