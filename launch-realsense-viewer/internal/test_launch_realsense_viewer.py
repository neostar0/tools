#!/usr/bin/env python3
"""Focused unit tests for launch-realsense-viewer's installation helpers."""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "launch_realsense_viewer", os.path.join(HERE, "launch_realsense_viewer.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Detection(unittest.TestCase):
    def test_find_app_prefers_path(self):
        with mock.patch.object(MODULE.shutil, "which", return_value="/usr/bin/realsense-viewer"):
            self.assertEqual(MODULE.find_app(), "/usr/bin/realsense-viewer")

    def test_find_app_falls_back_to_prefix(self):
        with tempfile.TemporaryDirectory() as prefix:
            bindir = os.path.join(prefix, "bin")
            os.makedirs(bindir)
            app = os.path.join(bindir, "realsense-viewer")
            with open(app, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\n")
            os.chmod(app, 0o755)
            with mock.patch.object(MODULE.shutil, "which", return_value=None):
                self.assertEqual(MODULE.find_app(prefix), app)

    def test_find_app_returns_none_when_missing(self):
        with mock.patch.object(MODULE.shutil, "which", return_value=None):
            with mock.patch.object(MODULE, "is_executable", return_value=False):
                self.assertIsNone(MODULE.find_app())


class KernelSelection(unittest.TestCase):
    def test_old_focal_uses_legacy_script(self):
        self.assertEqual(MODULE.kernel_patch_script("focal", "5.4.0-150-generic"),
                         "scripts/patch-realsense-ubuntu-lts.sh")

    def test_focal_513_uses_hwe_script(self):
        self.assertEqual(MODULE.kernel_patch_script("focal", "5.13.0-1-generic"),
                         "scripts/patch-realsense-ubuntu-lts-hwe.sh")

    def test_jammy_and_noble_use_hwe_script(self):
        self.assertEqual(MODULE.kernel_patch_script("jammy", "5.15.0-139-generic"),
                         "scripts/patch-realsense-ubuntu-lts-hwe.sh")
        self.assertEqual(MODULE.kernel_patch_script("noble", "6.8.0-1-generic"),
                         "scripts/patch-realsense-ubuntu-lts-hwe.sh")


class Commands(unittest.TestCase):
    def test_cmake_configure_command(self):
        command = MODULE.cmake_configure_command("/src/librealsense", "/src/librealsense/build",
                                                 "/usr/local")
        self.assertEqual(command[:4], ["cmake", "-S", "/src/librealsense", "-B"])
        self.assertIn("-DCMAKE_BUILD_TYPE=Release", command)
        self.assertIn("-DBUILD_EXAMPLES=true", command)
        self.assertIn("-DCMAKE_INSTALL_PREFIX=/usr/local", command)
        self.assertNotIn("-DCMAKE_CXX_STANDARD_LIBRARIES=-lidn2", command)

    def test_cmake_configure_command_adds_libidn2_when_available(self):
        command = MODULE.cmake_configure_command("/src", "/src/build", "/usr/local", True)
        self.assertIn("-DCMAKE_CXX_STANDARD_LIBRARIES=-lidn2", command)

    def test_libidn2_available_uses_pkg_config(self):
        completed = MODULE.subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(MODULE.shutil, "which", return_value="/usr/bin/pkg-config"):
            with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
                self.assertTrue(MODULE.libidn2_available())
        completed = MODULE.subprocess.CompletedProcess([], 1, "", "")
        with mock.patch.object(MODULE.shutil, "which", return_value="/usr/bin/pkg-config"):
            with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
                self.assertFalse(MODULE.libidn2_available())

    def test_missing_dependencies_keeps_only_uninstalled(self):
        installed = {MODULE.DEPENDENCIES[0]}
        with mock.patch.object(MODULE, "package_installed",
                               side_effect=lambda name: name in installed):
            missing = MODULE.missing_dependencies()
        self.assertNotIn(MODULE.DEPENDENCIES[0], missing)
        self.assertIn(MODULE.DEPENDENCIES[1], missing)

    def test_apt_update_failure_does_not_abort_install(self):
        runner = mock.Mock()
        runner.run.return_value = MODULE.subprocess.CompletedProcess([], 100, "", "E: repo")
        with mock.patch.object(MODULE, "missing_dependencies", return_value=["libssl-dev"]):
            with contextlib.redirect_stderr(io.StringIO()):
                MODULE.install_dependencies(runner)
        runner.run.assert_called_once()
        runner.require.assert_called_once()

    def test_apt_install_failure_suggests_fixing_repositories(self):
        runner = mock.Mock()
        runner.run.return_value = MODULE.subprocess.CompletedProcess([], 100, "", "E: repo")
        runner.require.side_effect = MODULE.InstallError("command failed")
        with mock.patch.object(MODULE, "missing_dependencies", return_value=["libssl-dev"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(MODULE.InstallError, "Check the apt repositories"):
                    MODULE.install_dependencies(runner)

    def test_dry_run_runner_does_not_execute(self):
        runner = MODULE.Runner(dry_run=True)
        with mock.patch.object(MODULE.subprocess, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()):
                result = runner.run(["echo", "hello"])
        run.assert_not_called()
        self.assertEqual(result.returncode, 0)

    def test_parse_args_defaults_build_dir_from_source(self):
        args = MODULE.parse_args(["--source", "/tmp/realsense-src", "--jobs", "4"])
        self.assertEqual(args.build_dir, "/tmp/realsense-src/build")
        self.assertEqual(args.jobs, 4)

    def test_parse_args_defaults_to_two_jobs(self):
        self.assertEqual(MODULE.parse_args([]).jobs, 2)

    def test_make_shim_caps_jobs_without_dropping_options(self):
        with tempfile.TemporaryDirectory() as root:
            real_make = os.path.join(root, "real-make")
            with open(real_make, "w", encoding="utf-8") as handle:
                handle.write('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            os.chmod(real_make, 0o755)
            shim = MODULE.install_make_shim(root, 2, make_path=real_make)
            result = MODULE.subprocess.run([shim, "-j", "8", "-C", "src"],
                                           capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.splitlines(), ["-j2", "-C", "src"])

    def test_make_shim_keeps_option_after_bare_j(self):
        with tempfile.TemporaryDirectory() as root:
            real_make = os.path.join(root, "real-make")
            with open(real_make, "w", encoding="utf-8") as handle:
                handle.write('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            os.chmod(real_make, 0o755)
            shim = MODULE.install_make_shim(root, 2, make_path=real_make)
            result = MODULE.subprocess.run([shim, "-j", "-C", "src"],
                                           capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.splitlines(), ["-j2", "-C", "src"])

    def test_parse_args_strips_separator_from_app_args(self):
        args = MODULE.parse_args(["--dry-run", "--", "--help", "camera"])
        self.assertEqual(args.app_args, ["--help", "camera"])

    def test_parse_args_rejects_bad_jobs(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                MODULE.parse_args(["--jobs", "0"])


class MainFlow(unittest.TestCase):
    def test_check_returns_zero_when_installed(self):
        with mock.patch.object(MODULE, "find_app", return_value="/usr/local/bin/realsense-viewer"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(MODULE.main(["--check"]), 0)

    def test_check_returns_one_when_missing(self):
        with mock.patch.object(MODULE, "find_app", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(MODULE.main(["--check"]), 1)

    def test_dry_run_plans_without_writing(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "librealsense")
            build = os.path.join(root, "build")
            prefix = os.path.join(root, "prefix")
            output = io.StringIO()
            with mock.patch.object(MODULE, "find_app", return_value=None):
                with contextlib.redirect_stdout(output):
                    code = MODULE.main([
                        "--dry-run", "--source", source, "--build-dir", build,
                        "--prefix", prefix, "--skip-kernel-patch", "--skip-udev",
                    ])
            self.assertEqual(code, 0)
            self.assertIn("would clone", output.getvalue())
            self.assertIn("launching:", output.getvalue())
            self.assertFalse(os.path.exists(source))
            self.assertFalse(os.path.exists(build))
            self.assertFalse(os.path.exists(prefix))

    def test_existing_install_skips_build(self):
        output = io.StringIO()
        with mock.patch.object(MODULE, "find_app", return_value="/usr/local/bin/realsense-viewer"):
            with mock.patch.object(MODULE, "build_and_install") as build:
                with mock.patch.object(MODULE, "launch_app", return_value=0):
                    with contextlib.redirect_stdout(output):
                        code = MODULE.main([])
        self.assertEqual(code, 0)
        build.assert_not_called()
        self.assertIn("skipping installation", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
