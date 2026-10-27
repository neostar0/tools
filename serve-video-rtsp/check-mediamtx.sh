#!/bin/bash
# Make sure the mediamtx binary exists under this tool's internal/bin,
# downloading the pinned GitHub release when it is missing.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

usage() { cat "$SCRIPT_DIR/internal/usage.md"; }

BIN_DIR="$SCRIPT_DIR/internal/bin"
MEDIAMTX_VERSION="${MEDIAMTX_VERSION:-1.21.2}"
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --force) FORCE=1 ;;
        -*) echo "[check-mediamtx] ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *) echo "[check-mediamtx] ERROR: unexpected argument: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

log() { echo "[check-mediamtx] $*"; }
fail() { echo "[check-mediamtx] ERROR: $*" >&2; exit 1; }

runs() { [ -x "$1" ] && "$1" --version >/dev/null 2>&1; }

if [ "$FORCE" -eq 0 ] && runs "$BIN_DIR/mediamtx"; then
    log "already installed: $("$BIN_DIR/mediamtx" --version 2>/dev/null | head -n 1)"
    log "path: $BIN_DIR/mediamtx"
    exit 0
fi

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$arch" in
    x86_64|amd64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    armv7l) arch=armv7 ;;
    armv6l) arch=armv6 ;;
    *) fail "unsupported architecture: $(uname -m)" ;;
esac
case "$os" in
    linux|darwin) ;;
    *) fail "unsupported OS: $(uname -s) - use check-mediamtx.cmd on Windows" ;;
esac

asset="mediamtx_v${MEDIAMTX_VERSION}_${os}_${arch}.tar.gz"
base="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}"

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --connect-timeout 20 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$2" "$1"
    else
        fail "neither curl nor wget is available to download mediamtx"
    fi
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

log "downloading $asset (v${MEDIAMTX_VERSION})"
fetch "$base/$asset" "$tmp/$asset" || fail "download failed: $base/$asset"
fetch "$base/checksums.sha256" "$tmp/checksums.sha256" || fail "download failed: checksums.sha256"

awk -v f="$asset" '$2 == f || $2 == "*" f { print }' "$tmp/checksums.sha256" > "$tmp/sha256.check"
[ -s "$tmp/sha256.check" ] || fail "no checksum entry for $asset"
(cd "$tmp" && sha256sum -c sha256.check) >/dev/null || fail "checksum mismatch for $asset"

tar -xzf "$tmp/$asset" -C "$tmp"
src="$(find "$tmp" -maxdepth 3 -type f -name mediamtx | head -n 1)"
[ -n "$src" ] || fail "the $asset archive contains no mediamtx binary"

mkdir -p "$BIN_DIR"
install -m 0755 "$src" "$BIN_DIR/mediamtx"
runs "$BIN_DIR/mediamtx" || fail "$BIN_DIR/mediamtx does not run on this system"

log "installed: $("$BIN_DIR/mediamtx" --version 2>/dev/null | head -n 1)"
log "path: $BIN_DIR/mediamtx"
