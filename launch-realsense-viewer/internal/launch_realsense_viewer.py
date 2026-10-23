#!/usr/bin/env python3
"""Check for realsense-viewer, install librealsense from source if missing, then launch it."""

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP = "realsense-viewer"
REPOSITORY = "https://github.com/realsenseai/librealsense.git"
DEFAULT_BRANCH = "master"
DEFAULT_PREFIX = "/usr/local"
DEFAULT_JOBS = 2
SUPPORTED_UBUNTU = {"20.04", "22.04", "24.04"}
DEPENDENCIES = [
    "libssl-dev",
    "libusb-1.0-0-dev",
    "libudev-dev",
    "pkg-config",
    "libgtk-3-dev",
    "git",
    "wget",
    "cmake",
    "build-essential",
    "libglfw3-dev",
    "libgl1-mesa-dev",
    "libglu1-mesa-dev",
    "at",
    "v4l-utils",
]


class InstallError(RuntimeError):
    """A user-facing installation failure."""


def log(message):
    print("[launch-realsense-viewer] %s" % message, flush=True)


def warn(message):
    print("[launch-realsense-viewer] WARNING: %s" % message, file=sys.stderr, flush=True)


def read_os_release(path="/etc/os-release"):
    values = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def kernel_tuple(release=None):
    release = release or platform.release()
    parts = release.split("-", 1)[0].split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        raise InstallError("cannot parse kernel version: %s" % release)


def kernel_patch_script(codename, release=None):
    major, minor = kernel_tuple(release)
    if codename == "focal" and major * 100 + minor < 513:
        return "scripts/patch-realsense-ubuntu-lts.sh"
    return "scripts/patch-realsense-ubuntu-lts-hwe.sh"


def is_executable(path):
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def find_app(prefix=DEFAULT_PREFIX):
    found = shutil.which(APP)
    if found:
        return found
    for candidate in (
        os.path.join(prefix, "bin", APP),
        os.path.join(DEFAULT_PREFIX, "bin", APP),
        "/usr/bin/" + APP,
    ):
        if is_executable(candidate):
            return os.path.abspath(candidate)
    return None


def default_source_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "launch-realsense-viewer", "librealsense")


def cmake_configure_command(source, build, prefix, libidn2=False):
    command = [
        "cmake",
        "-S", str(source),
        "-B", str(build),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_EXAMPLES=true",
        "-DCMAKE_INSTALL_PREFIX=" + str(prefix),
    ]
    if libidn2:
        command.append("-DCMAKE_CXX_STANDARD_LIBRARIES=-lidn2")
    return command


def libidn2_available():
    pkg_config = shutil.which("pkg-config")
    if not pkg_config:
        return False
    try:
        result = subprocess.run([pkg_config, "--exists", "libidn2"],
                                capture_output=True, text=True)
    except OSError:
        return False
    return result.returncode == 0


def package_installed(name):
    query = shutil.which("dpkg-query")
    if not query:
        return False
    result = subprocess.run(
        [query, "-W", "-f=${Status}", name],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "install ok installed" in result.stdout


def missing_dependencies():
    return [name for name in DEPENDENCIES if not package_installed(name)]


def prefix_requires_root(prefix):
    if os.geteuid() == 0:
        return False
    path = Path(prefix).expanduser().resolve()
    while not path.exists() and path != path.parent:
        path = path.parent
    return not os.access(str(path), os.W_OK)


def ensure_ubuntu():
    release = read_os_release()
    identifiers = (release.get("ID", "") + " " + release.get("ID_LIKE", "")).split()
    if "ubuntu" not in identifiers:
        raise InstallError("librealsense from source is supported on Ubuntu 20.04/22.04/24.04 only")
    version = release.get("VERSION_ID", "unknown")
    if version not in SUPPORTED_UBUNTU:
        warn("Ubuntu %s is outside the documented support matrix (%s); continuing"
             % (version, ", ".join(sorted(SUPPORTED_UBUNTU))))


class Runner:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run

    def command(self, command, sudo=False):
        command = [str(item) for item in command]
        if sudo and os.geteuid() != 0:
            return ["sudo"] + command
        return command

    def run(self, command, cwd=None, sudo=False, input_text=None, env=None):
        full = self.command(command, sudo)
        log("run: %s" % " ".join(full))
        if self.dry_run:
            return subprocess.CompletedProcess(full, 0, "", "")
        merged = os.environ.copy()
        if env:
            merged.update(env)
        try:
            return subprocess.run(
                full,
                cwd=str(cwd) if cwd else None,
                input=input_text,
                text=True,
                env=merged,
            )
        except FileNotFoundError:
            raise InstallError("command not found: %s" % full[0])
        except OSError as error:
            raise InstallError("could not run %s: %s" % (full[0], error))

    def require(self, command, cwd=None, sudo=False, input_text=None, env=None):
        result = self.run(command, cwd=cwd, sudo=sudo, input_text=input_text, env=env)
        if result.returncode:
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            raise InstallError("command failed (exit %d): %s%s"
                               % (result.returncode, " ".join(str(item) for item in command),
                                  "\n" + output if output else ""))
        return result


def install_dependencies(runner):
    missing = missing_dependencies()
    if not missing:
        log("all build dependencies are already installed")
        return
    log("installing missing packages: %s" % " ".join(missing))
    update = runner.run(["apt-get", "update"], sudo=True)
    if update.returncode:
        warn("apt-get update failed (exit %d); continuing with the existing package lists. "
             "Fix or disable the failing third-party repository if installation fails."
             % update.returncode)
    try:
        runner.require(["apt-get", "install", "-y"] + missing, sudo=True,
                       env={"DEBIAN_FRONTEND": "noninteractive"})
    except InstallError as error:
        raise InstallError("%s\nCheck the apt repositories reported by 'apt-get update' "
                           "(a broken third-party repo can cause this)." % error)


def ensure_source(runner, source, branch):
    source = Path(source).expanduser().resolve()
    if (source / "CMakeLists.txt").is_file():
        log("reusing librealsense checkout: %s" % source)
        return source
    if source.exists() and any(source.iterdir()):
        raise InstallError("%s exists but is not a librealsense checkout" % source)
    if runner.dry_run:
        log("would clone %s (%s) into %s" % (REPOSITORY, branch, source))
        return source
    source.parent.mkdir(parents=True, exist_ok=True)
    runner.require(["git", "clone", "--depth", "1", "--branch", branch,
                    REPOSITORY, str(source)])
    return source


def setup_udev_rules(runner, source):
    script = Path(source) / "scripts" / "setup_udev_rules.sh"
    video_devices = sorted(Path("/dev").glob("video*"))
    if video_devices:
        warn("video devices are present; the upstream udev script asks you to unplug "
             "RealSense cameras first. Continuing non-interactively.")
    if not runner.dry_run:
        if not script.is_file():
            raise InstallError("udev setup script not found: %s" % script)
        if not os.access(str(script), os.X_OK):
            os.chmod(str(script), 0o755)
    runner.require([str(script)], cwd=source, input_text="\n")


MAKE_SHIM = """#!/bin/bash
set -euo pipefail
args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -j|--jobs)
            shift
            if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
                shift
            fi
            ;;
        -j[0-9]*|--jobs=*)
            shift
            ;;
        *)
            args+=("$1")
            shift
            ;;
    esac
done
exec __MAKE__ -j__JOBS__ ${args[@]+"${args[@]}"}
"""


def install_make_shim(directory, jobs, make_path=None):
    real_make = make_path or shutil.which("make")
    if not real_make:
        raise InstallError("make not found; cannot cap kernel build parallelism")
    path = Path(directory) / "make"
    path.write_text(MAKE_SHIM.replace("__MAKE__", shlex.quote(str(real_make)))
                    .replace("__JOBS__", str(jobs)), encoding="utf-8")
    path.chmod(0o755)
    return path


def patch_kernel(runner, source, jobs):
    release = platform.release()
    codename = read_os_release().get("VERSION_CODENAME", "")
    script = Path(source) / kernel_patch_script(codename, release)
    stamp = Path(source) / (".launch-realsense-viewer-kernel-" + release + ".ok")
    if stamp.exists():
        log("kernel modules for %s were already patched by this tool" % release)
        return
    if not runner.dry_run and not script.is_file():
        raise InstallError("kernel patch script not found: %s" % script)
    log("patching kernel modules for %s (%s, -j%d)" % (release, script.name, jobs))
    if runner.dry_run:
        result = runner.run([str(script)], cwd=source, input_text="\n\n")
    else:
        with tempfile.TemporaryDirectory(prefix="launch-realsense-viewer-make-") as shim_dir:
            install_make_shim(shim_dir, jobs)
            environment = os.environ.copy()
            environment["PATH"] = shim_dir + os.pathsep + environment.get("PATH", "")
            environment["MAKEFLAGS"] = "-j%d" % jobs
            result = runner.run([str(script)], cwd=source, input_text="\n\n",
                                env=environment)
    if result.returncode:
        warn("kernel patch failed (exit %d). The SDK will still be built; depth streams may "
             "need the patched modules. Re-run with --skip-kernel-patch to silence this step."
             % result.returncode)
        return
    if not runner.dry_run:
        stamp.write_text("patched %s on %s\n" % (release, platform.node()), encoding="utf-8")


def build_and_install(runner, source, build, prefix, jobs):
    build = Path(build).expanduser().resolve()
    source = Path(source).expanduser().resolve()
    if not runner.dry_run:
        build.mkdir(parents=True, exist_ok=True)
    has_libidn2 = libidn2_available()
    if has_libidn2:
        log("libidn2 development files found; adding -lidn2 for the bundled libcurl")
    runner.require(cmake_configure_command(source, build, prefix, has_libidn2))
    runner.require(["cmake", "--build", str(build), "--parallel", str(jobs)])
    runner.require(["cmake", "--install", str(build)], sudo=prefix_requires_root(prefix))
    if prefix_requires_root(prefix):
        runner.require(["ldconfig"], sudo=True)


def launch_app(binary, app_args, prefix, dry_run):
    environment = os.environ.copy()
    if os.path.normpath(prefix) != DEFAULT_PREFIX:
        library_dir = os.path.join(prefix, "lib")
        current = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = library_dir + (":" + current if current else "")
    if not environment.get("DISPLAY") and not environment.get("WAYLAND_DISPLAY"):
        warn("neither DISPLAY nor WAYLAND_DISPLAY is set; a graphical session is required")
    command = [binary] + list(app_args)
    log("launching: %s" % " ".join(command))
    if dry_run:
        return 0
    try:
        return subprocess.call(command, env=environment)
    except FileNotFoundError:
        raise InstallError("installed app disappeared: %s" % binary)
    except KeyboardInterrupt:
        return 130


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Check for realsense-viewer, install librealsense from source if needed, then launch it.")
    parser.add_argument("--check", action="store_true",
                        help="report whether realsense-viewer is installed and exit")
    parser.add_argument("--reinstall", "--force", dest="reinstall", action="store_true",
                        help="install even when realsense-viewer is already present")
    parser.add_argument("--no-launch", action="store_true",
                        help="install only; do not start realsense-viewer")
    parser.add_argument("--source", default=default_source_dir(),
                        help="librealsense checkout (default: %(default)s)")
    parser.add_argument("--build-dir", default=None,
                        help="build directory (default: <source>/build)")
    parser.add_argument("--branch", default=DEFAULT_BRANCH,
                        help="branch or tag to clone (default: %(default)s)")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX,
                        help="install prefix (default: %(default)s)")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                        help="parallel build jobs (default: %(default)s)")
    parser.add_argument("--skip-kernel-patch", action="store_true",
                        help="do not run the upstream kernel-module patch script")
    parser.add_argument("--skip-udev", action="store_true",
                        help="do not install the RealSense udev rules")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the commands that would run without changing the system")
    parser.add_argument("app_args", nargs=argparse.REMAINDER,
                        help="arguments after -- are passed to realsense-viewer")
    args = parser.parse_args(argv)
    if args.app_args and args.app_args[0] == "--":
        args.app_args = args.app_args[1:]
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    if args.build_dir is None:
        args.build_dir = os.path.join(args.source, "build")
    return args


def run(args):
    if args.check:
        binary = find_app(args.prefix)
        if binary:
            print("installed: %s (%s)" % (APP, binary))
            return 0
        print("not installed: %s" % APP)
        return 1

    runner = Runner(dry_run=args.dry_run)
    binary = None if args.reinstall else find_app(args.prefix)
    if args.reinstall:
        log("forced reinstall requested")
    elif binary:
        log("already installed: %s" % binary)
        log("skipping installation")

    if not binary:
        ensure_ubuntu()
        install_dependencies(runner)
        source = ensure_source(runner, args.source, args.branch)
        if args.skip_udev:
            log("skipping udev rules")
        else:
            setup_udev_rules(runner, source)
        if args.skip_kernel_patch:
            log("skipping kernel patch")
        else:
            patch_kernel(runner, source, args.jobs)
        build_and_install(runner, source, args.build_dir, args.prefix, args.jobs)
        if args.dry_run:
            binary = os.path.join(args.prefix, "bin", APP)
        else:
            binary = find_app(args.prefix)
            if not binary:
                raise InstallError("installation finished but %s was not found under %s"
                                   % (APP, args.prefix))

    if args.no_launch:
        log("installed; skipping launch (--no-launch)")
        return 0
    return launch_app(binary, args.app_args, args.prefix, args.dry_run)


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except InstallError as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    except OSError as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
