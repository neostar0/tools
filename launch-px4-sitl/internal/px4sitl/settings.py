"""Constants and the settings dataclass shared across the package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_URL = "https://github.com/PX4/PX4-Autopilot.git"
RELEASES_API = "https://api.github.com/repos/PX4/PX4-Autopilot/releases/latest"

BOARD = "px4_sitl_default"
BIN_REL = Path("build") / BOARD / "bin" / "px4"
ROOTFS_REL = Path("build") / BOARD / "rootfs"
REQS_REL = Path("Tools") / "setup" / "requirements.txt"
VENV_DIR = ".venv"

SIMS = ("gz", "jmavsim")
DEFAULT_SIM = "gz"
DEFAULT_MODEL = "gz_x500"
DEFAULT_WORLD = "default"
DEFAULT_AUTOSTART = "10017"  # jmavsim_iris


def config_dir() -> Path:
    """XDG-style directory for the tool's persistent state."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "launch-px4-sitl"


@dataclass
class Settings:
    """Fully resolved options for one run."""

    root: Path
    branch: str | None = None
    sim: str = DEFAULT_SIM
    model: str = DEFAULT_MODEL
    world: str = DEFAULT_WORLD
    headless: bool = False
    rebuild: bool = False
    stop: bool = True
