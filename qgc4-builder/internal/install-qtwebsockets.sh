#!/usr/bin/env bash
# Copy the Qt 5.15.2 WebSockets runtime into a QGC staging tree.
#
# QGC's QtWebSockets QML module dlopen()s libQt5WebSockets.so.5, but the
# upstream Linux post-link list (QGCPostLinkCommon.pri) does not deploy it,
# so QGroundControl aborts with:
#   libQt5WebSockets.so.5: cannot open shared object file
# The library must be the exact Qt 5.15.2 build (Qt checks the patch
# version at load time, so a 5.15.3 or 5.15.x stand-in aborts instead).
#
# Sources, in order of preference:
#   1. The qgc-linux-docker image (its /opt/Qt install is that exact build).
#   2. A bundled archive under internal/deps/ (offline fallback).
set -euo pipefail

STAGING="${1:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="$HERE/deps/qtwebsockets-5.15.2-linux-gcc_64.tar.gz"
IMAGE_NAME="${QGC_DOCKER_IMAGE:-qgc-linux-docker}"
QT_LIB_IN_IMAGE="/opt/Qt/5.15.2/gcc_64/lib/libQt5WebSockets.so.5.15.2"

if [ -z "$STAGING" ]; then
    echo "install-qtwebsockets.sh: no staging directory given" >&2
    exit 2
fi

LIBDIR="$STAGING/Qt/libs"
if [ -d "$LIBDIR" ] && [ -e "$LIBDIR/libQt5WebSockets.so.5" ]; then
    exit 0
fi

if [ ! -d "$LIBDIR" ]; then
    echo "install-qtwebsockets.sh: no Qt libs directory: $LIBDIR" >&2
    exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    docker run --rm --entrypoint cat "$IMAGE_NAME" "$QT_LIB_IN_IMAGE" \
        > "$tmp/libQt5WebSockets.so.5.15.2"
elif [ -f "$ARCHIVE" ]; then
    tar xzf "$ARCHIVE" -C "$tmp"
else
    echo "install-qtwebsockets.sh: neither docker image '$IMAGE_NAME' nor bundled dependency $ARCHIVE available" >&2
    exit 3
fi

cp -a "$tmp/libQt5WebSockets.so.5.15.2" "$LIBDIR/"
ln -sf libQt5WebSockets.so.5.15.2 "$LIBDIR/libQt5WebSockets.so.5.15"
ln -sf libQt5WebSockets.so.5.15.2 "$LIBDIR/libQt5WebSockets.so.5"

echo "Installed libQt5WebSockets.so.5 into $LIBDIR"
