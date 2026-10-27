"""Cloning PX4 and resolving the latest release tag."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional

from . import process
from .settings import RELEASES_API, REPO_URL

ENV_RELEASES_JSON = "LAUNCH_PX4_SITL_RELEASES_JSON"
_SEMVER = re.compile(r"v(\d+)\.(\d+)(?:\.(\d+))?")


def _tag_from_json(text: str) -> Optional[str]:
    try:
        tag = json.loads(text).get("tag_name")
    except json.JSONDecodeError:
        return None
    return str(tag) if tag else None


def _version_key(tag: str):
    match = _SEMVER.match(tag)
    if not match:
        return (0, 0, 0, tag)
    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch or 0), tag)


def _latest_tag_from_git() -> Optional[str]:
    try:
        out = process.run(
            ["git", "ls-remote", "--tags", "--refs", REPO_URL], capture=True
        )
    except Exception:
        return None
    tags = []
    for line in out.splitlines():
        ref = line.split("\t", 1)[-1]
        name = ref.rsplit("/", 1)[-1]
        if _SEMVER.match(name):
            tags.append(name)
    return max(tags, key=_version_key) if tags else None


def latest_release_tag(releases_json: Optional[Path] = None) -> Optional[str]:
    """Latest *stable* release tag.

    Order: canned JSON file (``releases_json`` or the ``LAUNCH_PX4_SITL_*
    RELEASES_JSON`` env var, for hermetic tests) -> GitHub API -> ``git
    ls-remote`` fallback. Returns ``None`` if nothing resolves.
    """
    path = releases_json
    if path is None and os.environ.get(ENV_RELEASES_JSON):
        path = Path(os.environ[ENV_RELEASES_JSON])

    if path is not None and path.is_file():
        try:
            tag = _tag_from_json(path.read_text(encoding="utf-8"))
        except OSError:
            tag = None
        if tag:
            return tag

    try:
        with urllib.request.urlopen(RELEASES_API, timeout=20) as response:
            tag = _tag_from_json(response.read().decode("utf-8"))
        if tag:
            return tag
    except Exception:
        pass

    return _latest_tag_from_git()


def clone(root: Path, branch: str) -> None:
    """Shallow-free recursive clone of ``REPO_URL`` at ``branch`` into ``root``."""
    root = Path(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    process.run(
        [
            "git", "clone", "--recurse-submodules",
            "--branch", branch, REPO_URL, str(root),
        ]
    )
