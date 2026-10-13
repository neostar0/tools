# Build QGroundControl

Build QGroundControl with Qt's qmake/nmake on Windows, or inside Docker on
Linux. Use INSTEAD of setting up the toolchain (Visual Studio or Qt) by hand.

## Linux (Docker)

```bash
./build-linux.sh                 # build ./ (current dir)
./build-linux.sh /path/to/QGC    # build another checkout
./build-linux.sh -j8             # 8 parallel make jobs
./build-linux.sh --clean -j1     # wipe build/ first, single job
```

Runs the tool's own self-contained image
(`internal/docker/Dockerfile-build-linux`, Ubuntu 20.04 + Qt 5.15.2) and builds
into `<QGC_ROOT>/build/staging`, then installs the Qt 5.15.2 WebSockets runtime
(`libQt5WebSockets.so.5`) that the upstream deploy step forgets. Without it
QGroundControl aborts at launch with
`libQt5WebSockets.so.5: cannot open shared object file`.

| Arg / flag     | Default      | Description                                        |
| -------------- | ------------ | -------------------------------------------------- |
| `QGC_ROOT`     | `$PWD`       | Path to QGroundControl git repository              |
| `-j`, `--jobs` | `max(2, nproc/4)` | Parallel make jobs (also accepts `-jN`)       |
| `--clean`      | off          | Remove `build/` before building                    |
| `-h`, `--help` | -            | Print the usage screen and exit                    |

### Exit codes

`0` — build and dependency install succeeded; `1` — Docker or the build
failed; `2` — bad usage, `QGC_ROOT` is not a QGroundControl repository, or the
staging tree has no `Qt/libs`; `3` — the bundled WebSockets archive is missing.

### Requirements

- Linux with Docker, and network access on the first run to build the Qt image
- The bundled `internal/docker/` (image recipe) and
  `internal/deps/qtwebsockets-5.15.2-linux-gcc_64.tar.gz` (ships with the tool)

### Guarantees

- Builds only inside `<QGC_ROOT>/build` and removes the transient `cache/`
  directory it creates
- Installs the exact Qt 5.15.2 `libQt5WebSockets.so.5` — Qt compares the patch
  version at load time, so a 5.15.3 or other stand-in aborts instead
- Retries once after wiping `build/` when an incremental build fails
- Idempotent: a re-run reuses the existing image and skips the dependency copy
  when the library is already present
- The image is self-contained — it never reads the QGC repository's own
  `deploy/docker/` files

## Windows (qmake/nmake)

Build QGroundControl with Qt's qmake/nmake instead of setting up the Visual
Studio environment by hand. Use INSTEAD of manually running qmake/nmake.

### Drag & Drop

Drag a **QGroundControl git repository folder** onto `drop-qgc-folder-here.cmd`
— builds Debug under `build\Desktop_Qt_5_15_2_MSVC2019_64bit-Debug\`.

### Command Line

```cmd
internal\build-qgc.cmd E:\MyQGC                 REM debug (default)
internal\build-qgc.cmd E:\MyQGC release
internal\build-qgc.cmd E:\MyQGC debug <qmake_args...>
```

### Arguments

| Arg             | Default  | Description                           |
| --------------- | -------- | ------------------------------------- |
| `QGC_ROOT`      | required | Path to QGroundControl git repository |
| `CONFIG`        | debug    | `debug` or `release`                  |
| `qmake_args...` | (none)   | Additional arguments passed to qmake  |

### Exit codes

`0` — success, `1` — build or environment failed (qmake/Visual Studio missing,
qmake/nmake failed), `2` — no arguments; the entry prints the full supported
syntax.

### Requirements

- Windows, Qt 5.15.2 msvc2019_64 (default `C:\Qt\5.15.2\msvc2019_64`; set
  `QT_ROOT`/`QMAKE` to override), Visual Studio 2019/2022 with C++ workload

### Guarantees

- Uses Qt 5.15.2 msvc2019_64 and finds VS 2019/2022 automatically
- Builds in `build\Desktop_Qt_5_15_2_MSVC2019_64bit-Debug|Release`
- Outputs the executable path on success
- Never modifies source files or git history — only the `build/` directory is
  created

Read `internal/NOTES.md` only if the output looks wrong or you need to change
the script.
