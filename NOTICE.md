# Notices

jutsu is a port. The skills, principles, and language are Lauren Tan's (poteto). The Claude Code and T3 Code wiring is this repo's.

- **pstack** by Lauren Tan, MIT. Upstream: https://github.com/cursor/plugins/tree/main/pstack. Vendored unchanged in `vendor/pstack/` with its own `LICENSE`.
- Ideas and fixes adapted from other ports, all MIT:
  - **pstack-claude** by Michael Denyer (https://github.com/michael-denyer/pstack-claude): Claude Code rule fixes found in real runs, effort per subagent, the substitution-and-fork sync design, the stuck-cursor guard for review threads, and counting a merged PR only for the commit it merged.
  - **pstack-t3** by creedants (https://github.com/creedants/pstack-t3): T3 tool semantics, worktree isolation for delegated writers, the vendor-plus-overrides build with hash locks.
  - **p3-stack** by waffleflopper and Uzair Ansar (https://github.com/waffleflopper/p3-stack, https://github.com/uzairansaruzi/p3-stack): a provider hook that keeps the mode on, and per-instance Claude config dirs from T3's settings.
- Open fix pull requests in cursor/plugins, under pstack's MIT license: [#492](https://github.com/cursor/plugins/pull/492) by deanrie (for #470) and [#484](https://github.com/cursor/plugins/pull/484) by Yi-111-a (for #471).
- **T3 Code** by Ping Labs (https://github.com/pingdotgg/t3code, MIT) is the host this port targets. `tools/t3-tools.txt` lists its MCP tool names.
