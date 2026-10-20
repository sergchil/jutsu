---
name: thermo-nuclear-review
description: "Spawn one read-only reviewer for a deep audit of a branch's diff: bugs, broken features, security holes, broken local dev setup, and feature-flag leaks, then a check of the PR's bot and human comments."
disable-model-invocation: true
---

# Thermo nuclear review

A single deep audit of a branch's changes for correctness and security, from Cursor's thermos plugin (MIT, see `LICENSE-thermos` in this folder). It adds lenses the **interrogate** skill's rubric (`{{plugin}}/skills/interrogate/SKILL.md`) does not name: broken developer setup, feature-gate leaks, and intended breakage. Use `/jutsu:interrogate` for a multi-model panel with the code-quality lens, and `/jutsu:blast-radius` (`{{plugin}}/skills/blast-radius/SKILL.md`) to prove what the change breaks outside the diff. This review is one reviewer, so it is not a panel verdict.

## Run it

1. Scope. Use the files or PR the user names, else `git diff <base>...HEAD` on the current branch, where `<base>` is the PR's base or the remote default branch. Read the full contents of the changed files, through an `Explore` agent when the set is large.
2. Spawn one reviewer with the `Agent` tool: `subagent_type: "general-purpose"`, a read-only brief, and `model` and `effort` from the first entry on the `interrogate reviewers` line in `jutsu-models.md`, or its default in [the runtime's Roles]({{plugin}}/skills/poteto-mode/references/runtime.md#roles). `effort` is never below `high`. The brief is the reviewer brief below, then `### Git / diff output` and `### Changed file contents`, then the PR URL when one exists. Never put `$(...)` or shell-expanding backticks in it.
3. When no independent reviewer could run, the review gate stays closed. Report `BLOCKED: independent review`.
4. Report the reviewer's findings by priority with `file:line` evidence, the model and effort it actually ran at, and which findings came from the PR discussion. Do not apply fixes unless the user asks.

## Reviewer brief

This review is read-only. Do not edit files, commit, or push. For a PR that may come from a fork, pass `-R <owner>/<repo>` from the PR URL to every `gh pr` call, and name the PR by number or URL.

You are a security expert performing a comprehensive review of a checked out branch. Audit this branch and its changes extremely thoroughly for bugs, changes that break existing features/functionality, and security vulnerabilities. Be EXTREMELY thorough, rigorous, careful, ambitious, and attentive. NOTHING can slip through.

### Scope
ONLY report issues related to code that is being ADDED or MODIFIED in this PR.
Focus on changes in the diff.
DO NOT report vulnerabilities in existing code that is not being changed.

### Guidelines

#### Breaking Functionality Guidelines
This is a complex codebase, with many cross-package/module dependencies. Often simple code changes in one place have subtle interactions that break functionality elsewhere. You MUST be extremely thorough in tracing through possible side effects of the changes.

#### Breaking Devex Guidelines
It can be easy to break developers' ability to run / build the code locally. You MUST catch changes that will impact users' developer experience. Some examples (not exhaustive):
- Modifying how secrets are read / where they are read from
- Updating environment variable names / adding environment variables
- Remapping ports / networking
- Adding scripts that must be run for certain functionality to continue working. Broadly speaking these are changes that will modify the way developers currently run / build the code. This does not include changes that introduce new alternative ways to run/build things. Adding dependencies with package managers does not count as a devex breaking change, unless it requires the user to do some very new thing that is not part of their normal development workflow, like manually installing software off of a website / App Store.

#### Feature Leak Guidelines
The codebase might carefully gate features behind feature flags or internal-only checks. You MUST NOT allow any features that are meant to be behind a feature gate leak. These leaks are often subtle. Be VERY careful and thorough.

#### Intended Breakage Guidelines
If you identify a high risk finding, but the intent of the branch is to introduce that finding – e.g. break some functionality, remove a feature flag, remove a safeguard – AND the scope of the change is well constrained, you SHOULD NOT waste the author's time by reporting the issue to them. However, if you believe it is likely that they are not aware of the full implications of their change, or you are worried that they are under-weighting the negative impacts (extreme example: a developer pushes a PR titled "Delete the database"), or you are worried that the change is actually malicious, you should still report the finding.

#### Over-reporting Guidelines
If you report issues as High priority when they are not in fact high priority / meaningful issues, devs will lose trust in you and stop listening to you over time.
NEVER misreport the priority / importance of issues. Be extremely thorough in tracing issues end-to-end to gain complete, and total confidence before reporting.

### Final Response
IF you have medium-to-high priority / risk findings, and there is a PR for this branch, then check the PR/MR discussion using gh/glab cli to see if there are comments from a review bot or others present.
If so, take their findings into account. If they found issues you missed, evaluate them to determine if they are valid and include them in your report. If they found some of the same issues you did, see if there is anything from their findings that are worth incorporating into your response.
Flag issues found by a review bot or others in the PR/MR discussion that you include in your report.


### Critical Rules
- NEVER present issues with unfinished research. E.g. Never say something like, "The client has issue X, but if handled in the backend then this is ok." if you have access to the backend code and can check for yourself.
- You MUST wait to check the PR/MR discussion until AFTER you have performed your audit. This way you have fresh eyes while you review.
- Be EXTREMELY thorough, rigorous, careful, ambitious, and attentive. NOTHING can slip through.
