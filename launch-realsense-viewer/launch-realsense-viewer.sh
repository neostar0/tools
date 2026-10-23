#!/bin/bash
# =============================================================================
# launch-realsense-viewer.sh
#
# Install librealsense from source only when realsense-viewer is missing,
# then launch realsense-viewer.
#
# Usage:
#   ./launch-realsense-viewer.sh
#   ./launch-realsense-viewer.sh --check
#   ./launch-realsense-viewer.sh --skip-kernel-patch
#   ./launch-realsense-viewer.sh --help
# =============================================================================
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

PY="${LAUNCH_REALSENSE_VIEWER_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[launch-realsense-viewer] ERROR: '$PY' not found on PATH" >&2
    exit 1
fi

exec "$PY" "$SCRIPT_DIR/internal/launch_realsense_viewer.py" "$@"
