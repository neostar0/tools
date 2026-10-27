"""Command-line interface and the top-level orchestration."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from . import builder, gitops, resolve, runner
from .config import ConfigStore
from .errors import ExitCode, SiteError
from .settings import DEFAULT_MODEL, DEFAULT_SIM, DEFAULT_WORLD, REPO_URL, SIMS
from .ui import err, log

KEY_BRANCH = "PX4_BRANCH"


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """argparse, but with a capitalised ``Usage:`` prefix."""

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = "Usage: "
        return super()._format_usage(usage, actions, groups, prefix)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch-px4-sitl",
        description=(
            "Resolve the PX4 checkout, clone it if missing, build SITL if "
            "needed, then launch the simulator."
        ),
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "--root", type=resolve.expand_path,
        help="PX4 checkout location (overrides and saves the stored path)",
    )
    parser.add_argument(
        "--set-path", type=resolve.expand_path, metavar="PATH",
        help="store the PX4 location and exit",
    )
    parser.add_argument(
        "--print-path", action="store_true",
        help="print the stored PX4 location and exit",
    )
    parser.add_argument(
        "--sim", choices=SIMS, default=DEFAULT_SIM,
        help="simulator to launch (default: %(default)s)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="vehicle model for gz (default: %(default)s)",
    )
    parser.add_argument(
        "--world", default=DEFAULT_WORLD,
        help="gz world (default: %(default)s)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="launch without the simulator GUI",
    )
    parser.add_argument(
        "--branch",
        help="branch/tag to clone (default: latest GitHub release)",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="build even if the binary already exists",
    )
    parser.add_argument(
        "--no-stop", action="store_true",
        help="do not stop a running PX4/Gazebo before launching",
    )
    parser.add_argument(
        "--_latest-tag", action="store_true", help=argparse.SUPPRESS,
    )
    return parser


def _ensure_checkout(root: Path, store: ConfigStore, branch_opt: Optional[str]) -> None:
    if resolve.is_px4_checkout(root):
        return

    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise SiteError(
            f"{root} exists but is not a PX4 checkout "
            "(needs CMakeLists.txt + boards/px4/sitl)"
        )

    branch = branch_opt or gitops.latest_release_tag()
    if not branch:
        raise SiteError("could not determine the latest PX4 release tag (network?)")

    log(f"cloning {REPO_URL} (branch: {branch})")
    gitops.clone(root, branch)
    store.set(KEY_BRANCH, branch)


def run(args: argparse.Namespace) -> int:
    store = ConfigStore()

    if args._latest_tag:
        print(gitops.latest_release_tag() or "")
        return int(ExitCode.OK)

    if args.print_path:
        print(store.get(resolve.KEY_ROOT) or "")
        return int(ExitCode.OK)

    if args.set_path is not None:
        store.set(resolve.KEY_ROOT, str(args.set_path))
        log(f"stored PX4_ROOT={args.set_path}")
        return int(ExitCode.OK)

    root = resolve.resolve_root(args.root, store)
    _ensure_checkout(root, store, args.branch)
    store.set(resolve.KEY_ROOT, str(root))

    if args.rebuild or not builder.is_built(root):
        builder.ensure_python_env(root)
        log("building px4_sitl_default (this can take a while)")
        builder.build(root)
    else:
        log("binary already present, skipping build")

    runner.launch(
        root,
        sim=args.sim,
        model=args.model,
        world=args.world,
        headless=args.headless,
        stop=not args.no_stop,
    )
    return int(ExitCode.OK)  # unreachable: launch() exec()s


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except SiteError as exc:
        err(str(exc))
        return int(exc.code)
    except KeyboardInterrupt:
        return 130
