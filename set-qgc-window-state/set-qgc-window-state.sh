#!/bin/bash
# Linux entry for the QGroundControl wrapper. The generic tool owns the
# window behaviour; this entry fixes the process name and validates the
# state exactly as the Windows .cmd does.

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

if [ $# -ne 1 ]; then
    usage
    exit 2
fi

case "$1" in
    max|restore|full) ;;
    *) usage; exit 2 ;;
esac

exec "$SCRIPT_DIR/../set-window-state/set-window-state.sh" QGroundControl "$1"
