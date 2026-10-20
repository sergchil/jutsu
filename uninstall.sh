#!/bin/sh
# Remove everything jutsu added to your Claude Code setup: the skills/jutsu link in every
# Claude config dir T3 uses, jutsu's saved session state, and the rules/jutsu-models.md written by
# /jutsu:setup-pstack. Your repos and this folder are not touched. --dry-run shows the plan.
set -e
here=$(cd "$(dirname "$0")" && pwd)
exec python3 "$here/tools/install.py" --uninstall --purge "$@"
