Usage: set-window-state <process> <max|restore|full>
       (Windows: set-window-state.cmd, Linux: set-window-state.sh)

Set the window state of every top-level window of a running process.

  <process>  exact process name (no path, no wildcards, no case
             folding; Windows: image name without .exe; Linux: exact
             executable or kernel process name)
  max        maximize, standard title bar
  restore    normal size, title bar back
  full       maximize with the title bar hidden (borderless)

Exactly two arguments are required; the state must be one of the three
words above, in lowercase. max and restore always bring the standard
frame back; restore also returns the window to its normal size.

Linux uses wmctrl and xprop (X11/XWayland), so DISPLAY must be set and
native Wayland windows are not visible to the tool.

Exit codes: 0 = every window reached the requested state,
            1 = no window for that process, unsupported host, missing
                tool/display, or a window refused,
            2 = bad usage
