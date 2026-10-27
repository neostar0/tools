#!/bin/bash
# Serve a video file as a looping RTSP stream: mediamtx is the RTSP server,
# ffmpeg loops the file into it as a publisher, and the rtsp:// URL is printed.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

RUNTIME="$SCRIPT_DIR/internal/runtime"
BIN_DIR="$SCRIPT_DIR/internal/bin"
CONFIG="$RUNTIME/mediamtx.yml"
MEDIAMTX_PIDFILE="$RUNTIME/mediamtx.pid"
FFMPEG_PIDFILE="$RUNTIME/ffmpeg.pid"
FFMPEG_LOG="$RUNTIME/ffmpeg.log"

NAME="stream"
PORT="8554"
STOP=0
FILE=""

usage() { cat "$SCRIPT_DIR/internal/usage.md"; }
log() { echo "[serve-video-rtsp] $*"; }
fail() { echo "[serve-video-rtsp] ERROR: $*" >&2; exit 1; }
usage_error() {
    echo "[serve-video-rtsp] ERROR: $*" >&2
    usage >&2
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --stop) STOP=1 ;;
        -n|--name)
            [ $# -ge 2 ] || usage_error "$1 needs a value"
            NAME="$2"
            shift ;;
        -p|--port)
            [ $# -ge 2 ] || usage_error "$1 needs a value"
            PORT="$2"
            shift ;;
        -*) usage_error "unknown option: $1" ;;
        *)
            [ -z "$FILE" ] || usage_error "only one video file may be given"
            FILE="$1" ;;
    esac
    shift
done

case "$NAME" in
    ""|*[!A-Za-z0-9_.-]*) usage_error "invalid RTSP path name: '$NAME' (letters, digits, . _ - only)" ;;
esac
case "$PORT" in
    ""|*[!0-9]*) usage_error "invalid port: '$PORT'" ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    usage_error "invalid port: '$PORT' (1-65535)"
fi

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --connect-timeout 20 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$2" "$1"
    else
        fail "neither curl nor wget is available to download ffmpeg"
    fi
}

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }

read_pid() { cat "$1" 2>/dev/null || true; }

stop_pidfile() {
    local pidfile="$1" label="$2" pid i
    [ -f "$pidfile" ] || return 1
    pid="$(read_pid "$pidfile")"
    rm -f "$pidfile"
    alive "$pid" || return 1
    kill "$pid" 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do
        alive "$pid" || break
        sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
    log "stopped $label (pid $pid)"
    return 0
}

stop_server() {
    local stopped=0
    stop_pidfile "$FFMPEG_PIDFILE" "ffmpeg publisher" && stopped=1
    stop_pidfile "$MEDIAMTX_PIDFILE" "mediamtx server" && stopped=1
    if [ "$stopped" -eq 1 ]; then
        log "stopped"
    else
        log "not running"
    fi
}

server_running() {
    alive "$(read_pid "$MEDIAMTX_PIDFILE")" || alive "$(read_pid "$FFMPEG_PIDFILE")"
}

install_ffmpeg() {
    local url tmp src
    [ "$(uname -s)" = "Linux" ] || fail "no bundled ffmpeg for $(uname -s) - install ffmpeg yourself and set FFMPEG_BIN=/path/to/ffmpeg"
    case "$(uname -m)" in
        x86_64|amd64)
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" ;;
        aarch64|arm64)
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz" ;;
        *)
            fail "no bundled ffmpeg for $(uname -m) - install ffmpeg yourself and set FFMPEG_BIN=/path/to/ffmpeg" ;;
    esac
    tmp="$(mktemp -d)"
    log "ffmpeg not found - downloading the static build once (~150 MB)"
    fetch "$url" "$tmp/ffmpeg.tar.xz" || { rm -rf "$tmp"; fail "download failed: $url"; }
    tar -xJf "$tmp/ffmpeg.tar.xz" -C "$tmp"
    src="$(find "$tmp" -maxdepth 3 -type f -name ffmpeg | head -n 1)"
    [ -n "$src" ] || { rm -rf "$tmp"; fail "the ffmpeg archive contains no ffmpeg binary"; }
    mkdir -p "$BIN_DIR"
    install -m 0755 "$src" "$BIN_DIR/ffmpeg"
    rm -rf "$tmp"
    FFMPEG="$BIN_DIR/ffmpeg"
}

FFMPEG=""
select_ffmpeg() {
    if [ -n "${FFMPEG_BIN:-}" ]; then
        FFMPEG="$FFMPEG_BIN"
    elif [ -x "$BIN_DIR/ffmpeg" ]; then
        FFMPEG="$BIN_DIR/ffmpeg"
    elif command -v ffmpeg >/dev/null 2>&1; then
        FFMPEG="$(command -v ffmpeg)"
    else
        install_ffmpeg
    fi
    "$FFMPEG" -version >/dev/null 2>&1 || fail "ffmpeg does not run: $FFMPEG"
}

STARTED=0
OK=0
on_exit() {
    if [ "$OK" -ne 1 ] && [ "$STARTED" -eq 1 ]; then
        stop_pidfile "$FFMPEG_PIDFILE" "ffmpeg publisher" >/dev/null 2>&1 || true
        stop_pidfile "$MEDIAMTX_PIDFILE" "mediamtx server" >/dev/null 2>&1 || true
        log "cleaned up after a failed start"
    fi
}
trap on_exit EXIT

mkdir -p "$RUNTIME"

if [ "$STOP" -eq 1 ]; then
    [ -z "$FILE" ] || usage_error "--stop takes no video file"
    stop_server
    exit 0
fi

[ -n "$FILE" ] || usage_error "a video file is required"
[ -f "$FILE" ] || fail "not a file: $FILE"
[ -r "$FILE" ] || fail "not readable: $FILE"
FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"

if server_running; then
    fail "already running - run 'serve-video-rtsp --stop' first"
fi
rm -f "$MEDIAMTX_PIDFILE" "$FFMPEG_PIDFILE"

if port_open "$PORT"; then
    fail "port $PORT is already in use - use -p <port>, or 'serve-video-rtsp --stop' if that server is ours"
fi

log "checking mediamtx"
"$SCRIPT_DIR/check-mediamtx.sh"
select_ffmpeg
log "using ffmpeg: $FFMPEG"

cat > "$CONFIG" <<EOF
logLevel: info
logDestinations: [file]
logFile: "$RUNTIME/mediamtx.log"
rtspAddress: ":$PORT"
paths:
  $NAME:
    source: publisher
EOF

log "starting mediamtx on port $PORT"
(
    cd "$RUNTIME"
    exec "$BIN_DIR/mediamtx" "$CONFIG" >"$RUNTIME/mediamtx.out" 2>&1 </dev/null
) &
MTX_PID=$!
echo "$MTX_PID" > "$MEDIAMTX_PIDFILE"
STARTED=1

wait_for_port() {
    local i
    for i in $(seq 1 50); do
        port_open "$PORT" && return 0
        alive "$MTX_PID" || return 1
        sleep 0.2
    done
    return 1
}
if ! wait_for_port; then
    log "mediamtx did not open port $PORT - its output follows"
    tail -n 20 "$RUNTIME/mediamtx.out" >&2 || true
    tail -n 20 "$RUNTIME/mediamtx.log" >&2 || true
    exit 1
fi

launch_ffmpeg() {
    "$FFMPEG" -nostdin -hide_banner -loglevel warning -re -stream_loop -1 -i "$FILE" \
        "$@" -f rtsp -rtsp_transport tcp "rtsp://127.0.0.1:$PORT/$NAME" \
        >"$FFMPEG_LOG" 2>&1 </dev/null &
    FFMPEG_PID=$!
    echo "$FFMPEG_PID" > "$FFMPEG_PIDFILE"
}

log "publishing $FILE (loops forever)"
launch_ffmpeg -c copy
sleep 2
if ! alive "$FFMPEG_PID"; then
    log "stream copy was rejected - retrying with an H.264/AAC transcode"
    launch_ffmpeg -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac
    sleep 3
    if ! alive "$FFMPEG_PID"; then
        log "ffmpeg could not publish $FILE - its log follows"
        tail -n 30 "$FFMPEG_LOG" >&2 || true
        exit 1
    fi
fi

OK=1
LAN_IP="$( (hostname -I 2>/dev/null || true) | awk '{print $1}')"
[ -n "$LAN_IP" ] || LAN_IP="$(hostname 2>/dev/null || echo 127.0.0.1)"

echo
log "RTSP ready"
echo "    rtsp://$LAN_IP:$PORT/$NAME"
echo "    rtsp://127.0.0.1:$PORT/$NAME    (this machine)"
echo "    video:  $FILE   (loops forever)"
echo "    logs:   $RUNTIME/mediamtx.log, $RUNTIME/ffmpeg.log"
echo "    stop:   serve-video-rtsp --stop"
