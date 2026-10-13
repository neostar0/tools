# Set the QGroundControl Window State

QGC-specific entry point: maximize a running QGroundControl window,
restore it to its normal size, or show it maximized with no title bar.
It fixes the target process name to `QGroundControl` and delegates
every detail to the sibling `set-window-state` tool — read that
tool's README for the behaviour, the guarantees and the failure modes.
They are identical here, except that a QGC with no window is a
failure, not a success.

## Command Line

```cmd
set-qgc-window-state.cmd max      REM maximize, standard title bar
set-qgc-window-state.cmd restore  REM normal size, title bar back
set-qgc-window-state.cmd full     REM maximize with the title bar hidden
```

Exactly one lowercase argument is required. Run the entry without
arguments for the full usage screen.

## Exit codes

Same as `set-window-state`: `0` = every QGC window reached the
requested state, `1` = no QGC window found / non-Windows host / a
window refused the change, `2` = bad usage (the entry prints the full
syntax).

## Requirements

- The `set-window-state` folder next to this one: the entry calls
  `..\set-window-state\set-window-state.cmd`. If it is not there, cmd
  reports `The system cannot find the path specified.` and the entry
  exits non-zero.
- Windows 10/11 with the built-in Windows PowerShell, used through
  `set-window-state` — see that README for the exact error text.

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
