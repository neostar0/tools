#!/usr/bin/env bash
# =============================================================================
# run-qgc-apk.sh
#
# Run a QGroundControl APK on an Android virtual device and show its window.
#
# Picks an APK from the QGC repository (legacy build_android output or the
# qgc-android-builder dist directory) and delegates installation, launch and
# window handling to run-apk-on-avd.
#
# Usage:
#   ./run-qgc-apk.sh [QGC_REPO_ROOT]
#   ./run-qgc-apk.sh [QGC_REPO_ROOT] --abi x86_64
#   ./run-qgc-apk.sh [QGC_REPO_ROOT] --apk PATH
#   ./run-qgc-apk.sh [QGC_REPO_ROOT] --window-size 900x416
#   ./run-qgc-apk.sh --help
# =============================================================================

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
TOOLS_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    cat "$SCRIPT_DIR/internal/usage.md"
}

# ---------------------------------------------------------------------------
# Resolve the QGC repository root.
#  1. First positional argument, if it is a directory.
#  2. git rev-parse --show-toplevel from the current working directory.
#  3. Sibling directory of this tools repo, i.e. <tools_root>/../qgc.
# ---------------------------------------------------------------------------
resolve_qgc_root() {
    if [ -n "${1:-}" ] && [ -d "$1" ]; then
        QGC_ROOT="$(cd -- "$1" && pwd)"
        return 0
    fi

    if command -v git >/dev/null 2>&1; then
        local git_root
        git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ -n "$git_root" ] && [ -d "$git_root" ]; then
            QGC_ROOT="$git_root"
            return 0
        fi
    fi

    local sibling
    sibling="$(cd -- "$TOOLS_ROOT/.." && pwd)/qgc"
    if [ -d "$sibling" ]; then
        QGC_ROOT="$sibling"
        return 0
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Resolve the APK path.
#   --apk PATH wins.
#   --abi ABI uses build_android/ (arm64-v8a) or build_android_<abi>/ first,
#   then the dist/ copy.
#   Without --abi, prefer the arm64 build_android output, then x86_64, then
#   any dist APK.
# ---------------------------------------------------------------------------
apk_from_dir() {
    local dir="$1"
    local abi="$2"
    local candidate
    [ -d "$dir" ] || return 1
    if [ -n "$abi" ]; then
        for candidate in \
            "$dir/QGroundControl-$abi.apk" \
            "$dir/QGroundControl-${abi}-novideo.apk" \
            "$dir"/*"-${abi}.apk" \
            "$dir"/*"-${abi}-novideo.apk"; do
            if [ -f "$candidate" ]; then
                APK_PATH="$candidate"
                return 0
            fi
        done
        candidate="$(find "$dir" -maxdepth 1 -name "*${abi}*.apk" 2>/dev/null | head -n 1 || true)"
        if [ -n "$candidate" ]; then
            APK_PATH="$candidate"
            return 0
        fi
        return 1
    fi
    candidate="$(find "$dir" -maxdepth 1 -name "*.apk" 2>/dev/null | head -n 1 || true)"
    if [ -n "$candidate" ]; then
        APK_PATH="$candidate"
        return 0
    fi
    return 1
}

apk_from_build_dir() {
    local root="$1"
    local abi="$2"
    local dir
    if [ "$abi" = "arm64-v8a" ]; then
        dir="$root/build_android"
    else
        dir="$root/build_android_${abi//-/_}"
    fi
    local signed="$dir/android-build/build/outputs/apk/release/android-build-release-signed.apk"
    local unsigned="$dir/android-build/build/outputs/apk/release/android-build-release-unsigned.apk"
    if [ -f "$signed" ]; then
        APK_PATH="$signed"
        return 0
    fi
    if [ -f "$unsigned" ]; then
        APK_PATH="$unsigned"
        return 0
    fi
    return 1
}

resolve_apk() {
    local qgc_root="$1"
    local abi="$2"

    if [ -n "$APK_OVERRIDE" ]; then
        if [ -f "$APK_OVERRIDE" ]; then
            APK_PATH="$(cd -- "$(dirname "$APK_OVERRIDE")" && pwd)/$(basename "$APK_OVERRIDE")"
            return 0
        fi
        echo "ERROR: --apk file not found: $APK_OVERRIDE" >&2
        return 1
    fi

    if [ -n "$abi" ]; then
        apk_from_build_dir "$qgc_root" "$abi" && return 0
        apk_from_dir "$qgc_root/dist" "$abi" && return 0
        return 1
    fi

    apk_from_build_dir "$qgc_root" "arm64-v8a" && return 0
    apk_from_dir "$qgc_root/dist" "arm64-v8a" && return 0
    apk_from_build_dir "$qgc_root" "x86_64" && return 0
    apk_from_dir "$qgc_root/dist" "x86_64" && return 0
    apk_from_dir "$qgc_root/dist" "" && return 0

    local preferred="$qgc_root/build_android/package/QGroundControl64.apk"
    if [ -f "$preferred" ]; then
        APK_PATH="$preferred"
        return 0
    fi

    if [ -d "$qgc_root/build_android/package" ]; then
        local found
        found="$(find "$qgc_root/build_android/package" -maxdepth 1 \
            -name "QGroundControl*.apk" 2>/dev/null | head -n 1 || true)"
        if [ -n "$found" ]; then
            APK_PATH="$found"
            return 0
        fi
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Parse arguments: a leading directory is the QGC root; --abi and --apk select
# the APK. Everything else is passed through to run-apk-on-avd.
# ---------------------------------------------------------------------------
QGC_ROOT=""
ABI=""
APK_OVERRIDE=""
PASS_THROUGH=()
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --abi)
            if [ $# -lt 2 ]; then
                echo "ERROR: --abi needs a value" >&2
                exit 2
            fi
            ABI="$2"
            PASS_THROUGH+=("$1" "$2")
            shift 2
            ;;
        --abi=*)
            ABI="${1#*=}"
            PASS_THROUGH+=("$1")
            shift
            ;;
        --apk)
            if [ $# -lt 2 ]; then
                echo "ERROR: --apk needs a value" >&2
                exit 2
            fi
            APK_OVERRIDE="$2"
            shift 2
            ;;
        --apk=*)
            APK_OVERRIDE="${1#*=}"
            shift
            ;;
        -*)
            PASS_THROUGH+=("$1")
            shift
            ;;
        *)
            if [ -z "$QGC_ROOT" ] && [ -d "$1" ]; then
                QGC_ROOT="$1"
                shift
            else
                PASS_THROUGH+=("$1")
                shift
            fi
            ;;
    esac
done

if [ -z "$QGC_ROOT" ]; then
    if ! resolve_qgc_root; then
        echo "ERROR: could not locate the QGC repository." >&2
        echo "  Pass the QGC repo root as the first argument, or run from" >&2
        echo "  inside a QGC checkout, or place it next to this tools repo." >&2
        usage >&2
        exit 1
    fi
fi

echo "[run-qgc-apk] QGC root: $QGC_ROOT"

if ! resolve_apk "$QGC_ROOT" "$ABI"; then
    echo "ERROR: no matching QGroundControl APK found." >&2
    if [ "$ABI" = "arm64-v8a" ]; then
        echo "  Looked in $QGC_ROOT/build_android and $QGC_ROOT/dist" >&2
    elif [ -n "$ABI" ]; then
        echo "  Looked in $QGC_ROOT/build_android_${ABI//-/_} and $QGC_ROOT/dist" >&2
    else
        echo "  Looked in $QGC_ROOT/build_android, $QGC_ROOT/build_android_x86_64 and $QGC_ROOT/dist" >&2
    fi
    echo "  Build one with qgc-android-builder.sh --abi ${ABI:-all}" >&2
    exit 1
fi

echo "[run-qgc-apk] APK: $APK_PATH"

# Delegate to the sibling tool, forwarding all remaining arguments.
exec "$SCRIPT_DIR/../run-apk-on-avd/run-apk-on-avd.sh" "$APK_PATH" "${PASS_THROUGH[@]}"
