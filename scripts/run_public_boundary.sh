#!/bin/sh
set -eu

root=$(git rev-parse --show-toplevel) || exit 2
script="$root/scripts/check_public_boundary.py"

if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    exec python3 "$script" "$@"
fi
if command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    exec python "$script" "$@"
fi
if command -v py >/dev/null 2>&1 && py -3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    exec py -3 "$script" "$@"
fi

echo "public-boundary: ERROR: Python 3.11+ is required; refusing Git operation" >&2
exit 2
