#!/usr/bin/env python3
"""QGC smoke test: build -> launch -> wait -> close -> assert no new QML errors.

Reuses the sibling tools: qgc4-builder (build), qgc4-launch-with-logs
(launch + categorized log), close-qgc (shutdown). QML runtime errors are
extracted from the run log as signatures (file + message, line numbers
dropped so edits above the error do not invalidate the baseline) and
compared against a baseline: either an explicit --baseline file, or the
union of signatures found in the historical qgc_*.log files in QGC_ROOT.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent.parent
BUILDER_CMD = TOOLS_DIR / "qgc4-builder" / "internal" / "build-qgc.cmd"
LAUNCHER_PY = TOOLS_DIR / "qgc4-launch-with-logs" / "internal" / "launch_qgc.py"
CLOSE_BAT = TOOLS_DIR / "close-qgc" / "close-qgc.bat"
CLOSE_SH = TOOLS_DIR / "close-qgc" / "close-qgc.sh"

# Leading timestamp/pid/category of a launcher log line:
# "2026-10-12 02:22:29.354 20960 default: <message>"
LOG_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \d+ \S+: ")

# "<qml-or-js-file>:<line>[:<col>]: <message>" anywhere in a line.
QML_LOCATION = re.compile(r"([\w.:/\\-]+\.(?:qml|js)):(\d+)(?::\d+)?:\s*(.+)$")

# Messages that count as a QML error. Extend deliberately: every keyword
# here can fail a smoke run, so a broad word like "error" does not belong.
ERROR_KEYWORDS = (
    "TypeError",
    "ReferenceError",
    "SyntaxError",
    "Binding loop",
    "is not a type",
    "Cannot assign",
    "Unable to assign",
    "is not installed",
    "failed to load",
)

# Whole-line signatures (no .qml locator) that still count as QML errors.
ENGINE_FAILURE = "QQmlApplicationEngine failed"

# Startup window: QML load errors appear within the first seconds; a value
# large enough to cover a slow disk, small enough for a quick experiment.
DEFAULT_SECONDS = 30


def strip_prefix(line: str) -> str:
    """Remove the launcher's timestamp/pid/category prefix from a line."""
    return LOG_PREFIX.sub("", line.strip())


def signature_of(line: str) -> str | None:
    """Return the error signature of one log line, or None if not a QML error.

    Signature form is "<file>: <message>" with line/column numbers removed,
    so a baseline stays valid when code above the error shifts the line.
    """
    text = strip_prefix(line)
    if not text:
        return None
    if ENGINE_FAILURE in text:
        return text
    m = QML_LOCATION.search(text)
    if not m:
        return None
    message = re.sub(r"^\d+:\s*", "", m.group(3)).strip()
    if not any(k in message for k in ERROR_KEYWORDS):
        return None
    return "%s: %s" % (m.group(1), message)


def extract_signatures(log_path: Path) -> dict[str, int]:
    """Return {signature: count} for every QML error in the log."""
    signatures: dict[str, int] = {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        sig = signature_of(line)
        if sig:
            signatures[sig] = signatures.get(sig, 0) + 1
    return signatures


def load_baseline_file(path: Path) -> set[str]:
    """Read one signature per line; blank lines and #comments are skipped."""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def historical_baseline(qgc_root: Path, exclude: Path | None = None) -> set[str]:
    """Union of signatures across the historical qgc_*.log files in QGC_ROOT."""
    out: set[str] = set()
    for log in sorted(qgc_root.glob("qgc_*.log")):
        if exclude is not None and log.resolve() == exclude.resolve():
            continue
        out.update(extract_signatures(log))
    return out


def run_build(qgc_root: Path, config: str) -> int:
    """Run qgc4-builder; build output passes straight through to the console."""
    if not sys.platform.startswith("win"):
        print("[Smoke] ERROR: --build is Windows-only (qgc4-builder); use --no-build.", file=sys.stderr)
        return 3
    print("[Smoke] Building (%s)..." % config)
    return subprocess.run(["cmd", "/c", str(BUILDER_CMD), str(qgc_root), config]).returncode


def close_qgc() -> int:
    """Close every QGroundControl instance via the close-qgc tool."""
    if sys.platform.startswith("win"):
        return subprocess.run(["cmd", "/c", str(CLOSE_BAT)], capture_output=True, text=True).returncode
    return subprocess.run(["bash", str(CLOSE_SH)], capture_output=True, text=True).returncode


def wait_for_exit(launcher: subprocess.Popen, seconds: int) -> bool:
    """Wait up to `seconds`; return False if the launcher died early."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if launcher.poll() is not None:
            return False
        time.sleep(0.5)
    return True


def find_new_log(qgc_root: Path, before: set[str], started: float) -> Path | None:
    """Return the run log: a qgc_*.log that appeared in QGC_ROOT since launch."""
    candidates = [
        p for p in qgc_root.glob("qgc_*.log")
        if p.name not in before and p.stat().st_mtime >= started - 2
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description="QGC smoke test: build, launch, assert no new QML errors")
    parser.add_argument("qgc_root", help="QGroundControl git repository root")
    parser.add_argument("--config", choices=("debug", "release"), default="debug", help="build configuration (default: debug)")
    parser.add_argument("--no-build", action="store_true", help="skip the build step and test the existing executable")
    parser.add_argument("--seconds", type=int, default=DEFAULT_SECONDS, help="seconds to keep QGC running (default: %d)" % DEFAULT_SECONDS)
    parser.add_argument("--baseline", help="explicit baseline file (one signature per line); default: historical qgc_*.log files in QGC_ROOT")
    parser.add_argument("--save-baseline", metavar="FILE", help="write this run's signatures to FILE, then exit per the verdict")
    parser.add_argument("--pause", action="store_true", help="wait for Enter before exiting (drag-and-drop entries only)")
    args = parser.parse_args()

    qgc_root = Path(args.qgc_root).resolve()
    if not (qgc_root / "qgroundcontrol.pro").is_file():
        print("[Smoke] ERROR: %s does not look like a QGC repo root (qgroundcontrol.pro missing)" % qgc_root, file=sys.stderr)
        return 2

    exit_code = 1
    try:
        if not args.no_build:
            build_code = run_build(qgc_root, args.config)
            if build_code != 0:
                print("[Smoke] FAIL: build failed (exit %d)" % build_code, file=sys.stderr)
                return 3

        # Baseline BEFORE launch: the run's own log must never baseline itself.
        if args.baseline:
            baseline = load_baseline_file(Path(args.baseline))
            print("[Smoke] Baseline: %s (%d signatures)" % (args.baseline, len(baseline)))
        else:
            baseline = historical_baseline(qgc_root)
            print("[Smoke] Baseline: historical qgc_*.log in %s (%d signatures)" % (qgc_root, len(baseline)))

        # Determinism: a stale instance would swallow the launch and confuse
        # early-exit detection, so no QGC may be running when the run starts.
        close_qgc()

        before = {p.name for p in qgc_root.glob("qgc_*.log")}
        started = time.time()
        print("[Smoke] Launching QGC for %d seconds..." % args.seconds)
        tmp = open(os.path.join(os.environ.get("TEMP", "."), "qgc4-smoke-launcher.log"), "w", encoding="utf-8")
        try:
            launcher = subprocess.Popen(
                [sys.executable, str(LAUNCHER_PY), str(qgc_root)],
                cwd=str(qgc_root), stdout=tmp, stderr=subprocess.STDOUT,
            )
            exited_early = not wait_for_exit(launcher, args.seconds)
            if exited_early:
                print("[Smoke] WARNING: QGC exited before the wait finished (exit %d)" % launcher.returncode)
            close_qgc()
            launcher.wait(timeout=60)
        finally:
            tmp.close()

        log_path = find_new_log(qgc_root, before, started)
        if log_path is None:
            print("[Smoke] FAIL: no run log was produced - QGC did not start", file=sys.stderr)
            return 4
        print("[Smoke] Run log: %s" % log_path)

        signatures = extract_signatures(log_path)
        if args.save_baseline:
            Path(args.save_baseline).write_text(
                "".join(s + "\n" for s in sorted(signatures)), encoding="utf-8")
            print("[Smoke] Saved %d signatures to %s" % (len(signatures), args.save_baseline))

        new = {s: c for s, c in signatures.items() if s not in baseline}
        print("[Smoke] Signatures: %d total, %d in baseline, %d new" % (len(signatures), len(signatures) - len(new), len(new)))
        if new:
            for sig, count in sorted(new.items()):
                print("[Smoke] NEW QML ERROR (x%d): %s" % (count, sig))
            print("[Smoke] FAIL: %d new QML error signature(s)" % len(new))
            return 1
        if exited_early:
            print("[Smoke] FAIL: QGC exited early, but the log shows no new QML error - check the log", file=sys.stderr)
            return 4
        print("[Smoke] PASS: no new QML errors")
        exit_code = 0
    finally:
        if args.pause:
            try:
                input("\n[Smoke] Press Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        close_qgc()
        sys.exit(130)
