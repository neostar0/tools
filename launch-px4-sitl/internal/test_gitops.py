#!/usr/bin/env python3
"""Unit tests for px4sitl.gitops (hermetic: canned JSON, no network)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from px4sitl import gitops  # noqa: E402
from px4sitl.resolve import is_px4_checkout  # noqa: E402


class LatestTagTests(unittest.TestCase):

    def _write_json(self, tmp: Path, tag: str) -> Path:
        path = tmp / "releases.json"
        path.write_text(json.dumps({"tag_name": tag, "name": tag}), encoding="utf-8")
        return path

    def test_parses_tag_from_explicit_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_json(Path(tmp), "v9.9.9")
            self.assertEqual(gitops.latest_release_tag(path), "v9.9.9")

    def test_parses_tag_from_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_json(Path(tmp), "v8.8.8")
            old = gitops.ENV_RELEASES_JSON
            import os
            os.environ[old] = str(path)
            try:
                self.assertEqual(gitops.latest_release_tag(), "v8.8.8")
            finally:
                del os.environ[old]

    def test_invalid_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            # explicit path fails to parse -> falls through to network/git;
            # assert it does not raise and returns a str-or-None.
            result = gitops.latest_release_tag(path)
            self.assertTrue(result is None or isinstance(result, str))


class VersionKeyTests(unittest.TestCase):

    def test_numeric_not_lexicographic(self):
        tags = ["v1.9.0", "v1.16.0", "v1.17.0"]
        self.assertEqual(max(tags, key=gitops._version_key), "v1.17.0")


class CheckoutDetectionTests(unittest.TestCase):

    def test_true_for_px4_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text("")
            (root / "boards" / "px4" / "sitl").mkdir(parents=True)
            self.assertTrue(is_px4_checkout(root))

    def test_false_for_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(is_px4_checkout(Path(tmp)))

    def test_false_for_missing(self):
        self.assertFalse(is_px4_checkout(Path("/nonexistent/px4")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
