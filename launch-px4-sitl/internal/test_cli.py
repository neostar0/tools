#!/usr/bin/env python3
"""CLI tests: exercise the real entry point as a subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRY = HERE / "launch_px4_sitl.py"
sys.path.insert(0, str(HERE))

from px4sitl.resolve import expand_path  # noqa: E402


def run(args, xdg=None, env_extra=None):
    env = dict(os.environ)
    env.pop("XDG_CONFIG_HOME", None)
    tmp = None
    if xdg is None:
        tmp = tempfile.TemporaryDirectory()
        xdg = tmp.name
    env["XDG_CONFIG_HOME"] = xdg
    if env_extra:
        env.update(env_extra)
    try:
        return subprocess.run(
            [sys.executable, str(ENTRY)] + args,
            capture_output=True, text=True, timeout=60, env=env, cwd=str(HERE),
        )
    finally:
        if tmp is not None:
            tmp.cleanup()


class HelpAndUsage(unittest.TestCase):

    def test_help_exits_zero_and_prints_usage(self):
        r = run(["--help"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_unknown_option_is_usage_error(self):
        self.assertEqual(run(["--bogus"]).returncode, 2)

    def test_missing_option_value_is_usage_error(self):
        self.assertEqual(run(["--root"]).returncode, 2)

    def test_unsupported_sim_is_usage_error(self):
        self.assertEqual(run(["--sim", "boat"]).returncode, 2)


class PathPersistence(unittest.TestCase):

    def test_set_and_print_path(self):
        with tempfile.TemporaryDirectory() as xdg:
            r = run(["--set-path", "/tmp/px4-checkout"], xdg=xdg)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = run(["--print-path"], xdg=xdg)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.strip(), "/tmp/px4-checkout")

    def test_print_path_is_empty_when_unset(self):
        r = run(["--print-path"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_set_path_preserves_branch(self):
        with tempfile.TemporaryDirectory() as xdg:
            run(["--set-path", "/a"], xdg=xdg)
            cfg = Path(xdg) / "launch-px4-sitl" / "config"
            with cfg.open("a", encoding="utf-8") as fh:
                fh.write("PX4_BRANCH=v1.0.0\n")
            run(["--set-path", "/b"], xdg=xdg)
            text = cfg.read_text(encoding="utf-8")
            self.assertIn("PX4_ROOT=/b", text)
            self.assertIn("PX4_BRANCH=v1.0.0", text)
            self.assertNotIn("PX4_ROOT=/a", text)


class ExpandPathTests(unittest.TestCase):
    """Regression: '~/x' must not be treated as a relative path."""

    def test_tilde_expands_to_home(self):
        self.assertEqual(expand_path("~/my-px4"), Path.home() / "my-px4")

    def test_tilde_subdir_expands(self):
        self.assertEqual(
            expand_path("~/Codes/@PX4/PX4-Autopilot_git"),
            Path.home() / "Codes" / "@PX4" / "PX4-Autopilot_git",
        )

    def test_result_is_always_absolute(self):
        self.assertTrue(expand_path("relative/dir").is_absolute())
        self.assertTrue(expand_path("~/x").is_absolute())

    def test_env_var_expansion(self):
        os.environ["PX4_TEST_VAR"] = "/opt/px4"
        try:
            self.assertEqual(expand_path("$PX4_TEST_VAR/x"), Path("/opt/px4/x"))
        finally:
            del os.environ["PX4_TEST_VAR"]

    def test_absolute_unchanged(self):
        self.assertEqual(expand_path("/projects/PX4-Autopilot"), Path("/projects/PX4-Autopilot"))


class SetPathExpandsTilde(unittest.TestCase):

    def test_set_path_stores_expanded_home(self):
        with tempfile.TemporaryDirectory() as xdg:
            r = run(["--set-path", "~/my-px4"], xdg=xdg)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = run(["--print-path"], xdg=xdg)
            self.assertEqual(r.stdout.strip(), str(Path.home() / "my-px4"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
