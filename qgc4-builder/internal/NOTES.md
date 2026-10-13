# Build QGC - Developer Notes

## Layout

| File                                                    | Purpose                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------ |
| `drop-qgc-folder-here.cmd`                              | Drag & drop entry; forwards `%*` to `internal/build-qgc.cmd` |
| `internal/build-qgc.cmd`                                | Windows build logic: qmake + nmake + deploy                  |
| `internal/set-qt-env.cmd`                               | Hardcodes `QT_ROOT`/`QMAKE`, fails if qmake.exe is missing   |
| `internal/vc.cmd`                                       | Finds VS C++ tools via vswhere, calls `vcvars64.bat`         |
| `build-linux.sh`                                        | Linux entry: Docker build + WebSockets dependency install    |
| `internal/docker/Dockerfile-build-linux`                | Self-contained image: Ubuntu 20.04 + Qt 5.15.2               |
| `internal/docker/install-qt-linux.sh`                   | Qt install via aqtinstall, run by the Dockerfile             |
| `internal/install-qtwebsockets.sh`                      | Copies the bundled Qt 5.15.2 WebSockets lib into staging     |
| `internal/deps/qtwebsockets-5.15.2-linux-gcc_64.tar.gz` | Exact Qt 5.15.2 `libQt5WebSockets.so.5`                      |
| `internal/usage.md`                                     | Usage screen printed by `build-linux.sh -h`                  |
| `internal/NOTES.md`                                     | This file                                                    |

## How to Run Tests

No automated tests (the Windows path needs the Windows toolchain). Manual
verification:

```cmd
internal\build-qgc.cmd <QGC_ROOT>            :: debug (default)
internal\build-qgc.cmd <QGC_ROOT> release
```

The Linux dependency helper is checkable on its own: create an empty
`<staging>/Qt/libs`, run `internal/install-qtwebsockets.sh <staging>`, and
confirm `libQt5WebSockets.so.5` resolves. A second run must be a no-op.

## Detection Rules

- Qt: default `C:\Qt\5.15.2\msvc2019_64\bin\qmake.exe`, set in
  `set-qt-env.cmd`; override with the `QT_ROOT` / `QMAKE` environment
  variables. Missing → one-line error, exit 1.
- Visual Studio: `vswhere.exe -latest -products * -requires
  Microsoft.VisualStudio.Component.VC.Tools.x86.x64`; none found → exit 1.
- Build dir: `build\Desktop_Qt_5_15_2_MSVC2019_64bit-Debug|Release` under
  the QGC root, created if missing.

## Algorithm

1. Parse args: `QGC_ROOT` (required), config `debug|release` (default
   `debug`), extra qmake args (positions 3-9 only).
2. `call set-qt-env.cmd`, then `call vc.cmd`; either failing stops the build.
3. `mkdir` + `cd` into the shadow build directory.
4. Run qmake on `qgroundcontrol.pro` with `-spec win32-msvc` and
   `CONFIG+=<config> CONFIG+=qml_<config>`.
5. `nmake /NOLOGO`.
6. Deploy into `<build dir>\staging`: `windeployqt` (with `--qmldir src`),
   geoservices plugins, SDL2/OpenSSL DLLs, plus `msvcp140.dll` /
   `vcruntime140.dll` on release.
7. Print the final build directory.

## Linux Algorithm (`build-linux.sh`)

1. Resolve the script through symlinks (`build-qgc`) so `internal/` is found.
2. Parse args: `QGC_ROOT` (default `$PWD`), `-j N`/`-jN` (default
   `max(2, nproc/4)`), `--clean`; `-h`/`--help` prints `internal/usage.md`.
   Unknown flags or a `QGC_ROOT` without `qgroundcontrol.pro` exit 2.
3. Build the self-contained image (`internal/docker/Dockerfile-build-linux`)
   if absent (`qgc-linux-docker`), then `docker run` it with the QGC root
   mounted at `/project/source` and a ccache dir at `/cache`.
4. On build failure, wipe `build/` and retry the whole build once (guards
   against stale object files).
5. Drop the transient `cache/` ccache dir.
6. Run `internal/install-qtwebsockets.sh <QGC_ROOT>/build/staging` to place
   the Qt 5.15.2 WebSockets runtime the upstream post-link step omits.

`install-qtwebsockets.sh` skips when `libQt5WebSockets.so.5` already exists,
extracts the bundled tarball to a temp dir, and copies the `.so.5.15.2` plus
its `so.5` / `so.5.15` symlinks into `<staging>/Qt/libs`.

The image is self-contained: `Dockerfile-build-linux` installs the toolchain
and Qt 5.15.2 via `aqtinstall`, so the build never reads the QGC repo's own
`deploy/docker/` files.

## Known Limitations

- **Windows build needs Visual Studio; Linux build needs Docker** — there is
  no native Linux qmake build here.
- **Qt patch version is exact** — Qt checks the patch number in
  `QObjectPrivate`'s constructor, so only Qt 5.15.2's
  `libQt5WebSockets.so.5` works; 5.15.3 aborts with "Cannot mix incompatible
  Qt library".
- **Qt path** — the Windows build defaults to `C:\Qt\5.15.2\msvc2019_64`; set
  `QT_ROOT` (and `QMAKE` if needed) to use a different install.
- **Kit hardcoded** — build dir name assumes the
  `Desktop_Qt_5_15_2_MSVC2019_64bit` Qt kit.
- **Few forwarded args** — only `%3`..`%9` reach qmake.
- **Exit codes** — every failure returns 1; qmake/nmake exit codes are not
  propagated.

## Invariants to Preserve

1. **Never modify source** — only creates/updates `build/` under the QGC root.
2. **Fail loudly** — any missing dependency or failed step exits non-zero
   with a one-line message, never a traceback.
3. **Argument forwarding** — extra args go to qmake unchanged.
4. **Drag entry stays thin** — `drop-qgc-folder-here.cmd` only forwards `%*`.
