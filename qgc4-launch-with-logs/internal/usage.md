Usage: launch-qgc.sh [QGC_REPO_ROOT]

Launch QGroundControl with output tee'd to qgc_YYYY_MM_DD_HHMMSS.log in the
current directory. QGC_REPO_ROOT defaults to two levels above this script.

Exit codes: 0 = success, 1 = QGC root or executable not found, or launch failed,
            2 = more than one argument; other values are QGC's own exit code.
