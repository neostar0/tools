# run-qgc5

Launch a deployed QGroundControl 5 build with timestamped logs, automatic
log-category setup, and crash-dump preparation. Use it when debugging
parameter loading, MAVLink traffic, GStreamer/video issues, or crashes in a
CMake/Qt 6 build produced by `build-qgc5`.

## Command Line

```bash
run-qgc5                              # build/ in the nearest QGC 5 checkout
run-qgc5 ~/qgroundcontrol             # another checkout
run-qgc5 --build-dir ./build-debug   # specific build directory
run-qgc5 --categories MAVLink FactSystem  # override log categories
run-qgc5 --gst-dump                  # write GStreamer .dot graphs to qgc5_*_gst/
run-qgc5 --no-dump                   # skip core-dump preparation
run-qgc5 -- /path/extra/arg          # pass arguments to QGroundControl
run-qgc5 --executable ./build/AppDir/usr/bin/QGroundControl
```

On Windows, run the same arguments through `run-qgc5.cmd` or drag a
QGroundControl 5 checkout folder onto `drop-qgc5-folder-here.cmd`. The wrapper
opens a separate `QGC5 Launcher` window and passes `--pause`.

## Options

| Flag                 | Default                        | Description                              |
| -------------------- | ------------------------------ | ---------------------------------------- |
| `QGC_ROOT`           | current dir / nearest QGC 5    | QGroundControl 5 checkout                |
| `--root`             | same as above                  | Alternate form                           |
| `--build-dir`        | `<root>/build`                 | Build/deploy directory                   |
| `--executable`       | auto-detect                    | Binary or AppImage to run                |
| `--categories`       | 5 defaults                     | Log categories; comma or space separated |
| `--log-file`         | `./qgc5_YYYY_MM_DD_HHMMSS.log` | Custom log path                          |
| `--no-log-file`      | off                            | Console only                             |
| `--dump`/`--no-dump` | `--dump`                       | Prepare core dumps, write a crash report |
| `--gst-dump` `[DIR]` | off                            | Enable `GST_DEBUG_DUMP_DOT_DIR`          |
| `--pause`            | off                            | Wait for Enter before exiting            |
| `--`                 | -                              | Pass remaining args to QGroundControl    |
| `-h`, `--help`       | -                              | Print the usage screen and exit          |

Default categories: `FactSystem.ParameterManager`,
`FactSystem.FactPanelController`, `MAVLink`, `Video.GStreamer`,
`Comms.LinkManager`.

## Behavior

- Appends `--log-output` and `--logging <categories>` unless already
  specified after `--`.
- Auto-detects the deployed executable in order: newest `*.AppImage`, then
  `AppDir/AppRun`, then `AppRun` if `usr/bin` exists, macOS bundles,
  `Release/QGroundControl*`, or `usr/bin`/`bin` binaries. For a Docker-built
  tree the recommended targets are `build/QGroundControl-*.AppImage` or
  `build/AppDir/AppRun`.
- On Linux, sets `ulimit -c unlimited` for the child and, on crash, writes a
  `qgc5_*.dump` report describing the signal and how to retrieve a core file
  (apport, `systemd-coredump`/`coredumpctl`, or a local `core` file depending on
  `/proc/sys/kernel/core_pattern`).
- If `/dev/fuse` is missing, runs AppImages with `APPIMAGE_EXTRACT_AND_RUN=1`.
- Refuses to run as root (QGC itself requires a non-root user).
- Never modifies the checkout, settings, or build artifacts.

## Exit codes

`0` — success, `1` — not found or launch failed, `2` — bad usage, `130` —
interrupted; if signalled, returns `128 - signal`; otherwise QGC's own exit
code.

## Requirements

Python 3.6+, a deployed QGroundControl 5 build, and (for AppImages) FUSE or
`APPIMAGE_EXTRACT_AND_RUN` support.
