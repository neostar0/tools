#!/usr/bin/env python3
"""Install and run an APK on an Android Virtual Device."""

import argparse
import os
import re
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
AVD_CORE = os.path.join(REPO_ROOT, "android-avd", "internal")
if AVD_CORE not in sys.path:
    sys.path.insert(0, AVD_CORE)

import avd_core as avd  # noqa: E402

avd.set_prefix("run-apk-on-avd")


def apk_abis(apk):
    """Return the native ABIs packaged in an APK."""
    try:
        with zipfile.ZipFile(apk) as archive:
            abis = set()
            for name in archive.namelist():
                parts = name.split("/")
                if len(parts) >= 3 and parts[0] == "lib" and parts[1]:
                    abis.add(parts[1])
            return sorted(abis)
    except (OSError, zipfile.BadZipFile):
        return []


def install_apk(adb, serial, apk):
    avd.log("Installing APK: %s" % apk)
    result = avd.run([adb, "-s", serial, "install", "-r", apk], timeout=600)
    if result.returncode:
        raise RuntimeError("APK installation failed:\n%s" % (result.stdout + result.stderr).strip())


def _decode_length8(data, offset):
    value = data[offset]
    offset += 1
    if value & 0x80:
        value = ((value & 0x7F) << 8) | data[offset]
        offset += 1
    return value, offset


def _decode_length16(data, offset):
    value = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if value & 0x8000:
        value = ((value & 0x7FFF) << 16) | struct.unpack_from("<H", data, offset)[0]
        offset += 2
    return value, offset


def _string_pool(data, offset):
    _type, header_size, _size = struct.unpack_from("<HHI", data, offset)
    count, _style_count, flags, strings_start, _styles_start = struct.unpack_from(
        "<IIIII", data, offset + 8)
    utf8 = bool(flags & 0x100)
    offsets = struct.unpack_from("<%dI" % count, data, offset + header_size)
    strings = []
    for relative in offsets:
        position = offset + strings_start + relative
        if utf8:
            _utf16_length, position = _decode_length8(data, position)
            length, position = _decode_length8(data, position)
            strings.append(data[position:position + length].decode("utf-8", "replace"))
        else:
            length, position = _decode_length16(data, position)
            strings.append(data[position:position + length * 2].decode("utf-16-le", "replace"))
    return strings


def apk_manifest_package(apk):
    """Read the package attribute from an APK's binary AndroidManifest.xml.

    This is a dependency-free fallback for apkanalyzer, which needs the SDK
    build-tools (aapt) and fails on SDKs where only the emulator and platform
    tools are installed.
    """
    with zipfile.ZipFile(apk) as archive:
        data = archive.read("AndroidManifest.xml")
    _type, header_size, _size = struct.unpack_from("<HHI", data, 0)
    offset = header_size
    strings = []
    while offset + 8 <= len(data):
        chunk_type, _chunk_header, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_size < 8:
            break
        if chunk_type == 0x0001:
            strings = _string_pool(data, offset)
        elif chunk_type == 0x0102:
            attributes = offset + _chunk_header
            namespace, name, attribute_start, attribute_size, attribute_count = \
                struct.unpack_from("<IIHHH", data, attributes)
            if name < len(strings) and strings[name] == "manifest":
                base = attributes + attribute_start
                for index in range(attribute_count):
                    attribute = base + index * attribute_size
                    _ns, attr_name, raw_value = struct.unpack_from("<III", data, attribute)
                    if attr_name >= len(strings) or strings[attr_name] != "package":
                        continue
                    if raw_value != 0xFFFFFFFF and raw_value < len(strings):
                        return strings[raw_value]
                    _value_size, _res0, _value_type, value = struct.unpack_from(
                        "<HBBI", data, attribute + 12)
                    if value < len(strings):
                        return strings[value]
                return None
        offset += chunk_size
    return None


def apk_package_name(apkanalyzer, apk, java=None):
    environment = os.environ.copy()
    if java:
        environment["JAVA_HOME"] = os.path.dirname(os.path.dirname(java))
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    if not apkanalyzer:
        package, error, failed = "", "apkanalyzer not installed", True
    else:
        try:
            result = subprocess.run([apkanalyzer, "manifest", "application-id", apk],
                                    capture_output=True, text=True, timeout=60, env=environment)
            package = result.stdout.strip()
            error = (result.stderr or result.stdout).strip()
            failed = bool(result.returncode)
        except (OSError, subprocess.TimeoutExpired) as exception:
            package, error, failed = "", str(exception), True
    if failed or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", package):
        try:
            package = apk_manifest_package(apk) or ""
        except (OSError, KeyError, zipfile.BadZipFile, struct.error):
            package = ""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", package):
            raise RuntimeError("could not determine APK application ID: %s" % error)
    return package


def launch_apk(adb, serial, package, java=None):
    avd.log("Launching %s..." % package)
    environment = os.environ.copy()
    if java:
        environment["JAVA_HOME"] = os.path.dirname(os.path.dirname(java))
    environment["SKIP_JDK_VERSION_CHECK"] = "yes"
    result = subprocess.run([adb, "-s", serial, "shell", "monkey", "-p", package,
                              "-c", "android.intent.category.LAUNCHER", "1"],
                             capture_output=True, text=True, timeout=60, env=environment)
    if result.returncode or "No activities found" in result.stdout:
        raise RuntimeError("could not launch %s:\n%s" %
                           (package, (result.stdout + result.stderr).strip()))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", help="path to the APK file to install")
    parser.add_argument("--avd", help="AVD name (default: s24-plus for x86_64, s24-plus-<abi> otherwise)")
    parser.add_argument("--resolution", default=avd.DEFAULT_RESOLUTION,
                        help="display resolution WxH (default: %(default)s)")
    parser.add_argument("--sdk-root", help="Android SDK root (default: ANDROID_SDK_ROOT, ANDROID_HOME, or ~/Android/Sdk)")
    parser.add_argument("--emulator", help="use this emulator binary instead of the SDK-managed one")
    parser.add_argument("--api", default=avd.DEFAULT_API, help="Android API level (default: %(default)s)")
    parser.add_argument("--image-tag", default=avd.DEFAULT_IMAGE_TAG,
                        help="system-image tag (default: %(default)s)")
    parser.add_argument("--abi", default="x86_64",
                        help="system-image ABI; use arm64-v8a for arm64-only APKs (default: %(default)s)")
    parser.add_argument("--port", type=int, default=avd.DEFAULT_PORT,
                        help="emulator console port (default: %(default)s)")
    parser.add_argument("--timeout", type=int, default=avd.BOOT_TIMEOUT,
                        help="boot timeout in seconds (default: %(default)s)")
    parser.add_argument("--no-boot-wait", action="store_true",
                        help="install once adb connects; do not wait for boot completion")
    parser.add_argument("--headless", action="store_true",
                        help="run the emulator without a visible window (default: show the window)")
    parser.add_argument("--scale", type=float,
                        help="emulator window scale factor (for example 0.5)")
    parser.add_argument("--window-size", help="resize the emulator window to WIDTHxHEIGHT after launch")
    parser.add_argument("--window-position", help="move the emulator window to X,Y after launch")
    parser.add_argument("--gpu", default=avd.DEFAULT_GPU,
                        help="emulator GPU mode: auto, host, software, swangle, swiftshader, "
                             "lavapipe (default: %(default)s)")
    parser.add_argument("--software-emulation", action="store_true",
                        help="allow very slow emulation without hardware virtualization")
    args = parser.parse_args()
    if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", args.resolution):
        parser.error("--resolution must be WIDTHxHEIGHT, for example 1440x3120")
    if not 5554 <= args.port <= 5680 or args.port % 2:
        parser.error("--port must be an even emulator console port from 5554 through 5680")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.scale is not None and args.scale <= 0:
        parser.error("--scale must be positive")
    if args.window_size and not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", args.window_size):
        parser.error("--window-size must be WIDTHxHEIGHT, for example 900x416")
    if args.window_position and not re.fullmatch(r"-?[0-9]+,-?[0-9]+", args.window_position):
        parser.error("--window-position must be X,Y, for example 40,80")
    if not args.avd:
        args.avd = avd.default_avd_for(args.abi)
    return args


def main():
    args = parse_args()
    apk = os.path.abspath(args.apk)
    if not os.path.isfile(apk):
        print("ERROR: APK not found: %s" % apk, file=sys.stderr)
        return 1
    try:
        context = avd.open_emulator(
            root=args.sdk_root, avd=args.avd, abi=args.abi, api=args.api,
            image_tag=args.image_tag, resolution=args.resolution, port=args.port,
            gpu=args.gpu, headless=args.headless,
            software_emulation=args.software_emulation, emulator_path=args.emulator,
            timeout=args.timeout, no_boot_wait=args.no_boot_wait,
            window_size=args.window_size, window_position=args.window_position,
            scale=args.scale)
        adb = context["adb"]
        serial = context["serial"]
        java = context["java"]
        abis = apk_abis(apk)
        if args.abi == "x86_64" and abis and not any(a in ("x86_64", "x86") for a in abis):
            avd.warn("APK contains only %s; it runs through ARM translation on this "
                     "x86_64 emulator, which can break Qt image textures. Build with "
                     "--abi x86_64 in qgc-android-builder for a native run."
                     % ", ".join(abis))
        install_apk(adb, serial, apk)
        apkanalyzer = avd.find_sdk_tool(context["root"],
                                        ("cmdline-tools", "latest", "bin", "apkanalyzer"),
                                        ("cmdline-tools", "bin", "apkanalyzer"),
                                        ("tools", "bin", "apkanalyzer"))
        launch_apk(adb, serial, apk_package_name(apkanalyzer, apk, java), java)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print("[run-apk-on-avd] APK installed on %s (%s)." % (serial, args.resolution))
    print("[run-apk-on-avd] Stop it with: %s -s %s emu kill" % (adb, serial))
    return 0


if __name__ == "__main__":
    sys.exit(main())
