# Updating from upstream pstack

jutsu keeps poteto's pstack byte for byte in `vendor/pstack/`. Everything Claude Code and T3 need lives beside it in `port/`. An update is a sync plus a short, explicit list of things to port.

## Automatic

`.github/workflows/upstream.yml` runs every Monday (or on demand from the Actions tab). When upstream changed, it opens a pull request on branch `upstream/pstack` with the new `vendor/` and a body that lists every item to port. The CI check on that pull request stays red until the list is done.

## Upstream bugs fixed here

These overrides carry fixes for bugs that are still open upstream. When a sync flags one of these files, check whether upstream merged its fix. If it did, drop our copy of the fix from the override (or delete the override when nothing else is left in it), then relock.

| Upstream issue | Upstream fix | Override files under `port/overrides/skills/poteto-mode/` |
|---|---|---|
| [#449](https://github.com/cursor/plugins/issues/449): untracked and ignored files are deleted | none open | `scripts/worktree-audit.sh`, `playbooks/worktree-cleanup.md` |
| [#470](https://github.com/cursor/plugins/issues/470): closed-PR or unpushed work is called safe | [#492](https://github.com/cursor/plugins/pull/492) | the same two files |
| [#471](https://github.com/cursor/plugins/issues/471): only 100 review threads are read | [#484](https://github.com/cursor/plugins/pull/484), plus a stuck-cursor guard | `scripts/watch-pr/` `github.ts`, `policy.ts`, `types.ts` and their tests |

`tests/test_worktree_audit.py` and `watch-pr/github.test.ts` pin the fixed behavior, and `tools/check.py` rejects `worktree remove --force` and `rm -rf` in any playbook, so an upstream change cannot bring a bug back silently.

## By hand

```sh
python3 tools/sync_upstream.py          # pull the latest pstack into vendor/ and list what to port
```

The output names each item:

- `re-merge port/overrides/<path>`: upstream changed a file this repo rewrote. Run the `git diff HEAD -- vendor/pstack/<file>` it prints, apply the same change to the override in Claude and T3 terms (docs/PORTING.md), and keep the override's own edits.
- `substitution <id> matched nothing`: upstream reworded text a rule rewrites. Update the rule's `pattern` in `port/subs/*.json`, or delete the rule.
- `upstream removed the file behind port/overrides/<path>`: delete the override and its lock entry.

Files with no override flow through on their own, frontmatter included. A new upstream skill appears in `plugin/` with `disable-model-invocation: true`. `tools/check.py` then flags any Cursor-only text in it, which is the porting work for that skill.

Then:

```sh
python3 tools/build.py --relock        # record the new upstream hashes for the re-merged overrides
python3 tools/check.py                 # 0 problems
python3 -m unittest discover -s tests  # all pass
git add -A && git commit -m "Sync upstream pstack <version>"
```

`python3 tools/sync_upstream.py --dry-run` shows what changed without writing anything. `--ref <sha>` syncs to a specific upstream commit.
