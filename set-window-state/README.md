# Set the Window State of a Running Process

Maximize every window of a running process, restore them to their
normal size, or show them maximized with no title bar — without driving
the mouse or the keyboard. Use when a window must be shown full-screen,
when a maximized window has to go back to its previous size, or when
the title bar must not take space. A process with no window counts as a
failure, not a success.

Windows uses the Win32 API; Linux uses the window manager's EWMH state
through `wmctrl`. Both entries take the same arguments and return the
same exit codes.

## Command Line

Windows:

```cmd
set-window-state.cmd notepad max      REM maximize, standard title bar
set-window-state.cmd notepad restore  REM normal size, title bar back
set-window-state.cmd notepad full     REM maximize with the title bar hidden
```

Linux:

```bash
./set-window-state.sh PROCESS max      # maximize, standard title bar
./set-window-state.sh PROCESS restore  # normal size, title bar back
./set-window-state.sh PROCESS full     # maximize with the title bar hidden
```

The first argument is the exact name of the process; the second is
exactly one of `max`, `restore` or `full`, in lowercase. On Windows that
is the image name without `.exe`; on Linux it is matched literally
against the executable basename (`/proc/<pid>/exe`) and the kernel
process name (`/proc/<pid>/comm`). No path, wildcard, `.exe` completion
or case folding is ever applied. Run the entry without arguments for
the full usage screen; on Linux `--help` also prints it and exits `0`.

## Exit codes

`0` — every window reached the requested state; `1` — no window for
that process, an unsupported host, a missing Linux display/tool, or a
window refused the change; `2` — a missing argument, a third argument,
or anything other than `max`/`restore`/`full`; the entry prints the full
syntax.

## Requirements

- Windows 10/11 with the built-in Windows PowerShell (`powershell`), no
  extra install. If `powershell` is missing, the entry reports
  `'powershell' is not recognized as an internal or external command,
  operable program or batch file.` and exits `9009`.
- Linux with `python3`, `wmctrl` and `xprop` (`x11-utils`), and an X11
  or XWayland display (`DISPLAY` set). Native Wayland windows are not
  visible to these tools; a process whose window is native Wayland
  reports no window found. On Debian/Ubuntu:

  ```bash
  sudo apt install wmctrl x11-utils python3
  ```

## Guarantees

- Exact process-name match only: the name you pass is matched
  literally — never rewritten, never completed, no wildcards, no case
  folding — and no other process or application's window is ever
  touched
- No key or mouse input and no activation request: Windows never calls
  `SetForegroundWindow`; Linux never calls `wmctrl -a`. The window
  manager may still choose to focus a window when its state changes
- `max` is the standard maximized state with the title bar: Windows sets
  the frame bits and `IsZoomed`; Linux sets `maximized_vert` and
  `maximized_horz` and clears `fullscreen`
- `restore` is the normal state with the title bar: Windows restores the
  normal rectangle; Linux clears `fullscreen` and both maximized states,
  and the window manager hands back its saved geometry
- `full` is borderless fullscreen: Windows clears `WS_CAPTION` and
  `WS_THICKFRAME` and covers the monitor; Linux maximizes first and then
  sets the EWMH `fullscreen` state. Linux `restore` after `full` returns
  to the pre-`max` size, matching the Windows behaviour
- Running the same command twice is a no-op: a window already in the
  requested state receives no change request
- Success is reported only after re-reading the window state; a window
  that did not reach the requested state is reported as `[FAIL]` and
  makes the entry exit `1`
- Never starts, closes or modifies the process itself, its settings or
  its files
- Linux fullscreen covers the monitor chosen by the window manager (the
  window's current monitor), not an arbitrary rectangle; EWMH support
  and exact focus behaviour depend on the window manager

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
