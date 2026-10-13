# QML Previewer

Opens a `.qml` file in a preview window so you can see what it looks like
without running the whole application. Use to eyeball a component while
editing it, or to check that a file still renders after a change.
Runtime discovery belongs to the sibling tool `init-qt-env` (see its
README) — that tool resolves Qt, this one previews.

## Drag & Drop (Windows)

Drag one or more `.qml` files onto `drop-qml-file-here.cmd` — each file
opens in its own preview window, one after another, and QML errors
stream into this console until the window is closed.

## Command Line

Windows only, no Python needed:

```cmd
drop-qml-file-here.cmd FILE.qml            REM open one preview window
drop-qml-file-here.cmd A.qml B.qml         REM one window after another
cmd /c drop-qml-file-here.cmd FILE.qml     REM automation: exit code only, no pause
```

## Exit codes

`0` — every preview closed cleanly; `1` — a file is missing or a preview
failed (a QML error is the usual reason); `2` — no arguments (the entry
prints usage); `3` — no QML runtime found (`init-qt-env` reports why), or
`init-qt-env` is missing from the sibling folder.

## Requirements

Windows cmd, and the `init-qt-env` tool in place next to this folder
(`tools\init-qt-env\`) — through it a QML runtime: Qt 5.15.2
`qmlscene.exe` (default `C:\Qt\5.15.2\msvc2019_64`, or wherever
`QT_ROOT` points), else `qmlscene.exe` on `PATH`, else Qt 6's
`qmlscene6.exe`/`qml6.exe`. Without one of them the entry prints
`No QML runtime found`. The file must be loadable on its own: its
`import`s have to resolve from the file's own folder; the preview passes
no extra import paths.

## Guarantees

- Never modifies the `.qml` file or its folder: the preview runs with
  Qt's disk cache disabled, so no `.qmlc` files are written either
- One file, one window, opened in order; a missing file is reported and
  does not stop the other previews
- The runtime's exit code is the verdict: a file the runtime rejects
  fails the run even though the error text comes from Qt itself
- A wrong `QT_ROOT` is a hard error, never a silent fallback to another
  Qt (`init-qt-env` owns that contract)
- The console stays open while the window is up, so QML errors are
  visible; closing the window ends that preview
