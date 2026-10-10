### Authoring or modifying a skill

**You own the skill's voice.**

1. Write it as a Claude Code skill: a `SKILL.md` in a directory named for the skill, under `.claude/skills/` for a project or `$CLAUDE_CONFIG_DIR/skills/` (default `~/.claude/skills/`) for the user. Keep `name` equal to the directory name. The skill listing truncates `description` plus `when_to_use` at 1,536 characters. Quote a `description` that starts with a backtick. `disable-model-invocation: true` takes the skill out of the model's listing and the Skill tool, so only the user runs it and an agent reads it by path. `user-invocable: false` hides it from the `/` menu and T3's picker. A `commands/` file with the same name is ignored in favor of the skill, so do not add one. Claude Code's `skill-creator` plugin helps with evals when installed.
2. Validate the skill: frontmatter has `name` and `description`, referenced files exist, cross-skill links resolve.
3. Test cases if structural. Skip if subjective.
4. Run **Opening a PR**.

When in doubt, delete. Keep only prose that changes a decision. Tell it to do the thing and skip the reason. Explain only when the rule is confusing without one. Match tone to scope. Point at structural sources (types, READMEs, config) per the **encode-lessons-in-structure** principle skill (`../../../principles/principle-encode-lessons-in-structure.md`). Delegate to other skills by path. Don't restate. A workflow you keep hitting but isn't captured → propose a new skill.

**Reply:** summary of the skill, key design decisions, validation notes.
