# Contributing to jutsu

Thanks for helping. jutsu is a port. The playbooks and principles are Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack), and this repo connects them to Claude Code and T3 Code.

## Where to report what

- **It breaks in Claude Code or T3 Code** (install, `/jutsu`, a T3 tool call, the mode turning off): [open an issue here](https://github.com/sergchil/jutsu/issues/new/choose).
- **The playbook's advice itself is wrong**, and pstack in Cursor says the same: report it upstream in [cursor/plugins](https://github.com/cursor/plugins/issues).
- **A security problem**: follow [SECURITY.md](SECURITY.md). Please don't open a public issue.

## How the repo is built

| Folder | What it holds | Edit it? |
|---|---|---|
| `vendor/pstack/` | Upstream pstack, byte for byte | No. `tools/sync_upstream.py` updates it. |
| `port/` | Every change for Claude Code and T3: rewritten files, new files, text rules | Yes. Changes to the plugin go here. |
| `plugin/` | What users install, built from the two folders above | No. `tools/build.py` writes it. |
| `tools/` | The build, check, install, and sync scripts | Yes |
| `tests/` | Tests, run in CI | Yes |
| `docs/` | The docs and the website (`docs/index.html`) | Yes |

[docs/PORTING.md](docs/PORTING.md) has the porting rules. [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) explains the design.

## Make a change

You need Python 3.9 or newer. [bun](https://bun.sh) runs the tests of the bundled scripts.

1. Edit files under `port/`, `tools/`, `tests/`, or `docs/`.
2. Rebuild and check:

   ```sh
   python3 tools/build.py                 # rebuild plugin/
   python3 tools/check.py                 # expect 0 problems
   python3 -m unittest discover -s tests  # expect all to pass
   ```

3. Commit `port/` and `plugin/` together. CI fails when `plugin/` is out of date.
4. If you changed how jutsu behaves, try it for real. Run `./install.sh`, start a new T3 thread, and say in the pull request what you ran. [docs/TESTED.md](docs/TESTED.md) shows how each feature was tested.

A file in `port/overrides/` rewrites an upstream file, and it is locked to that file's upstream version. When upstream changes the file, the build names the override to update. [docs/UPDATING.md](docs/UPDATING.md) has the steps.

## Pull requests

- Keep each pull request to one topic, small enough to review in one sitting.
- Fill in the template: why, what changed, and how you checked it.
- Your contribution is released under the [MIT license](LICENSE).

Everyone here follows the [code of conduct](CODE_OF_CONDUCT.md).
