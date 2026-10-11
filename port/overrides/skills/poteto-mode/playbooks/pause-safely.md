### Pause safely

**You own a clean stop. Leave a checkpoint a cold-start agent can resume from.** This is explicit only. On "keep going", "going to bed, keep going", or "don't stop", do not pause.

1. Stop at a safe boundary. Finish the current atomic step or back out of it. Start nothing new, and cancel any nested subagents: stop each one (`task_cancel` for a `delegate_task` child) and confirm with `git status` that nothing still writes, since `completed` in the agent list means notified, not exited ([the runtime's Subagents](../references/runtime.md#subagents)). In T3, also pause the wakes this work owns, so none fires into the paused thread: `update_scheduled_task` with `enabled: false` for each of its schedules (`list_scheduled_tasks`), and `unwatch_pull_request` for each pull request it watches ([the runtime's Waking](../references/runtime.md#waking)). List them in the resume note.
2. Take no irreversible action to pause. No PR and no push unless you already had one out.
3. Make the work durable. Commit uncommitted edits as one clear `wip:` commit on the current branch so nothing is lost. If the tree is broken, say so in the commit body in one line.
4. Write the resume note off-context. Capture intent, what you were doing, progress and what's verified, current state, next steps, key files, and gotchas. Write it to `.jutsu/<slug>/resume.md` at the repo root ([the runtime's Store](../references/runtime.md#store)), so it survives compaction and a T3 or session restart. Report the note's absolute path in your reply, since a pickup in another worktree cannot find an uncommitted file by a relative path. If a show-me-your-work trail exists, point at it instead of duplicating it.

**Reply:** where you are in the loop, what's on disk versus still in your head (paths, no diff dumps), the commits you made and whether the tree is clean, and the first action on resume. This is a pause, not a final report.
