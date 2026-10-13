# QGC Smoke Test (build, launch, assert no new QML errors)

One command that builds QGroundControl, launches it, keeps it running for
a while, closes it, and fails if the run log contains any QML error
signature that was not already in the baseline noise. Use after any QML
or C++ change to catch load failures and runtime QML errors without
reading the log by hand.

## Command Line

```cmd
qgc4-smoke.cmd E:\MyQGC                 REM full smoke: build + launch + assert
qgc4-smoke.cmd E:\MyQGC --no-build      REM test the existing executable only
qgc4-smoke.cmd E:\MyQGC --seconds 60    REM keep QGC running longer
```

```bash
./qgc4-smoke.sh /path/to/QGC --no-build
```

## Options

| Flag                   | Default                                    | Description                                                |
| ---------------------- | ------------------------------------------ | ---------------------------------------------------------- |
| `qgc_root`             | required                                   | Path to QGroundControl git repository                      |
| `--config`             | `debug`                                    | `debug` or `release` (build configuration)                 |
| `--no-build`           | false                                      | Skip the build step, test the existing executable          |
| `--seconds`            | `30`                                       | Seconds to keep QGC running before closing it              |
| `--baseline FILE`      | historical `qgc_*.log` files in `qgc_root` | Baseline signatures (one per line, `#` comments allowed)   |
| `--save-baseline FILE` | (none)                                     | Write this run's signatures to FILE                        |
| `--pause`              | false                                      | Wait for Enter before exiting (drag-and-drop entries only) |

## Exit codes

`0` — no new QML errors; `1` — new QML error signature(s) found;
`2` — bad arguments or not a QGC repo root; `3` — build failed;
`4` — QGC did not start or exited early without a logable QML error;
`130` — interrupted (QGC is closed on the way out).

## Requirements

Windows for the build step (needs `qgc4-builder`: Qt 5.15.2 msvc2019_64,
Visual Studio C++ workload); any OS with Python 3.6+ for `--no-build`.
Sibling tools are required in place: `qgc4-builder`,
`qgc4-launch-with-logs`, `close-qgc`.

## Guarantees

- Baselines the known noise automatically: signatures are collected from
  the historical `qgc_*.log` files already in the repo root (or an
  explicit `--baseline` file), so only errors new to this codebase fail
  the run
- Signatures drop line/column numbers (`file.qml: message`), so edits
  above an error do not invalidate the baseline
- Closes QGC before and after every run; never leaves an instance running
- The run's own log never contributes to its own baseline
- Never modifies source, build artifacts, or settings; writes only the
  launcher's `qgc_*.log` in the repo root (same as `qgc4-launch-with-logs`)

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
