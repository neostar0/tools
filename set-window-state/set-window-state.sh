#!/bin/bash
# Linux entry for set-window-state. Argument rules live in the Python
# helper, the single copy; this entry only makes the usage screen and
# --help reachable without starting the window code.

set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

usage() {
    cat "$SCRIPT_DIR/internal/usage.md"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac

if [ $# -eq 0 ]; then
    usage
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "[FAIL] python3 is required." >&2
    exit 1
fi

exec python3 "$SCRIPT_DIR/internal/window_state_linux.py" "$@"
