#!/usr/bin/env python3
"""Smoke test for set-window-state's argument, platform and source paths.

Direct:   python3 internal/test_window_state.py
Discover: python3 -m unittest discover set-window-state/internal -v

Needs a PowerShell host (pwsh/powershell) for the script cases; skips
them when neither is on PATH. Never exercises max/restore against a live
window: those paths are verified by hand on Windows (internal/NOTES.md).
"""
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(HERE, "window_state.ps1")
ENTRY = os.path.join(HERE, "..", "set-window-state.cmd")

# Everything a user or an agent may read or run. The test module itself
# is excluded: it has to name the application prefix it forbids.
GENERIC_FILES = (
    "set-window-state.cmd",
    "README.md",
    os.path.join("internal", "usage.md"),
    os.path.join("internal", "NOTES.md"),
    os.path.join("internal", "window_state.ps1"),
    os.path.join("internal", "Native.cs"),
    os.path.join("internal", "WindowStateController.cs"),
)


def host():
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run(args):
    return subprocess.run(
        [host(), "-NoProfile", "-File", PS1] + args, capture_output=True, text=True, timeout=60
    )


@unittest.skipIf(host() is None, "no pwsh/powershell on PATH")
class UsageContract(unittest.TestCase):

    def test_missing_both_arguments_prints_usage(self):
        r = run([])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_missing_state_prints_usage(self):
        r = run(["notepad"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_unknown_state_prints_usage(self):
        r = run(["notepad", "toggle"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_third_argument_is_rejected(self):
        r = run(["notepad", "max", "restore"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_uppercase_state_is_not_rewritten(self):
        # README: anything other than max/restore/full exits 2 — no
        # case folding, no completion (LESSONS.md).
        r = run(["notepad", "MAX"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    @unittest.skipIf(os.name == "nt", "would touch a live window")
    def test_full_is_a_valid_argument(self):
        # Not usage (exit 2): full passes validation and dies on the
        # platform guard.
        r = run(["notepad", "full"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Windows only", r.stderr)

    @unittest.skipIf(os.name == "nt", "would touch a live window")
    def test_non_windows_host_exits_1(self):
        r = run(["notepad", "max"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Windows only", r.stderr)


class EntryContract(unittest.TestCase):
    """The entry is a launcher: it only makes the no-argument case
    double-clickable. Every real check lives in window_state.ps1
    (UsageContract above), the way md-table-aligner leaves argument
    handling to its internal script."""

    def read(self):
        with open(ENTRY, encoding="utf-8") as fh:
            return fh.read()

    def test_entry_prints_usage_for_a_double_click(self):
        text = self.read()
        self.assertIn('if "%~1"==""', text)
        self.assertIn("usage.md", text)
        self.assertIn("pause", text)

    def test_entry_passes_the_arguments_through_verbatim(self):
        # %* is passed untouched: the script decides what is valid, the
        # entry never rewrites or completes anything (LESSONS.md).
        text = self.read()
        self.assertIn("window_state.ps1\" %*", text)

    def test_entry_does_not_validate_the_arguments(self):
        # No duplicated state list here - window_state.ps1 owns it, and
        # a second copy would only drift apart from the first.
        text = self.read()
        self.assertNotIn('"%~2"=="max"', text)
        self.assertNotIn('"%~2"=="restore"', text)
        self.assertNotIn('"%~2"=="full"', text)
        self.assertNotIn('if not "%~3"==""', text)

    def test_entry_passes_exit_code_through(self):
        self.assertIn("exit /b %ERRORLEVEL%", self.read())


class SourceLayout(unittest.TestCase):
    """The Win32 helpers live in two .cs sources compiled in memory, and
    the tool stays application-agnostic."""

    def read(self, name):
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def test_both_sources_exist(self):
        for name in ("Native.cs", "WindowStateController.cs"):
            with self.subTest(source=name):
                self.assertTrue(os.path.exists(os.path.join(HERE, name)), name)

    def test_script_compiles_both_sources_in_one_add_type(self):
        text = self.read("window_state.ps1")
        self.assertIn("Native.cs", text)
        self.assertIn("WindowStateController.cs", text)
        # Two Add-Type calls would be two assemblies that cannot see
        # each other's types; the sources are concatenated instead.
        self.assertEqual(len(re.findall(r"^\s*Add-Type\b", text, re.M)), 1)

    def test_script_requires_a_process_name(self):
        # No default target: the generic tool must never guess which
        # application to touch.
        text = self.read("window_state.ps1")
        self.assertIn("[string]::IsNullOrEmpty($ProcessName)", text)
        self.assertNotIn("= 'QGroundControl'", text)

    def test_no_application_is_named_anywhere(self):
        # README: "the name you pass is matched literally". A hardcoded
        # application in this tool would be exactly the guess LESSONS.md
        # forbids, so none may exist - not in code, not in docs.
        for rel_path in GENERIC_FILES:
            with self.subTest(file=rel_path):
                path = os.path.join(HERE, "..", rel_path)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read().lower()
                self.assertNotIn("qgc", text)


class NormalRectangleContract(unittest.TestCase):
    """Regression notes for "full, then restore does not go back".

    The bug this guards: after ``full``, a following ``restore`` did not
    return the window to its previous size, and ``max`` -> ``full`` ->
    ``restore`` came back to the fullscreen rectangle instead of the
    size the window had *before* ``max`` -- which is the behaviour every
    other Windows app gets right.

    Root cause: Windows keeps one "normal rectangle" per window
    (``WINDOWPLACEMENT.rcNormalPosition``) -- the rectangle
    ``SW_RESTORE`` hands back. Resizing a window *while it is in its
    normal state* overwrites that rectangle with the new size; resizing
    it while it is maximized or minimized only replaces the maximized
    rectangle and leaves the normal one alone. The old ``full`` path
    restored the window first and then ``SetWindowPos``-ed it to the
    monitor rectangle, so the fullscreen rectangle became the new
    "normal" one and a later ``restore`` had nothing else to go back to.

    The fix (README: "full stays maximized while borderless, so the
    window's own normal size survives"): ``full`` maximizes first and
    only then resizes, so the pre-``full`` -- and pre-``max`` -- size
    survives inside the window itself. Nothing is written to disk; the
    window is the storage. Which is also why the verification must
    reject a borderless window that is *not* maximized: such a window
    has already lost that rectangle and reporting [OK] would hide it.

    These tests read the source: they pin the invariant that keeps the
    bug fixed. Moving a real window needs Windows and a live target,
    which no test here may touch (internal/NOTES.md).
    """

    def read(self, name):
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return fh.read()

    def full_path_body(self):
        source = self.read("WindowStateController.cs")
        start = source.index("private static void ApplyBorderlessFullscreen")
        return source[start : source.index("private static void Verify")]

    def test_full_path_never_restores_before_resizing(self):
        # Native.Show(hWnd, false) is the exact call that used to
        # destroy the normal rectangle: it put the window back into
        # its normal state right before the resize.
        self.assertNotIn("Native.Show(hWnd, false)", self.full_path_body())

    def test_full_path_maximizes_before_it_resizes(self):
        # Presence alone is not enough, the order is the fix: only
        # while the window is zoomed does the resize replace the
        # maximized rectangle instead of the normal one.
        body = self.full_path_body()
        self.assertIn("Native.Show(hWnd, true)", body)
        self.assertLess(
            body.index("Native.Show(hWnd, true)"),
            body.index("Native.SetFullBounds"),
        )

    def test_full_verification_rejects_a_non_maximized_window(self):
        # A borderless window that is not maximized has already lost
        # its normal rectangle, so it can never be restored again.
        # Verify must fail instead of reporting [OK].
        source = self.read("WindowStateController.cs")
        start = source.index("private static void Verify")
        body = source[start : source.index("private static void VerifyFullBounds")]

        self.assertIn("if (!Native.Zoomed(hWnd))", body)
        self.assertLess(
            body.index("if (!Native.Zoomed(hWnd))"),
            body.index("VerifyFullBounds(hWnd)"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
