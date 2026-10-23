---
name: setup-pstack
description: Configure which models pstack uses per role and at what reasoning budget. Detects your Claude models and, in T3, every provider T3 can delegate to (Codex, Cursor, and others), with their effort levels, and writes jutsu-models.md, which overrides the role defaults. Use for /jutsu:setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
disable-model-invocation: true
---

# Setup pstack

Write `jutsu-models.md`, the file that sets pstack's model and effort per role, to the `rules/` folder of the Claude config dir: `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/rules/jutsu-models.md`. Claude Code loads every `.md` file in that folder into each new session ([Claude Code's memory docs](https://code.claude.com/docs/en/memory#user-level-rules)), so [the runtime's Roles section]({{plugin}}/skills/poteto-mode/references/runtime.md#roles) finds the role lines already in context. When the user asks for this repo only, write `.claude/jutsu-models.md` in the repo instead. It wins over the rules file, and the runtime reads it from disk. Commit it: T3 worktree threads see only committed files. Never edit `settings.json`, `CLAUDE.md`, or `AGENTS.md`.

## Steps

### 1. Detect available models

The `Agent` tool's `model` takes only the aliases `opus`, `sonnet`, `fable`, and `haiku`, each running that family's current model. Its `effort` takes `low`, `medium`, `high`, `xhigh`, or `max` ([the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents)). That is the dependable source. Outside T3, those four aliases are the detected set.

In T3, also call `orchestrator_capabilities`. It lists every provider instance this thread can delegate to, with its models and each model's `options` descriptors, from the same catalog as T3's model picker. The Claude instances have `driverKind: "claudeAgent"`. The one named by `inheritedProviderInstanceId` is this session's account. Show the user which of the four current models it lists and the effort levels each one offers. An alias whose model the catalog does not list needs a choice.

Every other instance with `canRunChildTask: true` and `canRunCrossProviderChildTask: true` is a T3 target, whatever its `driverKind`: Codex, Cursor, Grok, OpenCode, or another Claude account. Offer each of its models as `t3:<providerInstanceId>/<modelId> @<effort>`, which runs through `delegate_task` ([the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents)). Its efforts are the choice ids of that model's own effort descriptor (a `select` option such as `effort`, `reasoningEffort`, or `thinking`), not Claude's ladder. Show them as the catalog lists them. A model with no such descriptor takes no effort, so write it without `@<effort>`. Name each instance that cannot run with its `constraints`, so the user knows what to turn on in T3's settings. A provider that is off in T3's settings does not count as available. If the call fails with an unknown-tool or capability error (T3 stable has no orchestration tools, per [the runtime's Host]({{plugin}}/skills/poteto-mode/references/runtime.md#host)), use the four aliases and say so.

Never write a model you have not confirmed is available. The value `inherit` is always valid. It runs the role on this session's model and effort, so the `Agent` call omits `model` and `effort`. For an alias, write only the five efforts above. The catalog's `ultracode` and `ultrathink` are not `Agent` efforts.

### 2. Load current state

The defaults are the role lines in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). If `jutsu-models.md` already exists where the runtime looks, or as `jutsu-models.md` directly in the Claude config dir (where jutsu 0.2 wrote it), read it and treat its `# budget` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Ask with `AskUserQuestion`. Offer these four options with these exact labels, and give each a non-empty description of what it costs, because a blank description can stall a T3 thread ([the runtime's Questions]({{plugin}}/skills/poteto-mode/references/runtime.md#questions)). Name the current budget when the file records one. With no file, say that the defaults are `balanced`.

- `balanced — the defaults (recommended)`: Opus `high` for code, Fable for perf and the hardest tasks, Sonnet for reading and workers, one architect runner, two reviewers
- `large — xhigh reasoning`: upstream's setting, every role at `xhigh`; much slower
- `medium — high reasoning`
- `small — medium reasoning`

Other takes `unlimited`, which sets every role to `max`.

**(b) Apply it.** Build the working table from the defaults, and on a re-run keep the model of any role the user changed (another alias, a list, a T3 target, or `inherit`). `balanced` keeps the defaults as they are. `unlimited`, `large`, `medium`, and `small` set the effort of every alias and T3 entry, panel entries included, to `max`, `xhigh`, `high`, or `medium`. The ladder is `max` > `xhigh` > `high` > `medium` > `low`. In T3, if a model's catalog entry does not offer the target, use the highest effort it offers at or below the target, else mark the role as needing a choice. A non-Claude model's effort ids follow its own descriptor. Map the budget to the nearest choice it offers, in the descriptor's order, and show the mapping. `inherit` does not change. `large` turns `opus @high` into `opus @xhigh`, `unlimited` into `opus @max`, and `small` into `opus @medium`. A level the user sets sets every role, panel entries included; it never adds or removes panel entries.

**(c) Show the roles and confirm.** Show every role with its value, marking any model not confirmed in step 1 as needing a choice. Also list each line step 2 dropped. Ask whether to accept as-is or change specific roles, with `AskUserQuestion` and a non-empty description on every option. The tool takes at most four options per question and adds an Other field, so ask accept or change first. Then, for each role to change, offer up to four values and let Other take the rest. The values are the detected aliases, any T3 targets, and `inherit` (this role runs on the session's model and effort). For panel roles (arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, `inherit` entries included, so the list length sets the count. When step 1 found a runnable non-Claude target, offer it first as one entry of each panel list and of `arena cross-judge pool`, and as a model-race arm for `swarm workers`. When none is runnable, say the panels stay Claude-only, so their diversity is weaker. Name the providers the user could turn on in T3's settings, such as Cursor (it uses the `cursor-agent` CLI) or Codex (T3 offers a managed install). `arena cross-judge pool` is also a list, but Arena selects one value from it whose model family differs from the parent's when possible. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every alias written must be in the detected set. Every T3 entry must name a runnable instance and a model listed under it in step 1, with an effort that is a choice id of that model's own effort descriptor. Every alias effort is one of `low`, `medium`, `high`, `xhigh`, or `max`. `inherit` always passes. If a chosen value is not available, stop and ask again.

### 5. Write the file

Create the `rules/` folder if it is missing, then write `jutsu-models.md` there (or the repo file, per the top of this skill) with no frontmatter, the comment lines, a `# budget` line with the chosen label and its target effort, and one line per role, using the same labels as [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). A value is `<alias> @<effort>`, `t3:<providerInstanceId>/<modelId> @<effort>`, or `inherit`. Overwrite the whole file so re-runs stay idempotent. Then delete a `jutsu-models.md` left directly in the Claude config dir by jutsu 0.2, so only one file sets the roles. Shape, with `balanced` (the defaults):

```
# jutsu model configuration, written by /jutsu:setup-pstack. Only jutsu skills read these lines. One line per role. Delete a line to fall back to the runtime default.
# `inherit` as a value: the role runs on the session's model and effort (omit Agent `model` and `effort`). Inherit entries in a panel list still count toward its fan-out.
# `t3:<providerInstanceId>/<modelId> @<effort>` runs the role through delegate_task on that T3 provider instance. `@<effort>` is a choice id of that model's effort option.
# budget: balanced (defaults)
feature, refactoring: opus @high
bug-fix: opus @high
perf-issue: fable @high
hillclimb: opus @high
judgment and prose: opus @high
hardest tasks: fable @xhigh
how explorer: sonnet @medium
how explainer: opus @high
why investigators: sonnet @medium
why synthesizer: opus @high
reflect tooling: sonnet @high
reflect judgment, divergent, synthesizer: opus @high
swarm workers: sonnet @high
arena runners: opus @high, fable @high
arena cross-judge pool: opus @high
architect runners: opus @xhigh
interrogate reviewers: opus @high, sonnet @high
```

A panel entry on another provider or a second Claude account reads `t3:<providerInstanceId>/<modelId> @<effort>`, with the instance id, model id, and effort id from step 1. For example, `interrogate reviewers: opus @high, sonnet @high, t3:<codexInstanceId>/<modelId> @high`.

### 6. Confirm

Tell the user where the file was written. A new session loads it. In a session that was already open, a jutsu skill uses the new lines once the user says "reread jutsu-models.md", or in a new session. Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify` skill in `.claude/skills/verify/`, an older `verify-*` skill, a `run-*` skill from Claude Code's `/run-skill-generator`, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /jutsu:create-verification-skill." On yes, read [`create-verification-skill`]({{plugin}}/skills/create-verification-skill/SKILL.md) and follow it. jutsu skills are user-invoked, so the Skill tool cannot start it. On no, move on without pushing.

### 8. Offer a formal verification skill (optional)

Check whether the project already has a formal verification skill (a project skill in `.claude/skills/` that runs a model checker, a proof, or another verifier against the code). If not, offer once: "want a formal verification skill, so agents can prove a key property of your code holds in every case in scope, not only the cases tests reach? I can generate one with /jutsu:create-formal-verification-skill." On yes, read [`create-formal-verification-skill`]({{plugin}}/skills/create-formal-verification-skill/SKILL.md) and follow it, as in step 7. On no, move on without pushing.
