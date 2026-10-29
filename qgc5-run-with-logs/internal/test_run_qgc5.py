#!/usr/bin/env python3
"""Unit tests for run_qgc5.py (stdlib only)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import run_qgc5 as tool


def make_qgc5(root: Path) -> Path:
    (root / "CMakeLists.txt").write_text("project(QGroundControl)\n", encoding="utf-8")
    docker_dir = root / "deploy/docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (docker_dir / "variants.json").write_text(
        json.dumps({"variants": [{"id": "ubuntu", "target": "linux", "image": "x"}]}),
        encoding="utf-8",
    )
    return root


class RootDetection(unittest.TestCase):
    def test_finds_qgc5_from_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            subdir = root / "src/Foo"
            subdir.mkdir(parents=True)
            self.assertEqual(tool.find_root(subdir), root.resolve())

    def test_rejects_qgc4_with_pointer_to_launch_qgc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "qgroundcontrol.pro").write_text("", encoding="utf-8")
            with self.assertRaises(tool.UsageError) as caught:
                tool.require_root(root)
            self.assertIn("launch-qgc", str(caught.exception))

    def test_rejects_unrelated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(tool.UsageError):
                tool.require_root(Path(tmp))


class ExecutableDetection(unittest.TestCase):
    def test_prefers_appimage_over_apprun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            appimage = build_dir / "QGroundControl-x86_64.AppImage"
            appimage.write_text("")
            os.chmod(appimage, 0o755)
            apprun = build_dir / "AppRun"
            apprun.write_text("")
            os.chmod(apprun, 0o755)
            self.assertEqual(tool.find_executable(build_dir), appimage.resolve())

    def test_uses_appdir_apprun_when_no_appimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            (build_dir / "AppDir").mkdir()
            apprun = build_dir / "AppDir" / "AppRun"
            apprun.write_text("")
            os.chmod(apprun, 0o755)
            self.assertEqual(tool.find_executable(build_dir), apprun.resolve())

    def test_uses_root_apprun_only_if_usr_bin_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            (build_dir / "usr/bin").mkdir(parents=True)
            apprun = build_dir / "AppRun"
            apprun.write_text("")
            os.chmod(apprun, 0o755)
            self.assertEqual(tool.find_executable(build_dir), apprun.resolve())

    def test_does_not_use_root_apprun_without_usr_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            apprun = build_dir / "AppRun"
            apprun.write_text("")
            os.chmod(apprun, 0o755)
            with self.assertRaises(tool.LaunchError):
                tool.find_executable(build_dir)

    def test_uses_explicit_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "QGroundControl"
            exe.write_text("")
            os.chmod(exe, 0o755)
            self.assertEqual(tool.find_executable(Path(tmp), str(exe)), exe.resolve())

    def test_rejects_non_executable_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "QGroundControl"
            exe.write_text("")
            os.chmod(exe, 0o644)
            with self.assertRaises(tool.UsageError):
                tool.find_executable(Path(tmp), str(exe))


class LoggingArgs(unittest.TestCase):
    def test_appends_log_flags(self) -> None:
        command = tool.build_command(Path("/tmp/qgc"), [], ["A", "B"])
        self.assertEqual(command[:1], ["/tmp/qgc"])
        self.assertIn("--log-output", command)
        self.assertIn("--logging", command)
        self.assertEqual(command[command.index("--logging") + 1], "A,B")

    def test_does_not_override_existing_log_flags(self) -> None:
        command = tool.build_command(Path("/tmp/qgc"), ["--logging", "X"], ["A"])
        self.assertNotIn("A", command)
        self.assertIn("X", command)
        self.assertIn("--log-output", command)

    def test_passes_qgc_args_after_flags(self) -> None:
        command = tool.build_command(Path("/tmp/qgc"), ["--fake-mobile"], ["A"])
        self.assertEqual(command[:1], ["/tmp/qgc"])
        self.assertIn("--fake-mobile", command)

    def test_normalize_categories_accepts_comma_list(self) -> None:
        self.assertEqual(
            tool.normalize_categories(["A,B", "C"]),
            ["A", "B", "C"],
        )

    def test_normalize_categories_rejects_empty(self) -> None:
        with self.assertRaises(tool.UsageError):
            tool.normalize_categories(["", " , "])


class ParseArgs(unittest.TestCase):
    def test_splits_qgc_args_after_dashdash(self) -> None:
        args = tool.parse_args(["/tmp/qgc", "--categories", "MAVLink", "--", "--unit-test"])
        self.assertEqual(args.root, "/tmp/qgc")
        self.assertEqual(args.categories, ["MAVLink"])
        self.assertEqual(args.qgc_args, ["--unit-test"])

    def test_default_categories(self) -> None:
        args = tool.parse_args([])
        self.assertEqual(list(args.categories), list(tool.DEFAULT_CATEGORIES))

    def test_help_is_captured(self) -> None:
        args = tool.parse_args(["--help"])
        self.assertTrue(args.help)


class CrashReport(unittest.TestCase):
    def test_formats_signalled_report(self) -> None:
        text = tool.format_crash_report(
            timestamp="2026_10_30_01_00_00",
            command=["/tmp/QGroundControl"],
            returncode=-11,
            log_path=Path("/tmp/qgc.log"),
            core_pattern="core",
        )
        self.assertIn("SIGSEGV", text)
        self.assertIn("qgc.log", text)
        self.assertIn("core", text)


class EntryPoints(unittest.TestCase):
    def test_help_prints_usage(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tool.main(["--help"]), 0)
        self.assertIn("Usage:", output.getvalue())

    def test_unknown_checkout_is_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(tool.main([tmp]), 2)
            self.assertIn("not a QGroundControl 5 checkout", errors.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
