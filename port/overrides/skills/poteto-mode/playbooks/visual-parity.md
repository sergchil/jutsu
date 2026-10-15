### Visual parity

**You own pixel-exact equivalence. The baseline is the spec. You do not touch it.** Equivalence is verified by image diff, not by eye.

1. Establish the baseline first, before any migration: a visual regression harness that screenshots the current component across its states, plus the target when matching two implementations. No baseline, no parity claim. A blocking prerequisite, not a follow-up. When the harness captures through T3's preview, pin the viewport with `preview_resize` and the theme with `preview_set_appearance`, so every capture runs under the same conditions. T3 has no image-diff tool, so the harness brings its own differ.
2. Anti-shortcut clauses, stated and held: no harness modifications, no baseline tampering, no component restructuring to make a diff pass. If the baseline looks wrong, stop and ask, don't edit it.
3. Migrate one component at a time. Parallelize with one owner per component, each in its own checkout per [the runtime's Isolation](../references/runtime.md#isolation). In T3 that is `delegate_task` with `isolation: "worktree"`, so commit first. Outside T3, remove each worktree you made once its component lands (the **separate-before-serializing-shared-state** principle skill, `{{plugin}}/principles/principle-separate-before-serializing-shared-state.md`). Shared primitives migrate first as a blocking phase.
4. Verify each component against its baseline via image diff on the matching surface per [the runtime's Proof surfaces](../references/runtime.md#proof-surfaces). A nonzero diff is a fail. Investigate the pixel delta. Loop per component until the diff is zero, with a wake from [the runtime's Waking](../references/runtime.md#waking) when the loop outlives your turn.
5. Run **Opening a PR** per component or per safe batch.

**Reply:** components migrated, the diff result for each, the baseline harness location, what's left.
