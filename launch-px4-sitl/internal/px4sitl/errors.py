"""Exit codes and the operational error type."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    FAILED = 1
    USAGE = 2


class SiteError(Exception):
    """An operational failure that maps to a specific process exit code."""

    def __init__(self, message: str, code: ExitCode = ExitCode.FAILED) -> None:
        super().__init__(message)
        self.code = code
