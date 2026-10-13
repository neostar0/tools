Usage: build-linux.sh [QGC_ROOT] [-j N] [--clean]

Build QGroundControl for Linux inside Docker using the bundled Qt 5.15.2
image (internal/docker/Dockerfile-build-linux), then install the
QtWebSockets runtime the upstream deploy step omits.

Arguments:
  QGC_ROOT       Path to the QGroundControl git repository (default: $PWD)
  -j, --jobs N   Parallel make jobs (default: max(2, nproc/4))
  -jN            Same as -j N (e.g. -j4)
  --clean        Remove build/ before building
  -h, --help     Show this message and exit

Exit codes: 0 = build succeeded, 1 = docker or build failed, 2 = bad usage,
QGC_ROOT is not a QGroundControl repository, or staging has no Qt/libs,
3 = bundled WebSockets archive missing
