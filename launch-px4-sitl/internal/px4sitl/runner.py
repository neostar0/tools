"""Stopping any stale instance and launching the SITL binary."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .errors import SiteError
from .settings import BIN_REL, DEFAULT_AUTOSTART, ROOTFS_REL
from .ui import log


def stop_existing() -> None:
    """Best-effort kill of a previously running PX4 / Gazebo."""
    for pattern in ("bin/px4", "gz sim"):
        subprocess.run(["pkill", "-9", "-f", pattern], capture_output=True)
    time.sleep(1)


def launch(
    root: Path,
    *,
    sim: str,
    model: str,
    world: str,
    headless: bool,
    stop: bool = True,
) -> None:
    """``exec`` the SITL binary with the right environment (never returns)."""
    root = Path(root)
    binary = root / BIN_REL
    rootfs = root / ROOTFS_REL

    if not os.access(binary, os.X_OK):
        raise SiteError(f"binary not found: {binary}")
    if not rootfs.is_dir():
        raise SiteError(f"rootfs not found: {rootfs}")
    if sim == "gz" and not shutil.which("gz"):
        raise SiteError("'gz' (Gazebo) not found on PATH")

    if stop:
        stop_existing()

    env = os.environ.copy()
    if sim == "gz":
        env["PX4_SIM_MODEL"] = model
        env["PX4_GZ_WORLD"] = world
        if headless:
            env["HEADLESS"] = "1"
    else:
        env["PX4_SYS_AUTOSTART"] = DEFAULT_AUTOSTART

    os.chdir(rootfs)
    log(f"launching (sim={sim} world={world} headless={headless})")
    # execve replaces this process; flush so buffered logs reach the terminal.
    sys.stdout.flush()
    sys.stderr.flush()
    os.execve(str(binary), [str(binary)], env)
