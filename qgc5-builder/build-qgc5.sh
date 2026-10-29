#!/usr/bin/env bash
# Build a QGroundControl 5 checkout (CMake/Qt 6) inside Docker.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
HERE="$(cd -P "$(dirname "$SOURCE")" && pwd)"

case "${1:-}" in
    -h|--help)
        cat "$HERE/internal/usage.md"
        exit 0
        ;;
esac

exec python3 "$HERE/internal/build_qgc5.py" "$@"
