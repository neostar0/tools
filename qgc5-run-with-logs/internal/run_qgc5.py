#!/usr/bin/env python3
"""Launch a deployed QGroundControl 5 build with logging and crash dumps."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_CATEGORIES = (
    "FactSystem.ParameterManager",
    "FactSystem.FactPanelController",
    "MAVLink",
    "Video.GStreamer",
    "Comms.LinkManager",
)
USAGE_FILE = Path(__file__).with_name("usage.md")
CORE_PATTERN_FILE = Path("/proc/sys/kernel/core_pattern")
AUTO_GST_DUMP = "__auto__"


class UsageError(Exception):
    """Bad arguments or an unusable checkout (exit code 2)."""


class LaunchError(Exception):
    """The deployment is missing or could not be started (exit code 1)."""


def usage_text() -> str:
    return USAGE_FILE.read_text(encoding="utf-8")


def is_qgc5(root: Path) -> bool:
    return (
        (root / "CMakeLists.txt").is_file()
        and (root / "deploy/docker/Dockerfile").is_file()
        and (root / "deploy/docker/variants.json").is_file()
    )


def find_root(start: Path) -> Path | None:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if is_qgc5(candidate):
            return candidate
    return None


def require_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if is_qgc5(root):
        return root
    if (root / "qgroundcontrol.pro").is_file():
        raise UsageError(
            f"{root} is a QGroundControl 4 checkout; use launch-qgc for QGC 4"
        )
    raise UsageError(
        "not a QGroundControl 5 checkout "
        f"(missing CMakeLists.txt or deploy/docker): {root}"
    )


def resolve_root(value: str | None) -> Path:
    if value:
        return require_root(value)
    found = find_root(Path.cwd())
    if found is None:
        raise UsageError(
            "no QGroundControl 5 checkout found from the current directory; "
            "pass QGC_ROOT or run from inside one"
        )
    return found


def default_build_dir(root: Path) -> Path:
    return root / "build"


def is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_executable(build_dir: Path, explicit: str | None = None) -> Path:
    if explicit:
        exe = Path(explicit).expanduser().resolve()
        if not is_executable(exe):
            raise UsageError(f"not an executable file: {exe}")
        return exe

    appimages = sorted(
        build_dir.glob("*.AppImage"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for exe in appimages:
        if is_executable(exe):
            return exe.resolve()

    appdir_run = build_dir / "AppDir" / "AppRun"
    if is_executable(appdir_run):
        return appdir_run.resolve()

    root_run = build_dir / "AppRun"
    if (build_dir / "usr/bin").is_dir() and is_executable(root_run):
        return root_run.resolve()

    for bundle in sorted(build_dir.glob("*.app")):
        exe = bundle / "Contents/MacOS/QGroundControl"
        if is_executable(exe):
            return exe.resolve()

    for relative in ("Release/QGroundControl.exe", "QGroundControl.exe"):
        exe = build_dir / relative
        if is_executable(exe):
            return exe.resolve()

    for relative in ("usr/bin/QGroundControl", "bin/QGroundControl"):
        exe = build_dir / relative
        if is_executable(exe):
            return exe.resolve()

    raise LaunchError(
        f"no deployed QGroundControl executable in {build_dir}; "
        "run build-qgc5 first or pass --executable"
    )


def normalize_categories(values: list[str]) -> list[str]:
    categories: list[str] = []
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item and item not in categories:
                categories.append(item)
    if not categories:
        raise UsageError("--categories needs at least one non-empty category")
    return categories


def build_command(
    executable: Path,
    qgc_args: list[str],
    categories: list[str],
) -> list[str]:
    command = [str(executable)]
    has_log_output = any(arg == "--log-output" or arg.startswith("--log-output=") for arg in qgc_args)
    has_logging = any(arg == "--logging" or arg.startswith("--logging=") for arg in qgc_args)
    if not has_log_output:
        command.append("--log-output")
    if not has_logging:
        command += ["--logging", ",".join(categories)]
    return command + qgc_args


def available_log_path(directory: Path, timestamp: str) -> Path:
    candidate = directory / f"qgc5_{timestamp}.log"
    counter = 1
    while candidate.exists():
        candidate = directory / f"qgc5_{timestamp}_{counter}.log"
        counter += 1
    return candidate


def available_dump_path(directory: Path, timestamp: str) -> Path:
    candidate = directory / f"qgc5_{timestamp}.dump"
    counter = 1
    while candidate.exists():
        candidate = directory / f"qgc5_{timestamp}_{counter}.dump"
        counter += 1
    return candidate


def read_core_pattern() -> str | None:
    try:
        return CORE_PATTERN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def core_pattern_hint(pattern: str | None) -> str:
    if pattern is None:
        return "core dumps are not exposed by this platform"
    if pattern.startswith("|"):
        if "apport" in pattern:
            return "apport collects crashes in /var/crash (inspect with apport-unpack)"
        if "systemd-coredump" in pattern:
            return "systemd-coredump collects crashes (inspect with coredumpctl)"
        return f"the kernel pipes core dumps to: {pattern}"
    return f"core files are written in the launch directory as '{pattern}'"


def make_preexec(core_dumps: bool):
    if os.name != "posix":
        return None

    def preexec() -> None:
        try:
            import resource

            limit = resource.RLIM_INFINITY if core_dumps else 0
            resource.setrlimit(resource.RLIMIT_CORE, (limit, limit))
        except (ImportError, OSError, ValueError):
            pass

    return preexec


def signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


def format_crash_report(
    *,
    timestamp: str,
    command: list[str],
    returncode: int,
    log_path: Path | None,
    core_pattern: str | None,
) -> str:
    signum = -returncode
    lines = [
        "QGroundControl 5 crash report",
        f"time: {timestamp}",
        f"signal: {signum} ({signal_name(signum)})",
        f"command: {' '.join(command)}",
        f"working directory: {Path.cwd()}",
        f"log: {log_path if log_path else 'disabled'}",
        f"core pattern: {core_pattern or 'unavailable'}",
        f"core hint: {core_pattern_hint(core_pattern)}",
    ]
    return "\n".join(lines) + "\n"


def fuse_available() -> bool:
    fuse = Path("/dev/fuse")
    return fuse.exists() and os.access(fuse, os.R_OK | os.W_OK)


def launch_environment(executable: Path, gst_dump: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    env["QT_ASSUME_STDERR_HAS_CONSOLE"] = "1"
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    if (
        executable.suffix == ".AppImage"
        and not fuse_available()
        and "APPIMAGE_EXTRACT_AND_RUN" not in env
    ):
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    if gst_dump is not None:
        env["GST_DEBUG_DUMP_DOT_DIR"] = str(gst_dump)
    return env


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def split_qgc_args(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" not in argv:
        return argv, []
    index = argv.index("--")
    return argv[:index], argv[index + 1 :]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    own_argv, qgc_args = split_qgc_args(raw)
    parser = Parser(
        prog="run-qgc5",
        description="Launch a QGroundControl 5 build with logging and dumps.",
        add_help=False,
    )
    parser.add_argument("root", nargs="?", help="QGroundControl 5 checkout")
    parser.add_argument("--root", dest="root_option", help=argparse.SUPPRESS)
    parser.add_argument("--build-dir")
    parser.add_argument("--executable")
    parser.add_argument("--categories", nargs="+", default=list(DEFAULT_CATEGORIES))
    parser.add_argument("--log-file")
    parser.add_argument("--no-log-file", action="store_true")
    parser.add_argument("--dump", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gst-dump", nargs="?", const=AUTO_GST_DUMP)
    parser.add_argument("--pause", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args(own_argv)

    if args.root and args.root_option:
        raise UsageError("pass the checkout either positionally or with --root, not both")
    args.root = args.root_option or args.root
    if args.no_log_file and args.log_file:
        raise UsageError("pass either --log-file or --no-log-file, not both")
    args.categories = normalize_categories(args.categories)
    args.qgc_args = qgc_args
    return args


def say(message: str, log_file=None, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(message + "\n")
    stream.flush()
    if log_file is not None:
        log_file.write((message + "\n").encode("utf-8", errors="replace"))
        log_file.flush()


def run(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    build_dir = (
        Path(args.build_dir).expanduser().resolve()
        if args.build_dir
        else default_build_dir(root)
    )
    executable = find_executable(build_dir, args.executable)
    command = build_command(executable, args.qgc_args, args.categories)

    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0:
        raise LaunchError("QGroundControl refuses to run as root; launch as a normal user")

    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    log_path: Path | None = None
    if not args.no_log_file:
        log_path = (
            Path(args.log_file).expanduser().resolve()
            if args.log_file
            else available_log_path(Path.cwd(), timestamp)
        )

    gst_dump: Path | None = None
    if args.gst_dump is not None:
        gst_dump = (
            Path.cwd() / f"qgc5_{timestamp}_gst"
            if args.gst_dump == AUTO_GST_DUMP
            else Path(args.gst_dump).expanduser().resolve()
        )
        gst_dump.mkdir(parents=True, exist_ok=True)

    pattern = read_core_pattern()
    env = launch_environment(executable, gst_dump)

    log_file = None
    proc = None
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_path, "wb")

        say(f"[run-qgc5] root:      {root}", log_file)
        say(f"[run-qgc5] build dir: {build_dir}", log_file)
        say(f"[run-qgc5] executable: {executable}", log_file)
        say(f"[run-qgc5] log file:  {log_path if log_path else 'disabled'}", log_file)
        say(f"[run-qgc5] categories: {', '.join(args.categories)}", log_file)
        say(
            f"[run-qgc5] dumps:     {'enabled' if args.dump else 'disabled'} "
            f"({core_pattern_hint(pattern)})",
            log_file,
        )
        if gst_dump is not None:
            say(f"[run-qgc5] GST dumps: {gst_dump}", log_file)
        say(f"[run-qgc5] command:   {' '.join(command)}", log_file)
        say("-" * 60, log_file)

        proc = subprocess.Popen(  # noqa: F841 - rebound in the except path
            command,
            env=env,
            cwd=Path.cwd(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            preexec_fn=make_preexec(args.dump),
        )
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            if log_file is not None:
                log_file.write(chunk)
                log_file.flush()
        returncode = proc.wait()

        say("-" * 60, log_file)
        say(f"[run-qgc5] QGroundControl exited with code {returncode}", log_file)

        if returncode < 0:
            signum = -returncode
            say(
                f"[run-qgc5] Crashed with signal {signum} ({signal_name(signum)})",
                log_file,
                error=True,
            )
            if args.dump:
                dump_path = available_dump_path(Path.cwd(), timestamp)
                dump_path.write_text(
                    format_crash_report(
                        timestamp=timestamp,
                        command=command,
                        returncode=returncode,
                        log_path=log_path,
                        core_pattern=pattern,
                    ),
                    encoding="utf-8",
                )
                say(f"[run-qgc5] Crash report: {dump_path}", log_file, error=True)
                say(f"[run-qgc5] Core dump:   {core_pattern_hint(pattern)}", log_file, error=True)

        if log_path is not None:
            say(f"[run-qgc5] Full log: {log_path}", log_file)
        if returncode < 0:
            return min(255, 128 - returncode)
        return returncode
    except KeyboardInterrupt:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        say("\n[run-qgc5] Interrupted by user", log_file, error=True)
        if log_path is not None and log_path.exists():
            say(f"[run-qgc5] Partial log: {log_path}", log_file, error=True)
        return 130
    finally:
        if log_file is not None:
            log_file.close()


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except UsageError as error:
        print(f"run-qgc5: {error}", file=sys.stderr)
        print("Try 'run-qgc5 --help' for usage.", file=sys.stderr)
        return 2

    if args.help:
        print(usage_text(), end="")
        return 0

    try:
        return run(args)
    except UsageError as error:
        print(f"run-qgc5: {error}", file=sys.stderr)
        return 2
    except LaunchError as error:
        print(f"run-qgc5: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"run-qgc5: failed to launch: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    pause_on_exit = "--pause" in sys.argv[1:]
    try:
        code = main()
    except KeyboardInterrupt:
        code = 130
    if pause_on_exit:
        try:
            input("\n[run-qgc5] Press Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(code)
