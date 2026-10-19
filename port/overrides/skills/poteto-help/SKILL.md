---
name: poteto-help
description: Guides users through jutsu setup, /jutsu, and picking the skill, playbook, or principle for a task. Type /jutsu:poteto-help with a question.
disable-model-invocation: true
---

# Poteto help

Answer the user's question about jutsu, hand them a prompt they can send, and link the file the answer came from. For a help question, don't start the work. The user asked how, and a jutsu run spends real tokens, so let them send the prompt.

A message that asks for work, such as "use jutsu to fix this bug", is not a help question. Read [`poteto-mode`]({{plugin}}/skills/poteto-mode/SKILL.md), do the work under it, and mention once that `/jutsu` keeps it on for the rest of the session.

This file maps questions to the skills and pages that hold the answers. Those files own the details. Read the file you route to before you quote it, and trust it when it disagrees with this map. The links here point into the installed plugin, which the user may not be able to open, so give the user the file's public copy: `https://github.com/sergchil/jutsu/blob/main/plugin/` followed by its path.

## Find out what they need

Infer the need from the message and the conversation. A named situation, such as "which skill reviews a PR?", goes straight to its section. If the need is still unclear, ask one `AskUserQuestion` with these options, then answer only the section they pick. Give each option a one-line description, because a blank one can stall a T3 thread. The tool takes at most four options and adds an Other field, so offer the first four and say in the question that Other covers the fifth.

- Get set up
- Start a task with `/jutsu`
- Pick a skill for a situation
- Fix a run that went wrong
- Make jutsu my own

Check the state that changes the answer, and mention it only when it does:

<<<<<<< jutsu override
- No `.claude/jutsu-models.md` in the repo and no `jutsu-models.md` in the Claude config dir (`$CLAUDE_CONFIG_DIR`, else `~/.claude`) means `/jutsu:setup-pstack` hasn't run for this user, so every role uses its default from [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles).
- No `verify` skill (`.claude/skills/verify/`, or an older `verify-*`), no `run-*` skill, and no other app harness in the project means agents have no scripted way to drive the app. Mention `/jutsu:create-verification-skill` when the question is about proving a change works.
=======
- No `~/.cursor/rules/pstack-models.mdc` means `/setup-pstack` hasn't run for this user, so every role uses its default model.
- No `verify-*` skill or other app harness in the project means agents have no scripted way to drive the app. Mention `/create-verification-skill` when the question is about proving a change works.
- No formal verification skill in the project means no property is checked past what tests reach. Mention `/create-formal-verification-skill` when the question is about a race, an invariant, or another case tests rarely hit. When one exists and the code it covers changed after the commit it records as last in sync, mention `/maintain-formal-verification-skill` if the question touches that code.
>>>>>>> upstream d457567332aa

When the models file is missing and it matters, ask whether the user wants to pick a model for each role and a reasoning budget now. It matters when the user is new, the question is about setup or cost, or the answer depends on which models run. Ask at most once per chat. If the need is also unclear, ask both questions in the same `AskUserQuestion` call. Offer two choices:

- Now: give them `/jutsu:setup-pstack` to type, and answer their question too.
- Later: answer their question, and add one line saying every role keeps its default model until they run `/jutsu:setup-pstack`.

## Get set up

<<<<<<< jutsu override
1. Install jutsu per the [jutsu README](https://github.com/sergchil/jutsu#readme). It is a Claude Code plugin, and T3 Code runs the user's own `claude`, so one install serves both.
2. Run [`/jutsu:setup-pstack`]({{plugin}}/skills/setup-pstack/SKILL.md). It asks for a reasoning budget, maps a model and effort to each role, and writes `jutsu-models.md`. In T3 it reads the live model catalog and can add any provider T3 can delegate to, such as Codex, Cursor, or a second Claude account. A non-Claude seat makes the review and arena panels cross-vendor. Without one they stay Claude-only, with weaker diversity. Each skill reads the file when it runs.
3. Start a real task with `/jutsu`, a goal, and a check that can pass or fail.
=======
1. Install with `/add-plugin pstack` in chat, or from Customize in the sidebar.
2. Run [`/setup-pstack`](../setup-pstack/SKILL.md). It asks for a reasoning budget, maps a model to each role, and writes a rule. The rule applies to new chats. Then it offers once each to generate a verification skill and a formal verification skill for the project, unless the project already has one.
3. Start a real task with `/poteto-mode`, a goal, and a check that can pass or fail.
>>>>>>> upstream d457567332aa

Installing changes nothing until the user types `/jutsu` or another jutsu skill. Most jutsu skills load only when the user types them. Three can also load on their own when the work matches. They are `tdd`, `typescript-best-practices`, and `benchmark-checklist`. The README has the details, including how to uninstall. Offer to word their first prompt with them, per [`references/prompting.md`](references/prompting.md).

If cost is the worry, say where the tokens go and how to spend fewer. jutsu spends extra tokens on subagents and review panels. Rerun `/jutsu:setup-pstack` and pick a smaller budget or cheaper models such as `sonnet` or `haiku`. A role set to `inherit` runs on the session's model and effort, which saves tokens when the session runs on a cheaper model or a lower effort. A shorter panel list runs fewer subagents, one for each entry. Save `/jutsu` for work that needs rigor.

<<<<<<< jutsu override
jutsu is pstack ported to Claude Code, built to run inside T3 Code. Plain Claude Code works too. Each step that needs a T3 tool names its fallback in [the runtime]({{plugin}}/skills/poteto-mode/references/runtime.md#host).
=======
pstack is built for Cursor, and it also installs in Claude Code with `/plugin marketplace add cursor/plugins`, then `/plugin install pstack@cursor-plugins`. There, each command takes a `pstack:` prefix, such as `/pstack:poteto-mode`. The [Claude Code adapter](../../docs/harness/claude-code.md) maps the Cursor names, and a step that needs a Cursor-only feature, such as Bugbot or Automations, is skipped with a one-line note.

Other tools can read the skills, because they use the Agent Skills format. But most workflow skills, including `/poteto-mode`, `/how`, `/why`, and `/teach`, spawn Cursor subagents with per-role models, and Custom Modes and `/loop` are Cursor features, so those parts may not work there.
>>>>>>> upstream d457567332aa

In T3, jutsu uses T3's own tools where Claude Code has none. `watch_pull_request` and `schedule_task` wake it on PR events and timed ticks. `t3_thread_launch` gives a long-lived PR owner its own thread and worktree. `delegate_task` runs a role on another provider or Claude account. `preview_*` drives web UIs, `device_*` drives simulators, `html_render` publishes visual reports, and `t3_thread_list`, `t3_thread_read`, and `t3_thread_search` read past threads. [The runtime]({{plugin}}/skills/poteto-mode/references/runtime.md) maps each one and its fallback.

## Start a task with `/jutsu`

`/jutsu` matches the task to a playbook, copies the playbook's steps into the todo list, and runs the other skills as the steps need them. A step it skips stays in the list as `skip: <reason>`. A good prompt states the goal and how to tell it's done. It doesn't list skills, because a hand-written sequence tends to drop or reorder steps the playbook would keep. Read [`references/prompting.md`](references/prompting.md) before you help word one.

How `/jutsu` stays on:

- `/jutsu <task>` at the start of a message, or `$jutsu` from T3's skill picker, turns poteto mode on for the rest of the session. `/jutsu:poteto-mode` does the same.
- Start any other jutsu skill with `/jutsu:<skill>`. T3's `$` picker sends `$jutsu:<skill>` as plain text, so it runs nothing. Only `$jutsu` works there.
- While it is on, a plugin hook adds a one-line reminder to every turn. The reminder says to apply the mode to a new task that matches a playbook or needs rigor, and to skip it on a casual turn or when the user opts out. So the mode stays on without taking over casual turns. After a compaction or a resume, the hook also tells the model to reread the router.
- `/jutsu off` turns it off. A new session starts with it off.

Link [Claude Code's skills docs](https://code.claude.com/docs/en/skills) when this comes up. Mid-chat, "new task" makes the mode match a fresh playbook. `/jutsu` already uses `jutsu:poteto-agent` for the subagents its playbook steps spawn. To get the same style from a subagent of your own, spawn it with `subagent_type: "jutsu:poteto-agent"`.

## Pick a skill

The default answer is `/jutsu`, which runs most of the others when its steps need them. Name a skill directly when the user wants more or less of something than the playbook gives. Read the skill before you recommend it, and give one example prompt.

| The user wants to | Skill |
|---|---|
<<<<<<< jutsu override
| Do any non-trivial task with rigor | [`/jutsu`]({{plugin}}/skills/poteto-mode/SKILL.md) |
| Check that the agent understood their goal and the problem before it starts | [`/jutsu:in-your-own-words`]({{plugin}}/skills/in-your-own-words/SKILL.md) |
| Know how code works now, or where new code should live | [`/jutsu:how`]({{plugin}}/skills/how/SKILL.md) |
| Know why code is shaped this way, or where a number came from | [`/jutsu:why`]({{plugin}}/skills/why/SKILL.md) |
| Understand a change or subsystem, explained plainly | [`/jutsu:teach`]({{plugin}}/skills/teach/SKILL.md) |
| Catch up on their own recent work on a topic | [`/jutsu:recall`]({{plugin}}/skills/recall/SKILL.md) |
| Catch up on what changed in this chat since their last message, in a few plain sentences and small visuals, with enough context to decide each action item | [`/jutsu:ketchup`]({{plugin}}/skills/ketchup/SKILL.md) |
| Know what a small diff could break outside itself | [`/jutsu:blast-radius`]({{plugin}}/skills/blast-radius/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [`/jutsu:architect`]({{plugin}}/skills/architect/SKILL.md) |
| Get several attempts at one brief, merged into the best one | [`/jutsu:arena`]({{plugin}}/skills/arena/SKILL.md) |
| Run parallel checks over slices, or race workers, each in its own worktree | [`/jutsu:swarm`]({{plugin}}/skills/swarm/SKILL.md) |
| Have different models review a diff and try to break it | [`/jutsu:interrogate`]({{plugin}}/skills/interrogate/SKILL.md) |
| Fix a bug test-first when a cheap local test exists | [`/jutsu:tdd`]({{plugin}}/skills/tdd/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [`/jutsu:typescript-best-practices`]({{plugin}}/skills/typescript-best-practices/SKILL.md) |
| Strip comments before review, using a reviewer that didn't write them | [`/jutsu:no-comments`]({{plugin}}/skills/no-comments/SKILL.md) |
| Clean AI tells out of prose | [`/jutsu:unslop`]({{plugin}}/skills/unslop/SKILL.md) |
| Write docs, an RFC, a README, a PR description, or a commit message to a standard | [`/jutsu:technical-writing`]({{plugin}}/skills/technical-writing/SKILL.md) |
| Hear the last reply again in plain words | [`/jutsu:bro`]({{plugin}}/skills/bro/SKILL.md) |
| Give agents a scripted way to drive the app and prove behavior, as the project's `verify` skill | [`/jutsu:create-verification-skill`]({{plugin}}/skills/create-verification-skill/SKILL.md) |
| Bring a verification skill and its feature map back in line with the app | [`/jutsu:maintain-verification-skill`]({{plugin}}/skills/maintain-verification-skill/SKILL.md) |
| Vet a performance number before reporting or acting on it | [`/jutsu:benchmark-checklist`]({{plugin}}/skills/benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [`/jutsu:figure-it-out`]({{plugin}}/skills/figure-it-out/SKILL.md) |
| Keep a decision log during a run, and review it afterward | [`/jutsu:show-me-your-work`]({{plugin}}/skills/show-me-your-work/SKILL.md) |
| Pick a model for each role and a reasoning budget | [`/jutsu:setup-pstack`]({{plugin}}/skills/setup-pstack/SKILL.md) |
| Turn their own working habits into a personal mode skill | [`/jutsu:automate-me`]({{plugin}}/skills/automate-me/SKILL.md) |
| Turn what a finished task taught into skill edits | [`/jutsu:reflect`]({{plugin}}/skills/reflect/SKILL.md) |
| Stop agents from repeating the same mistakes in this repo | [`/jutsu:correct`]({{plugin}}/skills/correct/SKILL.md) |
| Find their way around jutsu | `/jutsu:poteto-help` |

If a skill directory next to this one is missing from the table, read its frontmatter and route by its description. Principles live in `{{plugin}}/principles/` and are covered under principles below.
=======
| Do any non-trivial task with rigor | [`/poteto-mode`](../poteto-mode/SKILL.md) |
| Check that the agent understood their goal and the problem before it starts | [`/in-your-own-words`](../in-your-own-words/SKILL.md) |
| Aim a task higher before starting: more expert, more outcome-focused, not overspecified | [`/sharpen`](../sharpen/SKILL.md) |
| Know how code works now, or where new code should live | [`/how`](../how/SKILL.md) |
| Know why code is shaped this way, or where a number came from | [`/why`](../why/SKILL.md) |
| Understand a change or subsystem, explained plainly | [`/teach`](../teach/SKILL.md) |
| Catch up on their own recent work on a topic | [`/recall`](../recall/SKILL.md) |
| Catch up on what changed in this chat since their last message, in plain words and small visuals, with every item waiting on them listed and decidable from the reply alone | [`/ketchup`](../ketchup/SKILL.md) |
| Know what a small diff could break outside itself | [`/blast-radius`](../blast-radius/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [`/architect`](../architect/SKILL.md) |
| Get several attempts at one brief, merged into the best one | [`/arena`](../arena/SKILL.md) |
| Run parallel checks over slices, or race workers, as cloud agents | [`/swarm`](../swarm/SKILL.md) |
| Have different models review a diff and try to break it | [`/interrogate`](../interrogate/SKILL.md) |
| Fix a bug test-first when a cheap local test exists | [`/tdd`](../tdd/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [`/typescript-best-practices`](../typescript-best-practices/SKILL.md) |
| Strip comments before review, using a reviewer that didn't write them | [`/no-comments`](../no-comments/SKILL.md) |
| Clean AI tells out of prose | [`/unslop`](../unslop/SKILL.md) |
| Write docs, an RFC, a README, a PR description, or a commit message to a standard | [`/technical-writing`](../technical-writing/SKILL.md) |
| Hear the last reply again in plain words | [`/bro`](../bro/SKILL.md) |
| Give agents a scripted way to drive the app and prove behavior | [`/create-verification-skill`](../create-verification-skill/SKILL.md) |
| Bring a verification skill and its feature map back in line with the app | [`/maintain-verification-skill`](../maintain-verification-skill/SKILL.md) |
| Formally verify a race, invariant, or other property that tests rarely reach | [`/create-formal-verification-skill`](../create-formal-verification-skill/SKILL.md) |
| Bring a formal verification back in line after the code it covers changed, and learn whether a failure is drift or a bug | [`/maintain-formal-verification-skill`](../maintain-formal-verification-skill/SKILL.md) |
| Vet a performance number before reporting or acting on it | [`/benchmark-checklist`](../benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [`/figure-it-out`](../figure-it-out/SKILL.md) |
| Keep a decision log during a run, and review it afterward | [`/show-me-your-work`](../show-me-your-work/SKILL.md) |
| Pick a model for each role and a reasoning budget | [`/setup-pstack`](../setup-pstack/SKILL.md) |
| Turn their own working habits into a personal mode skill | [`/automate-me`](../automate-me/SKILL.md) |
| Turn what a finished task taught into skill edits | [`/reflect`](../reflect/SKILL.md) |
| Stop agents from repeating the same mistakes in this repo | [`/correct`](../correct/SKILL.md) |
| Build a page whose buttons wake a Grok Bot over a webhook | [`/make-bot-ui`](../make-bot-ui/SKILL.md) |
| Find their way around pstack | `/poteto-help` |

If a skill directory next to this one is missing from the table, read its frontmatter and route by its description. The `principle-*` directories are covered under principles below.
>>>>>>> upstream d457567332aa

Close calls:

- `/jutsu:how` explains what the code does. `/jutsu:why` explains the reasons. `/jutsu:teach` runs one or both and explains the result plainly.
- `/jutsu:arena` gives every worker the same brief and merges the best parts. `/jutsu:swarm` splits work into slices or a race and returns one report.
- `/jutsu:architect` implements right after it settles the design. Add "with checkpoint" to review the design before it writes code.
- `/jutsu:interrogate` reviews the diff. `/jutsu:blast-radius` looks for breakage outside the diff and proves the one fact that makes the change safe.
- `/jutsu:recall` rebuilds context across recent chats. `/jutsu:ketchup` covers only this chat since the user's last message. Resuming one specific chat or branch is the Session pickup playbook.
- `/jutsu:figure-it-out` designs one rigorous run. The Orchestrate playbook runs a program that spans days and many PRs. The Autonomous run playbook drives one task to a finish condition.

Not in jutsu:

- jutsu has no `/orchestrate` skill. Orchestrate is a `/jutsu` playbook. If the slash menu shows `/orchestrate`, another plugin provides it.

## Playbooks and principles

Playbooks are step lists inside `/jutsu`, not skills, so they have no slash command. Inside `/jutsu`, describing the task picks one, and these phrases name one directly:

- "babysit this pr" or "check on pr 123" runs Babysit. It drives the PR to merge-ready and stops there. It doesn't merge unless the user asks to merge, land, or ship.
- "land the stack" runs Shipping.
- "take over this branch" runs Session pickup.
- "pause safely" runs Pause safely.
- "full autopilot on this queue" runs Autopilot-full. "stack them, don't ship" runs Autopilot-stack.
- "run the eval playbook" runs Eval.

Without `/jutsu`, a phrase such as "babysit this pr" can start Claude Code's `/autofix-pr` or T3's own PR watching for the same job instead. With `/jutsu` on, the Babysit playbook wins. The Playbooks section of [`poteto-mode`]({{plugin}}/skills/poteto-mode/SKILL.md) lists every playbook and when it applies.

jutsu has no planning skill. Plan mode in T3 or Claude Code works alongside it. For work that spans phases or stacked PRs, asking `/jutsu` for a plan runs the [Multi-phase plan playbook]({{plugin}}/skills/poteto-mode/playbooks/multi-phase-plan.md), which writes the plan and doesn't implement it. For a design question, the Prototype playbook or `/jutsu:architect` settles it in code first.

Principles are one-rule files in `{{plugin}}/principles/` that `/jutsu` reads and cites in its replies. The user rarely asks for one. They steer with the names instead, as in "apply prove it works. show me the real output." A principle has no slash command. Naming it, as in "read the prove-it-works principle", loads it on demand from [`principle-prove-it-works.md`]({{plugin}}/principles/principle-prove-it-works.md) and its siblings.

## Fix a run that went wrong

| Symptom | Fix |
|---|---|
| The mode stopped applying after a few turns | It is a new session, or `/jutsu off` ran, or the task was started without `/jutsu` at the start of a message. Start the task with `/jutsu`. If the turn reminder never appears, check that jutsu is enabled with `claude plugin list`. |
| Every turn shows two routers or two reminders | Another pstack plugin is enabled next to jutsu, such as `pstack@pstack-claude`. Disable it with `claude plugin disable pstack@pstack-claude`, once in each Claude config dir that T3 or the user runs. |
| A question got treated as the next step of the last task | Say "new task", or say the turn doesn't need the mode. |
| A new model choice had no effect | A repo `.claude/jutsu-models.md` wins over the one in the Claude config dir, so check which one the run read. Each skill reads the file when it runs, so rerun the skill, or say "reread jutsu-models.md". |
| Runs cost more than expected | See the cost paragraph under Get set up. |
| A skill didn't load on its own | Most jutsu skills are user-invoked. They load when the user types `/jutsu:<skill>`, or when `/jutsu` reads the file, and `/jutsu` doesn't run every skill. Only `tdd`, `typescript-best-practices`, and `benchmark-checklist` load on their own. |
| `$jutsu:<skill>` from T3's picker did nothing | T3 sends it as plain text. Type `/jutsu:<skill>` instead. `$jutsu` alone works. |
| A T3 tool failed as unknown, or no PR watch or delegation ran | T3 stable ships only the preview, device, and PR link tools. The orchestration tools need a T3 nightly. jutsu takes the fallback in [the runtime's Host]({{plugin}}/skills/poteto-mode/references/runtime.md#host) and says so. |
| A `device_*` call was refused | Device access is off by default. Turn on agent device access in T3's settings. |
| "babysit this pr" ran another PR watcher | Claude Code's `/autofix-pr` or T3's own PR watching matched the words. Start the request with `/jutsu`. |
| Parallel agents overwrote each other | Give each writer its own worktree from your HEAD, per [the runtime's Isolation]({{plugin}}/skills/poteto-mode/references/runtime.md#isolation). |
| An overnight run moved but finished nothing | The run needs a check that can pass or fail, not a duration. |
| The reply claims success from a green build | Ask for the real command, flow, stored value, or profile. That's the prove-it-works principle. |

For a run that drifts, [`references/prompting.md`](references/prompting.md) has one-line steers, and [`references/recipes.md`](references/recipes.md) has recipes worth copying.

## Make jutsu my own

- [`/jutsu:automate-me`]({{plugin}}/skills/automate-me/SKILL.md) drafts a personal mode skill from the user's own history, to use alongside `/jutsu`.
- [`/jutsu:reflect`]({{plugin}}/skills/reflect/SKILL.md) after a session turns its lessons into skill edits the user approves.
- `/jutsu write a skill for <workflow>` runs the authoring playbook. The eval playbook tests a skill change blind.
- Fix a misbehaving skill in its own PR, not inside the feature work where it went wrong.

## Reply

Lead with the answer. Give at most one example prompt in a code block, adapted from [`references/recipes.md`](references/recipes.md) when one fits, then the link to that file. Keep it short unless the user asked for the whole map.
