# build-qgc5

Build a QGroundControl 5 checkout (CMake and Qt 6) inside Docker, using that
checkout's own `deploy/docker` builder image. Use it instead of installing Qt
and the native toolchain on the host. For QGroundControl 4 (qmake), use
`build-qgc`.

## Command Line

```bash
build-qgc5                              # build ./ with the ubuntu variant (Release)
build-qgc5 ~/qgroundcontrol             # build another checkout
build-qgc5 --build-type Debug -j8      # Debug with 8 parallel jobs
build-qgc5 --variant android            # build the Android APK image
build-qgc5 --clean --rebuild-image      # fresh build directory and image
build-qgc5 --list-variants              # show the checkout's variants
```

On Windows, run the same arguments through `build-qgc5.cmd` with Docker Desktop
and Python on `PATH`.

## Options

| Flag                 | Default           | Description                                        |
| -------------------- | ----------------- | -------------------------------------------------- |
| `QGC_ROOT`           | current directory | QGroundControl 5 checkout (or its subdirectory)    |
| `-b`, `--build-type` | `Release`         | `Release`, `Debug`, `RelWithDebInfo`, `MinSizeRel` |
| `--variant`          | `ubuntu`          | Variant from the checkout's `variants.json`        |
| `-j`, `--jobs`       | all cores         | Parallel build jobs                                |
| `--build-dir`        | `<root>/build`    | Build output (`<root>/build-aarch64` for aarch64)  |
| `--image`            | variant's image   | Docker image tag                                   |
| `--clean`            | off               | Remove the build directory before building         |
| `--rebuild-image`    | off               | Rebuild the image with `--no-cache`                |
| `--list-variants`    | off               | List variants from the checkout and exit           |
| `-h`, `--help`       | -                 | Print the usage screen and exit                    |

Variants are read from `<root>/deploy/docker/variants.json`; the default set is
`ubuntu`, `ubuntu-2204`, `ubuntu-2604`, `debian`, `fedora`, `arch`, `aarch64`,
and `android`.

## Output

The image is built once and reused. Build artifacts go to the build directory
above (for example `build/` with the AppImage and install tree, or
`build/android-build` for the Android variant). The container runs as your UID
and GID, so files are not owned by root.

Run the deployed application with the generated AppImage or
`<build-dir>/AppRun`. Do not run `<build-dir>/Release/QGroundControl` directly:
it is the unstaged linker output and cannot find the bundled Qt and GStreamer
libraries, so it fails with errors such as
`libQt6Bluetooth.so.6: cannot open shared object file`.

## Exit codes

`0` — build succeeded; `1` — Docker is missing, the image build failed, or the
QGC build failed; `2` — bad usage or `QGC_ROOT` is not a QGroundControl 5
checkout.

## Requirements

- Docker with a running daemon
- Python 3 (the `.sh` entry uses `python3`; the `.cmd` entry uses `python`)
- A QGroundControl 5 checkout containing `CMakeLists.txt`,
  `deploy/docker/Dockerfile`, and `deploy/docker/variants.json`
- Network access on the first run, while the image downloads Qt and the system
  dependencies

Passing a QGroundControl 4 checkout fails with "use build-qgc for QGC 4".

## Guarantees

- Builds only inside the selected build directory; source files are not modified
- Reuses an existing image and build directory between runs
- Builds the image with the checkout's own Dockerfile, target, and build
  arguments, so it stays in sync with upstream CI
- Runs the container as the host user and passes `JOBS`, `CLEAN_BUILD`, and the
  variant's FUSE options, matching `deploy/docker/run_docker.py`
- Reports failures as one line on stderr, never a traceback
