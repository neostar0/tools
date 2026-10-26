#!/usr/bin/env python3
"""Focused unit tests for the shared AVD core and CLI."""

import os
import tempfile
import unittest
from unittest import mock

import avd_core as MODULE


class Core(unittest.TestCase):
    def test_system_image_package(self):
        self.assertEqual(MODULE.system_image_package("35", "google_apis", "x86_64"),
                         "system-images;android-35;google_apis;x86_64")

    def test_serial_uses_requested_port(self):
        self.assertEqual(MODULE.serial_for(5556), "emulator-5556")

    def test_find_sdk_tool_uses_expected_layout(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "platform-tools")
            os.makedirs(path)
            tool = os.path.join(path, MODULE.executable("adb"))
            with open(tool, "w", encoding="utf-8") as output:
                output.write("#!/bin/sh\n")
            os.chmod(tool, 0o755)
            self.assertEqual(MODULE.find_sdk_tool(root, ("platform-tools", "adb")), tool)

    def test_archive_is_official_download(self):
        self.assertTrue(MODULE.command_line_tools_archive().startswith(
            "https://dl.google.com/android/repository/commandlinetools-"))

    def test_default_avd_name_tracks_abi(self):
        self.assertEqual(MODULE.default_avd_for("x86_64"), "s24-plus")
        self.assertEqual(MODULE.default_avd_for("arm64-v8a"), "s24-plus-arm64-v8a")

    def test_cross_architecture_guest_forces_software_emulation(self):
        with mock.patch.object(MODULE.platform, "machine", return_value="x86_64"):
            self.assertTrue(MODULE.guest_needs_software_emulation("arm64-v8a"))
            self.assertFalse(MODULE.guest_needs_software_emulation("x86_64"))
        with mock.patch.object(MODULE.platform, "machine", return_value="aarch64"):
            self.assertTrue(MODULE.guest_needs_software_emulation("x86_64"))
            self.assertFalse(MODULE.guest_needs_software_emulation("arm64-v8a"))

    def test_emulator_shows_window_unless_headless(self):
        with mock.patch.object(MODULE.subprocess, "Popen") as popen:
            MODULE.launch_emulator("emulator", "s24-plus", "1440x3120", 5554, False)
            visible = popen.call_args.args[0]
            MODULE.launch_emulator("emulator", "s24-plus", "1440x3120", 5554, False,
                                   headless=True)
            hidden = popen.call_args.args[0]
        self.assertNotIn("-no-window", visible)
        self.assertIn("-no-window", hidden)

    def test_emulator_uses_requested_scale(self):
        with mock.patch.object(MODULE.subprocess, "Popen") as popen:
            MODULE.launch_emulator("emulator", "s24-plus", "1440x3120", 5554, False,
                                   scale=0.5)
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index("-scale") + 1], "0.5")

    def test_emulator_uses_requested_gpu(self):
        with mock.patch.object(MODULE.subprocess, "Popen") as popen:
            MODULE.launch_emulator("emulator", "s24-plus", "1440x3120", 5554, False,
                                   gpu="guest")
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index("-gpu") + 1], "guest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
