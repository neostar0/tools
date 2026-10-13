#!/usr/bin/env python3
"""Unit tests for qgc-launcher (standard library only)."""

import unittest
import sys
import os
import subprocess
import tempfile
from pathlib import Path

# Add internal to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from launch_qgc import detect_os, find_qgc_executable, setup_log_categories, available_log_path

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch_qgc.py")


class TestQGCLaucher(unittest.TestCase):

    def test_detect_os(self):
        os_type = detect_os()
        self.assertIn(os_type, ["windows", "linux", "macos", "unknown"])

    def test_setup_log_categories(self):
        cats = ["FactPanelControllerLog", "ParameterManagerLog"]
        result = setup_log_categories(cats)
        self.assertEqual(result, "FactPanelControllerLog=true ParameterManagerLog=true")

    def test_setup_log_categories_empty(self):
        result = setup_log_categories([])
        self.assertEqual(result, "")

    def test_find_qgc_executable_windows_debug(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            debug = root / "build" / "Desktop_Qt_5_15_2_MSVC2019_64bit-Debug" / "staging"
            debug.mkdir(parents=True)
            exe = debug / "QGroundControl.exe"
            exe.write_text("dummy")
            found = find_qgc_executable(root, "windows")
            self.assertEqual(found, exe)

    def test_find_qgc_executable_windows_release_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            release = root / "build" / "Desktop_Qt_5_15_2_MSVC2019_64bit-Release" / "staging"
            release.mkdir(parents=True)
            exe = release / "QGroundControl.exe"
            exe.write_text("dummy")
            found = find_qgc_executable(root, "windows")
            self.assertEqual(found, exe)

    def test_find_qgc_executable_linux(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            staging = root / "build" / "staging"
            staging.mkdir(parents=True)
            exe = staging / "QGroundControl"
            exe.write_text("dummy")
            exe.chmod(0o755)
            found = find_qgc_executable(root, "linux")
            self.assertEqual(found, exe)

    def test_find_qgc_executable_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            found = find_qgc_executable(root, "windows")
            self.assertIsNone(found)

    def test_find_qgc_executable_mac_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mac = root / "build" / "staging" / "QGroundControl.app" / "Contents" / "MacOS"
            mac.mkdir(parents=True)
            exe = mac / "QGroundControl"
            exe.write_text("dummy")
            exe.chmod(0o755)
            found = find_qgc_executable(root, "macos")
            self.assertEqual(found, exe)

    def test_available_log_path_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = available_log_path(Path(tmpdir), "2026_1009_120000")
            first.write_text("log")
            second = available_log_path(Path(tmpdir), "2026_1009_120000")
            self.assertNotEqual(first, second)
            self.assertTrue(second.name.endswith("_1.log"))

    def test_missing_executable_exits_1_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT, tmpdir, "--no-log-file"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("Could not find", result.stdout)

    def test_pause_flag_waits_for_enter_but_survives_closed_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT, tmpdir, "--no-log-file", "--pause"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Press Enter to close", result.stdout)


if __name__ == "__main__":
    unittest.main()