"""Locating (and prompting for) the PX4 checkout."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, Union

from .config import ConfigStore

InputFn = Callable[[str], str]
PathLike = Union[str, "os.PathLike[str]"]

KEY_ROOT = "PX4_ROOT"


def expand_path(value: PathLike) -> Path:
    """Expand ``~``/``$VAR`` and return an absolute, normalized ``Path``.

    ``pathlib`` alone leaves ``~/x`` as a *relative* path, which would otherwise
    be silently joined onto the current working directory.
    """
    return Path(os.path.abspath(os.path.expandvars(os.path.expanduser(os.fspath(value)))))


def is_px4_checkout(path: Path) -> bool:
    """True when ``path`` looks like a PX4-Autopilot source tree."""
    return (
        (path / "CMakeLists.txt").is_file()
        and (path / "boards" / "px4" / "sitl").is_dir()
    )


def detect_default() -> Path:
    """Best guess for an existing checkout, else a conventional clone target."""
    candidates = [
        Path.home() / "PX4-Autopilot",
        Path("/projects/PX4-Autopilot"),
        Path.cwd(),
    ]
    for candidate in candidates:
        if is_px4_checkout(candidate):
            return candidate
    return Path.home() / "PX4-Autopilot"


def resolve_root(
    override: Optional[PathLike],
    store: ConfigStore,
    input_fn: InputFn = input,
) -> Path:
    """Priority: explicit override > stored path > interactive prompt."""
    if override is not None:
        return expand_path(override)

    stored = store.get(KEY_ROOT)
    if stored:
        return expand_path(stored)

    default = detect_default()
    answer = input_fn(f"PX4 clone location [{default}]: ").strip()
    return expand_path(answer) if answer else default
