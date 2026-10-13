# Build QGC - Developer Notes

## Layout

| File                       | Purpose                                                      |
| -------------------------- | ------------------------------------------------------------ |
| `drop-qgc-folder-here.cmd` | Drag & drop entry; forwards `%*` to `internal/build-qgc.cmd` |
| `internal/build-qgc.cmd`   | Build logic: qmake + nmake + deploy                          |
| `internal/set-qt-env.cmd`  | Hardcodes `QT_ROOT`/`QMAKE`, fails if qmake.exe is missing   |
| `internal/vc.cmd`          | Finds VS C++ tools via vswhere, calls `vcvars64.bat`         |
| `internal/NOTES.md`        | This file                                                    |

## How to Run Tests

No automated tests (Windows-only toolchain). Manual verification:

```cmd
internal\build-qgc.cmd <QGC_ROOT>            :: debug (default)
internal\build-qgc.cmd <QGC_ROOT> release
```

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

## Known Limitations

- **Windows only** — there is no Linux/macOS entry point or `.sh` script.
- **Qt path** — defaults to `C:\Qt\5.15.2\msvc2019_64`; set `QT_ROOT`
  (and `QMAKE` if needed) to use a different install.
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
