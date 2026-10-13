#!/usr/bin/env bash
#
# Build QGroundControl for Linux inside Docker.
#
# Uses the self-contained image in internal/docker (Ubuntu 20.04 + Qt 5.15.2)
# so the build does not depend on the QGC repository's own Dockerfile, then
# installs the QtWebSockets runtime the upstream deploy step omits — without
# it QGroundControl aborts at launch with
#   libQt5WebSockets.so.5: cannot open shared object file
set -euo pipefail

# Resolve this script through any symlink (init-tools-env links it as
# `build-qgc`) so internal/ is found however it is invoked.
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
HERE="$(cd -P "$(dirname "$SOURCE")" && pwd)"

DOCKER_DIR="$HERE/internal/docker"
DOCKERFILE="$DOCKER_DIR/Dockerfile-build-linux"
IMAGE_NAME="qgc-linux-docker"

usage() { cat "$HERE/internal/usage.md"; }

QGC_ROOT="${QGC_ROOT:-}"
JOBS=""
CLEAN=0

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -j|--jobs)
            if [ $# -lt 2 ]; then
                echo "build-linux.sh: $1 requires a value (e.g. $1 4)" >&2
                usage >&2
                exit 2
            fi
            JOBS="$2"
            shift
            ;;
        -j*)
            JOBS="${1#-j}"
            ;;
        --clean)
            CLEAN=1
            ;;
        -*)
            echo "build-linux.sh: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            QGC_ROOT="$1"
            ;;
    esac
    shift
done

QGC_ROOT="${QGC_ROOT:-$PWD}"
if [ ! -f "$QGC_ROOT/qgroundcontrol.pro" ]; then
    echo "build-linux.sh: not a QGroundControl repository: $QGC_ROOT" >&2
    exit 2
fi

# Default to a quarter of the cores (min 2) so a many-core host is not
# exhausted by the container; override with -j N.
if [ -z "$JOBS" ]; then
    JOBS=$(( $(nproc) / 4 ))
    if [ "$JOBS" -lt 2 ]; then
        JOBS=2
    fi
elif ! [[ "$JOBS" =~ ^[0-9]+$ ]] || [ "$JOBS" -lt 1 ]; then
    echo "build-linux.sh: -j must be a positive integer (got '$JOBS')" >&2
    exit 2
fi

if [ -z "$(docker images -q "$IMAGE_NAME")" ]; then
    echo "Building Docker image '$IMAGE_NAME' (Qt 5.15.2)..."
    docker build --file "$DOCKERFILE" -t "$IMAGE_NAME" "$DOCKER_DIR"
else
    echo "Docker image '$IMAGE_NAME' already exists, skipping image build."
fi

if [ "$CLEAN" -eq 1 ]; then
    rm -rf "$QGC_ROOT/build"
fi
mkdir -p "$QGC_ROOT/build" "$QGC_ROOT/cache"

echo "Building with -j${JOBS}"
run_build() {
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        -e HOME=/tmp \
        -e CCACHE_DIR=/cache \
        -v "$QGC_ROOT":/project/source \
        -v "$QGC_ROOT/build":/project/build \
        -v "$QGC_ROOT/cache":/cache \
        "$IMAGE_NAME" \
        bash -lc "qmake /project/source && make -j${JOBS}"
}

# A stale build tree (mixed old/new objects) can fail with "undefined
# reference to vtable/staticMetaObject"; clean and retry the whole build once.
if ! run_build; then
    echo "build-linux.sh: build failed; cleaning build/ and retrying once..." >&2
    rm -rf "$QGC_ROOT/build"
    mkdir -p "$QGC_ROOT/build"
    run_build
fi

rm -rf "$QGC_ROOT/cache"

"$HERE/internal/install-qtwebsockets.sh" "$QGC_ROOT/build/staging"
