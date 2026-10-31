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

from launch_qgc import (
    detect_os,
    find_qgc_executable,
    setup_log_categories,
    available_log_path,
    is_qgc_root,
    resolve_qgc_root,
)

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch_qgc.py")


def make_qgc_root(root: Path) -> Path:
    """Add the marker files that identify a QGroundControl checkout."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "qgroundcontrol.pro").write_text("# test marker\n")
    return root


def make_fake_build(root: Path, output: str) -> Path:
    """Create an executable at the standard Linux build path."""
    staging = root / "build" / "staging"
    staging.mkdir(parents=True)
    exe = staging / "QGroundControl"
    exe.write_text(f"#!/bin/sh\necho {output}\nexit 0\n")
    exe.chmod(0o755)
    return exe


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
            root = make_qgc_root(Path(tmpdir))
            result = subprocess.run(
                [sys.executable, SCRIPT, str(root), "--no-log-file"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("Could not find", result.stdout)

    def test_non_repo_directory_exits_1_with_hint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT, tmpdir, "--no-log-file"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("No QGroundControl repository found", result.stdout)
            self.assertIn("launch_qgc.py /path/to/GroundControlSystem_ui", result.stdout)

    def test_is_qgc_root_accepts_either_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertFalse(is_qgc_root(root))
            (root / "qgroundcontrol.qrc").write_text("")
            self.assertTrue(is_qgc_root(root))

    def test_resolve_qgc_root_walks_up_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = make_qgc_root(Path(tmpdir) / "GroundControlSystem_ui")
            nested = root / "src" / "api"
            nested.mkdir(parents=True)
            self.assertEqual(resolve_qgc_root(nested), root.resolve())

    def test_resolve_qgc_root_returns_none_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(resolve_qgc_root(Path(tmpdir)))

    @unittest.skipUnless(os.name == "posix", "fake executable is a shell script")
    def test_default_root_is_current_directory_not_sibling(self):
        """Running from repo B must launch B, never a sibling clone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_a = make_qgc_root(base / "GroundControlSystem_git")
            repo_b = make_qgc_root(base / "GroundControlSystem_ui")
            make_fake_build(repo_a, "RAN_REPO_A")
            make_fake_build(repo_b, "RAN_REPO_B")

            result = subprocess.run(
                [sys.executable, SCRIPT, "--no-log-file"],
                cwd=repo_b, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RAN_REPO_B", result.stdout)
            self.assertNotIn("RAN_REPO_A", result.stdout)

            result = subprocess.run(
                [sys.executable, SCRIPT, str(repo_a), "--no-log-file"],
                cwd=repo_b, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RAN_REPO_A", result.stdout)
            self.assertNotIn("RAN_REPO_B", result.stdout)

    def test_pause_flag_waits_for_enter_but_survives_closed_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT, tmpdir, "--no-log-file", "--pause"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Press Enter to close", result.stdout)


if __name__ == "__main__":
    unittest.main()