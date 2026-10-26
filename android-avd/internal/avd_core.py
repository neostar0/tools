#!/usr/bin/env python3
"""Shared Android SDK, AVD and emulator-window orchestration.

Both android-avd (the CLI) and run-apk-on-avd import this module so the
provisioning, launch and window-handling code exists in exactly one place.
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

DEFAULT_AVD = "s24-plus"
DEFAULT_RESOLUTION = "1440x3120"
DEFAULT_API = "35"
DEFAULT_IMAGE_TAG = "google_apis"
DEFAULT_PORT = 5554
# swangle (ANGLE + SwiftShader) renders icon textures correctly and does not
# depend on the host GPU driver; "host"/"auto" can produce blank or white
# icons when the driver rejects the app's texture uploads.
DEFAULT_GPU = "swangle"
BOOT_TIMEOUT = 600
# sdkmanager manages the current emulator and system-image versions. Update this
# bootstrap package revision when Google publishes a newer command-line tools ZIP.
COMMAND_LINE_TOOLS_REVISION = "15859902"

PREFIX = "android-avd"


def set_prefix(prefix):
    global PREFIX
    PREFIX = prefix


def log(message):
    print("[%s] %s" % (PREFIX, message))


def warn(message):
    print("[%s] WARNING: %s" % (PREFIX, message), file=sys.stderr)


def sdk_root(value=None):
    return os.path.abspath(value or os.environ.get("ANDROID_SDK_ROOT")
                           or os.environ.get("ANDROID_HOME")
                           or os.path.expanduser("~/Android/Sdk"))


def executable(name):
    return name + ".exe" if os.name == "nt" else name


def find_sdk_tool(root, *parts):
    for part in parts:
        candidate = os.path.join(root, *part[:-1], executable(part[-1]))
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def ensure_jdk(root):
    """Return a java binary that sdkmanager can run under.

    sdkmanager 34+ requires JDK 17; many build machines still ship JDK 11.
    When the detected JDK is too old, download Temurin 17 into the SDK root
    and use its java instead.
    """
    java = os.environ.get("JAVA_HOME")
    if java:
        candidate = os.path.join(java, "bin", executable("java"))
        if os.path.isfile(candidate):
            return candidate

    system_java = shutil.which("java")
    if system_java:
        try:
            result = subprocess.run([system_java, "-version"],
                                    capture_output=True, text=True, timeout=30)
            output = (result.stderr or result.stdout)
            match = re.search(r"(\d+)", output.splitlines()[0] if output else "")
            if match and int(match.group(1)) >= 17:
                return system_java
        except (OSError, subprocess.TimeoutExpired):
            pass

    # Fall back to a JDK 17 bundled under the SDK root so no system change
    # is required and the install is reproducible.
    jdk_dir = os.path.join(root, ".jdk")
    # The Temurin archive unpacks to <jdk_dir>/<jdk-17.x.y+zz>/bin/java,
    # so look one level deeper than the immediate bin/ directory.
    candidate = os.path.join(jdk_dir, "bin", executable("java"))
    if not os.path.isfile(candidate):
        for name in sorted(os.listdir(jdk_dir)) if os.path.isdir(jdk_dir) else []:
            nested = os.path.join(jdk_dir, name, "bin", executable("java"))
            if os.path.isfile(nested):
                candidate = nested
                break
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        # Tarballs sometimes ship without the executable/readable bits;
        # restore them so the JVM can map its shared memory files.
        for dirpath, _dirs, files in os.walk(jdk_dir):
            for name in files:
                path = os.path.join(dirpath, name)
                if os.path.isfile(path):
                    os.chmod(path, 0o644)
        for dirpath, _dirs, _files in os.walk(jdk_dir):
            os.chmod(dirpath, 0o755)
        os.chmod(candidate, 0o755)
        return candidate

    os.makedirs(jdk_dir, exist_ok=True)
    archive = os.path.join(jdk_dir, "jdk17.tar.gz")
    # Never re-download an archive that is already present and non-empty.
    if os.path.isfile(archive) and os.path.getsize(archive) > 1_000_000:
        log("Reusing existing JDK archive.")
    else:
        urls = [
            "https://github.com/adoptium/temurin17-binaries/releases/download/"
            "jdk-17.0.13%2B11/OpenJDK17U-jdk_x64_linux_hotspot_17.0.13_11.tar.gz",
            "https://github.com/adoptium/temurin17-binaries/releases/download/"
            "jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz",
        ]
        for url in urls:
            log("Downloading JDK 17 for sdkmanager...")
            try:
                download(url, archive)
                if os.path.getsize(archive) == 0:
                    raise RuntimeError("downloaded JDK archive is empty")
                break
            except (OSError, urllib.error.URLError) as error:
                warn("JDK download failed (%s), trying next URL..." % error)
                if os.path.isfile(archive):
                    os.remove(archive)
        else:
            raise RuntimeError("could not download a JDK 17 for sdkmanager; "
                               "install one (e.g. sudo apt-get install openjdk-17-jdk) "
                               "or set JAVA_HOME")

    import tarfile
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(jdk_dir)
    os.remove(archive)
    extracted = next((os.path.join(jdk_dir, d) for d in sorted(os.listdir(jdk_dir))
                      if os.path.isdir(os.path.join(jdk_dir, d))), None)
    if not extracted:
        raise RuntimeError("JDK archive did not contain a top-level directory")
    # Tarballs sometimes ship without the executable/readable bits; restore
    # them so the JVM can map its shared memory files.
    for dirpath, _dirs, files in os.walk(extracted):
        for name in files:
            path = os.path.join(dirpath, name)
            if os.path.isfile(path):
                os.chmod(path, 0o644)
    for dirpath, _dirs, _files in os.walk(extracted):
        os.chmod(dirpath, 0o755)
    candidate = os.path.join(extracted, "bin", executable("java"))
    if not os.path.isfile(candidate):
        raise RuntimeError("downloaded JDK has no java binary")
    os.chmod(candidate, 0o755)
    return candidate


def command_line_tools_archive():
    if sys.platform.startswith("linux"):
        host = "linux"
    elif sys.platform == "darwin":
        host = "mac_arm64" if platform.machine().lower() in ("arm64", "aarch64") else "mac_x86_64"
    elif os.name == "nt":
        host = "win"
    else:
        raise RuntimeError("unsupported host platform: %s" % sys.platform)
    return ("https://dl.google.com/android/repository/commandlinetools-%s-%s_latest.zip"
            % (host, COMMAND_LINE_TOOLS_REVISION))


def download(url, destination):
    log("Downloading %s..." % url)
    request = urllib.request.Request(url, headers={"User-Agent": "android-avd"})
    with urllib.request.urlopen(request, timeout=60) as response, open(destination, "wb") as output:
        shutil.copyfileobj(response, output)


def safe_extract(archive, destination):
    root = os.path.realpath(destination)
    with zipfile.ZipFile(archive) as zf:
        for item in zf.infolist():
            target = os.path.realpath(os.path.join(destination, item.filename))
            if not target.startswith(root + os.sep):
                raise RuntimeError("unsafe path in downloaded archive: %s" % item.filename)
        zf.extractall(destination)


def ensure_sdkmanager(root):
    found = find_sdk_tool(root,
                          ("cmdline-tools", "latest", "bin", "sdkmanager"),
                          ("cmdline-tools", "bin", "sdkmanager"),
                          ("tools", "bin", "sdkmanager"))
    if found:
        # Archives ship without the executable bit; restore it on any existing
        # tool so we never hit a spurious "Permission denied" on a valid install.
        tools_dir = os.path.dirname(os.path.dirname(found))
        for dirpath, _dirs, files in os.walk(tools_dir):
            for name in files:
                path = os.path.join(dirpath, name)
                if os.path.isfile(path) and not os.access(path, os.X_OK):
                    os.chmod(path, 0o755)
        return found

    os.makedirs(root, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="android-cli-", dir=root) as temporary:
        archive = os.path.join(temporary, "command-line-tools.zip")
        try:
            download(command_line_tools_archive(), archive)
            if os.path.getsize(archive) == 0:
                raise RuntimeError("downloaded command-line tools archive is empty")
            safe_extract(archive, temporary)
        except (OSError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError) as error:
            raise RuntimeError("could not download Android command-line tools: %s" % error)
        unpacked = os.path.join(temporary, "cmdline-tools")
        manager = os.path.join(unpacked, "bin", executable("sdkmanager"))
        if not os.path.isfile(manager):
            raise RuntimeError("downloaded command-line tools do not contain sdkmanager")
        # Archives ship without the executable bit; restore it so the tools
        # (sdkmanager, avdmanager, emulator, ...) can actually be invoked.
        for dirpath, _dirs, files in os.walk(unpacked):
            for name in files:
                path = os.path.join(dirpath, name)
                if os.path.isfile(path):
                    os.chmod(path, 0o755)
        destination = os.path.join(root, "cmdline-tools", "latest")
        if os.path.exists(destination):
            shutil.rmtree(destination)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(unpacked, destination)
    return os.path.join(root, "cmdline-tools", "latest", "bin", executable("sdkmanager"))


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, **kwargs)


def run_sdkmanager(manager, root, arguments, java=None, input_text=None):
    # sdkmanager 34+ requires JDK 17; run it under the JDK we ensure for that
    # purpose so it works on machines that only ship JDK 11.
    environment = os.environ.copy()
    if java:
        environment["JAVA_HOME"] = os.path.dirname(os.path.dirname(java))
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    result = subprocess.run([manager, "--sdk_root=" + root] + arguments,
                            input=input_text, text=True, capture_output=True,
                            timeout=1800, env=environment)
    if result.returncode:
        raise RuntimeError("sdkmanager failed while running %s\n%s" %
                           (" ".join(arguments), (result.stderr or result.stdout).strip()))


def system_image_package(api, tag, abi):
    return "system-images;android-%s;%s;%s" % (api, tag, abi)


def ensure_sdk(root, api, tag, abi):
    # sdkmanager is strict about package locations: every package must live
    # under its canonical path. Remove stray copies (emulator-2, emulator-3,
    # ...) left by interrupted or manual installs so it can load the local
    # repository and proceed.
    canonical = {
        "emulator": "emulator",
        "cmdline-tools": "cmdline-tools",
        "platform-tools": "platform-tools",
        "system-images": "system-images",
        "platforms": "platforms",
        "build-tools": "build-tools",
    }
    for entry in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if entry in canonical.values() or entry.startswith("."):
            continue
        if any(entry.startswith(name + "-") for name in canonical):
            stray = os.path.join(root, entry)
            log("Removing stray SDK directory %s..." % stray)
            shutil.rmtree(stray, ignore_errors=True)

    manager = ensure_sdkmanager(root)
    java = ensure_jdk(root)
    log("Accepting Android SDK licenses...")
    run_sdkmanager(manager, root, ["--licenses"], java, input_text="y\n" * 100)
    image = system_image_package(api, tag, abi)
    log("Installing emulator, adb, and %s..." % image)
    run_sdkmanager(manager, root, ["--install", "emulator", "platform-tools", image], java)
    # apkanalyzer shells out to aapt, which ships in build-tools. Install them
    # so application IDs can be resolved without the manifest parser fallback,
    # but do not fail the run when this API has no matching build-tools release.
    try:
        run_sdkmanager(manager, root, ["--install", "build-tools;%s.0.0" % api], java)
    except RuntimeError as error:
        warn("could not install build-tools;%s.0.0 (%s)"
             % (api, str(error).splitlines()[0]))
    emulator = find_sdk_tool(root, ("emulator", "emulator", "emulator"),
                                ("emulator", "emulator-headless"),
                                ("emulator", "emulator"))
    adb = find_sdk_tool(root, ("platform-tools", "adb"))
    avdmanager = find_sdk_tool(root, ("cmdline-tools", "latest", "bin", "avdmanager"),
                               ("cmdline-tools", "bin", "avdmanager"),
                               ("tools", "bin", "avdmanager"))
    if not all((emulator, adb, avdmanager)):
        raise RuntimeError("SDK installation completed but a required Android tool is missing")
    return emulator, adb, avdmanager, image, java


def list_avds(emulator):
    environment = os.environ.copy()
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    result = subprocess.run([emulator, "-list-avds"], capture_output=True, text=True,
                            timeout=30, env=environment)
    if result.returncode:
        raise RuntimeError("could not list Android virtual devices: %s" % result.stderr.strip())
    return set(line.strip() for line in result.stdout.splitlines() if line.strip())


def default_avd_for(abi):
    if abi == "x86_64":
        return DEFAULT_AVD
    return "%s-%s" % (DEFAULT_AVD, abi.replace("_", "-"))


def avd_config(name):
    return os.path.expanduser(os.path.join("~", ".android", "avd",
                                           name + ".avd", "config.ini"))


def _avd_value(name, key):
    try:
        with open(avd_config(name), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def avd_abi(name):
    return _avd_value(name, "abi.type")


def avd_image(name):
    return _avd_value(name, "image.sysdir.1")


def guest_needs_software_emulation(abi):
    host = platform.machine().lower()
    host_arm = host in ("arm64", "aarch64", "armv7l", "armv8l")
    guest_arm = abi.startswith("arm")
    return host_arm != guest_arm


def ensure_avd(emulator, avdmanager, name, image, resolution, java=None, abi=None):
    if name in list_avds(emulator):
        existing = avd_abi(name)
        if abi and existing and existing != abi:
            raise RuntimeError(
                "AVD %s uses %s but the requested ABI is %s; use a different "
                "--avd name (for example %s) or delete the AVD first"
                % (name, existing, abi, default_avd_for(abi)))
        return
    # Build a hardware skin from the requested resolution so the emulator
    # renders at exactly the requested WxH instead of a fixed device skin.
    # The emulator only ships with device-specific skins, so create a
    # full-screen skin directory for the requested resolution when missing.
    skin_dir = os.path.join(sdk_root(), "skins", resolution)
    if not os.path.isdir(skin_dir):
        os.makedirs(skin_dir, exist_ok=True)
        with open(os.path.join(skin_dir, "layout"), "w") as layout:
            layout.write("# Emulator skin: %s (Samsung S24 Plus aspect)\n" % resolution)
            layout.write("# Full-screen skin with no hardware buttons.\n")
            width, height = resolution.split("x")
            layout.write("primary 0 0 %s %s\n" % (width, height))
    log("Creating AVD %s at %s..." % (name, resolution))
    environment = os.environ.copy()
    if java:
        environment["JAVA_HOME"] = os.path.dirname(os.path.dirname(java))
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    result = subprocess.run([avdmanager, "create", "avd", "--force", "--name", name,
                             "--package", image, "--device", "pixel_8",
                             "--skin", resolution], input="no\n", timeout=300,
                            capture_output=True, text=True, env=environment)
    if result.returncode:
        raise RuntimeError("could not create AVD %s:\n%s" %
                           (name, (result.stderr or result.stdout).strip()))


def serial_for(port):
    return "emulator-%d" % port


def adb_device_state(adb, serial):
    result = run([adb, "devices"], timeout=30)
    for line in result.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[0] == serial:
            return fields[1]
    return None


def wait_for_device(adb, serial, process, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if adb_device_state(adb, serial) == "device":
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(2)
    return False


def boot_completed(adb, serial):
    result = run([adb, "-s", serial, "shell", "getprop", "sys.boot_completed"], timeout=30)
    return result.returncode == 0 and result.stdout.strip() == "1"


def wait_for_boot(adb, serial, timeout):
    log("Waiting for Android to finish booting (timeout %ss)..." % timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if boot_completed(adb, serial):
            return True
        time.sleep(5)
    return False


def launch_emulator(emulator, avd, resolution, port, software_emulation,
                    java=None, sdk_root=None, headless=False, gpu=DEFAULT_GPU,
                    scale=None):
    command = [emulator, "-avd", avd, "-port", str(port), "-no-audio",
               "-gpu", gpu, "-skin", resolution, "-no-snapshot-save"]
    if headless:
        command.append("-no-window")
    if scale:
        command += ["-scale", str(scale)]
    environment = os.environ.copy()
    if java:
        environment["JAVA_HOME"] = os.path.dirname(os.path.dirname(java))
    if sdk_root:
        environment["ANDROID_SDK_ROOT"] = sdk_root
        environment["ANDROID_HOME"] = sdk_root
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    if software_emulation:
        environment["ANDROID_I_WANT_MY_TCG"] = "yes"
        command += ["-accel", "off"]
    else:
        command += ["-accel", "auto"]
    log("Launching %s%s..." % (avd, " (headless)" if headless else ""))
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, env=environment)


# ---------------------------------------------------------------------------
# Host window geometry
# ---------------------------------------------------------------------------

def _window_titles(avd, port):
    """Titles used by the emulator's main display window."""
    return ["Android Emulator - %s:%s" % (avd, port),
            "Android Emulator - %s" % avd]


def _linux_windows(avd, port):
    tool = shutil.which("wmctrl")
    if not tool:
        return []
    result = subprocess.run([tool, "-l"], capture_output=True, text=True, timeout=15)
    titles = _window_titles(avd, port)
    matched = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) < 4:
            continue
        if any(fields[3].startswith(title) for title in titles):
            matched.append((fields[0], fields[3]))
    return matched


def _linux_geometry(window_id, size=None, position=None):
    tool = shutil.which("wmctrl")
    if not tool:
        raise RuntimeError("wmctrl is required to move or resize the emulator window")
    x, y, width, height = -1, -1, -1, -1
    if size:
        width, height = (int(value) for value in size.lower().split("x"))
    if position:
        x, y = (int(value) for value in position.split(","))
    subprocess.run([tool, "-i", "-r", window_id, "-e",
                    "0,%d,%d,%d,%d" % (x, y, width, height)],
                   check=True, timeout=15)


def _windows_geometry(avd, size=None, position=None):
    script = r'''
$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int X, int Y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@
$matches = Get-Process | Where-Object { $_.MainWindowTitle -like "Android Emulator - *" }
if (-not $matches) { exit 1 }
$p = $matches[0]
$h = $p.MainWindowHandle
$flags = 0x0004 -bor 0x0010   # SWP_NOZORDER | SWP_NOACTIVATE
$sw = -1; $sh = -1; $sx = -1; $sy = -1
$size = "%s"; $pos = "%s"
if ($size) { $parts = $size.Split("x"); $sw = [int]$parts[0]; $sh = [int]$parts[1] }
if ($pos) { $parts = $pos.Split(","); $sx = [int]$parts[0]; $sy = [int]$parts[1] }
[Win32]::SetWindowPos($h, [IntPtr]::Zero, $sx, $sy, $sw, $sh, $flags) | Out-Null
[Win32]::SetForegroundWindow($h) | Out-Null
''' % (size or "", position or "")
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   check=True, timeout=30)


def _macos_geometry(avd, size=None, position=None, activate=True):
    parts = []
    if position:
        x, y = position.split(",")
        parts.append("set position of window 1 to {%s, %s}" % (x, y))
    if size:
        width, height = size.lower().split("x")
        parts.append("set size of window 1 to {%s, %s}" % (width, height))
    if activate:
        parts.insert(0, "set frontmost to true")
    if not parts:
        return
    script = ('tell application "System Events" to tell process "qemu-system-*"\n'
              '  %s\nend tell' % "\n  ".join(parts))
    subprocess.run(["osascript", "-e", script], check=True, timeout=30)


def apply_window_geometry(avd, port, size=None, position=None, activate=False):
    """Move/resize and/or raise the emulator's main window."""
    if not size and not position and not activate:
        return False
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        if size or position:
            warn("no DISPLAY/WAYLAND_DISPLAY; cannot move the emulator window")
        return False
    if os.name == "nt":
        _windows_geometry(avd, size, position)
        return True
    if sys.platform == "darwin":
        _macos_geometry(avd, size, position, activate)
        return True

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        windows = _linux_windows(avd, port)
        if windows:
            for window_id, _title in windows:
                if size or position:
                    _linux_geometry(window_id, size, position)
            if activate:
                subprocess.run([shutil.which("wmctrl"), "-i", "-a", windows[0][0]],
                               timeout=15)
            if size:
                log("Emulator window size: %s" % size)
            if position:
                log("Emulator window position: %s" % position)
            return True
        time.sleep(1)
    if size or position:
        warn("emulator window '%s' not found; it may still be starting"
             % _window_titles(avd, port)[0])
    return False


# ---------------------------------------------------------------------------
# High-level lifecycle
# ---------------------------------------------------------------------------

def open_emulator(root=None, avd=None, abi="x86_64", api=DEFAULT_API,
                  image_tag=DEFAULT_IMAGE_TAG, resolution=DEFAULT_RESOLUTION,
                  port=DEFAULT_PORT, gpu=DEFAULT_GPU, headless=False,
                  software_emulation=False, emulator_path=None, timeout=BOOT_TIMEOUT,
                  no_boot_wait=False, window_size=None, window_position=None,
                  activate=True, scale=None):
    root = sdk_root(root)
    avd = avd or default_avd_for(abi)
    host = platform.machine().lower()
    if host in ("x86_64", "amd64", "i386", "i686") and abi.startswith("arm"):
        raise RuntimeError(
            "this x86 host cannot run an %s AVD: Android emulator 35.2+ rejects "
            "arm64 guests on x86_64. Run an x86_64 APK (--abi x86_64) or use a "
            "physical arm64 device." % abi)
    software = software_emulation or guest_needs_software_emulation(abi)
    if software and not software_emulation:
        log("Host is %s but the guest is %s; using slow software CPU "
            "emulation. Expect a long first boot."
            % (platform.machine(), abi))

    emulator, adb, avdmanager, image, java = ensure_sdk(root, api, image_tag, abi)
    if emulator_path:
        emulator = os.path.abspath(emulator_path)
        if not os.path.isfile(emulator) or not os.access(emulator, os.X_OK):
            raise RuntimeError("--emulator is not an executable file: %s" % emulator)
    ensure_avd(emulator, avdmanager, avd, image, resolution, java, abi)
    run([adb, "start-server"], timeout=30)
    serial = serial_for(port)
    state = adb_device_state(adb, serial)
    if state == "device":
        log("Reusing running emulator %s." % serial)
        process = None
    else:
        if state:
            raise RuntimeError("%s is %s; stop it with '%s -s %s emu kill' and retry"
                               % (serial, state, adb, serial))
        if sys.platform.startswith("linux") and not os.access("/dev/kvm", os.R_OK | os.W_OK):
            warn("/dev/kvm is unavailable. Startup may fail or be very slow; "
                 "use --software-emulation to explicitly allow software emulation.")
        process = launch_emulator(emulator, avd, resolution, port, software,
                                  java, root, headless, gpu, scale)
        device_timeout = 900 if software else 90
        if not wait_for_device(adb, serial, process, device_timeout):
            raise RuntimeError("emulator did not register with adb within %s seconds. "
                               "Check KVM access or retry with --software-emulation."
                               % device_timeout)
    if not no_boot_wait and not wait_for_boot(adb, serial, timeout):
        raise RuntimeError("Android did not finish booting within %s seconds" % timeout)
    if not headless:
        apply_window_geometry(avd, port, window_size, window_position, activate)
    return {
        "root": root,
        "avd": avd,
        "serial": serial,
        "adb": adb,
        "emulator": emulator,
        "java": java,
        "api": api,
        "abi": abi,
        "resolution": resolution,
        "port": port,
        "headless": headless,
        "process": process,
    }


def emulator_avd_name(adb, serial):
    result = run([adb, "-s", serial, "emu", "avd", "name"], timeout=15)
    if result.returncode:
        return None
    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return line if line and line != "OK" else None


def running_emulators(adb):
    result = run([adb, "devices"], timeout=30)
    serials = []
    for line in result.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[0].startswith("emulator-"):
            serials.append((fields[0], fields[1]))
    return serials


def close_emulator(adb, serial):
    result = run([adb, "-s", serial, "emu", "kill"], timeout=30)
    if result.returncode:
        raise RuntimeError("could not stop %s: %s"
                           % (serial, (result.stderr or result.stdout).strip()))
