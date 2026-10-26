#!/usr/bin/env bash
# =============================================================================
# qgc-android-builder.sh
#
# Build QGroundControl Android APKs with this repo's own Docker image.
#
# Usage:
#   ./qgc-android-builder.sh [QGC_ROOT] [--abi x86_64] [--abi arm64-v8a]
#   ./qgc-android-builder.sh --abi all
#   ./qgc-android-builder.sh --help
# =============================================================================

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

case "${1:-}" in
    -h|--help)
        cat "$SCRIPT_DIR/internal/usage.md"
        exit 0
        ;;
esac

exec python3 "$SCRIPT_DIR/internal/build_android.py" "$@"
