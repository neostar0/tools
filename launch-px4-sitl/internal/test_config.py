#!/usr/bin/env python3
"""Unit tests for px4sitl.config.ConfigStore."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from px4sitl.config import ConfigStore  # noqa: E402


class ConfigStoreTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "config"
        self.store = ConfigStore(self.path)

    def test_get_is_none_when_missing(self):
        self.assertIsNone(self.store.get("PX4_ROOT"))

    def test_set_then_get(self):
        self.store.set("PX4_ROOT", "/tmp/px4")
        self.assertEqual(self.store.get("PX4_ROOT"), "/tmp/px4")

    def test_set_preserves_other_keys(self):
        self.store.set("PX4_ROOT", "/a")
        self.store.set("PX4_BRANCH", "v1.0.0")
        self.store.set("PX4_ROOT", "/b")
        self.assertEqual(self.store.get("PX4_ROOT"), "/b")
        self.assertEqual(self.store.get("PX4_BRANCH"), "v1.0.0")

    def test_value_may_contain_equals(self):
        self.store.set("PX4_ROOT", "/a=b=c")
        self.assertEqual(self.store.get("PX4_ROOT"), "/a=b=c")

    def test_comments_and_blank_lines_ignored(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("# comment\n\nPX4_ROOT=/x\n", encoding="utf-8")
        self.assertEqual(self.store.get("PX4_ROOT"), "/x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
