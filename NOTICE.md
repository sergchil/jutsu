# Notices

jutsu is a port. The skills, principles, and language are Lauren Tan's (poteto). The Claude Code and T3 Code wiring is this repo's.

- **pstack** by Lauren Tan, MIT. Upstream: https://github.com/cursor/plugins/tree/main/pstack. Vendored unchanged in `vendor/pstack/` with its own `LICENSE`.
- Ideas and fixes adapted from other ports, all MIT:
  - **pstack-claude** by Michael Denyer (https://github.com/michael-denyer/pstack-claude): Claude Code rule fixes found in real runs, effort per subagent, the substitution-and-fork sync design, the stuck-cursor guard for review threads, counting a merged PR only for the commit it merged, and (0.4.0) the build and cache folder list, `hold-reflog`, and `hold-locked` in the worktree audit, a verified pause checkpoint (after its `resume.mjs`), clearing auto-merge and the merge queue before a restack (after its `ship-pr` and merge-safety reference), the router adherence count (its issue #264), the marketplace install, and the thermos skills it bundles.
  - **pstack-t3** by creedants (https://github.com/creedants/pstack-t3): T3 tool semantics, worktree isolation for delegated writers, the vendor-plus-overrides build with hash locks, and the 3-way merge on upstream sync.
  - **p3-stack** by waffleflopper and Uzair Ansar (https://github.com/waffleflopper/p3-stack, https://github.com/uzairansaruzi/p3-stack): a provider hook that keeps the mode on, turning it on from `$` text and `skill://` links, and per-instance Claude config dirs from T3's settings.
  - **open-pstack** by Eric Litman (https://github.com/ericlitman/open-pstack): the 3-way upstream merge script.
  - **t3-pstack** by pmwoz (https://github.com/pmwoz/t3-pstack): failing the build on an override that matches upstream, generating the T3 tool list from a pinned T3 snapshot, and the `t3_worktree_handoff` and zsh separator rules.
  - **p3-executor** by osmelmora (https://github.com/osmelmora/p3-executor): launching short delegate waves async and waiting on each child in the same turn.
  - **pstack-for-codex** by Aqua-123 (https://github.com/Aqua-123/pstack-for-codex): a subagent-start hook that hands poteto-agent children the mode.
  - **pstack** by mdsmithaustin (https://github.com/mdsmithaustin/pstack): passing `-R <owner>/<repo>` to `gh` for pull requests from forks.
  - **pstack-t3** by mariusflorescu (https://github.com/mariusflorescu/pstack-t3): a probe date on each host fact.
  - Ideas only, no code: **claude-pstack** by janrizmlibres (https://github.com/janrizmlibres/claude-pstack, no license file), checker rules that test themselves; **pstack-portable** by meganemura (https://github.com/meganemura/pstack-portable), a commit list in each upstream sync.
- **thermos** by Cursor (https://github.com/cursor/plugins/tree/118e73b0e196e4d49d5aade7ce6dd8985a621f68/thermos, MIT, (c) 2026 Cursor): the `thermo-nuclear-review` skill, adapted to run as one read-only Claude Code reviewer. Its license is `plugin/skills/thermo-nuclear-review/LICENSE-thermos`. Found through pstack-claude, which bundles it.
- Open fix pull requests in cursor/plugins, under pstack's MIT license: [#492](https://github.com/cursor/plugins/pull/492) by deanrie (for #470), [#484](https://github.com/cursor/plugins/pull/484) by Yi-111-a (for #471, since merged), [#510](https://github.com/cursor/plugins/pull/510) by izeigerman (no-CI pull requests), with a guard for the premature READY that Cursor Bugbot found in it, and [#519](https://github.com/cursor/plugins/pull/519) (for #367, slash-only skill descriptions).
- Upstream's own Claude Code adapter (`docs/harness/claude-code.md`, cursor/plugins [#637](https://github.com/cursor/plugins/pull/637) and [#705](https://github.com/cursor/plugins/pull/705)): the models file in Claude Code's `rules/` folder and the `Skipped in Claude Code:` line.
- **T3 Code** by Ping Labs (https://github.com/pingdotgg/t3code, MIT) is the host this port targets. `tools/t3-tools.txt` lists its MCP tool names.
