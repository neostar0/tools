# Stop a Process by Exact Name

Stop running processes by exact name, cross-platform. Use when asked to
kill or stop a process by name, when a hung program must be closed, or
before rebuilding a binary that is still running. A process that is not
running counts as success.

## Command Line

```cmd
stop-process.cmd <name>    REM Windows
```

```bash
./stop-process.sh <name>   # Linux/macOS
```

Run the entry without arguments for the full usage screen.

## Exit codes

`0` — nothing matching is running (already stopped counts), `1` — a match
survived, `2` — no arguments or a second name; the entry prints the full
syntax.

## Guarantees

- Exact OS name match only (`taskkill /IM`, `pkill -x`); never touches
  other processes. On Windows that is the full image name, `.exe`
  included — no name is ever rewritten
- Graceful first (WM_CLOSE / SIGTERM), force (`/F` / `-9`) after 3s
- Linux matches the process name (15-char limit there)
