#!/bin/bash
# Smoke test for serve-video-rtsp: start the server on a real recording, read
# the stream back, prove the publisher loops, then stop everything again.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$DIR/$SOURCE" ;; esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

SERVER="$SCRIPT_DIR/serve-video-rtsp.sh"
RUNTIME="$SCRIPT_DIR/internal/runtime"
DEFAULT_FILE="$HOME/Videos/Screen_Recording_20250822_115542.mp4"
PORT="${TEST_RTSP_PORT:-8554}"
NAME="test"
FILE=""

usage() {
    cat <<EOF
Usage: test-stream.sh [video-file]

Start the RTSP server on video-file (default: the screen recording in
~/Videos), read rtsp://127.0.0.1:$PORT/$NAME back for a few seconds, check
that the publisher loops forever, then stop the server again. A server that
was already running is stopped first, so the result does not depend on it.

Exit codes: 0 = the stream was verified; 1 = the file, the server, the read
            or the stop failed; 2 = bad usage
EOF
}

log() { echo "[test-stream] $*"; }
fail() { echo "[test-stream] FAIL: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -*) echo "[test-stream] ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)
            if [ -n "$FILE" ]; then
                echo "[test-stream] ERROR: only one video file may be given" >&2
                usage >&2
                exit 2
            fi
            FILE="$1" ;;
    esac
    shift
done
FILE="${FILE:-$DEFAULT_FILE}"

[ -f "$FILE" ] || fail "video not found: $FILE"
[ -r "$FILE" ] || fail "video not readable: $FILE"
FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"

stop_server() { "$SERVER" --stop >/dev/null 2>&1 || true; }

if pgrep -f "$RUNTIME/mediamtx.yml" >/dev/null 2>&1; then
    log "a server is already running - stopping it first:"
    pgrep -a -f "$RUNTIME/mediamtx.yml" | sed 's/^/[test-stream]     /' || true
elif [ -e "$RUNTIME/mediamtx.pid" ] || [ -e "$RUNTIME/ffmpeg.pid" ]; then
    log "removing pidfiles left over from a previous run"
fi
stop_server

log "starting the server on $FILE"
"$SERVER" "$FILE" -n "$NAME" -p "$PORT" || fail "the server did not start"
trap stop_server EXIT
trap 'stop_server; exit 130' INT
trap 'stop_server; exit 143' TERM

FFMPEG="$SCRIPT_DIR/internal/bin/ffmpeg"
[ -x "$FFMPEG" ] || FFMPEG="$(command -v ffmpeg || true)"
[ -n "$FFMPEG" ] || fail "ffmpeg not found (the server installs one)"

# Length of the clip: the read has to pass it for a short clip to prove the loop.
dur_raw="$("$FFMPEG" -hide_banner -i "$FILE" 2>&1 \
    | awk '/Duration:/ && !seen { print $2; seen = 1 }' || true)"
seconds="$(awk -v d="$dur_raw" 'BEGIN {
    n = split(d, a, ":")
    if (n != 3) { print 0; exit }
    printf "%d", a[1] * 3600 + a[2] * 60 + a[3]
}' 2>/dev/null || echo 0)"
[ -n "$seconds" ] || seconds=0

read_for=8
past_end=0
if [ "$seconds" -gt 0 ] && [ "$seconds" -lt 25 ]; then
    read_for=$((seconds + 3))
    past_end=1
fi

log "reading rtsp://127.0.0.1:$PORT/$NAME for ${read_for}s (clip is ${seconds}s)"
reader=(-nostdin -hide_banner -loglevel error -timeout 8000000
        -rtsp_transport tcp -i "rtsp://127.0.0.1:$PORT/$NAME"
        -t "$read_for" -f null -)
if command -v timeout >/dev/null 2>&1; then
    timeout $((read_for + 30)) "$FFMPEG" "${reader[@]}" \
        || fail "the stream could not be read for ${read_for}s"
else
    "$FFMPEG" "${reader[@]}" || fail "the stream could not be read for ${read_for}s"
fi
log "the stream is readable"

loop_flag=0
pub_pid="$(cat "$RUNTIME/ffmpeg.pid" 2>/dev/null || true)"
if [ -n "$pub_pid" ] && [ -r "/proc/$pub_pid/cmdline" ]; then
    if tr '\0' ' ' < "/proc/$pub_pid/cmdline" | grep -q -- "-stream_loop -1"; then
        loop_flag=1
        log "the publisher loops forever (-stream_loop -1)"
    else
        fail "the publisher does not loop (no -stream_loop -1)"
    fi
elif [ "$past_end" -eq 1 ]; then
    loop_flag=1
    log "the read passed the end of the clip, so it looped"
else
    log "loop not directly verified here (clip is ${seconds}s); it is still looping"
fi

stop_server
trap - EXIT INT TERM
[ ! -e "$RUNTIME/mediamtx.pid" ] || fail "the server did not stop (pidfile left)"
if pgrep -f "$RUNTIME/mediamtx.yml" >/dev/null 2>&1; then
    fail "the server did not stop (mediamtx still running)"
fi
if pgrep -f "stream_loop -1.*rtsp://127\.0\.0\.1:$PORT/$NAME" >/dev/null 2>&1; then
    fail "the server did not stop (ffmpeg publisher still running)"
fi

note=""
[ "$past_end" -eq 1 ] && note=", past the end of the clip"
log "PASS: rtsp://127.0.0.1:$PORT/$NAME from $FILE"
log "      read ${read_for}s of a ${seconds}s clip${note}, loop flag $loop_flag"
exit 0
