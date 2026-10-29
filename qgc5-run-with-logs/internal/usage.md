Usage: run-qgc5 [QGC_ROOT] [options] [-- QGC_ARGS...]

Launch a deployed QGroundControl 5 build (AppImage, AppDir/AppRun, or the
installed binary) with timestamped logs, core-dump capture, and QGC's CLI
logging enabled.

Arguments:
    QGC_ROOT              QGroundControl 5 checkout. Default: the current
                          directory or its nearest QGC 5 parent.
    --                   Pass remaining arguments to QGroundControl.

Options:
    --root DIR            Same as QGC_ROOT (for tooling).
    --build-dir DIR       Build/deploy directory (default: <root>/build)
    --executable PATH     Launch a specific binary or AppImage
    --categories C [C...] Log categories to enable (default: FactSystem.ParameterManager,
                          FactSystem.FactPanelController, MAVLink, Video.GStreamer,
                          Comms.LinkManager). Accepts comma-separated lists.
    --log-file FILE       Write logs to FILE (default: ./qgc5_YYYY_MM_DD_HHMMSS.log)
    --no-log-file         Output to console only, no log file
    --dump / --no-dump    Enable or disable core-dump preparation (default: enabled).
                          Sets ulimit -c unlimited; if QGC crashes the launcher writes
                          a crash report and tells you where to look for the core
                          (kernel core_pattern, apport, or systemd-coredump).
    --gst-dump [DIR]      Set GST_DEBUG_DUMP_DOT_DIR to capture GStreamer pipeline
                          .dot files (default DIR: ./qgc5_YYYY_MM_DD_HHMMSS_gst/)
    --pause               Wait for Enter before exiting (used by the .cmd wrapper)
    -h, --help            Show this message and exit

Detection priority (build dir):
    1. Newest *.AppImage (executable)
    2. <build-dir>/AppDir/AppRun
    3. <build-dir>/AppRun  (only if <build-dir>/usr/bin exists)
    4. *.app bundle (macOS)
    5. Release/QGroundControl(.exe)
    6. usr/bin/QGroundControl or bin/QGroundControl

Notes:
    - Appends --log-output and --logging <categories> unless they are passed
      via -- QGC_ARGS...
    - Running as root is refused (QGC exits on root).
    - If /dev/fuse is missing, AppImages are launched with APPIMAGE_EXTRACT_AND_RUN=1.
    - On Ubuntu, apport may collect cores; use apport-unpack or systemd-coredump's
      coredumpctl to inspect them. The launcher cannot force-write a core file if
      the system collector is configured.

Exit codes:
    0   success
    1   QGC root/build not found or launch failed
    2   bad usage
    130 interrupted by user
    < 0 signalled: reported as 128 - signal (e.g. SIGSEGV -> 134)
    other values are QGC's own exit code
