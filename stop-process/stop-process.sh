#!/bin/bash

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

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

name="$1"

if ! command -v pkill >/dev/null || ! command -v pgrep >/dev/null; then
    echo "ERROR: pkill/pgrep not found (procps required)." >&2
    exit 1
fi

pkill -x "$name"

for ((i = 0; i < 3; i++)); do
    pgrep -x "$name" >/dev/null || exit 0
    sleep 1
done

pkill -9 -x "$name"
if pgrep -x "$name" >/dev/null; then
    echo "[FAIL] $name survived." >&2
    exit 1
fi
exit 0
