qml-preview - open a .qml file in a preview window

Usage:
  drop-qml-file-here.cmd FILE.qml [FILE.qml ...]    drag & drop, or command line

Each file opens in its own preview window, one after another: close a
window to let the next file open. QML errors stream into this console.

Exit codes:
  0    every preview closed cleanly
  1    a file is missing, or a preview failed (a QML error is the usual reason)
  2    no arguments given
  3    no QML runtime found (init-qt-env reports why), or init-qt-env is missing
