#!/usr/bin/env python3
"""Build a QGroundControl 5 checkout inside its Docker builder image.

The checkout owns ``deploy/docker`` (Dockerfile and variants.json); this tool
selects a variant, builds the image when needed, and runs the build as the host
UID so the artifacts in the build directory stay user-owned.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_TYPES = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")
DEFAULT_VARIANT = "ubuntu"
DOCKERFILE = Path("deploy/docker/Dockerfile")
VARIANTS_FILE = Path("deploy/docker/variants.json")
USAGE_FILE = Path(__file__).with_name("usage.md")


class UsageError(Exception):
    """Bad arguments or an unusable checkout (exit code 2)."""


class BuildError(Exception):
    """Docker or the build itself failed (exit code 1)."""


def usage_text() -> str:
    return USAGE_FILE.read_text(encoding="utf-8")


def is_qgc5(root: Path) -> bool:
    return (
        (root / "CMakeLists.txt").is_file()
        and (root / DOCKERFILE).is_file()
        and (root / VARIANTS_FILE).is_file()
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
            f"{root} is a QGroundControl 4 checkout; use build-qgc for QGC 4"
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


def load_variants(root: Path) -> dict[str, dict]:
    path = root / VARIANTS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise UsageError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise UsageError(f"invalid JSON in {path}: {error}") from error

    variants = data.get("variants") if isinstance(data, dict) else None
    if not isinstance(variants, list) or not variants:
        raise UsageError(f"{path} has no variants list")

    result: dict[str, dict] = {}
    for variant in variants:
        if not isinstance(variant, dict):
            raise UsageError(f"{path} contains a non-object variant")
        missing = [key for key in ("id", "target", "image") if not variant.get(key)]
        if missing:
            raise UsageError(
                f"{path} variant is missing {', '.join(missing)}: {variant!r}"
            )
        result[str(variant["id"])] = variant
    return result


def default_build_dir(root: Path, variant_id: str) -> Path:
    if variant_id == "aarch64":
        return root / "build-aarch64"
    return root / "build"


def default_jobs() -> int:
    return max(1, os.cpu_count() or 1)


def host_user_argument() -> list[str]:
    if hasattr(os, "getuid"):
        return ["--user", f"{os.getuid()}:{os.getgid()}"]
    return []


def build_image_command(
    root: Path, variant: dict, image: str, *, rebuild: bool
) -> list[str]:
    command = [
        "docker",
        "build",
        "--file",
        str(root / DOCKERFILE),
        "--target",
        str(variant["target"]),
    ]
    build_args = variant.get("build_args") or {}
    for key, value in build_args.items():
        command += ["--build-arg", f"{key}={value}"]
    if rebuild:
        command.append("--no-cache")
    command += ["-t", image, str(root)]
    return command


def run_build_command(
    root: Path,
    build_dir: Path,
    variant: dict,
    image: str,
    build_type: str,
    jobs: int,
    *,
    clean: bool,
) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        *host_user_argument(),
        "--env",
        "HOME=/tmp",
        "--env",
        f"JOBS={jobs}",
        "--env",
        f"CLEAN_BUILD={1 if clean else 0}",
    ]
    if variant.get("fuse"):
        command += [
            "--cap-add",
            "SYS_ADMIN",
            "--device",
            "/dev/fuse",
            "--security-opt",
            "apparmor:unconfined",
        ]
    command += [
        "-v",
        f"{root}:/project/source",
        "-v",
        f"{build_dir}:/project/build",
        image,
        build_type,
    ]
    return command


def run_hints(build_dir: Path) -> list[str]:
    hints = []
    appimages = sorted(build_dir.glob("*.AppImage"))
    if appimages:
        hints.append(f"AppImage: {appimages[0]}")
        hints.append(f"Run:      {appimages[0]}  (or: run-qgc5)")
        return hints
    appdir_run = build_dir / "AppDir" / "AppRun"
    if appdir_run.is_file():
        hints.append(f"Run:      {appdir_run}  (or: run-qgc5)")
        return hints
    app_run = build_dir / "AppRun"
    if app_run.is_file() and (build_dir / "usr/bin").is_dir():
        hints.append(f"Run:      {app_run}  (or: run-qgc5)")
        return hints
    return hints


def image_exists(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run(command: list[str]) -> None:
    try:
        result = subprocess.run(command, check=False)
    except OSError as error:
        raise BuildError(f"failed to run {command[0]}: {error}") from error
    if result.returncode != 0:
        raise BuildError(f"{command[0]} failed with exit code {result.returncode}")


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = Parser(
        prog="build-qgc5",
        description="Build a QGroundControl 5 checkout inside Docker.",
        add_help=False,
    )
    parser.add_argument("root", nargs="?", help="QGroundControl 5 checkout")
    parser.add_argument("--root", dest="root_option", help=argparse.SUPPRESS)
    parser.add_argument("-b", "--build-type", default="Release", choices=BUILD_TYPES)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("-j", "--jobs", type=int)
    parser.add_argument("--build-dir")
    parser.add_argument("--image")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--rebuild-image", action="store_true")
    parser.add_argument("--list-variants", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args(argv)

    if args.root and args.root_option:
        raise UsageError("pass the checkout either positionally or with --root, not both")
    args.root = args.root_option or args.root
    if args.jobs is not None and args.jobs < 1:
        raise UsageError("--jobs must be a positive integer")
    return args


def describe_variants(variants: dict[str, dict]) -> str:
    lines = []
    for variant_id in sorted(variants):
        variant = variants[variant_id]
        lines.append(
            f"{variant_id:14} target={variant['target']:12} image={variant['image']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except UsageError as error:
        print(f"build-qgc5: {error}", file=sys.stderr)
        print("Try 'build-qgc5 --help' for usage.", file=sys.stderr)
        return 2

    if args.help:
        print(usage_text(), end="")
        return 0

    try:
        root = resolve_root(args.root)
        variants = load_variants(root)

        if args.list_variants:
            print(describe_variants(variants))
            return 0

        variant = variants.get(args.variant)
        if variant is None:
            raise UsageError(
                f"unknown variant '{args.variant}'; choose from: "
                f"{', '.join(sorted(variants))}"
            )

        if shutil.which("docker") is None:
            raise BuildError("docker is not installed or not on PATH")

        image = args.image or str(variant["image"])
        build_dir = (
            Path(args.build_dir).expanduser().resolve()
            if args.build_dir
            else default_build_dir(root, args.variant)
        )
        jobs = args.jobs or default_jobs()

        if args.clean and build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        if args.rebuild_image or not image_exists(image):
            action = "Rebuilding" if args.rebuild_image else "Building"
            print(
                f"[build-qgc5] {action} image {image} "
                f"(target {variant['target']})",
                flush=True,
            )
            run(build_image_command(root, variant, image, rebuild=args.rebuild_image))

        print(f"[build-qgc5] source:     {root}")
        print(f"[build-qgc5] variant:    {args.variant}")
        print(f"[build-qgc5] build type: {args.build_type}")
        print(f"[build-qgc5] build dir:  {build_dir}")
        print(f"[build-qgc5] jobs:       {jobs}", flush=True)

        run(
            run_build_command(
                root,
                build_dir,
                variant,
                image,
                args.build_type,
                jobs,
                clean=args.clean,
            )
        )
        print(f"[build-qgc5] Build complete: {build_dir}")
        for hint in run_hints(build_dir):
            print(f"[build-qgc5] {hint}")
        return 0
    except UsageError as error:
        print(f"build-qgc5: {error}", file=sys.stderr)
        return 2
    except BuildError as error:
        print(f"build-qgc5: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
