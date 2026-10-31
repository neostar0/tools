#!/usr/bin/env python3
"""Tests for the Linux set-window-state entry.

The state tests replace wmctrl and xprop with fakes on PATH and use the
test process itself as the target window owner. They never touch a real
window or need an X display.

Direct:   python3 internal/test_window_state_linux.py
Discover: python3 -m unittest discover set-window-state/internal -v
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
IMPL = os.path.join(HERE, "window_state_linux.py")
ENTRY = os.path.join(TOOL, "set-window-state.sh")

FAKE_WMCTRL = """\
#!/usr/bin/env python3
import os
import sys

state_path = os.environ["FAKE_STATE"]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")


def load():
    try:
        with open(state_path, encoding="utf-8") as fh:
            return {line.strip() for line in fh if line.strip()}
    except FileNotFoundError:
        return set()


def save(states):
    with open(state_path, "w", encoding="utf-8") as fh:
        for state in sorted(states):
            fh.write(state + "\\n")


args = sys.argv[1:]
if args == ["-l", "-p"]:
    print("0x00100001 0 %s host Fake Window"
          % os.environ["FAKE_TARGET_PID"])
    raise SystemExit(0)

if "-b" in args:
    index = args.index("-b")
    try:
        spec = args[index + 1]
        action, *properties = spec.split(",")
        states = load()
        if action == "add":
            states.update(properties)
        elif action == "remove":
            states.difference_update(properties)
        elif action == "toggle":
            for prop in properties:
                if prop in states:
                    states.remove(prop)
                else:
                    states.add(prop)
        else:
            raise ValueError("unknown action " + action)
        save(states)
        raise SystemExit(0)
    except Exception as exc:
        sys.stderr.write("fake wmctrl: %s\\n" % exc)
        raise SystemExit(1)

sys.stderr.write("fake wmctrl: unsupported arguments %r\\n" % args)
raise SystemExit(1)
"""

FAKE_XPROP = """\
#!/usr/bin/env python3
import os
import sys

state_path = os.environ["FAKE_STATE"]
args = sys.argv[1:]

if len(args) >= 3 and args[0] == "-id" and args[2] == "_NET_WM_STATE":
    try:
        with open(state_path, encoding="utf-8") as fh:
            states = sorted(line.strip() for line in fh if line.strip())
    except FileNotFoundError:
        states = []
    if states:
        atoms = ", ".join(
            "_NET_WM_STATE_" + state.upper() for state in states)
        print("_NET_WM_STATE(ATOM) = " + atoms)
    else:
        print("_NET_WM_STATE:  not found.")
    raise SystemExit(0)

sys.stderr.write("fake xprop: unsupported arguments %r\\n" % args)
raise SystemExit(1)
"""


def write_executable(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, 0o755)


def run_entry(args, env=None):
    return subprocess.run(
        [ENTRY] + list(args),
        capture_output=True, text=True, timeout=60, env=env
    )


class EntryUsage(unittest.TestCase):

    def test_help_prints_usage(self):
        r = run_entry(["--help"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_no_arguments_prints_usage(self):
        r = run_entry([])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_missing_state_prints_usage(self):
        r = run_entry(["anything"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_unknown_state_prints_usage(self):
        r = run_entry(["anything", "toggle"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)

    def test_third_argument_is_rejected(self):
        r = run_entry(["anything", "max", "restore"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_empty_process_name_is_rejected(self):
        r = run_entry(["", "max"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_uppercase_state_is_not_rewritten(self):
        r = run_entry(["anything", "MAX"])
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Usage", r.stdout)


class FakeX11Case(unittest.TestCase):
    """Run the real Linux implementation against fake wmctrl/xprop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir)
        write_executable(os.path.join(bindir, "wmctrl"), FAKE_WMCTRL)
        write_executable(os.path.join(bindir, "xprop"), FAKE_XPROP)

        self.state_path = os.path.join(self.tmp.name, "state")
        self.log_path = os.path.join(self.tmp.name, "log")

        self.env = os.environ.copy()
        self.env["PATH"] = bindir + os.pathsep + self.env.get("PATH", "")
        self.env["DISPLAY"] = ":99"
        self.env["FAKE_STATE"] = self.state_path
        self.env["FAKE_LOG"] = self.log_path
        self.env["FAKE_TARGET_PID"] = str(os.getpid())

        target_exe = os.readlink("/proc/%d/exe" % os.getpid())
        self.process_name = os.path.basename(target_exe)

    def run_tool(self, *args, env=None):
        return subprocess.run(
            [sys.executable, IMPL] + list(args),
            capture_output=True, text=True, timeout=60,
            env=env if env is not None else self.env
        )

    def states(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                return {line.strip() for line in fh if line.strip()}
        except FileNotFoundError:
            return set()

    def log_lines(self):
        try:
            with open(self.log_path, encoding="utf-8") as fh:
                return fh.read().splitlines()
        except FileNotFoundError:
            return []

    def test_max_from_normal(self):
        r = self.run_tool(self.process_name, "max")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(
            self.states(), {"maximized_vert", "maximized_horz"}
        )
        self.assertIn("[OK] max: 1 window(s) maximized.", r.stdout)

    def test_restore_after_max(self):
        self.assertEqual(self.run_tool(self.process_name, "max").returncode, 0)
        r = self.run_tool(self.process_name, "restore")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.states(), set())
        self.assertIn("[OK] restore: 1 window(s) restored.", r.stdout)

    def test_full_sets_maximized_and_fullscreen(self):
        r = self.run_tool(self.process_name, "full")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(
            self.states(),
            {"maximized_vert", "maximized_horz", "fullscreen"},
        )
        self.assertIn("[OK] full: 1 window(s) borderless fullscreen.", r.stdout)

    def test_restore_after_full_clears_every_state(self):
        self.assertEqual(self.run_tool(self.process_name, "full").returncode, 0)
        r = self.run_tool(self.process_name, "restore")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.states(), set())

    def test_max_clears_fullscreen(self):
        self.assertEqual(self.run_tool(self.process_name, "full").returncode, 0)
        r = self.run_tool(self.process_name, "max")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(
            self.states(), {"maximized_vert", "maximized_horz"}
        )

    def test_repeating_the_same_state_sends_no_change_request(self):
        self.assertEqual(self.run_tool(self.process_name, "max").returncode, 0)
        before = len(self.log_lines())
        r = self.run_tool(self.process_name, "max")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        changes = [line for line in self.log_lines()[before:]
                   if " -b " in " %s " % line]
        self.assertEqual(changes, [])

    def test_absent_process_exits_1(self):
        r = self.run_tool("definitely-not-a-running-process", "max")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(
            "[FAIL] no window found for process "
            "definitely-not-a-running-process.",
            r.stderr,
        )

    def test_missing_display_exits_1(self):
        env = dict(self.env)
        env.pop("DISPLAY", None)
        r = self.run_tool(self.process_name, "max", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("DISPLAY", r.stderr)

    def test_missing_wmctrl_exits_1(self):
        env = dict(self.env)
        env["PATH"] = self.tmp.name
        r = self.run_tool(self.process_name, "max", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("wmctrl is required", r.stderr)


class SourceLayout(unittest.TestCase):

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_implementation_uses_wmctrl_and_verifies_with_xprop(self):
        text = self.read(IMPL)
        self.assertIn('"wmctrl"', text)
        self.assertIn('"xprop"', text)
        self.assertIn("_NET_WM_STATE", text)
        self.assertIn("VERIFY_TIMEOUT_SECONDS", text)

    def test_implementation_never_activates_a_window(self):
        text = self.read(IMPL)
        self.assertNotIn('"-a"', text)
        self.assertNotIn("'-a'", text)

    def test_implementation_matches_proc_exe_and_comm(self):
        text = self.read(IMPL)
        self.assertIn("/proc/%d/exe", text)
        self.assertIn("/proc/%d/comm", text)

    def test_linux_guard_exists(self):
        self.assertIn("Linux only", self.read(IMPL))

    def test_shell_entry_resolves_symlinks_and_uses_lf(self):
        self.assertIn('BASH_SOURCE[0]', self.read(ENTRY))
        with open(ENTRY, "rb") as fh:
            data = fh.read()
        self.assertNotIn(b"\r\n", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
