Usage: set-qgc-window-state max|restore|full
       (Windows: set-qgc-window-state.cmd, Linux: set-qgc-window-state.sh)

Set the window state of a running QGroundControl.

  max      maximize every QGC window (standard title bar)
  restore  restore every QGC window to its normal size (title bar back)
  full     maximize and hide the title bar (borderless)

Exactly one lowercase argument is required; nothing else is accepted.
max and restore always bring the standard frame back; restore also
returns the window to its normal size.

Linux delegates to set-window-state.sh with the exact process name
QGroundControl and needs wmctrl, xprop and an X11/XWayland display.

Exit codes: 0 = every QGC window reached the requested state,
            1 = no QGC window found, unsupported host, missing
                tool/display, or a window refused,
            2 = bad usage
