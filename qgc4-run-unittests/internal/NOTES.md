# internal/NOTES.md — qgc4-run-unittests

## Layout

- `run_unittests.py` — the whole tool: exe lookup, launch, live progress
  filter, verdict parsing.
- `test_run_unittests.py` — unit tests for the pure functions
  (`parse_output`, `is_live_line`, `available_log_path`,
  `failure_ids`, `classify_failures`, `historical_baseline`,
  `load_baseline_file`); the orchestration loop needs a real QGC build
  and is exercised manually.

## How to run the tests

```bash
python3 internal/test_run_unittests.py
```

## Detection rules

- Verdict markers (src/main.cc:403,406):
  - `<n> TESTS FAILED!` -> failed; this marker has priority: a
    stress run can emit both markers across iterations
  - `ALL TESTS PASSED` (and no failure marker) -> passed
  - neither -> no-verdict (exit 4): QGC crashed, or the Debug build is
    missing UNITTEST_BUILD (qgroundcontrol.pro:495 requires DebugBuild
    plus firmware plugin scopes). A no-verdict run ignores the baseline
    and always fails — an unfinished run proves nothing about tests.
- Per-suite counts come from QTest's own `Totals: N passed, M failed`
  lines; a suite counts as failed when M > 0.
- `FAIL!  : TestName::case() message` lines are reported verbatim; their
  identity for baseline purposes is `TestName::case` (message dropped:
  messages embed temp paths/indexes that vary between runs).

## Known-failure baseline (NEW vs KNOWN)

- Identity: `FAIL_ID` regex `^FAIL!\s+:\s*([\w:]+)\(\)`.
- Default source: union of `failure_ids()` over `qgc_unittest_*.log`
  in the *current working directory*, computed BEFORE the current run
  opens its log — self-baselining is structurally impossible
  (`historical_baseline` runs before `available_log_path`).
- `--baseline FILE` replaces the auto scan; missing file -> exit 2.
- Classification only affects the failed-marker branch:
  - any `NEW FAIL` -> exit 1
  - all `KNOWN FAIL` -> exit 0, `RESULT: PASSED - only baseline-known
    failures` (matches qgc4-smoke's "noise never fails the run")
- Stale logs are a real hazard (a fixed test stays known forever);
  delete old logs or use a curated `--baseline` file to tighten it.

## Why the exit code is ignored

QGC's `main()` returns 0 on success, but teardown asserts in
`qhostinfo.cpp` (`QCoreApplication::instance()` already deleted) and the
process aborts with exit 3 — observed on this fork (2026-10-12). A
verdict based on exit codes would therefore always report failure. The
output markers are written before teardown and are reliable.

## Single-test argument form

`ParseCmdLineOptions` (src/CmdLineOptParser.cc:38) only accepts
`--unittest:Name` (colon). `--unittest Name` sets the flag but leaves the
name empty -> runs every test. The runner always emits the colon form.

## Algorithm

1. Require `qgroundcontrol.pro` in qgc_root (exit 2).
2. Require the Debug staging exe (exit 3); never guess a release build.
3. Compute the baseline (auto scan of cwd logs, or `--baseline FILE`;
   missing file -> exit 2) BEFORE picking this run's log path.
4. Launch with `--no-windows-assert-ui --unittest[:Name]`, cwd = exe dir,
   `QT_ASSUME_STDERR_HAS_CONSOLE` + `QT_FORCE_STDERR_LOGGING` set so
   qDebug markers reach stderr on Windows.
5. Tee stdout+stderr to a timestamped log via a reader thread; echo
   progress lines matching `LIVE_PREFIXES` only.
6. Poll the process against the deadline (`--timeout`); on expiry kill the
   whole process tree (exit 4). The reader thread exists because a blocking
   readline() on a hung-but-open pipe defeats a naive `proc.wait(timeout=)`.
7. Parse the log for markers, Totals, and FAIL lines; classify each FAIL
   as NEW or KNOWN against the baseline; print the closing block
   (totals, NEW/KNOWN FAIL lines, log path+size when non-empty, blank
   line, one `RESULT:` verdict line); exit 0/1/4.

## Known limitations

- Executable lookup is Windows-only (Debug staging path); on other OSes
  point the wrapper at a Windows-built tree or extend `find_debug_exe`.
- `--unittest-stress` and `--unittest` extras are not exposed; add flags
  only when a real workflow needs them.

## Invariants to preserve when editing

- The verdict must never be derived from the process exit code.
- The colon form of `--unittest:Name` must be preserved; a test asserts it.
- `--no-windows-assert-ui` must stay in the command line (unattended runs).
- The baseline must be computed BEFORE this run's log path is chosen;
  a run must never baseline itself.
- A no-verdict (crashed) run must ignore the baseline and always exit 4.
