---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
disable-model-invocation: true
---

# How

Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

Each spawn below names a role line in `p3-models.md` and its default in [the runtime's Roles](../../skills/poteto-mode/references/runtime.md#roles). Set `model` and `effort` from that line, or from the default if the file or the line is missing. Omit both when the value is `inherit`. If the `Agent` tool rejects a value, use the default and say so. A line that names a T3 target runs that spawn through `delegate_task` per [the runtime's Subagents](../../skills/poteto-mode/references/runtime.md#subagents). Pass `options` with `effort` on every call and a distinct `clientRequestId` per call, and read the result with `task_status` after the wake.

## Step 1. Assess Complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): no explorers. One explainer explores and explains in a single pass. Go to Step 2b.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): spawn parallel explorers first, then hand off to the explainer. Go to Step 2a.

When in doubt, take the simple path.

## Step 2a. Explore (complex questions only)

Decompose the question into 2 to 4 exploration angles, each a distinct slice of the subsystem. Spawn all explorers in a single message:

- `subagent_type`: `Explore`, with search breadth `very thorough`
- `model` and `effort`: the `how explorer` line
- a read-only brief, which the explorer prompt carries

Each explorer gets the prompt in `references/explorer-prompt.md` with its angle filled in. Then go to Step 3.

## Step 2b. Direct Explain (simple questions)

Spawn one `Agent` subagent that explores and explains in one pass:

- `subagent_type`: `general-purpose`
- `model` and `effort`: the `how explainer` line
- a read-only brief, which the explainer prompt carries

Build its prompt from `references/explainer-prompt.md` without the explorer-findings section. Go to Step 4.

## Step 3. Synthesize (complex questions only)

Once all explorers have returned, spawn one `Agent` subagent to synthesize their findings into one explanation:

- `subagent_type`: `general-purpose`
- `model` and `effort`: the `how explainer` line
- a read-only brief, which the explainer prompt carries

Build its prompt from `references/explainer-prompt.md` with every explorer's findings filled in.

## Step 4. Present

Present the explainer's output to the user. Light edits for clarity or context from the conversation are fine. Do not substantially rewrite it.

## Output Format

The explanation uses the sections defined in `references/explainer-prompt.md`, dropping any that do not apply: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
