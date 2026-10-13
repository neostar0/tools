# QGC Launcher - Developer Notes

## Layout

| File                          | Purpose                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| `internal/launch_qgc.py`      | Cross-platform Python launcher (Windows/Linux/macOS)       |
| `internal/test_launch_qgc.py` | Unit tests (stdlib only)                                   |
| `drop-qgc-folder-here.cmd`    | Windows drag-and-drop entry; calls `launch_qgc.py`         |
| `launch-qgc.sh`               | Shell launcher for Linux/macOS (self-contained, no Python) |
| `internal/NOTES.md`           | This file                                                  |

## How to Run Tests

```bash
# Direct
python internal/test_launch_qgc.py -v

# Discovery (from this package folder)
python -m unittest discover internal -v
```

## Detection Rules

### OS Detection
- `sys.platform.startswith("win")` → windows
- `sys.platform.startswith("linux")` → linux
- `sys.platform.startswith("darwin")` → macos
- else → unknown

### Executable Search Priority (Windows)
1. `build/Desktop_Qt_5_15_2_MSVC2019_64bit-Debug/staging/QGroundControl.exe`
2. `build/Desktop_Qt_5_15_2_MSVC2019_64bit-Release/staging/QGroundControl.exe`
3. Recursive `rglob("QGroundControl.exe")` fallback

### Executable Search Priority (Linux)
1. `build/staging/QGroundControl` (executable)
2. `build/release/staging/QGroundControl` (executable)
3. Recursive `rglob("QGroundControl")` + executable check

### Executable Search Priority (macOS)
1. `build/staging/QGroundControl.app/Contents/MacOS/QGroundControl`

## Algorithm (launch_qgc.py)

1. Parse CLI args (repo root, `--categories`, `--no-log-file`, `--pause`)
2. Detect OS via `sys.platform`
3. Resolve QGC repo root (arg → three levels above the tool root → cwd)
4. Search for executable per OS priority list
5. Build environment: `QGC_LOGGING_CATEGORIES`, `QT_FORCE_STDERR_LOGGING=1`,
   `QT_ASSUME_STDERR_HAS_CONSOLE=1`, `QT_LOGGING_RULES`, `PYTHONUNBUFFERED=1`
6. Generate timestamp: `YYYY_MM_DD_HHMMSS`; log file is
   `<cwd>/qgc_<timestamp>.log` (`_1`, `_2`… appended if that name already
   exists, so same-second runs cannot overwrite each other)
7. Launch process; tee stdout+stderr (binary chunks) to console and log file
8. Print QGC's exit code and propagate it (130 on Ctrl+C)
9. If `--pause` was given, wait for Enter before exiting — on every exit
   code, Ctrl+C (130) included (the `.cmd` wrapper passes it; agents never
   should). A second Ctrl+C during the wait force-closes

## The .cmd Wrapper (Ctrl+C)

`drop-qgc-folder-here.cmd` starts python with:

```
start "QGC Launcher" python "...launch_qgc.py" --pause %*
```

Why `start` and not a direct call:

- "Terminate batch job (Y/N)?" is printed by **cmd.exe** while it is running
  a batch file and a Ctrl+C landed. If python runs in its own console
  (`start` without `/b`), no cmd.exe is attached to that window, so the
  prompt is impossible there — by construction, not by trick.
- The wrapper's own window exits immediately after `start` returns; the QGC
  window shows the launcher output, the summary, and the `--pause` wait.
  One prompt total, never two.
- Ctrl+C in the QGC window reaches only python + QGC, so the user's
  interactive shell (if the wrapper was called from one) is never
  interrupted, and vice versa.
- The npm cmd-shim `goto #_undefined_#` suppression was tried here and
  **failed on real Windows** (prompt still appeared after a paused exit) —
  do not bring it back.
- On Ctrl+C python terminates the QGC child itself instead of relying on
  QGC handling the console event; otherwise a QGC that ignores it would
  outlive python and keep the window alive.

## Known Limitations

- **Drag & drop**: Windows only, via `drop-qgc-folder-here.cmd`; the `.sh`
  and Python entries take the repo path as a CLI argument
- **Qt version**: Standard search paths hardcoded to Qt 5.15 MSVC2019 64-bit
- **Log file location**: Always in CWD, not next to the exe
- **Exit codes**: QGC's own exit code is propagated; the launcher exits 1
  when no executable is found or the launch raises, 2 on bad CLI args,
  130 on Ctrl+C
- **No config file**: Categories only via `--categories` or defaults

## Invariants to Preserve

1. **Never modify QGC files** — only environment variables for the subprocess
2. **Timestamp per invocation** — not per log line
3. **Idempotent launches** — each run creates a new timestamped log file
4. **Stdout+stderr to log** — both streams captured (merged in the Python
   launcher; the `.sh` entry uses `tee`)
5. **Missing executable fails loudly** — one-line error listing the searched
   paths, exit 1, never a traceback
