# internal/NOTES.md — qgc4-smoke

## Layout

- `smoke_qgc.py` — the whole tool: build step, launch/wait/close loop,
  log analysis (pure functions at the top), verdict.
- `test_smoke_qgc.py` — unit tests for the pure functions only; the
  orchestration loop needs a real QGC run and is exercised manually.

## How to run the tests

```bash
python3 internal/test_smoke_qgc.py
```

## Detection rules

- A log line is a QML error when, after stripping the launcher's
  `timestamp pid category:` prefix, it either
  - contains `QQmlApplicationEngine failed` (whole line becomes the
    signature), or
  - matches `<file>.qml|js:<line>[:<col>]: <message>` where `<message>`
    contains one of `ERROR_KEYWORDS` (TypeError, ReferenceError,
    SyntaxError, Binding loop, is not a type, Cannot assign, Unable to
    assign, is not installed, failed to load).
- Keyword list is deliberately narrow: a broad word like `error` would
  fail the run on unrelated C++/GStreamer warnings seen in the historical
  logs. Add a keyword only after seeing a real missed QML error.
- Baseline default = union of signatures across `qgc_*.log` in the repo
  root. The run's own log is excluded by name snapshot taken before
  launch (`before` set in `main`).

## Algorithm

1. Parse args; require `qgroundcontrol.pro` in `qgc_root` (exit 2).
2. Build via `qgc4-builder/internal/build-qgc.cmd` unless `--no-build`
   (exit 3 on failure; Windows-only).
3. Compute the baseline BEFORE launching (explicit file, or historical
   logs), so the new run cannot baseline itself.
4. `close-qgc` first: a stale instance would swallow the launch and make
   early-exit detection lie.
5. Snapshot `qgc_*.log` names, record start time, launch
   `launch_qgc.py` with cwd = qgc_root (the launcher tees the log into
   its cwd), wait `--seconds`, note early death, close QGC, reap.
6. Find the new log (name not in snapshot, mtime >= start - 2s).
7. Extract signatures, subtract baseline, report, exit 0/1. No log at
   all = exit 4.

## Known limitations

- `--build` is Windows-only because `qgc4-builder` is; `--no-build`
  works anywhere Python runs.
- MockLink is not started, so vehicle-dependent TypeErrors only appear
  once someone adds a `--mocklink` flag (tooling gap #5).
- Two runs within the same second can race the log-name collision; the
  launcher's `_counter` suffix handles it, `find_new_log` takes the
  newest mtime.
- `--seconds` counts from process start; a very slow first build inside
  the same invocation is not counted (build happens before launch).
- The baseline glob `qgc_*.log` also matches `qgc_unittest_*.log` files
  written by `qgc4-run-unittests` into the same directory. This is
  deliberate: those are real QGC runs too, and QTest `FAIL!` lines have
  no `.qml:` locator so they are never extracted as signatures.

## Invariants to preserve when editing

- The baseline is computed before the launcher starts; never move it
  after launch.
- Signatures must stay line-number-free; tests assert this.
- Exit codes are part of the README contract; update README and this
  file in the same edit (see ../../LESSONS.md).
