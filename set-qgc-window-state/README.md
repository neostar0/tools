# Set the QGroundControl Window State

QGC-specific entry point: maximize a running QGroundControl window,
restore it to its normal size, or show it maximized with no title bar.
It fixes the target process name to `QGroundControl` and delegates
every detail to the sibling `set-window-state` tool — read that tool's
README for the behaviour, the guarantees and the failure modes. They
are identical here, except that a QGC with no window is a failure, not
a success.

## Command Line

Windows:

```cmd
set-qgc-window-state.cmd max      REM maximize, standard title bar
set-qgc-window-state.cmd restore  REM normal size, title bar back
set-qgc-window-state.cmd full     REM maximize with the title bar hidden
```

Linux:

```bash
./set-qgc-window-state.sh max      # maximize, standard title bar
./set-qgc-window-state.sh restore  # normal size, title bar back
./set-qgc-window-state.sh full     # maximize with the title bar hidden
```

Exactly one lowercase argument is required. Run the entry without
arguments for the full usage screen; on Linux `--help` also prints it
and exits `0`.

On Linux the window title is not used for matching. Branded builds may
show a different title (or change it at runtime); the wrapper always
targets windows owned by the `QGroundControl` process.

## Exit codes

Same as `set-window-state`: `0` = every QGC window reached the
requested state, `1` = no QGC window found / unsupported host / missing
Linux display or tool / a window refused the change, `2` = bad usage
(the entry prints the full syntax).

## Requirements

- The `set-window-state` folder next to this one: the Windows entry
  calls `..\set-window-state\set-window-state.cmd`, the Linux entry
  calls `../set-window-state/set-window-state.sh`. If it is not there,
  the entry exits non-zero with the shell's "not found" error.
- Windows 10/11 with the built-in Windows PowerShell, used through
  `set-window-state` — see that README for the exact error text.
- Linux with `python3`, `wmctrl`, `xprop` (`x11-utils`) and an
  X11/XWayland display. Native Wayland QGC windows are not visible to
  `wmctrl`; the entry then reports no QGC window found.

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
