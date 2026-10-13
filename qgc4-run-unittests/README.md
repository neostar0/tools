# QGC Unit Test Runner

Run QGroundControl's in-process unit tests (`--unittest`) and get a
trustworthy pass/fail verdict. Use before committing C++ or QML-adjacent
changes, or to reproduce a single failing test, without reading the output
by hand.

## Command Line

```cmd
qgc4-run-unittests.cmd E:\MyQGC                    REM every registered test
qgc4-run-unittests.cmd E:\MyQGC SignalSpyTest      REM one test object
qgc4-run-unittests.cmd E:\MyQGC --timeout 600      REM kill a hung run sooner
```

```bash
./qgc4-run-unittests.sh /path/to/QGC SignalSpyTest
```

## Arguments

| Arg          | Default  | Description                                                                                                                       |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `qgc_root`   | required | Path to QGroundControl git repository                                                                                             |
| `test_name`  | (none)   | Test object name (e.g. `SignalSpyTest`); default runs them all                                                                    |
| `--timeout`  | `1800`   | Seconds before the run is killed as hung                                                                                          |
| `--baseline` | (auto)   | Known-failure file, one `TestName::case` per line; default unions the `qgc_unittest_*.log` files already in the current directory |

## Known failures vs new failures

Failures are classified by test identity (`TestName::case`) against a
baseline, so a pre-existing broken test never hides a new regression:

- The closing block prints `NEW  FAIL:` and `KNOWN FAIL: ... (in
  baseline)` lines separately.
- **Exit 1 only when there is at least one NEW failure.** If every failure
  is already in the baseline the run reports
  `RESULT: PASSED - only baseline-known failures` (exit 0) — you broke
  nothing new.
- The baseline is computed **before** this run writes its own log, so a
  run can never baseline itself.
- To freeze what counts as known, pass `--baseline known_tests.txt` (one
  id per line, `#` comments). To forget old failures, delete the stale
  `qgc_unittest_*.log` files.
- A crash (no verdict marker) is always exit 4 regardless of the
  baseline: missing coverage is not "known", it is a broken run.

## Exit codes

`0` — `ALL TESTS PASSED`, or every reported failure is baseline-known;
`1` — at least one **new** test failure; `2` — bad arguments, not a QGC
repo root, or missing `--baseline` file; `3` — Debug executable not
found (release builds have no `--unittest`); `4` — no verdict marker
(QGC crashed) or the `--timeout` killed the run; `130` — interrupted.

## Requirements

- A **Debug** build with `UNITTEST_BUILD` (built via `qgc4-builder`
  default debug). Release builds compile `--unittest` out — the runner
  refuses with exit 3 rather than silently launching the GUI.
- Windows paths for the executable (`build\Desktop_...\staging\
  QGroundControl.exe`); the Python wrapper itself is cross-platform.

## Guarantees

- Judges **only** by QGC's own output markers (`ALL TESTS PASSED` /
  `N TESTS FAILED!`) — never by the process exit code, which is
  unreliable: QGC aborts during shutdown even on success
- Always passes `--no-windows-assert-ui` so an assert cannot pop a dialog
  and hang an unattended run
- Uses the colon form `--unittest:Name`; a space is silently ignored by
  QGC's parser and would run every test instead of one
- Prints the closing block (totals, every failure split into
  `NEW FAIL` / `KNOWN FAIL`, log path+size when non-empty, blank line, one
  `RESULT: PASSED/FAILED` line with exit code); full output saved to
  `qgc_unittest_YYYY_MM_DD_HHMMSS.log` in the current directory
- Never modifies source, build artifacts, or settings; a hung run is
  killed process-tree-wide at `--timeout`

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
