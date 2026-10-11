#!/bin/sh
# Remove everything p3 added to your Claude Code setup: the skills/p3 link in every
# Claude config dir T3 uses, p3's saved session state, and the p3-models.md written by
# /p3:setup-pstack. Your repos and this folder are not touched. --dry-run shows the plan.
set -e
here=$(cd "$(dirname "$0")" && pwd)
exec python3 "$here/tools/install.py" --uninstall --purge "$@"
