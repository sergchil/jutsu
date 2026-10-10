#!/bin/sh
# Link p3 into every Claude Code config dir that T3 Code uses. See tools/install.py --help.
set -e
here=$(cd "$(dirname "$0")" && pwd)
exec python3 "$here/tools/install.py" "$@"
