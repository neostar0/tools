# internal/NOTES.md — set-qgc-window-state

Developer notes. Never loaded by an agent; the interface is
`README.md`.

This tool is only the QGroundControl wrapper. All window behaviour,
matching, verification and output live in the sibling
`../set-window-state` tool; nothing here may duplicate that logic.

## Layout

- `../set-qgc-window-state.cmd` — Windows entry: validates exactly one
  lowercase state, then calls
  `..\set-window-state\set-window-state.cmd QGroundControl <state>`.
- `../set-qgc-window-state.sh` — Linux entry: validates exactly one
  lowercase state, then execs
  `../set-window-state/set-window-state.sh QGroundControl <state>`.
- `usage.md` — the usage screen used by both entries.
- `test_qgc_window_state.py` — argument-surface and delegation tests
  for both entries. It never runs a real state change.

## Why the process name is QGroundControl

The generic tool matches a process, not a window title. The QGC binary
is named `QGroundControl` on both platforms, so that is the name fixed
here. The visible title is not stable: branded builds may show names
such as `AiseedGCS`, and the same binary can change its title at
runtime. Matching the title would be a different tool with different
failure modes.

Linux additionally requires an X11/XWayland QGC window; `wmctrl` cannot
see native Wayland clients.

## Invariants

1. The wrapper never implements window logic itself: no `wmctrl`, no
   `xprop`, no Win32 call belongs in this folder.
2. Exactly one argument, exactly `max`/`restore`/`full`, case-sensitive;
   anything else prints `usage.md` and exits 2.
3. The process name is always `QGroundControl`, never derived from the
   current directory, a title or user input.
4. The generic tool's exit code is propagated unchanged: 0 success,
   1 no window / unsupported host / missing tool or display / refused,
   2 bad usage.
5. `.cmd` stays CRLF; `.sh` stays LF and resolves symlinks.

## Manual verification

Windows:

```cmd
set-qgc-window-state.cmd                       & rem usage, exit 2
set-qgc-window-state.cmd max restore           & rem usage, exit 2
set-qgc-window-state.cmd toggle                & rem usage, exit 2
set-qgc-window-state.cmd max                   & rem QGC maximized, exit 0
set-qgc-window-state.cmd full                  & rem borderless fullscreen, exit 0
set-qgc-window-state.cmd restore               & rem pre-max size, exit 0
```

Linux:

```bash
set-qgc-window-state/set-qgc-window-state.sh --help   # usage, exit 0
set-qgc-window-state/set-qgc-window-state.sh          # usage, exit 2
set-qgc-window-state/set-qgc-window-state.sh toggle   # usage, exit 2
set-qgc-window-state/set-qgc-window-state.sh max      # QGC maximized, exit 0
set-qgc-window-state/set-qgc-window-state.sh full     # fullscreen, exit 0
set-qgc-window-state/set-qgc-window-state.sh restore  # pre-max size, exit 0
```

With QGC closed, `max` must print
`[FAIL] no window found for process QGroundControl.` and exit 1.
