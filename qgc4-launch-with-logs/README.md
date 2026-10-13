# QGroundControl Launcher with Logging

Launch QGroundControl and capture C++/QML logs to a timestamped file
(`qgc_YYYY_MM_DD_HHMMSS.log` in the current working directory). Use this
INSTEAD of running QGC directly when debugging parameter loading, MAVLink
issues, vehicle connection, or any C++ qCDebug/qCInfo output.

## Drag & Drop (Windows)

Drag a **QGroundControl git repository folder** onto `drop-qgc-folder-here.cmd`.

The wrapper window returns immediately; launcher output, QGC logs and the
final summary live in the separate **QGC Launcher** window. Press Ctrl+C
there to stop QGC — no `Terminate batch job` prompt can appear in that
window — and the launcher reports where the partial log was saved.

## Command Line

```bash
python internal/launch_qgc.py --help     # all options, Windows/Linux/macOS
./launch-qgc.sh [QGC_REPO_ROOT]          # shell launcher
```

The log is created in the current working directory. Default categories
cover parameter loading, MAVLink, health checks and GStreamer (see
`--help`).

## Options

| Flag            | Default                           | Description                              |
| --------------- | --------------------------------- | ---------------------------------------- |
| `QGC_REPO_ROOT` | three levels above the tool folder | Path to QGroundControl git repository   |
| `--categories`  | 5 default categories              | Space-separated log categories to enable |
| `--no-log-file` | false                             | Output to console only, no log file      |
| `--pause`       | false                             | Wait for Enter before exiting            |
| `--help`        | -                                 | Print all options and exit               |

## Exit codes

`0` — success, `1` — executable not found or launch failed, `2` — invalid
arguments, `130` — interrupted; any other value is QGC's own exit code.

## Requirements

Python 3.6+ (for the `.py` launcher); QGroundControl built with Qt 5.15.

## Guarantees

- Auto-detects OS (Windows/Linux/macOS) and finds the Debug/Release
  executable
- Never modifies QGC source, build artifacts, or settings/INI files — only
  environment variables for the launched process
- Log file created in **current working directory**, not the repo
- Idempotent: multiple runs produce separate timestamped logs
- stdout/stderr both captured to the log file and console

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
