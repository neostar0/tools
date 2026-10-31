#!/usr/bin/env python3
"""Set the EWMH window state of every window of a running process.

Linux implementation of set-window-state. The tool is application
agnostic: the caller supplies the exact process name and the requested
state. Windows are found through wmctrl, changed through wmctrl's
_NET_WM_STATE request and verified through xprop. Both are X11/XWayland
tools; native Wayland windows are not visible to them.
"""
import os
import shutil
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
USAGE = os.path.join(HERE, "usage.md")

STATES = ("max", "restore", "full")
REPORTED = {
    "max": "maximized",
    "restore": "restored",
    "full": "borderless fullscreen",
}

POLL_SECONDS = 0.05
VERIFY_TIMEOUT_SECONDS = 3.0

FULLSCREEN = "fullscreen"
MAXIMIZED = ("maximized_vert", "maximized_horz")
ATOM_PREFIX = "_NET_WM_STATE_"


def print_usage():
    with open(USAGE, encoding="utf-8") as fh:
        sys.stdout.write(fh.read())


def fail(message):
    sys.stderr.write("[FAIL] %s\n" % message)


def run(command):
    return subprocess.run(
        command, capture_output=True, text=True, timeout=15
    )


def process_names(pid):
    """Return the names that identify a process, exactly as Linux has them.

    /proc/<pid>/comm is the kernel's process name (possibly truncated to
    15 characters); /proc/<pid>/exe is the executable image. A caller
    may pass either. Nothing is shortened, completed or case-folded.
    """
    names = set()

    try:
        exe = os.readlink("/proc/%d/exe" % pid)
        if exe.endswith(" (deleted)"):
            exe = exe[: -len(" (deleted)")]
        base = os.path.basename(exe)
        if base:
            names.add(base)
    except OSError:
        pass

    try:
        with open("/proc/%d/comm" % pid, encoding="utf-8",
                  errors="replace") as fh:
            comm = fh.read().strip()
        if comm:
            names.add(comm)
    except OSError:
        pass

    return names


def list_windows(wmctrl):
    """Yield (window id, pid, title) for managed windows with a title."""
    result = run([wmctrl, "-l", "-p"])
    if result.returncode != 0:
        raise RuntimeError(
            "wmctrl -l -p failed: %s"
            % (result.stderr.strip() or "exit %d" % result.returncode)
        )

    seen = set()
    windows = []

    for line in result.stdout.splitlines():
        # ID, desktop, PID, client machine, title (may contain spaces).
        fields = line.split(None, 4)
        if len(fields) < 5:
            continue

        window_id, _desktop, pid_text, _host, title = fields
        if window_id in seen or not title.strip():
            continue

        try:
            pid = int(pid_text)
        except ValueError:
            continue

        seen.add(window_id)
        windows.append((window_id, pid, title))

    return windows


def read_states(xprop, window_id):
    """Read the EWMH state atoms of one window."""
    result = run([xprop, "-id", window_id, "_NET_WM_STATE"])
    if result.returncode != 0:
        raise RuntimeError(
            "xprop failed for window %s: %s"
            % (window_id, result.stderr.strip() or "exit %d" % result.returncode)
        )

    text = result.stdout
    return {
        name
        for name in (FULLSCREEN,) + MAXIMIZED
        if ATOM_PREFIX + name.upper() in text
    }


def matches(state, atoms):
    has_fullscreen = FULLSCREEN in atoms
    has_maximized = all(name in atoms for name in MAXIMIZED)

    if state == "max":
        return has_maximized and not has_fullscreen
    if state == "restore":
        return not has_maximized and not has_fullscreen
    return has_fullscreen


def request(wmctrl, window_id, action, properties):
    spec = "%s,%s" % (action, ",".join(properties))
    result = run([wmctrl, "-i", "-r", window_id, "-b", spec])
    if result.returncode != 0:
        raise RuntimeError(
            "wmctrl -b %s failed for window %s: %s"
            % (spec, window_id,
               result.stderr.strip() or "exit %d" % result.returncode)
        )


def apply_state(wmctrl, xprop, window_id, state):
    atoms = read_states(xprop, window_id)
    if matches(state, atoms):
        return

    if state == "max":
        # Leave fullscreen first: a fullscreen window that is simply
        # maximized underneath would still cover the screen.
        request(wmctrl, window_id, "remove", [FULLSCREEN])
        request(wmctrl, window_id, "add", list(MAXIMIZED))
    elif state == "restore":
        request(wmctrl, window_id, "remove", [FULLSCREEN])
        request(wmctrl, window_id, "remove", list(MAXIMIZED))
    else:
        # Maximize before fullscreen, mirroring the Windows behaviour:
        # leaving fullscreen returns to the maximized window, and the
        # following restore can hand back the pre-max size. Fullscreen
        # alone would be enough to cover the monitor, but the retained
        # maximized state is what keeps full reversible.
        request(wmctrl, window_id, "add", list(MAXIMIZED))
        request(wmctrl, window_id, "add", [FULLSCREEN])

    deadline = time.monotonic() + VERIFY_TIMEOUT_SECONDS
    while True:
        atoms = read_states(xprop, window_id)
        if matches(state, atoms):
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(POLL_SECONDS)

    raise RuntimeError(
        "window %s did not reach state '%s' (EWMH states: %s)"
        % (window_id, state, ", ".join(sorted(atoms)) or "none")
    )


def main(argv):
    if len(argv) != 2 or not argv[0] or argv[1] not in STATES:
        print_usage()
        return 2

    process_name, state = argv

    if sys.platform != "linux":
        fail("set-window-state is Linux only.")
        return 1

    if not os.environ.get("DISPLAY"):
        fail("no X display: DISPLAY is not set (wmctrl needs X11/XWayland).")
        return 1

    wmctrl = shutil.which("wmctrl")
    if wmctrl is None:
        fail("wmctrl is required (install it with: sudo apt install wmctrl).")
        return 1

    xprop = shutil.which("xprop")
    if xprop is None:
        fail("xprop is required (install it with: sudo apt install x11-utils).")
        return 1

    try:
        targets = [
            (window_id, title, pid)
            for window_id, pid, title in list_windows(wmctrl)
            if process_name in process_names(pid)
        ]
    except Exception as exc:
        fail(str(exc))
        traceback.print_exc(file=sys.stderr)
        return 1

    if not targets:
        fail("no window found for process %s." % process_name)
        return 1

    failed = 0
    for window_id, title, _pid in targets:
        try:
            apply_state(wmctrl, xprop, window_id, state)
        except Exception as exc:
            failed += 1
            fail("window %s (%s): %s" % (window_id, title, exc))
            traceback.print_exc(file=sys.stderr)

    if failed:
        fail(
            "%s: %d of %d window(s) did not reach the requested state."
            % (state, failed, len(targets))
        )
        return 1

    sys.stdout.write(
        "[OK] %s: %d window(s) %s.\n"
        % (state, len(targets), REPORTED[state])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
