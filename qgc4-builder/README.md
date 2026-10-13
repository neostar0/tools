# Build QGroundControl (qmake/nmake)

Build QGroundControl with Qt's qmake/nmake instead of setting up the
Visual Studio environment by hand. Use INSTEAD of manually running
qmake/nmake.

## Drag & Drop (Windows)

Drag a **QGroundControl git repository folder** onto `drop-qgc-folder-here.cmd`
— builds Debug under `build\Desktop_Qt_5_15_2_MSVC2019_64bit-Debug\`.

## Command Line

```cmd
internal\build-qgc.cmd E:\MyQGC                 REM debug (default)
internal\build-qgc.cmd E:\MyQGC release
internal\build-qgc.cmd E:\MyQGC debug <qmake_args...>
```

## Arguments

| Arg             | Default  | Description                           |
| --------------- | -------- | ------------------------------------- |
| `QGC_ROOT`      | required | Path to QGroundControl git repository |
| `CONFIG`        | debug    | `debug` or `release`                  |
| `qmake_args...` | (none)   | Additional arguments passed to qmake  |

## Exit codes

`0` — success, `1` — build or environment failed (qmake/Visual Studio
missing, qmake/nmake failed), `2` — no arguments; the entry prints the
full supported syntax.

## Requirements

- Windows, Qt 5.15.2 msvc2019_64 (default `C:\Qt\5.15.2\msvc2019_64`; set
  `QT_ROOT`/`QMAKE` to override), Visual Studio 2019/2022 with C++ workload

## Guarantees

- Uses Qt 5.15.2 msvc2019_64 and finds VS 2019/2022 automatically
- Builds in `build\Desktop_Qt_5_15_2_MSVC2019_64bit-Debug|Release`
- Outputs the executable path on success
- Never modifies source files or git history — only the `build/`
  directory is created
