# p3-stack

[pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan (poteto), ported to **Claude Code running inside [T3 Code](https://github.com/pingdotgg/t3code)**.

pstack turns an agent into an engineering team. One mode reads each request and routes it to a playbook (bug fix, feature, refactor, babysit a PR, overnight run, and 18 more). Principles ground each decision, and verification is strict enough that you can run work in parallel and trust the result. p3-stack keeps all of it. It changes only the mechanics, so each step uses what Claude Code and T3 actually have.

## What changes from Cursor

| pstack in Cursor | p3-stack in Claude Code + T3 |
|---|---|
| Custom Mode keeps `/poteto-mode` on | `/p3` turns it on. A plugin hook adds pstack's one-line reminder to every turn and re-points Claude at the router after compaction. `/p3 off` turns it off. |
| `Task` subagents with model slugs | Claude's `Agent` tool with a model alias and an `effort` level per role. Roles live in one table you can override with `/p3:setup-pstack`. |
| Cloud agents on their own VM | A git worktree from your HEAD for each writer. Long-lived PR owners are T3 threads launched with `t3_thread_launch` in their own worktree. |
| `/loop` polling for PR status | `watch_pull_request` wakes the thread on failed checks, comments, and conflicts. A `schedule_task` heartbeat covers merges, which do not wake a watch. |
| `/loop 1h` for overnight work | `schedule_task`, which survives a T3 restart. |
| `control-ui` and simulator skills | T3's `preview_*` browser tools and `device_*` simulators. |
| Mining Cursor transcripts | `t3_thread_read`, `t3_thread_search`, and Claude's own transcripts. |
| Second opinions from another vendor | A panel of opus, fable, and sonnet. `delegate_task` adds another T3 provider when you have one. |

Outside T3, in plain Claude Code, every step has a fallback, so p3 works there too.

## Requirements

- **Claude Code 2.1.292 or later** (`claude --version`). That release added the per-subagent `effort` the role table needs.
- **T3 Code nightly from 2026-10-03 or later** for the orchestration tools (`delegate_task`, `t3_thread_*`, `watch_pull_request`, `schedule_task`). T3 stable 0.0.45 has only the preview, device, and PR link tools. p3 still runs there and says which fallback it took.
- `git` and `python3` (3.9 or later). `gh` for pull requests. `bun` for the bundled `watch-pr` and `orch` scripts.

## Install

```sh
git clone https://github.com/sergchil/p3-stack.git
cd p3-stack
./install.sh
```

`install.sh` reads T3's provider settings and finds the Claude config dir of every Claude instance, the same way T3 does (`homePath`, else the instance's `CLAUDE_CONFIG_DIR`, else `~/.claude`). In each one it creates a single symlink, `skills/p3 -> <checkout>/plugin`. Claude Code loads that folder as the plugin `p3@skills-dir`, with its skills, agents, and hooks. The installer writes nothing else: no `settings.json` edits, no marketplace records.

Then start a new Claude thread in T3.

**Update:** `git pull`. The symlink picks up the new version.
**Check:** `./install.sh --status`.
**Uninstall:** `./install.sh --uninstall`. Add `--purge` to delete p3's per-session state too.

### Another pstack port installed?

Two routers in one session fight each other. The installer reports any enabled `pstack@…` plugin and any `poteto-mode` or `p3-mode` skill in each config dir, and prints the command to turn it off, for example:

```sh
claude plugin disable pstack@pstack-claude
```

To keep the other port everywhere else and turn it off for one repo only, commit this to the repo's `.claude/settings.json`:

```json
{ "enabledPlugins": { "pstack@pstack-claude": false } }
```

## Use

In a T3 thread with Claude:

```text
$p3 the checkout page double-charges on retry. repro first, then fix.
```

Pick `$p3` from the composer's skill menu, or type `/p3 <task>` at the start of the message. The mode stays on for the rest of the thread.

```text
/p3 off
```

Other entry points are plain commands: `/p3:setup-pstack` (pick models and effort per role), `/p3:poteto-help` (which skill fits), `/p3:how`, `/p3:why`, `/p3:interrogate`, `/p3:architect`, `/p3:arena`, `/p3:swarm`, `/p3:reflect`, and the rest of pstack's skills.

The guide that comes with pstack still applies: [prompting](plugin/skills/poteto-help/references/prompting.md) and [recipes](plugin/skills/poteto-help/references/recipes.md).

### Picking a T3 runtime mode

- **Approval required** asks before every write. Good for a first try.
- **Auto** and **Full access** approve tool calls without asking. p3 still pauses on its own before force-pushes, deploys, data deletion, and messages to customers. An unattended run (`im stepping away…`) needs one of these modes, because a child can never have more access than its parent.
- **Plan** works for read-only playbooks. T3 keeps Claude's plan and stops, so approve it and send the next message to continue.

## How it is built

```text
vendor/pstack/      upstream pstack, byte for byte (now 0.15.15)
port/spec.json      path moves and frontmatter rules
port/subs/*.json    small mechanical rewrites
port/overrides/     files rewritten for Claude + T3, pinned by upstream hash
port/added/         the runtime map, the mode hook, the /p3 alias, the manifest
plugin/             the generated plugin (committed, so install needs no build)
```

- Every skill is user-invoked (`disable-model-invocation: true`), and the 24 principles are plain files the router reads by path. Claude's skill list holds about 8,000 characters at a 200k context, and pstack's descriptions alone are about 11,000. This keeps them out of it.
- `plugin/skills/poteto-mode/references/runtime.md` is the single map from each Cursor mechanism to its Claude Code and T3 equivalent. Playbooks link to its sections instead of repeating them.
- [docs/PORTING.md](docs/PORTING.md) has the porting rules and the lessons from earlier ports that each override encodes.

```sh
python3 tools/build.py            # rebuild plugin/
python3 tools/build.py --check    # fail if plugin/ is stale
python3 tools/check.py            # static checks on plugin/
python3 -m unittest discover -s tests
python3 tools/sync_upstream.py    # pull a new pstack; the build then names each override to re-merge
```

## Credit

The skills, principles, and language are Lauren Tan's. The Claude Code and T3 wiring is this repo's, with ideas from the other ports listed in [NOTICE.md](NOTICE.md). MIT, see [LICENSE](LICENSE).
