# pstack ports compared

Checked on **2026-10-11** against each repo's default branch. Every cell comes from a file at the commit listed below, a command run that day, or the GitHub API. ✅ meets the point, ⚠️ partly, ❌ does not, — not a goal of that repo.

| Repo | Commit | Date (UTC) |
|---|---|---|
| [pstack](https://github.com/cursor/plugins/tree/main/pstack) (original) | `978ca6e` (0.15.17) | 2026-10-10 |
| [**sergchil/jutsu**](https://github.com/sergchil/jutsu) (this repo) | `main` | 2026-10-11 |
| [creedants/pstack-t3](https://github.com/creedants/pstack-t3) | `a9fca20` | 2026-10-11 |
| [waffleflopper/p3-stack](https://github.com/waffleflopper/p3-stack) | `fc4a5fb` | 2026-10-09 |
| [uzairansaruzi/p3-stack](https://github.com/uzairansaruzi/p3-stack) | `09909eb` | 2026-10-05 |
| [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude) | `5f07f5e` (0.9.81) | 2026-10-10 |

## The points, with evidence

| Point | pstack | **jutsu** | pstack-t3 | waffle | uzair | pstack-claude |
|---|---|---|---|---|---|---|
| Runs in | Cursor | Claude Code in T3, plain Claude Code too | T3: Claude, Codex, Grok, Cursor | T3: Claude, Codex | T3 providers that read `~/.agents/skills` | Claude Code, Codex, Pi, Copilot |
| Built from pstack | 0.15.17 | 0.15.17 | 0.15.17 | 0.15.15 | about 0.15.10 (no pin) | 0.15.15 |
| Upstream skills present, of 52 | 52 | 51: `make-bot-ui` left out, it builds Cursor automations | 52 | 51: no `ketchup` | 51: no `ketchup` | 50: no `ketchup`, `make-bot-ui` |
| Claude in T3 finds the skills after install | — | ✅ links every enabled T3 Claude instance | ⚠️ ignores a T3 instance's `homePath` (`scripts/install.py:38-47`) | ✅ | ❌ links only `~/.agents/skills`, which Claude does not read ([issue #2](https://github.com/uzairansaruzi/p3-stack/issues/2)) | ✅ as a plugin; not in T3's `$` picker |
| Mode stays on: every turn, after compaction, after a fork | ✅ Cursor Custom Mode | ✅ mode hook (`plugin/hooks/jutsu-mode`) | ❌ no hooks; the per-turn reminder is dropped (`scripts/build.py:27`) | ⚠️ a forked thread loses it (`hooks/install.py:22-26`) | ❌ no hooks | ⚠️ session start only (`hooks.json:5`) |
| The router can reach the other skills under Claude | — | ✅ reads them by path | ✅ | ❌ 50 of 51 skills set `disable-model-invocation: true`, which Claude's Skill tool refuses | ❌ same as waffle | ✅ |
| Uses T3's own tools (threads, PR watch, schedules, browser, simulator) | — | ✅ | ✅ | ✅ | ✅ | — |
| Each parallel writer gets its own worktree | ✅ Cursor cloud agents | ✅ worktree from HEAD per writer | ✅ | ❌ owners share one checkout (`autopilot-full.md:11-12`) | ❌ same as waffle | ✅ `isolation: "worktree"` |
| `delegate_task` calls carry a retry key (`clientRequestId`) | — | ✅ | ✅ | ❌ 0 of 40 files | ❌ 0 of 40 files | — |
| Launched T3 threads start from a commit SHA | — | ✅ | ⚠️ from a branch name | ⚠️ not specified | ⚠️ not specified | — |
| A merge wait has a heartbeat (a merge never wakes a T3 watch) | — | ✅ | ✅ | ⚠️ waits for a merge wake (`shipping.md:14`) | ⚠️ same as waffle | — |
| Upstream update: sync script, per-file drift check, CI | — | ✅ weekly upstream PR that lists what to port | ⚠️ 2 rewritten files not drift-checked | ❌ | ❌ | ✅ |
| Tests | 52 pass | 50 pass | 1,931 (suite over 3 min, not run) | 21 pass, 1 skip | none | 1,187 pass, 40 skip |
| Uninstall | Cursor's plugin manager | ✅ `./uninstall.sh` | ✅ | ✅ | ❌ | ✅ `claude plugin uninstall` |
| Adds scope beyond pstack | — | none | `brigade`, `landing`, light mode, 4 provider harnesses | Codex hooks | none | 3 more runtimes, 8 extra skills |

## Known gaps in jutsu

- Three open upstream bugs ship unchanged, as they do in every port that keeps upstream's scripts: [#449](https://github.com/cursor/plugins/issues/449) (worktree cleanup treats untracked files as disposable), [#470](https://github.com/cursor/plugins/issues/470) (the worktree audit marks closed, unmerged PRs as safe), [#471](https://github.com/cursor/plugins/issues/471) (`watch-pr` reads only the first 100 review threads). pstack-claude has fixed #449 and #471.
- Worktree isolation is a rule in each brief, not something T3 enforces. pstack-t3 works the same way.
- The live tests in [TESTED.md](TESTED.md) were run by hand. The automated tests cover the build, checks, mode hook, installer, and bundled scripts, not whole playbooks.
- New repo: no stars, forks, or outside issues yet.

## How to re-check

Clone each repo at the commit above. Counts of T3 tool use and of `clientRequestId` are `grep -rl` over the files each repo installs. The skill count compares each repo's installed skill names with upstream 0.15.17's 52 skills.
