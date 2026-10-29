---
name: qgc5-run-with-logs
description: Launch a deployed QGroundControl 5 (CMake/Qt 6) build with timestamped logs, QGC CLI logging, core-dump preparation, and optional GStreamer dot dumps. Use when running a Docker/AppImage/AppDir build for debugging crashes, MAVLink, parameters, or video without modifying the checkout.
---

## Commands

```bash
run-qgc5                                    # auto-detect build/ in nearest QGC 5 checkout
run-qgc5 ~/qgroundcontrol --build-dir ./build
run-qgc5 --gst-dump --categories MAVLink FactSystem
run-qgc5 --no-dump                          # skip ulimit/core-dump prep
run-qgc5 -- --clear-settings                # pass args to QGroundControl
```

## Options

| Flag                 | Default                 | Description                                    |
| -------------------- | ----------------------- | ---------------------------------------------- |
| `QGC_ROOT`           | current / nearest QGC 5 | Checkout root                                  |
| `--build-dir`        | `<root>/build`          | Build/deploy directory                         |
| `--executable`       | auto-detect             | Binary or AppImage                             |
| `--categories`       | 5 defaults              | Comma or space separated log categories        |
| `--log-file`         | `./qgc5_*.log`          | Custom log file                                |
| `--no-log-file`      | off                     | Console only                                   |
| `--dump`/`--no-dump` | `--dump`                | Prepare core dumps; write crash report         |
| `--gst-dump` `[DIR]` | off                     | Set `GST_DEBUG_DUMP_DOT_DIR` for `.dot` graphs |
| `--`                 | -                       | Pass remaining args to QGroundControl          |
| `-h`, `--help`       | -                       | Show usage                                     |

## Exit codes

`0` — success, `1` — not found/launch failed, `2` — bad usage, `130` —
interrupted, `128-signal` — crashed (crash report written), otherwise QGC's
exit code.

## Guarantees

- Auto-detects AppImage, `AppDir/AppRun`, or other deployed binaries; does not
  run the unlinked `build/Release/QGroundControl`
- Adds `--log-output` and `--logging` unless already provided
- On crash, leaves a `qgc5_*.dump` report and explains core capture based on
  `/proc/sys/kernel/core_pattern` (apport/systemd-coredump/local)
- Never modifies the checkout, settings, or build artifacts
- Refuses root and works around missing `/dev/fuse` for AppImages

Read `internal/NOTES.md` only if the output looks wrong or you need to change
the script.
