#!/usr/bin/env bash
# =============================================================================
# android-avd.sh
#
# Open, close and position Android Virtual Devices.
#
# Usage:
#   ./android-avd.sh open [options]
#   ./android-avd.sh close --avd NAME
#   ./android-avd.sh geometry --avd NAME --window-size 900x416
#   ./android-avd.sh list
#   ./android-avd.sh status
#   ./android-avd.sh --help
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

exec python3 "$SCRIPT_DIR/internal/android_avd.py" "$@"
