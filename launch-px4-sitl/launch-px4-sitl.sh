#!/bin/bash
# Bootstrap shim: resolve this script through any symlinks, pick a Python 3
# interpreter, then hand off to the real implementation in internal/.
# All logic lives in the px4sitl package (internal/px4sitl/).
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

PY="${LAUNCH_PX4_SITL_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[launch-px4-sitl] ERROR: '$PY' not found on PATH" >&2
    exit 1
fi

exec "$PY" "$SCRIPT_DIR/internal/launch_px4_sitl.py" "$@"
