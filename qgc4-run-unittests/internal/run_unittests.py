#!/usr/bin/env python3
"""Run QGroundControl's in-process unit tests and report the verdict.

QGC's --unittest mode (debug builds only, src/main.cc) runs every registered
QTest and prints either "ALL TESTS PASSED" or "<n> TESTS FAILED!". QGC's
process exit code is NOT a verdict: it aborts during shutdown even on
success, so this tool judges solely by those output markers.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Qt logging must reach stderr on Windows or the verdict markers are lost
# to OutputDebugString (same variables the qgc4-launch-with-logs launcher sets).
RUN_ENV_KEYS = {
    "QT_ASSUME_STDERR_HAS_CONSOLE": "1",
    "QT_FORCE_STDERR_LOGGING": "1",
}

# QTest per-suite summary: "Totals: 3 passed, 2 failed, 0 skipped, 0 blacklisted, 81ms"
TOTALS = re.compile(r"Totals:\s+(\d+) passed,\s+(\d+) failed")
# QTest failure line: "FAIL!  : TestName::case() message"
FAIL_LINE = re.compile(r"^FAIL!\s+:\s+(\S+)\s*(.*)$")
# Test identity of a failure: "TestName::case" in "FAIL!  : TestName::case() ..."
FAIL_ID = re.compile(r"^FAIL!\s+:\s*([\w:]+)\(\)")
# Live-output prefixes: enough to follow progress without flooding the console.
LIVE_PREFIXES = ("********* Start testing", "Totals:", "FAIL!", "QFATAL", "ALL TESTS PASSED", " TESTS FAILED!")


def find_debug_exe(qgc_root: Path) -> Path | None:
    """Return the Debug staging executable; release builds have no --unittest."""
    exe = qgc_root / "build" / "Desktop_Qt_5_15_2_MSVC2019_64bit-Debug" / "staging" / "QGroundControl.exe"
    return exe if exe.is_file() else None


def available_log_path(directory: Path, timestamp: str) -> Path:
    """Return a log path in `directory` that does not exist yet."""
    candidate = directory / f"qgc_unittest_{timestamp}.log"
    counter = 1
    while candidate.exists():
        candidate = directory / f"qgc_unittest_{timestamp}_{counter}.log"
        counter += 1
    return candidate


def parse_output(text: str) -> dict:
    """Extract the verdict and per-suite counts from a full test run's output.

    Returns {"verdict": "passed"|"failed"|"no-verdict", "suites_passed": int,
    "suites_failed": int, "failures": [FAIL line, ...]}.
    """
    result = {"verdict": "no-verdict", "suites_passed": 0, "suites_failed": 0, "failures": []}
    for line in text.splitlines():
        m = FAIL_LINE.match(line)
        if m:
            result["failures"].append(line.strip())
        m = TOTALS.search(line)
        if m:
            if m.group(2) == "0":
                result["suites_passed"] += 1
            else:
                result["suites_failed"] += 1
    # Priority to the failure marker: a stress run can print BOTH markers
    # (an iteration passes, a later one fails) — the run as a whole failed.
    if "TESTS FAILED!" in text:
        result["verdict"] = "failed"
    elif "ALL TESTS PASSED" in text:
        result["verdict"] = "passed"
    return result


def is_live_line(line: str) -> bool:
    """Whether a progress line is worth echoing to the console as it arrives."""
    return any(p in line for p in LIVE_PREFIXES)


def failure_ids(text: str) -> list[str]:
    """Test identities of every FAIL! line, in order, de-duplicated.

    The identity is "TestName::case" (not the message): messages carry temp
    paths and indexes that vary between runs, the identity does not.
    """
    ids: list[str] = []
    for line in text.splitlines():
        m = FAIL_ID.match(line)
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def classify_failures(failures: list[str], baseline: set[str]) -> tuple[list[str], list[str]]:
    """Split FAIL lines into (new, known) according to the baseline ids."""
    new: list[str] = []
    known: list[str] = []
    for line in failures:
        m = FAIL_ID.match(line)
        fid = m.group(1) if m else line
        (known if fid in baseline else new).append(line)
    return new, known


def historical_baseline(directory: Path) -> set[str]:
    """Union of failure ids from earlier runs' logs in `directory`.

    Call BEFORE the current run creates its own log so a run can never
    baseline itself (same invariant as qgc4-smoke).
    """
    baseline: set[str] = set()
    for log in sorted(directory.glob("qgc_unittest_*.log")):
        try:
            baseline.update(failure_ids(log.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return baseline


def load_baseline_file(path: Path) -> set[str]:
    """Failure ids from a curated file: one id per line, `#` comments."""
    baseline: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            baseline.add(line)
    return baseline


def kill_tree(pid: int) -> None:
    """Kill a process and its children; best effort."""
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, text=True)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except (ProcessLookupError, PermissionError):
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QGroundControl unit tests and judge by output markers")
    parser.add_argument("qgc_root", help="QGroundControl git repository root")
    parser.add_argument("test_name", nargs="?",
                        help="single test object to run (default: every registered test)")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="seconds before the run is killed as hung (default: 1800)")
    parser.add_argument("--baseline", metavar="FILE",
                        help="curated known-failure file (one TestName::case per line); "
                             "default: union of historical qgc_unittest_*.log in cwd")
    args = parser.parse_args()

    qgc_root = Path(args.qgc_root).resolve()
    if not (qgc_root / "qgroundcontrol.pro").is_file():
        print("[Unittests] ERROR: %s does not look like a QGC repo root (qgroundcontrol.pro missing)" % qgc_root,
              file=sys.stderr)
        return 2

    exe = find_debug_exe(qgc_root)
    if exe is None:
        print("[Unittests] ERROR: Debug executable not found under %s\\build\\" % qgc_root, file=sys.stderr)
        print("  --unittest is compiled out of release builds; build Debug first (qgc4-builder).",
              file=sys.stderr)
        return 3

    # Colon form is the contract: a space between --unittest and the name is
    # silently ignored by QGC's parser and runs ALL tests instead.
    cmd = [str(exe), "--no-windows-assert-ui"]
    cmd.append("--unittest:%s" % args.test_name if args.test_name else "--unittest")

    env = os.environ.copy()
    env.update(RUN_ENV_KEYS)

    # Baseline BEFORE this run creates its own log — a run never baselines itself.
    if args.baseline:
        baseline_path = Path(args.baseline)
        if not baseline_path.is_file():
            print("[Unittests] ERROR: baseline file not found: %s" % baseline_path, file=sys.stderr)
            return 2
        baseline = load_baseline_file(baseline_path)
        baseline_desc = str(baseline_path)
    else:
        baseline = historical_baseline(Path.cwd())
        baseline_desc = "historical qgc_unittest_*.log in %s" % Path.cwd()

    log_path = available_log_path(Path.cwd(), datetime.now().strftime("%Y_%m_%d_%H%M%S"))
    print("[Unittests] Executable: %s" % exe)
    print("[Unittests] Command:    %s" % " ".join(cmd))
    print("[Unittests] Log file:   %s" % log_path)
    print("[Unittests] Baseline:   %d known failure(s) from %s" % (len(baseline), baseline_desc))

    started = time.monotonic()
    deadline = started + max(1, args.timeout)
    timed_out = False
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, cwd=str(exe.parent), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace",
                                start_new_session=sys.platform.startswith("linux") or sys.platform == "darwin")

        # Pump output in a thread: a blocking readline() on a hung-but-still
        # open pipe would otherwise defeat the timeout entirely.
        def pump() -> None:
            for line in proc.stdout:
                log.write(line)
                if is_live_line(line):
                    print("[Unittests] %s" % line.rstrip())

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
        if proc.poll() is None:
            timed_out = True
            kill_tree(proc.pid)
            proc.wait()
        reader.join(timeout=10)
    elapsed = time.monotonic() - started

    parsed = parse_output(log_path.read_text(encoding="utf-8", errors="replace"))
    log_size = log_path.stat().st_size
    new_failures, known_failures = classify_failures(parsed["failures"], baseline)

    # Closing block: totals, every failure split NEW/KNOWN, then ONE verdict
    # line — separated by blank lines so it cannot blend into the progress.
    print()
    print("[Unittests] Suites: %d passed, %d failed (%.0fs)" %
          (parsed["suites_passed"], parsed["suites_failed"], elapsed))
    for failure in new_failures:
        print("[Unittests] NEW  FAIL: %s" % failure)
    for failure in known_failures:
        print("[Unittests] KNOWN FAIL: %s  (in baseline)" % failure)
    if log_size > 0:
        print("[Unittests] Full log (%d bytes): %s" % (log_size, log_path))
    print()
    sys.stdout.flush()

    if timed_out:
        print("[Unittests] RESULT: FAILED - run killed after %ds timeout (exit 4)" % args.timeout,
              file=sys.stderr)
        return 4
    if parsed["verdict"] == "passed":
        print("[Unittests] RESULT: PASSED - ALL TESTS PASSED (exit 0)")
        return 0
    if parsed["verdict"] == "failed":
        if new_failures:
            print("[Unittests] RESULT: FAILED - %d NEW failure(s), %d known in baseline "
                  "(exit 1)" % (len(new_failures), len(known_failures)), file=sys.stderr)
            return 1
        print("[Unittests] RESULT: PASSED - only baseline-known failures "
              "(%d), no new regressions (exit 0)" % len(known_failures))
        return 0
    print("[Unittests] RESULT: FAILED - no verdict marker, QGC crashed before finishing, "
          "full log above (exit 4)", file=sys.stderr)
    return 4


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
