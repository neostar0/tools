"""Preparing the Python environment and building PX4 SITL."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import process
from .settings import BIN_REL, BOARD, REQS_REL, VENV_DIR


def venv_dir(root: Path) -> Path:
    return Path(root) / VENV_DIR


def venv_python(root: Path) -> Path:
    return venv_dir(root) / "bin" / "python"


def ensure_python_env(root: Path) -> Path:
    """Create a repo-local ``.venv`` and best-effort install PX4 requirements.

    Uses ``--system-site-packages`` so preinstalled dependencies are reused and
    the install stays fast; a failing individual requirement only warns.
    """
    root = Path(root)
    python = venv_python(root)
    if not python.is_file():
        process.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir(root))]
        )

    requirements = root / REQS_REL
    if requirements.is_file():
        try:
            subprocess.run(
                [str(python), "-m", "pip", "install", "--quiet", "-r", str(requirements)],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            print(
                "warning: some pip requirements failed, relying on system packages",
                file=sys.stderr,
            )
    return python


def binary_path(root: Path) -> Path:
    return Path(root) / BIN_REL


def is_built(root: Path) -> bool:
    return os.access(binary_path(root), os.X_OK)


def build(root: Path) -> None:
    process.run(["make", "-C", str(root), BOARD])
