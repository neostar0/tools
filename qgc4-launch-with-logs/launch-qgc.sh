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

# --- Linux host preflight ---------------------------------------------------
# QGC itself refuses to start when the user cannot access serial devices:
# it parses /etc/group for the dialout group and shows a modal dialog
# (QGCApplication.cc). ModemManager additionally fights over the same
# devices. Detect both here so the user gets an actionable console message
# and an automatic fix instead of QGC's dialog. This lives in the launcher,
# not init-tools-env: the tools repo never edits system configuration from
# its symlink manager, and the failure surfaces at launch time.
if [[ "$OS_TYPE" == "linux" ]]; then
    if [[ "$(id -u)" -eq 0 ]]; then
        echo "[ERROR] QGroundControl refuses to run as root. Launch as your normal user instead." >&2
        exit 1
    fi

    confirm() {
        local reply
        read -r -p "$1 [y/N] " reply || return 1
        [[ "$reply" == [yY] || "$reply" == [yY][eE][sS] ]]
    }

    USER_NAME="$(id -un)"
    NEED_DIALOUT_SG=0

    if ! id -nG "$USER_NAME" | grep -qw dialout; then
        echo "[Launcher] User '$USER_NAME' is not in the dialout group (serial device access)."
        if [[ -t 0 ]] && confirm "Add '$USER_NAME' to dialout now? (runs: sudo usermod -a -G dialout $USER_NAME)"; then
            if ! sudo usermod -a -G dialout "$USER_NAME"; then
                echo "[ERROR] usermod failed; cannot continue." >&2
                exit 1
            fi
            echo "[Launcher] Added to dialout. The current session predates the change,"
            echo "[Launcher] so QGC will be started via 'sg dialout' (no re-login needed)."
            NEED_DIALOUT_SG=1
        else
            cat >&2 <<EOF
[ERROR] QGroundControl will refuse to start without dialout group membership.
Fix it once, then run launch-qgc again (or simply re-login):
    sudo usermod -a -G dialout $USER_NAME
Also recommended, to stop ModemManager from grabbing serial devices:
    sudo apt-get remove modemmanager
EOF
            exit 1
        fi
    elif [[ ":$(id -nG):" != *:dialout:* ]]; then
        # Member per /etc/group, but this login session predates the change.
        # sg grants the group for this one process; no re-login needed.
        NEED_DIALOUT_SG=1
    fi

    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet modemmanager 2>/dev/null; then
        echo "[Launcher] ModemManager is active; it interferes with serial devices."
        if [[ -t 0 ]] && confirm "Disable it now? (runs: sudo systemctl disable --now modemmanager)"; then
            sudo systemctl disable --now modemmanager || echo "[Launcher] WARNING: could not disable ModemManager" >&2
        else
            echo "[Launcher] Recommended: sudo systemctl disable --now modemmanager"
        fi
    fi
fi

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
if command -v stdbuf >/dev/null 2>&1; then
    QGC_CMD=(stdbuf -oL -eL "$EXE")
else
    QGC_CMD=("$EXE")
fi
set +e
if [[ "${NEED_DIALOUT_SG:-0}" -eq 1 ]]; then
    # Session predates the usermod: sg re-executes with 'dialout' as a
    # supplementary group for this process only.
    sg dialout -c "$(printf '%q ' "${QGC_CMD[@]}")" 2>&1 | tee "$LOGFILE"
else
    "${QGC_CMD[@]}" 2>&1 | tee "$LOGFILE"
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