### Opening a PR

Invoked at the end of every other playbook.

**Worktree.** Work from a git worktree off main. Subagents inherit it. Multiple `Agent` calls on the same branch each get their own worktree per [the runtime's Isolation section](../references/runtime.md#isolation), or `git fetch && git reset --hard origin/<branch>` between them. Dirty branch with unrelated work: patch out, fresh worktree, apply. Snarled worktree: reset from main, redo minimally. Before you commit, merge, push, or deploy from a worktree, stop every child that writes there, grandchildren included, and confirm with `git status`, per [the runtime's Subagents section](../references/runtime.md#subagents).

**Commits.** Commit liberally. Rebase into small, ordered commits before opening PRs. Each commit is a future PR: landable, ordered to tell the story. Amend when the fix belongs in a just-made commit. New commit when separable.

**PRs.** Deslop the diff before commit per [the runtime's Missing companions](../references/runtime.md#missing-companions). Run the **no-comments** skill (`{{p3}}/skills/no-comments/SKILL.md`) before review. Write every PR title, PR description, and commit body with the **technical-writing** skill (`{{p3}}/skills/technical-writing/SKILL.md`), then apply the **unslop** skill (`{{p3}}/skills/unslop/SKILL.md`). Apply every technical-writing layer except Diátaxis. Use one word for each action, keep articles, and avoid `-ing` when a plain verb works.

**Titles.** Use Conventional Commits in the form `type(scope): subject`. Use `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, or `perf` as the type. Use the changed area, such as `pstack` or `poteto-mode`, as the scope. Keep the subject short and imperative. Name a real symbol when one carries the change. For example, `fix(pstack): retarget opening-a-pr babysit trigger`. Do not add a trailing period.

**Descriptions.** The PR body is a briefing, not the lab notebook. A reviewer who has the diff should learn why the change exists, what it leaves out, what it could break, and how you proved it works, in under a minute. Write short, simple sentences with few identifiers. Do not write walls of text. The squash commit body is the PR body. If the body would make the squash commit longer than about 40 lines, cut the body.

Put each section under a `##` heading, not a bold lead-in, so the sections stand apart. Use these sections in order. Drop a section when it has nothing to say.

- `## Why` gives the problem and the approach in one to three short sentences. Do not list SHAs or rebase genealogy. Do not add a "based on main" preamble.
- `## What changed` has one to three short bullets. Name a real symbol or path only when it carries the change. Name both sides of a rename or retarget.
- `## Scope` always names what the PR covers and what it deliberately leaves out, for example a related follow-up or a known gap. Use one to three short items. Do not list symbols or paths, and do not write a file-by-file essay.
- `## Tradeoffs` names only rejected alternatives that a reviewer would otherwise ask about. Skip this section when there was no real choice.
- `## Blast Radius` gives one or two sentences on who or what the change touches and why that is safe or risky. If main is red, state the cost of leaving it red.
- `## Verification` has one to three bullets. Each bullet names a real run path and its outcome. For a performance change, report one primary number with its unit in `before → after` form. Link the arena or swarm directory for the remaining evidence. Do not include sample-size methodology, swarm recitals, or metric tables.

After these sections, attach videos or screenshots when they prove a claim. Do not paste full SHAs, swarm or arena lane recitals, lever-correction essays, file-by-file checklists, or "CLEAN" verdicts. Put these details in a linked artifact. A commit body does not restate its subject.

**Forge.** GitHub CLI (`gh`) is the forge for create, edit, view, watch, and merge. Do not require Graphite (`gt`).

**Built-in PR tool.** T3 has no tool that creates a PR, so create, edit, retarget, and mark ready with `gh`. In T3, call `link_pull_request` with each PR's URL as soon as you create or adopt it, one call per stack layer, per [the runtime's Pull requests section](../references/runtime.md#pull-requests). The link puts the PR on the thread. T3 auto-settles a thread once every linked PR has merged or closed, and settling ends its watches, so link every layer before the root merges. Outside T3, skip the link.

**Size and stacks.** Prefer five narrow PRs to one large PR. A stack is a base-branch chain. The root PR targets trunk. Each child branch rebases onto its parent's exact tip and its PR targets the parent branch. Create a child with `gh pr create --base <parent-branch>`, and retarget an existing child with `gh pr edit <pr> --base <parent-branch>`. Branch from trunk only for independent work. Rebase on trunk before substantial stack work.

**Readiness.** Open every PR ready, never as a draft. With `gh`, omit `--draft`. If a PR still opens as a draft, run `gh pr ready <number>`. Run `gh pr view <number>` before you refer to PR status.

**Babysit.** Opening a PR does not start a babysit. Post the URL and keep building. Finish the phase or stack first. Run a separate babysit pass only when the user asks for one after the whole stack exists. A babysit for each new PR stalls the build and spends checks on commits that later waves restart. Push back when feedback drifts from intent.

A subagent that opens a PR runs the **interrogate** skill (`{{p3}}/skills/interrogate/SKILL.md`), the deslop pass, and **no-comments**, and posts the URL. Then it returns to the parent without babysitting, unless it is an Autopilot-full or Autopilot-stack owner. That owner's brief assigns the babysit loop and is the ask `playbooks/babysit.md` waits for. Babysit needs a top-level thread, so in T3 that owner is a launched thread per [the runtime's Isolation section](../references/runtime.md#isolation). The owner starts the loop after its code-ready report and reports merge-ready or STACK-READY as its playbook says. The rules here and in `playbooks/babysit.md` that hold babysitting until a whole stack is built do not apply to that owner. In T3, the parent calls `link_pull_request` for each URL a subagent posts, so the PR shows on the parent's thread.
