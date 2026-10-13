#!/bin/bash
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
if [ $# -gt 1 ]; then usage; exit 2; fi

DEFAULT_QGC_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Get QGC root from argument or use default (cd+pwd: realpath is not everywhere)
QGC_ROOT="${1:-$DEFAULT_QGC_ROOT}"
QGC_ROOT="$(cd -- "$QGC_ROOT" && pwd)"

echo "[Launcher] QGC root: $QGC_ROOT"

# Detect OS
OS_TYPE="$(uname -s | tr '[:upper:]' '[:lower:]')"
echo "[Launcher] OS detected: $OS_TYPE"

# Find executable based on OS
EXE=""
if [[ "$OS_TYPE" == "linux" ]]; then
    EXE_DEBUG="$QGC_ROOT/build/staging/QGroundControl"
    EXE_RELEASE="$QGC_ROOT/build/release/staging/QGroundControl"
    if [[ -f "$EXE_DEBUG" && -x "$EXE_DEBUG" ]]; then
        EXE="$EXE_DEBUG"
        echo "[Launcher] Using Debug build"
    elif [[ -f "$EXE_RELEASE" && -x "$EXE_RELEASE" ]]; then
        EXE="$EXE_RELEASE"
        echo "[Launcher] Using Release build"
    else
        # Fallback search (-perm works on both GNU and BSD find)
        FOUND=$(find "$QGC_ROOT" -name "QGroundControl" -type f -perm -0100 2>/dev/null | head -1 || true)
        if [[ -n "$FOUND" ]]; then
            EXE="$FOUND"
            echo "[Launcher] Found via search: $EXE"
        fi
    fi
elif [[ "$OS_TYPE" == "darwin" ]]; then
    EXE_APP="$QGC_ROOT/build/staging/QGroundControl.app"
    EXE_BIN="$EXE_APP/Contents/MacOS/QGroundControl"
    if [[ -f "$EXE_BIN" && -x "$EXE_BIN" ]]; then
        EXE="$EXE_BIN"
        echo "[Launcher] Using macOS app bundle"
    fi
fi

if [[ -z "$EXE" ]]; then
    echo "[ERROR] Could not find QGroundControl executable in $QGC_ROOT"
    echo "  Searched:"
    [[ "$OS_TYPE" == "linux" ]] && echo "    $EXE_DEBUG" && echo "    $EXE_RELEASE"
    [[ "$OS_TYPE" == "darwin" ]] && echo "    $EXE_APP"
    echo ""
    echo "Usage: $0 [QGC_REPO_ROOT]"
    exit 1
fi

echo "[Launcher] Executable: $EXE"

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y_%m_%d_%H%M%S")
LOGFILE="$(pwd)/qgc_${TIMESTAMP}.log"
echo "[Launcher] Log file: $LOGFILE"

# Set log categories
export QGC_LOGGING_CATEGORIES="FactPanelControllerLog=true ParameterManagerLog=true MAVLinkLogManagerLog=true HealthAndArmingChecks=true GStreamerAPILog=true"
export QT_LOGGING_RULES="qt.qml.connections=false;*.debug=false"

echo "[Launcher] Log categories: FactPanelControllerLog, ParameterManagerLog, MAVLinkLogManagerLog, HealthAndArmingChecks, GStreamerAPILog"
echo "------------------------------------------------"

# Launch with tee to both console and log file.
# stdbuf is GNU/Linux only, so fall back to a plain launch elsewhere.
# The tee pipeline runs with set +e so a non-zero QGC exit code reaches
# the summary below instead of killing the script (set -e + pipefail).
set +e
if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL "$EXE" 2>&1 | tee "$LOGFILE"
else
    "$EXE" 2>&1 | tee "$LOGFILE"
fi
EXIT_CODE=${PIPESTATUS[0]}
set -e

echo "------------------------------------------------"
echo "[Launcher] QGroundControl exited with code $EXIT_CODE"
echo "[Launcher] Full log saved to: $LOGFILE"

if [[ $EXIT_CODE -ne 0 ]]; then
    echo "[WARNING] Non-zero exit code. Check log for details."
fi

# Hand QGC's exit code to the caller, same as the Python launcher
exit "$EXIT_CODE"