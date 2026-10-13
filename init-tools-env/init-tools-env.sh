#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    cat "$SCRIPT_DIR/internal/usage.md"
}

BIN_DIR="${HOME}/.local/bin"
CHECK=0
FORCE=0
REMOVE=0
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --check) CHECK=1 ;;
        --force) FORCE=1 ;;
        --remove|--uninstall) REMOVE=1 ;;
        -*) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *) BIN_DIR="$1" ;;
    esac
    shift
done

echo "[init-tools-env] repo root: $REPO_ROOT"
echo "[init-tools-env] bin dir:   $BIN_DIR"

if [ ! -d "$BIN_DIR" ]; then
    if [ "$REMOVE" -eq 1 ] || [ "$CHECK" -eq 1 ]; then
        echo "ERROR: bin dir does not exist: $BIN_DIR" >&2
        exit 1
    fi
    mkdir -p "$BIN_DIR"
fi

LINKS="
launch-qgc:qgc4-launch-with-logs/launch-qgc.sh
close-qgc:close-qgc/close-qgc.sh
format-md-table:md-table-aligner/format-md-table.sh
build-qgc:qgc4-builder/build-linux.sh
"

failed=0
for spec in $LINKS; do
    name="${spec%%:*}"
    rel="${spec#*:}"
    target="$REPO_ROOT/$rel"
    link="$BIN_DIR/$name"

    if [ "$REMOVE" -eq 1 ]; then
        if [ ! -e "$link" ] && [ ! -L "$link" ]; then
            echo "absent   $name"
            continue
        fi
        if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
            if [ "$CHECK" -eq 1 ]; then
                echo "removable $name -> $link"
            else
                rm -f "$link"
                echo "removed  $name"
            fi
        else
            echo "ERROR: $link does not point into this repo (left untouched)" >&2
            failed=1
        fi
        continue
    fi

    if [ ! -f "$target" ]; then
        echo "ERROR: target missing: $target" >&2
        failed=1
        continue
    fi

    if [ ! -x "$target" ]; then
        if [ "$CHECK" -eq 1 ]; then
            echo "missing  $name (target is not executable: $target)"
            failed=1
            continue
        fi
        chmod +x "$target"
    fi

    if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
        echo "ok       $name -> $target"
        continue
    fi

    if [ -e "$link" ] || [ -L "$link" ]; then
        if [ "$FORCE" -ne 1 ]; then
            echo "ERROR: $link exists and is not our link (use --force to replace)" >&2
            failed=1
            continue
        fi
        if [ "$CHECK" -eq 1 ]; then
            echo "stale    $name (collides with $link)"
            failed=1
            continue
        fi
        rm -f "$link"
        ln -s "$target" "$link"
        echo "updated  $name -> $target"
    else
        if [ "$CHECK" -eq 1 ]; then
            echo "missing  $name -> $target"
            failed=1
            continue
        fi
        ln -s "$target" "$link"
        echo "created  $name -> $target"
    fi
done

exit "$failed"
