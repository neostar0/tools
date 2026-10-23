Usage:
    launch-realsense-viewer.sh [options] [-- APP_ARGS...]

Check whether realsense-viewer is installed. If it is missing, install
librealsense from source, then launch realsense-viewer.

Options:
    --check              Report whether realsense-viewer is installed and exit
    --reinstall, --force Install even when realsense-viewer is already present
    --no-launch          Install only; do not start realsense-viewer
    --source DIR         librealsense checkout directory
    --build-dir DIR      Build directory (default: <source>/build)
    --branch REF         Branch or tag to clone (default: master)
    --prefix DIR         Install prefix (default: /usr/local)
    --jobs N             Parallel build jobs (default: 2)
    --skip-kernel-patch  Do not run the upstream kernel-module patch script
    --skip-udev          Do not install the RealSense udev rules
    --dry-run            Print commands without changing the system
    -h, --help           Show this message

Exit codes:
    0  realsense-viewer is installed, installation succeeded, or --check found it
    1  realsense-viewer is missing (--check), or installation/launch failed
    2  bad usage
    The launched app's own exit code is returned when it closes.
