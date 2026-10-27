"""Persistent KEY=VALUE config store (XDG location from ``settings.config_dir``)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .settings import config_dir


class ConfigStore:
    """Reads/writes a flat ``KEY=VALUE`` file, preserving unrelated keys."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path if path is not None else config_dir() / "config"

    def read_all(self) -> Dict[str, str]:
        data: Dict[str, str] = {}
        if not self.path.is_file():
            return data
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value
        return data

    def get(self, key: str) -> Optional[str]:
        return self.read_all().get(key)

    def set(self, key: str, value: str) -> None:
        data = self.read_all()
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f"{k}={v}\n" for k, v in data.items())
        self.path.write_text(body, encoding="utf-8")
