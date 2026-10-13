Usage: set-qgc-window-state max|restore|full

Set the window state of a running QGroundControl.

  max      maximize every visible QGC window (standard title bar)
  restore  restore every QGC window to its normal size (title bar back)
  full     maximize and hide the title bar (no caption, no thick frame)

Exactly one lowercase argument is required; nothing else is accepted.
max and restore always bring the standard frame back, so a window left
in the full state is returned to normal by either of them.

Exit codes: 0 = every QGC window reached the requested state,
            1 = no QGC window found, non-Windows host, or a window refused,
            2 = bad usage
