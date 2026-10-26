#!/usr/bin/env python3
"""Focused unit tests for APK inspection helpers."""

import importlib.util
import os
import tempfile
import unittest
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "run_apk_on_avd", os.path.join(HERE, "run_apk_on_avd.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ApkInspection(unittest.TestCase):
    def test_apk_package_name_uses_apkanalyzer(self):
        completed = MODULE.subprocess.CompletedProcess([], 0, "org.mavlink.qgroundcontrol\n", "")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed) as command:
            self.assertEqual(MODULE.apk_package_name("apkanalyzer", "app.apk"),
                             "org.mavlink.qgroundcontrol")
        self.assertEqual(command.call_args.args[0],
                         ["apkanalyzer", "manifest", "application-id", "app.apk"])

    def test_apk_package_name_rejects_invalid_output(self):
        completed = MODULE.subprocess.CompletedProcess([], 0, "not a package\n", "")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
            with self.assertRaises(RuntimeError):
                MODULE.apk_package_name("apkanalyzer", "app.apk")

    def test_apk_package_name_falls_back_to_manifest(self):
        failed = MODULE.subprocess.CompletedProcess([], 1, "", "Cannot locate latest build tools")
        with mock.patch.object(MODULE.subprocess, "run", return_value=failed):
            with mock.patch.object(MODULE, "apk_manifest_package",
                                   return_value="Aiseed.GCS"):
                self.assertEqual(MODULE.apk_package_name("apkanalyzer", "app.apk"),
                                 "Aiseed.GCS")

    def test_apk_abis_lists_native_directories(self):
        with tempfile.NamedTemporaryFile(suffix=".apk") as handle:
            with zipfile.ZipFile(handle.name, "w") as archive:
                archive.writestr("lib/x86_64/libfoo.so", b"")
                archive.writestr("lib/arm64-v8a/libfoo.so", b"")
                archive.writestr("classes.dex", b"")
            self.assertEqual(MODULE.apk_abis(handle.name), ["arm64-v8a", "x86_64"])

    def test_apk_abis_ignores_broken_apk(self):
        with tempfile.NamedTemporaryFile(suffix=".apk") as handle:
            handle.write(b"not a zip")
            handle.flush()
            self.assertEqual(MODULE.apk_abis(handle.name), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
