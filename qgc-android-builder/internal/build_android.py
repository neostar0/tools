#!/usr/bin/env python3
"""Build QGroundControl Android APKs for x86_64 and arm64-v8a."""

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(TOOL_ROOT)

DEFAULT_IMAGE = "qgc-android-builder:latest"
DEFAULT_JOBS = 4
DEFAULT_ABI = "arm64-v8a"
ABIS = ("x86_64", "arm64-v8a")
SIGNED_APK = os.path.join("android-build", "build", "outputs", "apk", "release",
                          "android-build-release-signed.apk")
UNSIGNED_APK = os.path.join("android-build", "build", "outputs", "apk", "release",
                            "android-build-release-unsigned.apk")


def log(message):
    print("[qgc-android-builder] %s" % message)


def warn(message):
    print("[qgc-android-builder] WARNING: %s" % message, file=sys.stderr)


def docker(*arguments, **kwargs):
    return subprocess.run(["docker"] + list(arguments), text=True, **kwargs)


def qgc_root(value):
    if value:
        candidates = [os.path.abspath(value)]
    else:
        candidates = []
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            candidates.append(result.stdout.strip())
        candidates.append(os.path.join(REPO_ROOT, "..", "qgc"))
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.isfile(os.path.join(candidate, "qgroundcontrol.pro")):
            return candidate
    raise RuntimeError("%s does not look like a QGroundControl checkout "
                       "(qgroundcontrol.pro missing)" % (candidates[0] if candidates else "?"))


def keystore_password(root):
    password = os.environ.get("ANDROID_KEYSTORE_PASSWORD")
    if password:
        return password
    # The checkout's own build script keeps the local development keystore
    # password. Read it without executing the script, and fall back to an
    # unsigned build when it is absent.
    script = os.path.join(root, "build-android.sh")
    try:
        with open(script, encoding="utf-8") as handle:
            match = re.search(r"ANDROID_KEYSTORE_PASSWORD=([^\s\"']+)", handle.read())
            if match:
                return match.group(1)
    except OSError:
        pass
    return None


def image_exists(image):
    result = docker("image", "inspect", image, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    return result.returncode == 0


def build_image(image, rebuild=False):
    if image_exists(image) and not rebuild:
        log("Reusing Docker image %s" % image)
        return
    if rebuild:
        log("Rebuilding Docker image %s" % image)
    else:
        log("Building Docker image %s (first run downloads Qt and the Android SDK)"
            % image)
    result = docker("build", "--tag", image, "--file", os.path.join(TOOL_ROOT, "docker", "Dockerfile"),
                    os.path.join(TOOL_ROOT, "docker"))
    if result.returncode:
        raise RuntimeError("could not build Docker image %s" % image)


def _write_if_changed(path, content):
    try:
        with open(path, encoding="utf-8") as handle:
            if handle.read() == content:
                return
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _replace(text, old, new, description):
    if old not in text:
        raise RuntimeError("could not patch %s: expected text not found" % description)
    return text.replace(old, new, 1)


def write_x86_overlays(root, directory):
    """Create the files that make the x86_64 UI build work.

    The official GStreamer x86_64 static libraries are not PIC, so linking
    video into libQGroundControl fails and Android rejects the resulting
    text-relocated .so. The UI build disables video streaming and supplies
    no-op GStreamer entry points instead.
    """
    os.makedirs(directory, exist_ok=True)

    common = os.path.join(root, "QGCCommon.pri")
    with open(common, encoding="utf-8") as handle:
        text = handle.read()
    text = _replace(
        text,
        '        } else:equals(ANDROID_TARGET_ARCH, x86)  {\n'
        '            CONFIG += Androidx86Build\n'
        '            DEFINES += __androidx86__\n'
        '            message("Android x86 build")\n'
        '        } else {',
        '        } else:equals(ANDROID_TARGET_ARCH, x86)  {\n'
        '            CONFIG += Androidx86Build\n'
        '            DEFINES += __androidx86__\n'
        '            message("Android x86 build")\n'
        '        } else:equals(ANDROID_TARGET_ARCH, x86_64)  {\n'
        '            DEFINES += __androidx86_64__\n'
        '            message("Android x86_64 build")\n'
        '        } else {',
        "QGCCommon.pri Android architecture")
    text = _replace(
        text,
        '    equals(ANDROID_TARGET_ARCH, arm64-v8a)  {\n'
        '        ANDROID_TRUE_BITNESS = 64\n'
        '        ANDROID_VERSION_BITNESS = 66\n'
        '    } else {',
        '    equals(ANDROID_TARGET_ARCH, arm64-v8a)|equals(ANDROID_TARGET_ARCH, x86_64)  {\n'
        '        ANDROID_TRUE_BITNESS = 64\n'
        '        ANDROID_VERSION_BITNESS = 66\n'
        '    } else {',
        "QGCCommon.pri Android bitness")
    text = "SOURCES += /project/build/.patches/gst_stub.cpp\n" + text
    _write_if_changed(os.path.join(directory, "QGCCommon.pri"), text)

    header = os.path.join(root, "src", "Joystick", "JoystickManager.h")
    with open(header, encoding="utf-8") as handle:
        text = handle.read()
    text = _replace(text, '#include "../VideoReceiver/GstVideoReceiver.h"',
                    'class GstVideoReceiver;', "JoystickManager.h GStreamer include")
    _write_if_changed(os.path.join(directory, "JoystickManager.h"), text)

    source = os.path.join(root, "src", "Joystick", "JoystickManager.cc")
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    text = _replace(text, 'gst_rec = dynamic_cast<GstVideoReceiver*>(v_rec);',
                    'gst_rec = reinterpret_cast<GstVideoReceiver*>(v_rec);',
                    "JoystickManager.cc GStreamer cast")
    _write_if_changed(os.path.join(directory, "JoystickManager.cc"), text)

    _write_if_changed(os.path.join(directory, "gst_stub.cpp"),
        '#include <jni.h>\n'
        '#include "VideoReceiver/GStreamer.h"\n\n'
        'void GStreamer::blacklist(VideoSettings::VideoDecoderOptions) {}\n'
        'void GStreamer::initialize(int, char**, int) {}\n'
        'void* GStreamer::createVideoSink(QObject*, QQuickItem*) { return nullptr; }\n'
        'void GStreamer::releaseVideoSink(void*) {}\n'
        'VideoReceiver* GStreamer::createVideoReceiver(QObject*) { return nullptr; }\n\n'
        'extern "C" void gst_amc_jni_set_java_vm(JavaVM*) {}\n')


def build_dir_for(root, abi):
    """arm64-v8a keeps the original build_android directory; other ABIs are separate."""
    if abi == "arm64-v8a":
        return os.path.join(root, "build_android")
    return os.path.join(root, "build_android_%s" % abi.replace("-", "_"))


def build_abi(root, abi, args, password):
    build_dir = build_dir_for(root, abi)
    if args.clean and os.path.isdir(build_dir):
        log("Removing %s" % build_dir)
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)

    video = abi == "arm64-v8a" or args.x86_video
    if abi == "x86_64" and not video:
        log("x86_64: video streaming is disabled (GStreamer x86_64 is not PIC)")

    command = ("qmake /project/source CONFIG+=installer %sANDROID_ABIS=%s && "
               "make -j%d" % ("CONFIG+=DISABLE_VIDEOSTREAMING " if not video else "",
                              abi, args.jobs))
    volumes = ["-v", "%s:/project/source" % root,
               "-v", "%s:/project/build" % build_dir]
    patches = os.path.join(build_dir, ".patches")
    if abi == "x86_64" and not video:
        write_x86_overlays(root, patches)
        volumes += [
            "-v", "%s/QGCCommon.pri:/project/source/QGCCommon.pri:ro" % patches,
            "-v", "%s/JoystickManager.h:/project/source/src/Joystick/JoystickManager.h:ro" % patches,
            "-v", "%s/JoystickManager.cc:/project/source/src/Joystick/JoystickManager.cc:ro" % patches,
        ]
    environment = ["-e", "ANDROID_ABIS=%s" % abi,
                   "-e", "GRADLE_USER_HOME=/project/build/.gradle"]
    if password:
        environment += ["-e", "ANDROID_KEYSTORE_PASSWORD=%s" % password]
    log("Building %s into %s" % (abi, build_dir))
    user_args = []
    if os.name != "nt":
        user_args = ["--user", "%s:%s" % (os.getuid(), os.getgid())]
    result = subprocess.run(
        ["docker", "run", "--rm"] + user_args
        + environment + volumes + [args.image, "/bin/sh", "-c", command])
    if result.returncode:
        raise RuntimeError("%s build failed" % abi)

    signed = os.path.join(build_dir, SIGNED_APK)
    unsigned = os.path.join(build_dir, UNSIGNED_APK)
    apk = signed if os.path.isfile(signed) else unsigned
    if not os.path.isfile(apk):
        raise RuntimeError("%s build finished but no APK was produced" % abi)
    log("APK: %s" % apk)
    if not os.path.isfile(signed):
        warn("no signed APK was produced; export ANDROID_KEYSTORE_PASSWORD "
             "before installing it on a device")
    if args.out:
        suffix = "" if video else "-novideo"
        name = "%s-%s%s.apk" % (args.name, abi, suffix)
        os.makedirs(args.out, exist_ok=True)
        destination = os.path.join(args.out, name)
        shutil.copy2(apk, destination)
        log("Copied APK to %s" % destination)
        return destination
    return apk


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", nargs="?", help="QGroundControl checkout (same as --root)")
    parser.add_argument("--root", help="QGroundControl checkout (default: current git root)")
    parser.add_argument("--abi", action="append", choices=ABIS + ("all",),
                        help="ABI to build; repeat or use all (default: arm64-v8a)")
    parser.add_argument("--out", help="also copy the APK into this directory")
    parser.add_argument("--name", default="QGroundControl",
                        help="APK base name (default: %(default)s)")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                        help="parallel make jobs (default: %(default)s)")
    parser.add_argument("--image", default=DEFAULT_IMAGE,
                        help="Docker image (default: %(default)s)")
    parser.add_argument("--rebuild-image", action="store_true",
                        help="rebuild the Docker image even when it exists")
    parser.add_argument("--clean", action="store_true",
                        help="remove each ABI's build directory first")
    parser.add_argument("--x86-video", action="store_true",
                        help="try to build x86_64 with video (needs PIC GStreamer)")
    args = parser.parse_args()
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    abis = args.abi or [DEFAULT_ABI]
    if "all" in abis:
        args.abis = list(ABIS)
    else:
        args.abis = [abi for abi in ABIS if abi in abis]
    args.root = qgc_root(args.root or args.checkout)
    args.out = os.path.abspath(args.out) if args.out else None
    return args


def main():
    args = parse_args()
    try:
        if not shutil.which("docker"):
            raise RuntimeError("docker not found; install Docker and retry")
        build_image(args.image, args.rebuild_image)
        password = keystore_password(args.root)
        if not password:
            warn("ANDROID_KEYSTORE_PASSWORD is not set and no local development "
                 "password was found; the APK will be unsigned")
        outputs = []
        failures = []
        for abi in args.abis:
            try:
                outputs.append(build_abi(args.root, abi, args, password))
            except RuntimeError as error:
                failures.append("%s: %s" % (abi, error))
        for output in outputs:
            print("[qgc-android-builder] Built %s" % output)
        for failure in failures:
            print("[qgc-android-builder] FAILED %s" % failure, file=sys.stderr)
        return 1 if failures else 0
    except (OSError, RuntimeError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
