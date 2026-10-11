# Security policy

## Report a problem

Report it privately through GitHub: [Security, then Report a vulnerability](https://github.com/sergchil/jutsu/security/advisories/new). Only the maintainer sees the report. Please don't open a public issue for a security problem.

Fixes go to the latest version on `main`.

## What jutsu runs on your machine

- **Install and uninstall.** `install.sh` reads T3 Code's settings to find Claude Code's config folders, then adds one link, `skills/jutsu`, to each. `uninstall.sh` removes those links, jutsu's session state, and the models file that `/jutsu:setup-pstack` wrote. Neither script edits `settings.json`.
- **The mode hook** (`plugin/hooks/jutsu-mode`) runs on each prompt. It reads the session id, and after a fork, resume, or compaction it reads the session's transcript. It keeps one small file per session in Claude Code's plugin data folder and deletes its own files after 30 days. It makes no network calls.
- **The bundled scripts** (`watch-pr`, `orch`, `worktree-audit.sh`) run only when a playbook calls them, with your permissions. They reach the network only through `git`, `gh`, or `gt`, with your own login. On first run, `bun install --frozen-lockfile` downloads their pinned packages from npm.
- **No telemetry.** jutsu has no server and collects nothing. Claude Code and T3 Code decide what Claude may do, under your permission settings.
