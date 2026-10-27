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

# Generate timestamp for log file and crash artifacts
TIMESTAMP=$(date +"%Y_%m_%d_%H%M%S")
LOGFILE="$(pwd)/qgc_${TIMESTAMP}.log"
CRASH_DUMP_DIR="$(pwd)/dump"
CRASH_CORE="$CRASH_DUMP_DIR/qgc_${TIMESTAMP}.core"
CRASH_BT="$CRASH_DUMP_DIR/qgc_${TIMESTAMP}.bt"
echo "[Launcher] Log file: $LOGFILE"

# Set log categories
export QGC_LOGGING_CATEGORIES="FactPanelControllerLog=true ParameterManagerLog=true MAVLinkLogManagerLog=true HealthAndArmingChecks=true GStreamerAPILog=true"
export QT_LOGGING_RULES="qt.qml.connections=false;*.debug=false"

echo "[Launcher] Log categories: FactPanelControllerLog, ParameterManagerLog, MAVLinkLogManagerLog, HealthAndArmingChecks, GStreamerAPILog"
echo "------------------------------------------------"

# Run QGC under gdb on Linux so a crash produces a core dump and a
# backtrace even when the system core_pattern is routed to apport (or
# core dumps are disabled with ulimit -c 0).  Set QGC_LAUNCH_NO_GDB=1 to
# launch directly instead.
USE_GDB=0
GDB_CMDFILE=""
if [[ "$OS_TYPE" == "linux" ]] && command -v gdb >/dev/null 2>&1 && [[ "${QGC_LAUNCH_NO_GDB:-0}" != "1" ]]; then
    USE_GDB=1
    mkdir -p "$CRASH_DUMP_DIR"
    echo "[Launcher] Crash dump directory: $CRASH_DUMP_DIR"
    GDB_CMDFILE="$(mktemp "${TMPDIR:-/tmp}/qgc-gdb.XXXXXX")"
    trap 'rm -f "${GDB_CMDFILE:-}"' EXIT
    cat > "$GDB_CMDFILE" <<'GDB'
set pagination off
set confirm off
set print thread-events off
set use-coredump-filter on
handle SIGPIPE nostop noprint pass
handle SIGTERM nostop noprint pass
handle SIGINT nostop noprint pass
run
python
import gdb, os
inf = gdb.selected_inferior()
if inf.pid and inf.threads():
    corefile = os.environ.get("QGC_CORE_FILE", "")
    btfile = os.environ.get("QGC_BT_FILE", "")
    if os.environ.get("QGC_CORE_DISABLED") == "1":
        corefile = ""
    print("\n[Launcher] QGroundControl crashed; collecting diagnostics...")
    try:
        bt = gdb.execute("bt full", to_string=True)
        allbt = gdb.execute("thread apply all bt", to_string=True)
        print(bt)
        print(allbt)
        if btfile:
            with open(btfile, "w") as f:
                f.write(bt)
                f.write("\n")
                f.write(allbt)
            print("[Launcher] Backtrace written to " + btfile)
        if corefile:
            # Ask gdb to honor coredump_filter (skip file-backed pages).
            # QGC can still produce a multi-GB core; use
            # QGC_LAUNCH_NO_CORE=1 if disk space is a concern.
            try:
                with open("/proc/%d/coredump_filter" % inf.pid, "w") as f:
                    f.write("0x11\n")
            except OSError:
                pass
            # generate-core-file takes a bare filename; quote-like characters
            # would become part of the path.
            escaped_core = corefile.replace('\\', '\\\\').replace(' ', '\\ ')
            gdb.execute("generate-core-file " + escaped_core)
            print("[Launcher] Core dump written to " + corefile)
    except gdb.error as exc:
        print("[Launcher] Could not collect crash diagnostics: %s" % exc)
    try:
        signo = int(gdb.parse_and_eval("$_siginfo.si_signo"))
        code = 128 + signo
    except Exception:
        code = 139
    gdb.execute("quit %d" % code)
else:
    try:
        code = int(gdb.parse_and_eval("$_exitcode"))
    except Exception:
        code = 1
    gdb.execute("quit %d" % code)
end
GDB
    export QGC_CORE_FILE="$CRASH_CORE"
    export QGC_BT_FILE="$CRASH_BT"
    if [[ "${QGC_LAUNCH_NO_CORE:-0}" == "1" ]]; then
        export QGC_CORE_DISABLED=1
        echo "[Launcher] Crash diagnostics: gdb enabled (backtrace only, core disabled)"
    else
        echo "[Launcher] Crash diagnostics: gdb enabled (core: $CRASH_CORE)"
    fi
    echo "[Launcher] Set QGC_LAUNCH_NO_GDB=1 to launch without gdb."
    echo "[Launcher] Set QGC_LAUNCH_NO_CORE=1 to keep only the backtrace."
elif [[ "$OS_TYPE" == "linux" ]]; then
    # Fallback for systems without gdb: raise the core limit.  Whether a
    # core file is actually written still depends on kernel.core_pattern.
    ulimit -c unlimited 2>/dev/null || true
    echo "[Launcher] WARNING: gdb not found; relying on system core dump settings."
fi

# Launch with tee to both console and log file.
# stdbuf is GNU/Linux only, so fall back to a plain launch elsewhere.
# The tee pipeline runs with set +e so a non-zero QGC exit code reaches
# the summary below instead of killing the script (set -e + pipefail).
if [[ "$USE_GDB" -eq 1 ]]; then
    # gdb owns the inferior, so stdbuf cannot wrap it. QGC's Qt logging is
    # still captured from stderr.
    QGC_CMD=(gdb -q -batch -x "$GDB_CMDFILE" --args "$EXE")
elif command -v stdbuf >/dev/null 2>&1; then
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

if [[ -f "$CRASH_CORE" ]]; then
    echo "[Launcher] Crash core dump: $CRASH_CORE"
fi
if [[ -f "$CRASH_BT" ]]; then
    echo "[Launcher] Crash backtrace: $CRASH_BT"
fi

if [[ $EXIT_CODE -ne 0 ]]; then
    echo "[WARNING] Non-zero exit code. Check log for details."
    if [[ ! -f "$CRASH_CORE" && ! -f "$CRASH_BT" ]]; then
        echo "[WARNING] No crash dump was captured. Re-run with gdb available (Linux) or"
        echo "          check that QGC_LAUNCH_NO_GDB is not set."
    fi
fi

# Hand QGC's exit code to the caller, same as the Python launcher
exit "$EXIT_CODE"