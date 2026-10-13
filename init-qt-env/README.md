# init-qt-env

Resolves which Qt/QML runtime to use and sets `QMLSCENE` (and `QT_ROOT`
when the kit root is known) in the **current console**, the way
`vcvarsall.bat` does — so a human, another `.cmd` tool, or an agent can
address the runtime by name instead of every tool re-discovering it. Use
it by hand before running any QML tool, or `call` it from another batch
file (e.g. `qml-preview` does exactly that).

## Command Line

Windows only. It must be **`call`ed** from a batch file or cmd prompt:
a batch file that runs without `call` hands control away, and the
variables would be set in a child shell that then exits.

```cmd
call init-qt-env\init-qt-env.bat          REM from another .cmd: sets the variables here
call init-qt-env\init-qt-env.bat && "%QMLSCENE%" file.qml
cmd /c "call init-qt-env\init-qt-env.bat && echo %QMLSCENE%"    REM one-shot check
```

## Variables set

| Variable   | When                            | Value                                                    |
| ---------- | ------------------------------- | -------------------------------------------------------- |
| `QMLSCENE` | always, when a runtime exists   | full path to `qmlscene.exe` or `qml6.exe`                |
| `QT_ROOT`  | only when the kit root is known | the kit root: a valid `QT_ROOT` kept, or the default kit |

## Detection order

1. An existing `QT_ROOT`: it must contain `bin\qmlscene.exe`. A wrong
   value is an error (exit 1), never a fallback.
2. The default kit `C:\Qt\5.15.2\msvc2019_64` (same default as
   qgc4-builder).
3. `qmlscene.exe` on `PATH` — only `QMLSCENE` is set: a kit root cannot
   be derived from a random `bin` folder, so `QT_ROOT` stays unset.
4. Qt 6, with a warning line (a file written for Qt 5 may fail to load):
   `qmlscene6.exe`, then `qml6.exe` on `PATH`.

## Exit codes

`0` — a runtime was found and the variables are set. `1` — nothing was
found, or an existing `QT_ROOT` is wrong; the error line says why and
nothing usable is left set.

## Guarantees

- Never overrides a valid caller-chosen `QT_ROOT`: what you set is what
  is validated and kept
- Never guesses `QT_ROOT` from a `PATH` hit — a bare runtime gets
  `QMLSCENE` only
- Sets exactly two variables, `QMLSCENE` and `QT_ROOT`; on failure it
  clears `QMLSCENE` (a stale pointer is never left behind) and leaves
  `QT_ROOT` untouched
- Deliberately no `setlocal`: the variables persist for the caller —
  that is the point of the tool
- Changes no files and no other variables
