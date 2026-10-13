# Close QGroundControl

Close a running QGroundControl, cross-platform. Use when asked to close,
stop, or kill QGC, after a debug launch, before rebuilding QGC, or when
QGC is hung. A QGC that is not running counts as success.

## Command Line

```cmd
close-qgc.bat    REM Windows (double-click works)
```

```bash
./close-qgc.sh   # Linux/macOS
```

## Exit codes

`0` — QGC closed or was not running; `1` — QGC survived.

## Guarantees

- Exact name match only (`QGroundControl.exe`); never touches other processes
- Graceful first, force after 3s; not running returns immediately
