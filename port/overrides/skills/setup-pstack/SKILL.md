---
name: setup-pstack
description: Configure which models pstack uses per role and at what reasoning budget. Detects your available Claude models and effort levels and writes jutsu-models.md, which overrides the role defaults. Use for /jutsu:setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
disable-model-invocation: true
---

# Setup pstack

Write `jutsu-models.md`, the file that sets pstack's model and effort per role. [The runtime's Roles section]({{plugin}}/skills/poteto-mode/references/runtime.md#roles) reads it. It looks for `.claude/jutsu-models.md` in the repo first, then `jutsu-models.md` in the Claude config dir (`$CLAUDE_CONFIG_DIR`, else `~/.claude`). Write the config-dir file unless the user asks for this repo only. Never edit `settings.json` or `CLAUDE.md`. Every skill reads `jutsu-models.md` directly. Commit a repo's `.claude/jutsu-models.md`: T3 worktree threads see only committed files.

## Steps

### 1. Detect available models

The `Agent` tool's `model` takes only the aliases `opus`, `sonnet`, `fable`, and `haiku`, each running that family's current model. Its `effort` takes `low`, `medium`, `high`, `xhigh`, or `max` ([the runtime's Subagents]({{plugin}}/skills/poteto-mode/references/runtime.md#subagents)). That is the dependable source. Outside T3, those four aliases are the detected set.

In T3, also call `orchestrator_capabilities`. It lists the provider instances and models this thread can delegate to, with each model's effort options, from the same catalog as T3's model picker. The Claude instances have `driverKind: "claudeAgent"`. The one named by `inheritedProviderInstanceId` is this session's account. Show the user which of the four current models it lists and the effort levels each one offers. An alias whose model the catalog does not list needs a choice. Another Claude instance with `canRunChildTask: true` is another Claude account. Offer its models as T3 targets, written `t3:<providerInstanceId>/<modelId> @<effort>`, which run through `delegate_task`. Name each instance that cannot run with its `constraints`, so the user knows what to fix in T3 settings. If the call fails with an unknown-tool or capability error (T3 stable has no orchestration tools, per [the runtime's Host]({{plugin}}/skills/poteto-mode/references/runtime.md#host)), use the four aliases and say so.

Never write a model you have not confirmed is available. The value `inherit` is always valid. It runs the role on this session's model and effort, so the `Agent` call omits `model` and `effort`. Write only the five efforts above. The catalog's `ultracode` and `ultrathink` are not `Agent` efforts.

### 2. Load current state

The defaults are the role lines in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). If `jutsu-models.md` already exists where the runtime looks, read it and treat its `# budget` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Ask with `AskUserQuestion`. Offer these four options with these exact labels, and give each a non-empty description of what it costs, because a blank description can stall a T3 thread ([the runtime's Questions]({{plugin}}/skills/poteto-mode/references/runtime.md#questions)). Name the current budget when the file records one. With no file, say that the defaults match `large`: every role runs at `xhigh`, as upstream runs.

- `unlimited — max reasoning`
- `large — xhigh reasoning`
- `medium — high reasoning`
- `small — medium reasoning`

**(b) Apply it.** Build the working table from the defaults, and on a re-run keep the model of any role the user changed (another alias, a list, a T3 target, or `inherit`). `unlimited`, `large`, `medium`, and `small` set the effort of every alias and T3 entry, panel entries included, to `max`, `xhigh`, `high`, or `medium`. The ladder is `max` > `xhigh` > `high` > `medium` > `low`. In T3, if a model's catalog entry does not offer the target, use the highest effort it offers at or below the target, else mark the role as needing a choice. `inherit` does not change. The defaults already run at `xhigh`, so `large` keeps them. `unlimited` turns `opus @xhigh` into `opus @max`, and `small` turns `opus @xhigh` and `fable @xhigh` into `opus @medium` and `fable @medium`.

**(c) Show the roles and confirm.** Show every role with its value, marking any model not confirmed in step 1 as needing a choice. Also list each line step 2 dropped. Ask whether to accept as-is or change specific roles, with `AskUserQuestion` and a non-empty description on every option. The tool takes at most four options per question and adds an Other field, so ask accept or change first. Then, for each role to change, offer up to four values and let Other take the rest. The values are the detected aliases, any T3 targets, and `inherit` (this role runs on the session's model and effort). For panel roles (arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, `inherit` entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but Arena selects one value from it whose model family differs from the parent's when possible. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every alias written must be in the detected set. Every T3 entry must name a runnable instance and a model listed under it in step 1, with an effort that model offers. Every effort is one of `low`, `medium`, `high`, `xhigh`, or `max`. `inherit` always passes. If a chosen value is not available, stop and ask again.

### 5. Write the file

Write `jutsu-models.md` with a `# budget` line with the chosen label and its target effort, and one line per role, using the same labels as [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). A value is `<alias> @<effort>`, `t3:<providerInstanceId>/<modelId> @<effort>`, or `inherit`. Overwrite the whole file so re-runs stay idempotent. Shape, with `large` applied to the defaults:

```
# jutsu model configuration. One line per role. Delete a line to fall back to the runtime default.
# `inherit` as a value: the role runs on the session's model and effort (omit Agent `model` and `effort`). Inherit entries in a panel list still count toward its fan-out.
# `t3:<providerInstanceId>/<modelId> @<effort>` runs the role through delegate_task on that T3 provider instance.
# budget: large (xhigh)
feature, refactoring: opus @xhigh
bug-fix: fable @xhigh
perf-issue: fable @xhigh
hillclimb: fable @xhigh
judgment and prose: opus @xhigh
hardest tasks: opus @xhigh
how explorer: sonnet @xhigh
how explainer: opus @xhigh
why investigators: sonnet @xhigh
why synthesizer: opus @xhigh
reflect tooling: sonnet @xhigh
reflect judgment, divergent, synthesizer: opus @xhigh
arena runners: opus @xhigh, fable @xhigh, sonnet @xhigh
arena cross-judge pool: opus @xhigh, fable @xhigh, sonnet @xhigh
swarm workers: opus @xhigh
architect runners: opus @xhigh, fable @xhigh, sonnet @xhigh
interrogate reviewers: opus @xhigh, fable @xhigh, sonnet @xhigh
```

A panel entry on a second Claude account reads `t3:<providerInstanceId>/claude-opus-5-5 @xhigh`, with the instance id from step 1.

### 6. Confirm

Tell the user where the file was written and that it applies to new sessions. Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill in `.claude/skills/`, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /jutsu:create-verification-skill." On yes, read [`create-verification-skill`]({{plugin}}/skills/create-verification-skill/SKILL.md) and follow it. jutsu skills are user-invoked, so the Skill tool cannot start it. On no, move on without pushing.
