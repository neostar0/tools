# serve-video-rtsp

Serve a video file as a live RTSP stream that loops forever. mediamtx is the
RTSP server, ffmpeg reads the file in real time and publishes it into the
server, and the `rtsp://` URL is printed as soon as both are up. Use it when a
phone, a ground station, VLC or an RTSP client needs a camera-like source
built from a file: a test clip, a recorded flight, a synthetic pattern.

Two entries ship here. Every download (mediamtx, plus ffmpeg when the machine
has none) lands in this folder's `internal/bin`, so the tool is self-contained
and `--stop` is the only thing needed to take it back down.

## Command Line

```cmd
serve-video-rtsp.cmd <video-file> [-n NAME] [-p PORT]   REM Windows
serve-video-rtsp.cmd --stop                             REM Windows
```

```bash
./serve-video-rtsp/serve-video-rtsp.sh <video-file> [-n NAME] [-p PORT]
./serve-video-rtsp/serve-video-rtsp.sh --stop

./serve-video-rtsp/check-mediamtx.sh [--force]   # install mediamtx alone
./serve-video-rtsp/check-mediamtx.cmd            REM Windows
```

Run an entry with no arguments (or `--help`) for the full usage screen.
`check-mediamtx` is the dedicated installer: it verifies the pinned release
against the published SHA-256 and unpacks it into `internal/bin`, and does
nothing at all when a working binary is already there.

## Output

```text
[serve-video-rtsp] RTSP ready
    rtsp://192.168.50.113:8554/stream
    rtsp://127.0.0.1:8554/stream    (this machine)
    video:  /videos/demo.mp4   (loops forever)
    logs:   .../internal/runtime/mediamtx.log, .../internal/runtime/ffmpeg.log
    stop:   serve-video-rtsp --stop
```

Play the second URL on the same machine, the first one from anywhere that can
reach this host.

## Options

| Flag/arg       | Default  | Effect                                       |
| -------------- | -------- | -------------------------------------------- |
| `<video-file>` | -        | File to stream; must exist and be readable   |
| `-n`, `--name` | `stream` | RTSP path name, `[A-Za-z0-9_.-]+`            |
| `-p`, `--port` | `8554`   | RTSP listen port, `1-65535`                  |
| `--stop`       | -        | Stop the server this tool started            |
| `--force`      | -        | `check-mediamtx` only: download and replace  |
| `-h`, `--help` | -        | Print the usage screen and exit              |

## Exit codes

`0` — the stream is up, the server stopped cleanly, or mediamtx is already
installed; `1` — a dependency could not be installed, the file is missing or
unreadable, the port is busy, an already running instance was not stopped, or
ffmpeg/mediamtx died during startup (the failing log is printed); `2` — bad
usage (unknown option, missing value, bad name or port, two files).

## Test

`test-stream.sh` is the smoke test for this tool (Linux/macOS):

```bash
./serve-video-rtsp/test-stream.sh                    # uses ~/Videos/Screen_Recording_20250822_115542.mp4
./serve-video-rtsp/test-stream.sh /path/to/clip.mp4  # or any other file
```

It stops the server first if one is already running (so the result never
depends on what was up before - a stream you are watching goes away), starts a
fresh one on the file under the RTSP path `test`, reads
`rtsp://127.0.0.1:8554/test` back for a few seconds, checks that the publisher
loops forever, then stops everything again: a passed test leaves nothing
running. `TEST_RTSP_PORT` changes the port, and `--help` prints the screen
above.

Exit codes: `0` — the stream was verified; `1` — the file, the server, the
read or the stop failed; `2` — bad usage (unknown option or two files).

## Requirements

Bash on Linux/macOS, or `cmd` with Windows PowerShell 5.1 on Windows.
Network access is needed on the first run to fetch mediamtx and, only when the
machine has no `ffmpeg` on `PATH` and none in `internal/bin`, one static
ffmpeg build. Unix downloads use `curl` or `wget`; Windows uses
`Invoke-WebRequest`. The file must hold a codec RTSP can carry (H.264/AAC and
friends); when stream copy is rejected the publisher retries once with an
H.264/AAC transcode, and reports ffmpeg's log if that fails too.

## Guarantees

- The file loops forever (`-stream_loop -1` at the file's native rate), so a
  three second clip keeps playing until `--stop`
- Nothing is written outside this folder: binaries in `internal/bin`, config,
  pid files and logs in `internal/runtime`
- `--stop` kills exactly the two pid files this tool wrote and reports
  `not running` (exit `0`) when there is nothing to stop
- The mediamtx archive is checked against the release's SHA-256 before it is
  installed, and the version is pinned (`MEDIAMTX_VERSION` overrides it)
- User input never reaches a child process as command text on Windows: the
  file path and stream name travel as environment variables into
  `internal/start-process.ps1`
