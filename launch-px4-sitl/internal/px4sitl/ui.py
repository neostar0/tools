"""Console output helpers."""

from __future__ import annotations

import sys


def log(message: str) -> None:
    print(f"[launch-px4-sitl] {message}", flush=True)


def err(message: str) -> None:
    print(f"[launch-px4-sitl] ERROR: {message}", file=sys.stderr, flush=True)
