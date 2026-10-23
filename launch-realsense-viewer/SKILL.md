---
name: launch-realsense-viewer
description: Check for the RealSense Viewer (realsense-viewer), install librealsense from source on Ubuntu only when it is missing, then launch the app. Use when asked to install, verify, or start realsense-viewer on Linux.
---

## Commands

```bash
./launch-realsense-viewer.sh                     # install if needed, then launch
./launch-realsense-viewer.sh --check             # status only
./launch-realsense-viewer.sh --skip-kernel-patch # skip kernel module patching
./launch-realsense-viewer.sh --dry-run           # show the plan, change nothing
```

## Options

| Flag                  | Default     | Effect                                        |
| --------------------- | ----------- | --------------------------------------------- |
| `--check`             | off         | Exit 0 if installed, 1 if missing             |
| `--reinstall`         | off         | Rebuild even if the app exists                |
| `--no-launch`         | off         | Install only                                  |
| `--source DIR`        | user data   | librealsense checkout directory               |
| `--build-dir DIR`     | source/build | CMake build directory                        |
| `--branch REF`        | `master`    | Branch or tag to clone                        |
| `--prefix DIR`        | `/usr/local` | Install prefix                               |
| `--jobs N`            | `2`         | Parallel build jobs (`-jN`)                   |
| `--skip-kernel-patch` | off         | Skip the upstream kernel patch script         |
| `--skip-udev`         | off         | Skip the RealSense udev rules                 |
| `--dry-run`           | off         | Print commands without executing them         |

## Exit codes

`0` — installed/launched or `--check` found it; `1` — missing or
install/launch failed; `2` — bad usage. After launch, the app's own exit code
is returned.

## Guarantees

- Reuses an existing `realsense-viewer`; builds from source only when missing
- Reuses an existing checkout and installs only missing APT packages
- Builds with `-j2` by default, including the kernel patch script; `--jobs` overrides
- Adds `-lidn2` when libidn2 dev files exist, fixing bundled-libcurl link errors
- A failing `apt-get update` is a warning, not an abort; install continues
- Kernel patch failures are reported but do not stop the SDK build
- `--check` and `--dry-run` make no system changes; the app never runs as root
