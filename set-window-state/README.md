# Set the Window State of a Running Process

Maximize every window of a running process, restore them to their
normal size, or show them maximized with no title bar — without driving
the mouse or the keyboard. Use when a window must be shown full-screen,
when a maximized window has to go back to its previous size, or when
the title bar must not take space. A process with no window counts as a
failure, not a success.

## Command Line

```cmd
set-window-state.cmd notepad max      REM maximize, standard title bar
set-window-state.cmd notepad restore  REM normal size, title bar back
set-window-state.cmd notepad full     REM maximize with the title bar hidden
```

The first argument is the exact image name of the process (no `.exe`,
no path, no wildcards, no case folding); the second is exactly one of
`max`, `restore` or `full`, in lowercase. Run the entry without
arguments for the full usage screen.

## Exit codes

`0` — every window reached the requested state; `1` — no window for
that process, a non-Windows host, or a window refused the change; `2` —
a missing argument, a third argument, or anything other than
`max`/`restore`/`full`; the entry prints the full syntax.

## Requirements

Windows 10/11 with the built-in Windows PowerShell (`powershell`), no
extra install. If `powershell` is missing, the entry reports
`'powershell' is not recognized as an internal or external command,
operable program or batch file.` and exits `9009`.

## Guarantees

- Exact process-name match only: the name you pass is matched
  literally against the process image name — never rewritten, never
  completed, no wildcards, no case folding — and no other process or
  application's window is ever touched
- No `SetForegroundWindow`, no key or mouse input: `max` and `restore`
  only change the show state and the two frame bits; `full` is the only
  state that also sets a position and a size (the monitor rectangle)
- `full` stays maximized while borderless, so the window's own normal
  size survives: `restore` after `full` — and after `max` then `full` —
  brings back the size the window had before `full`, which is the size
  it had before `max`
- `full` clears exactly `WS_CAPTION` and `WS_THICKFRAME`; `max` and
  `restore` always set them back, so any of the three states leaves the
  window in a state the other two can undo
- Running the same command twice is a no-op
- Never starts, closes or modifies the process itself, its settings or
  its files

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
