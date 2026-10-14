# Updating from upstream pstack

jutsu keeps poteto's pstack byte for byte in `vendor/pstack/`. Everything Claude Code and T3 need lives beside it in `port/`. An update is a sync, a 3-way merge of each override upstream touched, and a short, explicit list of things to review.

## Automatic

`.github/workflows/upstream.yml` runs every Monday (or on demand from the Actions tab). When upstream changed, it opens a pull request on branch `upstream/pstack` with the new `vendor/`, the merged overrides, and a body that lists the upstream commits (each linked), the merge result per override, and every item to port. The CI check on that pull request stays red until each item is reviewed and relocked.

## Upstream bugs fixed here

These overrides carry fixes for upstream bugs. Their entries in `port/overrides.json` have `kind: upstream-bug` and the upstream link. When a sync touches one, it prints the link, and when `gh` says the issue or PR is closed it adds "upstream may have fixed this; drop our copy if so". Check whether upstream's fix covers ours. If it does, drop our copy of the fix from the override (or delete the override, its lock entry, and its `overrides.json` entry when nothing else is left in it), then relock.

| Upstream issue | Upstream fix | Override files under `port/overrides/skills/poteto-mode/` |
|---|---|---|
| [#449](https://github.com/cursor/plugins/issues/449): untracked and ignored files are deleted | none open | `scripts/worktree-audit.sh`, `playbooks/worktree-cleanup.md` |
| [#470](https://github.com/cursor/plugins/issues/470): closed-PR or unpushed work is called safe | [#492](https://github.com/cursor/plugins/pull/492) (open) | the same two files |
| [#471](https://github.com/cursor/plugins/issues/471): only 100 review threads are read | [#484](https://github.com/cursor/plugins/pull/484), merged 2026-10-12. jutsu keeps only its two extra cursor guards: fail closed on a missing `endCursor`, and stop on a repeated one | `scripts/watch-pr/github.ts` and `github.test.ts` |

`tests/test_worktree_audit.py` and `watch-pr/github.test.ts` pin the fixed behavior, and `tools/check.py` rejects `worktree remove --force` and `rm -rf` in any playbook, so an upstream change cannot bring a bug back silently.

## By hand

```sh
python3 tools/sync_upstream.py          # pull the latest pstack into vendor/, merge, and list what to port
```

For each override whose upstream file changed, the sync runs `git merge-file` with the old vendor file as base, the override as ours, and the new vendor file as theirs. It merges only when the old vendor file's sha256 equals the lock value. The output names each item:

- `merged cleanly, review then relock: port/overrides/<path>`: the merge is written. Read the upstream change (`git diff HEAD -- vendor/pstack/<file>`) and the merged override. A clean merge can still bring in a Cursor mechanism, so fix it in Claude and T3 terms (docs/PORTING.md), then `python3 tools/build.py --relock <path>`.
- `conflict (N), resolve the markers then relock`: the override is written with git's `<<<<<<<`, `=======`, `>>>>>>>` lines. The build fails on any marker line under `port/` or `plugin/`. Resolve each one, then relock.
- `not merged: the old vendor file does not match the lock`: the override was not merged against the upstream file the lock names. Re-merge it by hand, then relock.
- `merged into a copy of upstream`, or the build's `matches upstream; delete the override and its lock entry`: the override has nothing of ours left. Delete it, its lock entry, and its `overrides.json` entry.
- `upstream removed its file`: delete the override, its lock entry, and its `overrides.json` entry.
- `substitution <id> matched nothing`: upstream reworded text a rule rewrites. Update the rule's `pattern` in `port/subs/*.json`, or delete the rule.

The lock is never refreshed by the sync. A merged override fails the build until a person relocks it, so a merge is never shipped unread. A new override needs an entry in `port/overrides.json` (`kind`, a one-sentence `why`, and the `upstream` issue or PR URL or `null`), or the build fails.

Files with no override flow through on their own, frontmatter included. A new upstream skill appears in `plugin/` with `disable-model-invocation: true`. `tools/check.py` then flags any Cursor-only text in it, which is the porting work for that skill.

Then:

```sh
python3 tools/build.py --relock <path>...  # record the new upstream hashes for the reviewed overrides
python3 tools/build.py                     # regenerate plugin/
python3 tools/check.py                     # 0 problems
python3 -m unittest discover -s tests      # all pass
git add -A && git commit -m "Sync upstream pstack <version>"
```

`python3 tools/sync_upstream.py --dry-run` shows what changed and how each override would merge, without writing anything. `--ref <sha>` syncs to a specific upstream commit. `--summary FILE` also writes the Markdown the weekly pull request uses.
