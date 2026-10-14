# pstack ports compared

Checked on **2026-10-14** against each repo's default branch. Every cell comes from a file at the commit listed below, a command run that day, or the GitHub API. ✅ meets the point, ⚠️ partly or not specified, ❌ fails it (shown by a run or by the code path), — not a goal of that repo. jutsu is held to the same bar: a ❌ needs a shown failure, and a point a repo does not address is ⚠️, not ❌.

A search on 2026-10-14 found 311 public pstack ports. These are the 10 closest to jutsu: every T3 Code port with real use or a distinct technique, and the largest Claude Code ports.

| Repo | Commit | Date (UTC) |
|---|---|---|
| [pstack](https://github.com/cursor/plugins/tree/main/pstack) (original) | `ce649c0` (0.15.23) | 2026-10-14 |
| [**sergchil/jutsu**](https://github.com/sergchil/jutsu) (this repo) | 0.2.0 | 2026-10-14 |
| [creedants/pstack-t3](https://github.com/creedants/pstack-t3) | `6da5eb3` | 2026-10-14 |
| [waffleflopper/p3-stack](https://github.com/waffleflopper/p3-stack) | `fc4a5fb` | 2026-10-09 |
| [uzairansaruzi/p3-stack](https://github.com/uzairansaruzi/p3-stack) | `09909eb` | 2026-10-05 |
| [pmwoz/t3-pstack](https://github.com/pmwoz/t3-pstack) | `0f329b4` | 2026-10-14 |
| [chhoumann/t3-pstack](https://github.com/chhoumann/t3-pstack) | `5c3f2fa` | 2026-10-13 |
| [mariusflorescu/pstack-t3](https://github.com/mariusflorescu/pstack-t3) | `564759a` | 2026-10-14 |
| [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude) | `94f5ce9` (0.9.84) | 2026-10-14 |
| [ericlitman/open-pstack](https://github.com/ericlitman/open-pstack) | `40d506c` | 2026-10-13 |
| [backnotprop/pstack](https://github.com/backnotprop/pstack) | `1f0f9c3` | 2026-10-14 |

## T3 Code ports

| Point | **jutsu** | creedants pstack-t3 | waffle p3-stack | uzair p3-stack | pmwoz t3-pstack | chhoumann t3-pstack | marius pstack-t3 |
|---|---|---|---|---|---|---|---|
| Runs in | Claude Code in T3, plain Claude Code too | T3: Claude, Codex, Grok, Cursor | T3: Claude, Codex | T3 providers that read `~/.agents/skills` | T3: Claude, Codex | T3: Claude, Codex | T3: Claude, Codex |
| Built from pstack | 0.15.23 (`port/upstream.json`) | 0.15.23 | 0.15.15 | about 0.15.10 (no pin) | 0.15.23 (`pins.json`) | 0.15.21, through pstack-claude | 0.15.23 (`UPSTREAM`) |
| Upstream skills present, of 53 | 52: `make-bot-ui` left out, it builds Cursor automations | 53 | 51 at 0.15.15: no `ketchup` | 51 at ~0.15.10: no `ketchup` | 53 | 51: no `in-your-own-words`, `make-bot-ui` | 53 |
| Claude in T3 finds the skills after install | ✅ links every enabled T3 Claude instance, `homePath` included | ⚠️ ignores a T3 instance's `homePath` (`scripts/install.py`) | ✅ | ❌ links only `~/.agents/skills`, which Claude does not read ([issue #2](https://github.com/uzairansaruzi/p3-stack/issues/2)) | ✅ Claude plugin (`README.md:16`) | ✅ Claude plugin (`README.md:15`) | ✅ `~/.claude/skills` link (`README.md:11`) |
| Mode stays on: every turn, after compaction, after a fork | ✅ hooks on prompt expansion, prompt submit, session start, and subagent start (`plugin/hooks/hooks.json`) | ⚠️ no hooks; the per-turn reminder is dropped (`scripts/build.py:27`) | ⚠️ a forked thread loses it (`hooks/install.py:22-26`) | ⚠️ no hooks | ⚠️ session start only: startup, clear, compact (`hooks/hooks.json`) | ⚠️ session start only: startup, resume, clear, compact | ⚠️ no hooks |
| The router can reach the other skills under Claude | ✅ reads them by path | ✅ | ❌ 50 of 51 skills set `disable-model-invocation: true`, which Claude's Skill tool refuses | ❌ same as waffle | ✅ reads them by path (`t3-adapter.md:17`) | ✅ skills stay model-invocable | ✅ reads them by path (`T3-NATIVE.md:41`) |
| Uses T3's own tools (threads, PR watch, schedules, browser, simulator) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ through T3's MCP tools | ✅ |
| Each parallel writer gets its own worktree | ✅ worktree from HEAD per writer | ✅ | ❌ owners share one checkout (`autopilot-full.md:11-12`) | ❌ same as waffle | ✅ the parent adds a worktree per writing lane (`t3-adapter.md:64`) | ✅ `t3_thread_launch` worktree per PR owner (`t3-tools.md:122`) | ⚠️ `delegate_task` writers share the checkout and split files; a launched thread gets a worktree (`T3-NATIVE.md:67`) |
| `delegate_task` calls carry a retry key (`clientRequestId`) | ✅ | ✅ | ❌ 0 of 40 files | ❌ 0 of 40 files | ✅ | ✅ | ✅ |
| Launched T3 threads start from a commit SHA | ✅ | ⚠️ from a branch name | ⚠️ not specified | ⚠️ not specified | ⚠️ from a ref; read-only lanes from a SHA (`t3-adapter.md:64-66`) | ⚠️ from `baseRef` (`t3-tools.md:122`) | ⚠️ `baseRef` is a commit or a branch (`T3-NATIVE.md:67`) |
| A merge wait has a heartbeat (a merge never wakes a T3 watch) | ✅ | ✅ | ⚠️ waits for a merge wake (`shipping.md:14`) | ⚠️ same as waffle | ✅ `schedule_task` fallback (`t3-adapter.md:83`) | ⚠️ holds the watch under `/loop` (`shipping.md:15`); no T3 schedule | ✅ `schedule_task` fallback (`shipping.md:14`) |
| Update technique | Vendor copy, sha256-locked overrides, exact substitutions; the sync 3-way merges each touched override; a reason per override; weekly upstream PR and weekly T3 tool-list PR | Vendor copy, sha256-locked overrides, 3-way `--merge` (`scripts/sync_upstream.py:10-17`) | ⚠️ by hand | ⚠️ by hand | Verbatim snapshot, 9 declared drift files with reasons (`drift.json`), 3-way merge (`tools/sync.ts`), pinned T3 contract snapshot (`tools/t3.ts`) | `git merge` from pstack-claude | Hand port against a written contract (`T3-NATIVE.md`) and a regex checker |
| [#449](https://github.com/cursor/plugins/issues/449): cleanup keeps untracked and ignored files | ✅ both held (`tests/test_worktree_audit.py`) | ❌ both bucketed safe (fixture run); playbook says `--force` and `rm -rf` (`worktree-cleanup.md:9`) | ❌ `worktree-audit.sh:116`, `worktree-cleanup.md:9` | ❌ `worktree-cleanup.md:9`; no audit script | ❌ both bucketed safe (fixture run); `worktree-cleanup.md:7` | ⚠️ untracked held, ignored bucketed safe (fixture run) | ❌ both bucketed safe (fixture run) |
| [#470](https://github.com/cursor/plugins/issues/470): closed-PR or unpushed work is not called safe | ✅ (`tests/test_worktree_audit.py`) | ❌ closed PR and closed-PR-plus-local-commits bucketed safe (fixture run, `worktree-audit.sh:443`) | ❌ (`worktree-audit.sh:116`) | — no audit script | ❌ bucketed safe (fixture run) | ✅ bucketed review (fixture run) | ❌ bucketed safe (fixture run) |
| A PR in a repo with no CI gets a verdict ([PR #510](https://github.com/cursor/plugins/pull/510)) | ✅ after 60 s with no checks (`watch-pr/policy.test.ts`) | ❌ `resolveChecks` throws on an empty check list, same code as upstream | — no watch-pr | — no watch-pr | ❌ same code as upstream | ✅ handles gh's "no checks reported" (`watch-pr/github.ts`); not run | ❌ same code as upstream |
| Tests | 95 Python + 85 bun pass | 40 test files (suite over 3 min, not run) | 21 pass, 1 skip | none | `bun run check` + 22 pass | 55 test files (not run) | checker 54/54 clean; no unit tests of its own |
| Uninstall | ✅ `./uninstall.sh` | ✅ | ✅ | ❌ | ✅ Claude's plugin manager | ✅ Claude's plugin manager | ⚠️ not documented |
| Adds scope beyond pstack | none | `brigade`, `landing`, light mode, 4 provider harnesses | Codex hooks | none | 3 cursor-team-kit skills, Codex | Codex, cursor-team-kit and thermos skills | `deslop`, Codex |

## Claude Code ports, and upstream

| Point | pstack | **jutsu** | pstack-claude | open-pstack | backnotprop pstack |
|---|---|---|---|---|---|
| Runs in | Cursor | Claude Code in T3, plain Claude Code too | Claude Code, Codex, Pi, Copilot, OpenCode, Gemini, Prime | Claude Code and Codex, with Grok lanes | Claude Code, Codex, Pi (plain skills folder) |
| Built from pstack | 0.15.23 | 0.15.23 | 0.15.21 (`tools/upstream.json`) | 0.15.20 (`UPSTREAM.md:12`) | 0.15.23 (commit `1f0f9c3`) |
| Upstream skills present, of 53 | 53 | 52 | 51: no `in-your-own-words`, `make-bot-ui` | 51: no `in-your-own-words`, `make-bot-ui` | 53 |
| Mode stays on | ✅ Cursor Custom Mode | ✅ mode hook | ⚠️ session start only (`hooks.json`) | ⚠️ session start only: startup, clear, compact | ⚠️ no hooks |
| Each parallel writer gets its own worktree | ✅ Cursor cloud agents | ✅ | ✅ `isolation: "worktree"` (`skills/swarm/SKILL.md`) | ⚠️ a worktree for Codex and external lanes; not stated for Claude lanes (`provider-dispatch.md:38-46`) | ⚠️ not specified for Claude (`poteto-mode/SKILL.md:105`) |
| Update technique | — | see above | Generated tree, 3-way `git merge-file` (`tools/sync.mjs`), every fork declared with a reason (`tools/forks.json`) | Audit JSON, then upstream blob or `git merge-file` per file (`scripts/upstream-merge.py`); a ledger of upstream commits not applied (`UPSTREAM.md`) | An `upstream` branch that mirrors Cursor's files, merged into `main` (`MIRROR.md`) |
| #449: keeps untracked and ignored files | ❌ both bucketed safe (fixture run); `worktree-cleanup.md:7` | ✅ | ⚠️ untracked held, ignored bucketed safe (fixture run); `worktree-cleanup.md:7` keeps `--force` and `rm -rf` | ❌ both bucketed safe (fixture run) | ❌ both bucketed safe (fixture run) |
| #470: closed-PR or unpushed work is not called safe | ❌ bucketed safe (fixture run) | ✅ | ✅ bucketed review (fixture run) | ❌ bucketed safe (fixture run) | ❌ bucketed safe (fixture run) |
| A PR in a repo with no CI gets a verdict | ❌ `resolveChecks` throws (`watch-pr/github.ts`); fix open as PR #510 | ✅ | ✅ handles "no checks reported" (`watch-pr/github.ts`); not run | ❌ same code as upstream | ❌ same code as upstream |
| Tests | 68 bun pass | 95 Python + 85 bun pass | 51 test files (not run; 1,187 passed on 2026-10-11 at `5f07f5e`) | 24 test files (not run) | upstream's 5 bun test files only |
| Uninstall | Cursor's plugin manager | ✅ `./uninstall.sh` | ✅ `claude plugin uninstall` | ✅ Claude's plugin manager | ⚠️ not documented |
| Adds scope beyond pstack | — | none | 6 more runtimes, extra skills | cross-provider routing and failover, extra skills | harness-neutral rewrites of some skills |

[#471](https://github.com/cursor/plugins/issues/471) (only 100 review threads read) is fixed upstream since 0.15.23 ([PR #484](https://github.com/cursor/plugins/pull/484)), so it is no longer a row. jutsu keeps two extra cursor guards on top of that fix.

## Technique: what jutsu took, and from whom

jutsu 0.2.0 adopted these after reading the ports above. Each is credited in [NOTICE.md](../NOTICE.md).

- **3-way merge on upstream sync** (`tools/sync_upstream.py`): michael-denyer/pstack-claude (`tools/sync.mjs`), creedants/pstack-t3 (`--merge`), pmwoz/t3-pstack (`tools/sync.ts`), ericlitman/open-pstack (`scripts/upstream-merge.py`). jutsu keeps its sha256 lock on top, so a clean merge still fails the build until a person reviews and relocks it.
- **A reason per override** (`port/overrides.json`): pstack-claude's `forks.json` and pmwoz's `drift.json`.
- **Fail on an override that matches upstream**: pmwoz (`tools/check.ts:30`). **Fail on conflict markers**: pstack-claude's generator.
- **Checker rules that test themselves** (`tools/check.py`): janrizmlibres/claude-pstack (idea only).
- **T3 tool list generated from pinned T3 source** (`tools/t3_tools.py`, `port/t3.json`, weekly T3 PR): pmwoz (`tools/t3.ts`).
- **Upstream commit list in the sync PR**: meganemura/pstack-portable.
- **watch-pr on a repo with no CI**: upstream PR #510 by izeigerman, also fixed in pstack-claude. jutsu adds a 60 s wait before it calls a PR with no checks ready, for the premature READY that Cursor Bugbot found in #510.
- **Mode from `$jutsu` text and `skill://` links**: waffleflopper/p3-stack's prompt hook.
- **A `SubagentStart` hook for poteto-agent children**: Aqua-123/pstack-for-codex; the need was measured in pstack-claude issue #264.
- **Never `t3_worktree_handoff`, and the zsh separator rule**: pmwoz.
- **Async delegate waves, then `t3_thread_wait` per child**: osmelmora/p3-executor.
- **`gh -R <owner>/<repo>` for PRs from forks**: mdsmithaustin/pstack.
- **A probe date on each host fact**: mariusflorescu/pstack-t3.
- **Slash-only skill descriptions**: upstream issue #367 and PR #519.

Where others still do better: pmwoz keeps 9 drift files where jutsu keeps 52 whole-file overrides, so jutsu reviews more per upstream release. pstack-claude and open-pstack cover more runtimes. jutsu targets Claude Code only.

## Known gaps in jutsu

- 0.2.0 has not been rerun in the T3 desktop app. Its live run used Claude Code headless in stream-json mode, the mode T3 uses ([TESTED.md](TESTED.md)). The 0.1.0 T3 runs still stand for what did not change.
- The no-CI `watch-pr` path is tested with fake GitHub replies, not on a real repo without CI.
- To tell "no CI" from "checks not registered yet", `watch-pr` looks for a check rollup on the PR's last 50 commits only. On a longer PR, checks on older commits are not seen.
- `worktree-audit.sh` uses `awk`. It was not tested with mawk.
- `watch-pr` reading past 100 review threads is tested with fake GitHub pages, not on a real PR that has more than 100 threads.
- Worktree isolation is a rule in each brief, not something T3 enforces. Most ports above work the same way.
- The automated tests cover the build, checks, hooks, installer, and bundled scripts, not whole playbooks.
- New repo: no stars, forks, or outside issues yet.

## How to re-check

Clone each repo at the commit above. The "fixture run" cells come from jutsu's own `tests/test_worktree_audit.py` pointed at each repo's `worktree-audit.sh` (or `.mjs`): 15 real worktrees in a real git repo, with a stub `gh` that lists closed and merged PRs. creedants holds every worktree active in the last 4 days as `verify-recent`, so it ran with `RECENT_DAYS=-1`. waffle's script holds every new worktree the same way, so its cells cite the code. The "same code as upstream" cells mean the repo's `resolveChecks` in `watch-pr/github.ts` is byte-identical to upstream's, which throws when a PR has no checks. Skill counts compare each repo's skill and principle names with upstream 0.15.23's 53. Counts of `clientRequestId` are `grep -rl` over the files each repo installs.
