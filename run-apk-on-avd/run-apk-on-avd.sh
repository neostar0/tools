#!/usr/bin/env bash
# =============================================================================
# run-apk-on-avd.sh
#
# Run an APK on an Android virtual device at 1440x3120 (s24 plus).
#
# Usage:
#   ./run-apk-on-avd.sh APK_PATH
#   ./run-apk-on-avd.sh APK_PATH --avd s24-plus
#   ./run-apk-on-avd.sh APK_PATH --timeout 600
#   ./run-apk-on-avd.sh --help
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

exec python3 "$SCRIPT_DIR/internal/run_apk_on_avd.py" "$@"