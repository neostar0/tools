Usage: launch-qgc.sh [QGC_REPO_ROOT]

Launch QGroundControl with output tee'd to qgc_YYYY_MM_DD_HHMMSS.log in the
current directory.

The repository is selected in this order:
  1. the QGC_REPO_ROOT argument
  2. the QGC_ROOT environment variable
  3. the current directory, walking up to the checkout root
  4. the checkout containing this tool, if any

A checkout is recognised by qgroundcontrol.pro or qgroundcontrol.qrc. The
launcher never searches sibling clones, so running it from repo B launches
B even when repo A sits next to it.

Exit codes: 0 = success, 1 = no checkout found, executable not found, Linux
            preflight failed (not in dialout group and fix declined, or run as
            root), or launch failed,
            2 = more than one argument; other values are QGC's own exit code.
