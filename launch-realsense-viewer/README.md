# launch-realsense-viewer

One command that checks whether the RealSense Viewer (`realsense-viewer`)
is installed, installs librealsense from source only when it is missing,
and then launches the app. Use it when a machine needs a working RealSense
viewer but you do not want to repeat the source-build steps by hand.

The install follows RealSense's
[Linux Ubuntu installation from source](https://dev.realsenseai.com/installation/linux-ubuntu-installation-from-source/):
APT build dependencies, a `librealsense` checkout, udev rules, the kernel
module patch, a Release build with examples, and `cmake --install`.

## Command Line

Linux/Ubuntu only.

```bash
./launch-realsense-viewer.sh                     # install if missing, then launch
./launch-realsense-viewer.sh --check             # exit 0 if installed, 1 if not
./launch-realsense-viewer.sh --skip-kernel-patch # skip kernel module patching
./launch-realsense-viewer.sh --reinstall         # rebuild even if already installed
./launch-realsense-viewer.sh --no-launch         # install only
./launch-realsense-viewer.sh --dry-run           # print the plan, change nothing
./launch-realsense-viewer.sh -- --help           # pass arguments to the app
```

## Options

| Flag/arg              | Default                                      | Effect                                          |
| --------------------- | -------------------------------------------- | ----------------------------------------------- |
| `--check`             | off                                          | Report installation status and exit             |
| `--reinstall`         | off                                          | Build and install even if the app exists        |
| `--force`             | off                                          | Alias for `--reinstall`                         |
| `--no-launch`         | off                                          | Stop after installation                         |
| `--source DIR`        | `~/.local/share/launch-realsense-viewer/librealsense` | Existing checkout or clone target      |
| `--build-dir DIR`     | `<source>/build`                             | CMake build directory                           |
| `--branch REF`        | `master`                                     | Branch or tag used when cloning                 |
| `--prefix DIR`        | `/usr/local`                                 | CMake install prefix                            |
| `--jobs N`            | `2`                                          | Parallel build jobs (`-jN`)                     |
| `--skip-kernel-patch` | off                                          | Do not run the upstream kernel patch script     |
| `--skip-udev`         | off                                          | Do not install the RealSense udev rules         |
| `--dry-run`           | off                                          | Print commands without executing them           |
| `APP_ARGS`            | -                                            | Arguments after `--` are forwarded to the app   |
| `-h`, `--help`        | -                                            | Print the usage screen and exit                 |

## Exit codes

`0` — the app is installed, installation and launch succeeded, or `--check`
found it; `1` — `--check` found it missing, or installation/launch failed;
`2` — bad usage. Once the app starts, its own exit code is returned when it
closes.

## Requirements

Ubuntu 20.04, 22.04 or 24.04 with `sudo`, network access, and enough disk
space for the librealsense build. The first run needs an interactive
terminal for the `sudo` password prompt and can take a long time because it
builds the SDK and patches kernel modules. `--skip-kernel-patch` and
`--skip-udev` are available for environments where those system-level steps
must be handled separately.

The tool never runs `apt-get upgrade`/`dist-upgrade`; it only runs
`apt-get update` and installs the build packages that are still missing.
`apt-get update` is best-effort: a broken third-party repository is reported
as a warning but does not abort the install, which continues with the existing
package lists.

## Guarantees

- Checks `realsense-viewer` first; an existing installation is reused and
  launched without rebuilding
- Installs only missing APT packages, and reuses an existing librealsense
  checkout instead of cloning over it
- Kernel patch failures are reported but do not block the SDK build; use
  `--skip-kernel-patch` when kernel modules are managed elsewhere
- Builds with `-j2` by default, including the upstream kernel patch script,
  to avoid overheating machines that struggle above `-j2`; `--jobs N`
  overrides it
- Adds `-lidn2` automatically when libidn2 development files are installed,
  fixing the bundled-libcurl `undefined reference to idn2_*` link error
- `--check` and `--dry-run` make no system changes
- Launches the app as the current user, never as root
