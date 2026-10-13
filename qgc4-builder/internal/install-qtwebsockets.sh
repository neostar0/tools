#!/usr/bin/env bash
# Copy the Qt 5.15.2 WebSockets runtime into a QGC staging tree.
#
# QGC's QtWebSockets QML module dlopen()s libQt5WebSockets.so.5, but the
# upstream Linux post-link list (QGCPostLinkCommon.pri) does not deploy it,
# so QGroundControl aborts with:
#   libQt5WebSockets.so.5: cannot open shared object file
# The bundled archive is the exact Qt 5.15.2 build (Qt checks the patch
# version at load time, so a 5.15.3 or 5.15.x stand-in aborts instead).
set -euo pipefail

STAGING="${1:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="$HERE/deps/qtwebsockets-5.15.2-linux-gcc_64.tar.gz"

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

if [ ! -f "$ARCHIVE" ]; then
    echo "install-qtwebsockets.sh: missing bundled dependency: $ARCHIVE" >&2
    exit 3
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

tar xzf "$ARCHIVE" -C "$tmp"
cp -a "$tmp/lib/libQt5WebSockets.so.5.15.2" "$LIBDIR/"
ln -sf libQt5WebSockets.so.5.15.2 "$LIBDIR/libQt5WebSockets.so.5.15"
ln -sf libQt5WebSockets.so.5.15.2 "$LIBDIR/libQt5WebSockets.so.5"

echo "Installed libQt5WebSockets.so.5 into $LIBDIR"
