#!/usr/bin/env python3
"""Open, close and position Android Virtual Devices."""

import argparse
import os
import re
import shutil
import sys

import avd_core as core


def positive_size(value):
    if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, for example 900x416")
    return value


def position(value):
    if not re.fullmatch(r"-?[0-9]+,-?[0-9]+", value):
        raise argparse.ArgumentTypeError("expected X,Y, for example 40,80")
    return value


def add_common(parser):
    parser.add_argument("--sdk-root", help="Android SDK root (default: ANDROID_SDK_ROOT, ANDROID_HOME, or ~/Android/Sdk)")
    parser.add_argument("--avd", help="AVD name (default: s24-plus for x86_64, s24-plus-<abi> otherwise)")
    parser.add_argument("--abi", default="x86_64", help="system-image ABI (default: %(default)s)")
    parser.add_argument("--api", default=core.DEFAULT_API, help="Android API level (default: %(default)s)")
    parser.add_argument("--image-tag", default=core.DEFAULT_IMAGE_TAG, help="system-image tag (default: %(default)s)")
    parser.add_argument("--port", type=int, default=core.DEFAULT_PORT, help="emulator console port (default: %(default)s)")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Open, close and position Android Virtual Devices.")
    sub = parser.add_subparsers(dest="command", required=True)

    open_parser = sub.add_parser("open", help="start (or reuse) an emulator window")
    add_common(open_parser)
    open_parser.add_argument("--resolution", default=core.DEFAULT_RESOLUTION,
                             help="guest display resolution WxH (default: %(default)s)")
    open_parser.add_argument("--gpu", default=core.DEFAULT_GPU,
                             help="emulator GPU mode: auto, host, software, swangle, "
                                  "swiftshader, lavapipe (default: %(default)s)")
    open_parser.add_argument("--emulator", help="use this emulator binary")
    open_parser.add_argument("--timeout", type=int, default=core.BOOT_TIMEOUT,
                             help="boot timeout in seconds (default: %(default)s)")
    open_parser.add_argument("--headless", action="store_true",
                             help="run without a visible window")
    open_parser.add_argument("--software-emulation", action="store_true",
                             help="allow slow software CPU emulation")
    open_parser.add_argument("--no-boot-wait", action="store_true",
                             help="return as soon as adb connects")
    open_parser.add_argument("--scale", type=float,
                             help="emulator window scale factor (for example 0.5)")
    open_parser.add_argument("--window-size", type=positive_size,
                             help="resize the host window to WIDTHxHEIGHT")
    open_parser.add_argument("--window-position", type=position,
                             help="move the host window to X,Y")
    open_parser.add_argument("--no-activate", action="store_true",
                             help="do not raise the emulator window")

    close_parser = sub.add_parser("close", help="stop a running emulator")
    close_parser.add_argument("--sdk-root", help="Android SDK root")
    close_parser.add_argument("--avd", help="stop the emulator running this AVD")
    close_parser.add_argument("--port", type=int, help="stop emulator-<port>")
    close_parser.add_argument("--serial", help="stop this adb serial")
    close_parser.add_argument("--all", action="store_true", help="stop every emulator")

    geometry_parser = sub.add_parser("geometry", help="move/resize a running emulator window")
    geometry_parser.add_argument("--sdk-root", help="Android SDK root")
    geometry_parser.add_argument("--avd", help="AVD name of the running emulator")
    geometry_parser.add_argument("--port", type=int, default=core.DEFAULT_PORT,
                                 help="emulator console port (default: %(default)s)")
    geometry_parser.add_argument("--window-size", type=positive_size,
                                 help="resize the window to WIDTHxHEIGHT")
    geometry_parser.add_argument("--window-position", type=position,
                                 help="move the window to X,Y")
    geometry_parser.add_argument("--no-activate", action="store_true",
                                 help="do not raise the window")

    list_parser = sub.add_parser("list", help="list AVDs")
    list_parser.add_argument("--sdk-root", help="Android SDK root")

    status_parser = sub.add_parser("status", help="list running emulators")
    status_parser.add_argument("--sdk-root", help="Android SDK root")

    return parser


def validate(args, parser):
    if getattr(args, "port", None) is not None:
        if not 5554 <= args.port <= 5680 or args.port % 2:
            parser.error("--port must be an even emulator console port from 5554 through 5680")
    if getattr(args, "timeout", None) is not None and args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "scale", None) is not None and args.scale <= 0:
        parser.error("--scale must be positive")
    if getattr(args, "avd", None) is None and getattr(args, "abi", None):
        args.avd = core.default_avd_for(args.abi)


def find_emulator(root):
    emulator = core.find_sdk_tool(root, ("emulator", "emulator", "emulator"),
                                  ("emulator", "emulator-headless"),
                                  ("emulator", "emulator"))
    return emulator


def find_adb(root):
    return core.find_sdk_tool(root, ("platform-tools", "adb")) or shutil.which("adb")


def command_open(args, parser):
    context = core.open_emulator(
        root=args.sdk_root, avd=args.avd, abi=args.abi, api=args.api,
        image_tag=args.image_tag, resolution=args.resolution, port=args.port,
        gpu=args.gpu, headless=args.headless,
        software_emulation=args.software_emulation, emulator_path=args.emulator,
        timeout=args.timeout, no_boot_wait=args.no_boot_wait,
        window_size=args.window_size, window_position=args.window_position,
        activate=not args.no_activate, scale=args.scale)
    print("[android-avd] %s is ready (%s)" % (context["serial"], context["avd"]))
    print("[android-avd] Stop it with: %s -s %s emu kill"
          % (context["adb"], context["serial"]))
    return 0


def command_close(args, parser):
    root = core.sdk_root(args.sdk_root)
    adb = find_adb(root)
    if not adb:
        raise RuntimeError("adb not found; run android-avd open once to install the SDK")
    targets = []
    if args.all:
        targets = [serial for serial, state in core.running_emulators(adb)
                   if state in ("device", "offline", "unauthorized")]
    elif args.serial:
        targets = [args.serial]
    elif args.port:
        targets = [core.serial_for(args.port)]
    elif args.avd:
        for serial, _state in core.running_emulators(adb):
            if core.emulator_avd_name(adb, serial) == args.avd:
                targets.append(serial)
        if not targets:
            raise RuntimeError("no running emulator for AVD %s" % args.avd)
    else:
        parser.error("close needs --avd, --port, --serial or --all")
    for serial in targets:
        core.close_emulator(adb, serial)
        print("[android-avd] Stopped %s" % serial)
    return 0


def command_geometry(args, parser):
    if not args.window_size and not args.window_position:
        parser.error("geometry needs --window-size and/or --window-position")
    avd = args.avd
    if not avd:
        root = core.sdk_root(args.sdk_root)
        adb = find_adb(root)
        if adb:
            for serial, _state in core.running_emulators(adb):
                if serial == core.serial_for(args.port):
                    avd = core.emulator_avd_name(adb, serial)
                    break
    if not avd:
        parser.error("--avd is required when the emulator is not running")
    if not core.apply_window_geometry(avd, args.port, args.window_size,
                                      args.window_position,
                                      activate=not args.no_activate):
        return 1
    return 0


def command_list(args, parser):
    root = core.sdk_root(args.sdk_root)
    emulator = find_emulator(root)
    if not emulator:
        raise RuntimeError("emulator not found under %s; run android-avd open once" % root)
    for name in sorted(core.list_avds(emulator)):
        print("%s\t%s" % (name, core.avd_abi(name) or "?"))
    return 0


def command_status(args, parser):
    root = core.sdk_root(args.sdk_root)
    adb = find_adb(root)
    if not adb:
        raise RuntimeError("adb not found; run android-avd open once to install the SDK")
    for serial, state in core.running_emulators(adb):
        avd = core.emulator_avd_name(adb, serial) or "?"
        print("%s\t%s\t%s" % (serial, state, avd))
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate(args, parser)
    handlers = {
        "open": command_open,
        "close": command_close,
        "geometry": command_geometry,
        "list": command_list,
        "status": command_status,
    }
    try:
        return handlers[args.command](args, parser)
    except (OSError, RuntimeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
