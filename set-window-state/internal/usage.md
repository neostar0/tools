Usage: set-window-state <process> <max|restore|full>

Set the window state of every top-level window of a running process.

  <process>  exact image name of the process, for example notepad
             (no .exe, no path, no wildcards, no case folding)
  max        maximize, standard title bar
  restore    normal size, title bar back
  full       maximize with the title bar hidden (borderless)

Exactly two arguments are required; the state must be one of the three
words above, in lowercase. max and restore always bring the standard
frame back, so a window left in the full state is returned to normal by
either of them.

Exit codes: 0 = every window reached the requested state,
            1 = no window for that process, non-Windows host, or a window refused,
            2 = bad usage
