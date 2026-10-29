#!/usr/bin/env bash
# Launch a QGroundControl 5 build with logs and crash dumps.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
HERE="$(cd -P "$(dirname "$SOURCE")" && pwd)"

usage() {
    cat "$HERE/internal/usage.md"
}

if [[ $# -eq 0 ]]; then
    : # allow default discovery
fi
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        usage
        exit 0
    fi
done

exec python3 "$HERE/internal/run_qgc5.py" "$@"
