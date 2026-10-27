"""Thin subprocess helpers with uniform error reporting."""

from __future__ import annotations

import subprocess
from typing import Sequence

from .errors import SiteError


def run(cmd: Sequence[str], *, capture: bool = False, check: bool = True) -> str:
    """Run a command; return stdout when ``capture`` else an empty string."""
    try:
        if capture:
            completed = subprocess.run(
                list(cmd), check=check, capture_output=True, text=True
            )
            return completed.stdout
        subprocess.run(list(cmd), check=check)
        return ""
    except FileNotFoundError:
        raise SiteError(f"command not found: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        if check:
            raise SiteError(f"command failed (exit {exc.returncode}): {' '.join(cmd)}")
        return exc.stdout or ""
