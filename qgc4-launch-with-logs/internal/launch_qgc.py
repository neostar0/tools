#!/usr/bin/env python3
"""
QGroundControl Launcher with Logging
- Auto-detects OS and executable path
- Enables useful log categories
- Redirects output to timestamped log file
- Accepts QGC repo root as argument (drag & drop support)
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Default log categories to enable
DEFAULT_LOG_CATEGORIES = [
    "FactPanelControllerLog",
    "ParameterManagerLog",
    "MAVLinkLogManagerLog",
    "HealthAndArmingChecks",
    "GStreamerAPILog",
]

def detect_os():
    """Detect current operating system"""
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform.startswith("darwin"):
        return "macos"
    return "unknown"

# A QGroundControl checkout is identified by these top-level files.
QGC_ROOT_MARKERS = ("qgroundcontrol.pro", "qgroundcontrol.qrc")

def is_qgc_root(path: Path) -> bool:
    """Return True when `path` is the root of a QGroundControl checkout."""
    return any((path / marker).is_file() for marker in QGC_ROOT_MARKERS)

def resolve_qgc_root(start: Path) -> "Path | None":
    """Walk up from `start` until a QGroundControl checkout is found."""
    path = start.resolve()
    while True:
        if is_qgc_root(path):
            return path
        if path.parent == path:
            return None
        path = path.parent

def find_qgc_executable(qgc_root: Path, os_type: str) -> "Path | None":
    """Find QGroundControl executable based on OS and build type"""
    if os_type == "windows":
        # Windows debug build path
        debug_path = qgc_root / "build" / "Desktop_Qt_5_15_2_MSVC2019_64bit-Debug" / "staging" / "QGroundControl.exe"
        release_path = qgc_root / "build" / "Desktop_Qt_5_15_2_MSVC2019_64bit-Release" / "staging" / "QGroundControl.exe"
        if debug_path.exists():
            return debug_path
        if release_path.exists():
            return release_path
        # Fallback: search for any QGroundControl.exe
        for exe in qgc_root.rglob("QGroundControl.exe"):
            return exe
    elif os_type == "linux":
        # Linux build paths
        debug_path = qgc_root / "build" / "staging" / "QGroundControl"
        release_path = qgc_root / "build" / "release" / "staging" / "QGroundControl"
        if debug_path.exists():
            return debug_path
        if release_path.exists():
            return release_path
        # Fallback
        for exe in qgc_root.rglob("QGroundControl"):
            if exe.is_file() and os.access(exe, os.X_OK):
                return exe
    elif os_type == "macos":
        # macOS app bundle
        app_path = qgc_root / "build" / "staging" / "QGroundControl.app"
        if app_path.exists():
            return app_path / "Contents" / "MacOS" / "QGroundControl"
    return None

def setup_log_categories(categories):
    """Build QGC_LOGGING_CATEGORIES environment value"""
    return " ".join(f"{cat}=true" for cat in categories)

def available_log_path(directory: Path, timestamp: str) -> Path:
    """Return a log path in `directory` that does not exist yet.

    Two launches within the same second would otherwise share a name and
    silently overwrite each other's log.
    """
    candidate = directory / f"qgc_{timestamp}.log"
    counter = 1
    while candidate.exists():
        candidate = directory / f"qgc_{timestamp}_{counter}.log"
        counter += 1
    return candidate

def main():
    parser = argparse.ArgumentParser(description="Launch QGroundControl with logging")
    parser.add_argument("qgc_root", nargs="?", help="QGroundControl git repository root (drag & drop supported)")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_LOG_CATEGORIES, help="Log categories to enable")
    parser.add_argument("--no-log-file", action="store_true", help="Don't redirect output to log file")
    parser.add_argument("--pause", action="store_true", help="Wait for Enter before exiting (passed by DROP-QGC-FOLDER-HERE.cmd)")
    args = parser.parse_args()

    os_type = detect_os()
    print(f"[Launcher] OS detected: {os_type}")

    # Determine QGC root: explicit argument > QGC_ROOT > current directory.
    # Never derive it from the tool folder unless the tool is installed inside
    # a checkout: a shared parent such as ~/Codes would launch whichever QGC
    # clone happens to be found first.
    explicit = args.qgc_root or os.environ.get("QGC_ROOT") or None
    if args.qgc_root:
        root_source = "argument"
    elif explicit:
        root_source = "QGC_ROOT"
    else:
        root_source = "current directory"

    qgc_root = None
    if explicit:
        qgc_root = resolve_qgc_root(Path(explicit).expanduser())
    else:
        qgc_root = resolve_qgc_root(Path.cwd())

    if qgc_root is None:
        script_dir = Path(__file__).parent.parent.resolve()  # internal/ -> tool root
        qgc_root = resolve_qgc_root(script_dir)
        if qgc_root is not None:
            root_source = "tool location"

    if qgc_root is None:
        looked_from = Path(explicit).expanduser() if explicit else Path.cwd()
        print("[ERROR] No QGroundControl repository found "
              f"(looked from {root_source}: {looked_from})")
        print("  A checkout is recognised by qgroundcontrol.pro or qgroundcontrol.qrc.")
        print("  Run the launcher from the checkout, or pass its root:")
        print("    python internal/launch_qgc.py /path/to/GroundControlSystem_ui")
        print("  To pick a checkout from anywhere:")
        print("    QGC_ROOT=/path/to/GroundControlSystem_ui python internal/launch_qgc.py")
        sys.exit(1)

    print(f"[Launcher] QGC root: {qgc_root} (from {root_source})")

    # Find executable
    exe = find_qgc_executable(qgc_root, os_type)
    if not exe:
        print(f"[ERROR] Could not find QGroundControl executable in {qgc_root}")
        print("  Searched paths:")
        if os_type == "windows":
            print(f"    {qgc_root}/build/Desktop_Qt_5_15_2_MSVC2019_64bit-Debug/staging/QGroundControl.exe")
            print(f"    {qgc_root}/build/Desktop_Qt_5_15_2_MSVC2019_64bit-Release/staging/QGroundControl.exe")
        elif os_type == "linux":
            print(f"    {qgc_root}/build/staging/QGroundControl")
            print(f"    {qgc_root}/build/release/staging/QGroundControl")
        sys.exit(1)

    print(f"[Launcher] Found executable: {exe}")

    # Setup environment
    env = os.environ.copy()
    env["QGC_LOGGING_CATEGORIES"] = setup_log_categories(args.categories)
    # Force Qt logging to stderr (modern Qt 5.14+ variables)
    env["QT_ASSUME_STDERR_HAS_CONSOLE"] = "1"
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    env["QT_LOGGING_RULES"] = "qt.qml.connections=false;*.debug=false"
    # Force unbuffered output
    env["PYTHONUNBUFFERED"] = "1"

    # Prepare log file (unique per run, even within the same second)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    log_file = available_log_path(Path.cwd(), timestamp)
    print(f"[Launcher] Log file: {log_file}")

    # Same command on every OS; running the bundle binary directly keeps
    # its stdout/stderr attached to our tee pipe.
    cmd = [str(exe)]

    print(f"[Launcher] Command: {' '.join(cmd)}")
    print(f"[Launcher] Log categories: {', '.join(args.categories)}")
    print("-" * 60)

    proc = None
    try:
        if args.no_log_file:
            # Just run, output to console; hand QGC's exit code to the caller
            # (subprocess.run kills the child itself if interrupted)
            result = subprocess.run(cmd, env=env, cwd=exe.parent)
            sys.exit(result.returncode)
        else:
            # Redirect stdout and stderr to log file
            # Use binary mode for better control, decode with replace errors
            with open(log_file, "wb") as f:
                proc = subprocess.Popen(cmd, env=env, cwd=exe.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
                # Tee output to both console and file (binary mode)
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    f.write(chunk)
                    f.flush()
                proc.wait()
                return_code = proc.returncode
            print("-" * 60)
            print(f"[Launcher] QGroundControl exited with code {return_code}")
            print(f"[Launcher] Full log saved to: {log_file}")
            print(f"[Launcher] Note: On Windows, C++ qCDebug/qCInfo logs go to OutputDebugString by default.")
            print(f"       Use DebugView (Sysinternals) or run from debugger to capture them.")
            print(f"       QT_ASSUME_STDERR_HAS_CONSOLE=1 and QT_FORCE_STDERR_LOGGING=1 are set to redirect Qt logging to stderr.")
            sys.exit(return_code)
    except KeyboardInterrupt:
        # Stop QGC ourselves: do not rely on it handling the console event.
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("\n[Launcher] Interrupted by user")
        if log_file.exists():
            print(f"[Launcher] Partial log saved to: {log_file}")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] Failed to launch: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # The .cmd wrapper passes --pause: every exit code, Ctrl+C (130) included,
    # holds the window open so the summary and partial-log path stay readable.
    # A second Ctrl+C during the wait force-closes (the pause swallows it).
    pause_on_exit = "--pause" in sys.argv[1:]
    try:
        main()
    except SystemExit as exc:
        code = exc.code
        if not isinstance(code, int):
            code = 0 if code is None else 1
        if pause_on_exit:
            try:
                input("\n[Launcher] Press Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
        sys.exit(code)
    except KeyboardInterrupt:
        # Landed outside main()'s try (startup, or a second Ctrl+C racing the
        # interrupt handler): no traceback, no pause - the user is leaving.
        sys.exit(130)