#!/usr/bin/env python3
"""Tests for the set-qgc-window-state entries.

The wrapper contains no window logic: these tests cover its argument
surface and the delegation contract. Window behaviour belongs to the
sibling set-window-state tool and is tested there.

Direct:   python3 internal/test_qgc_window_state.py
Discover: python3 -m unittest discover set-qgc-window-state/internal -v
"""
import os
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
SH_ENTRY = os.path.join(TOOL, "set-qgc-window-state.sh")
CMD_ENTRY = os.path.join(TOOL, "set-qgc-window-state.cmd")
NOTES = os.path.join(HERE, "NOTES.md")


def run_sh(args):
    return subprocess.run(
        [SH_ENTRY] + list(args), capture_output=True, text=True, timeout=60
    )


class ShellEntry(unittest.TestCase):

    def test_help_prints_usage(self):
        r = run_sh(["--help"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_no_arguments_prints_usage(self):
        r = run_sh([])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_two_arguments_are_rejected(self):
        r = run_sh(["max", "restore"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_unknown_state_is_rejected(self):
        r = run_sh(["toggle"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_uppercase_state_is_not_rewritten(self):
        r = run_sh(["MAX"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_shell_entry_is_lf_and_resolves_symlinks(self):
        with open(SH_ENTRY, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('BASH_SOURCE[0]', text)
        with open(SH_ENTRY, "rb") as fh:
            self.assertNotIn(b"\r\n", fh.read())

    def test_shell_entry_delegates_to_the_generic_linux_tool(self):
        with open(SH_ENTRY, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("QGroundControl", text)
        self.assertIn("../set-window-state/set-window-state.sh", text)
        self.assertIn("exec ", text)


class WindowsEntry(unittest.TestCase):

    def test_cmd_entry_delegates_to_the_generic_windows_tool(self):
        with open(CMD_ENTRY, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("QGroundControl", text)
        self.assertIn(r"..\set-window-state\set-window-state.cmd", text)
        self.assertIn("exit /b %ERRORLEVEL%", text)

    def test_cmd_entry_uses_the_shared_usage_screen(self):
        with open(CMD_ENTRY, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("usage.md", text)
        self.assertIn("pause", text)


class Docs(unittest.TestCase):

    def test_notes_pointer_resolves(self):
        self.assertTrue(os.path.exists(NOTES))
        with open(os.path.join(TOOL, "README.md"), encoding="utf-8") as fh:
            self.assertIn("internal/NOTES.md", fh.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
