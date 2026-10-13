# internal/NOTES.md — set-window-state

Developer notes. Never loaded by an agent; the interface is
`README.md`.

This tool is deliberately application-agnostic: no file here may name
a concrete application, not even in a comment. An application-specific
wrapper (one that knows which process to pass) lives in its own tool
folder and calls this one.

## Layout

- `../set-window-state.cmd` — entry, a launcher: it prints `usage.md` +
  `pause` only when run with no arguments (so a double-click still
  shows the screen), otherwise it hands `%*` to `window_state.ps1` and
  propagates its exit code. It does **not** validate anything — the
  argument rules belong to the script alone, one copy only.
- `window_state.ps1` — the implementation: argument handling, the
  platform guard, the compile-and-load step, per-window failure
  reporting, output.
- `Native.cs` — P/Invoke declarations, Win32 constants and structs,
  plus the thin wrappers that turn a Win32 failure into an exception
  (and the DPI-context enter/restore).
- `WindowStateController.cs` — the window logic: find the target windows of a
  *given* process name, apply a `WindowState` and verify the result.
- `usage.md` — the usage screen, printed by the entry.
- `test_window_state.py` — smoke test for the argument/platform paths,
  the source layout and the normal-rectangle regression.

## How the C# is loaded

Both `.cs` files are read as text and handed to a **single**
`Add-Type -TypeDefinition` call, so they compile as one unit and
`WindowStateController` can call `Native` directly. Two `Add-Type` calls would
produce two assemblies that cannot see each other's types (and
`-ReferencedAssemblies` cannot point at an in-memory type).

Consequences to preserve:

- Each `.cs` declares its own `namespace WindowControl { ... }` block
  and keeps its `using` directives **inside** that block. C# requires
  `using` directives at the top of a compilation unit, so concatenating
  two files that put them at file scope does not compile.
- Both files stay pure ASCII. Windows PowerShell 5.1 reads a BOM-less
  file as ANSI; a mangled comment is not worth an encoding bug.
- Nothing is precompiled and no DLL is produced: the user needs no
  compiler, no build step and no extra install. The compile happens in
  memory on every run.
- The type check after `Add-Type` (`'WindowControl.WindowStateController' -as
  [type]`) is what turns a compile failure into a clean `[FAIL]` with
  the real compiler errors, instead of a misleading "Unable to find
  type" from the first call site.

## How to run the tests

```bash
python3 internal/test_window_state.py                 # direct
python3 -m unittest discover set-window-state/internal -v
python3 test_repo.py                                  # whole repo
```

The smoke test needs `pwsh` or `powershell` on `PATH`; without either it
skips the cases that run the script. The real window manipulation has to
be verified by hand on Windows (see below) — no test here may touch a
live window.

## Detection rules

A window is a target when **all** hold: it is a top-level window from
`EnumWindows`, `IsWindowVisible` is true, its title is non-empty, and
its `GetWindowThreadProcessId` pid belongs to a process whose image
name is exactly the one the caller passed.

- The process list is read once with `Process.GetProcessesByName`
  inside `WindowStateController.FindTopLevelWindows`: a literal name, no
  wildcards, no case folding, no `.exe` rewriting — whatever the caller
  passes is what is matched, and a wrong name is the caller's problem,
  never something to "fix" here (LESSONS.md).
- An absent process yields an empty array and `[FAIL] no window found
  for process <name>.`, never a silent success; a genuine lookup failure
  throws and is reported.
- Skip reasons: tool windows, hidden splash/dialog windows and other
  applications are excluded by the visible/title/pid tests. Matching by
  window title is deliberately avoided — titles change with the
  application's own state.

## The three states

| State     | `IsZoomed` | frame bits (`WS_CAPTION` + `WS_THICKFRAME`) |
| --------- | ---------- | ------------------------------------------- |
| `max`     | true       | set                                         |
| `restore` | false      | set                                         |
| `full`    | true       | cleared                                     |

The frame mask is `0x00C40000` (`WS_CAPTION` `0x00C00000` |
`WS_THICKFRAME` `0x00040000`). Only these two bits are ever touched;
every other style bit (`WS_SYSMENU`, min/max buttons, toolkit bits) is
read-modify-write preserved. Because `max`/`restore` require the frame
bits, either of them undoes a `full` — no state has to be remembered
between runs.

**The normal rectangle must survive.** Every window keeps a "normal
rectangle" (`WINDOWPLACEMENT.rcNormalPosition`): the size `SW_RESTORE`
hands back. Windows overwrites it whenever the window is resized *while
in its normal state*, and leaves it alone while the window is zoomed or
minimized. So `full` must never resize a normal window — it maximizes
first and only then positions the window, which is what makes
`full` → `restore` (and `max` → `full` → `restore`) return to the size
the window had before `full`. Nothing is written to disk for this; the
window itself remembers.

## Algorithm

1. Print usage and exit 2 unless there are exactly two arguments and
   the second is `max`, `restore` or `full` in lowercase.
2. Exit 1 with a one-line stderr message when `$env:OS` is not
   `Windows_NT` (the Win32 calls below cannot work elsewhere).
3. Read `Native.cs` + `WindowStateController.cs` and compile them as **one**
   unit with `Add-Type` (see above).
4. `WindowStateController.FindTopLevelWindows($ProcessName)`: snapshot the
   process's pids, enumerate top-level windows, keep the targets.
5. Exit 1 with `[FAIL] no window found for process <name>.` when there
   is none — an absent process is a failure here, because nothing was
   ever set.
6. Per target `WindowStateController.ApplyState($h, $state)`: if the frame
   bits disagree with the requested state, set or clear them
   (`GetWindowLongPtr`/`SetWindowLongPtr`, read-modify-write) and push
   `SWP_FRAMECHANGED | SWP_NOACTIVATE` via `SetWindowPos` with
   `SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER` so the non-client area is
   rebuilt **without** moving or activating the window. The frame goes
   first so `SW_MAXIMIZE` measures the borderless window.
7. Then apply the show state:
   - `max` / `restore`: `ShowWindow` with `SW_MAXIMIZE` (3) or
     `SW_RESTORE` (9) when **either** the frame bits were just touched
     **or** `IsZoomed` disagrees with the request. The frame change
     invalidates the cached maximize rect (it is computed from the
     frame style), so re-applying is mandatory even when `IsZoomed`
     already agrees; see the incident below.
   - `full`: `SW_MAXIMIZE` **first**, then `SWP_FRAMECHANGED` again,
     then `SetWindowPos` to the monitor rectangle. The order is the
     fix for the incident below: a resize before the maximize would
     overwrite the normal rectangle and `restore` could not go back.
8. A target whose frame bits and `IsZoomed` both already match is not
   touched at all — this is what makes a repeat run a no-op.
9. `ShowWindow`'s return value is "was previously visible", not success,
   so **verification is the only success signal**: re-read both
   `IsZoomed` and the frame bits and require both to match, and for
   `full` also require `IsZoomed` to still be true (that is what keeps
   the window reversible) and the outer rectangle to equal the monitor
   rectangle. Any target that is wrong is counted and reported.
10. Print `[OK] <state>: N window(s) ...` on stdout and exit 0 when
    every target is right. Otherwise exit 1 after printing, on stderr,
    one grep-able `[FAIL] ...` headline per problem **followed by the
    full exception detail** (`Write-Failure`: exception type, message,
    .NET stack, inner exceptions, script position) — the bare message is
    never the whole report.

### Incident: a frame change but no show state (Oct 2026)

The first version only called `ShowWindow` when `IsZoomed` disagreed,
so after `max` a following `full` changed the frame bits but skipped
the show state — the window kept the maximize rect computed for the
*other* frame and looked wrong, while the tool still reported `[OK]`
(both checked values were true). Fix: a frame change always re-applies
`ShowWindow`. The verification stayed as it was; it checked the right
values, the missing call was the bug.

### Incident: `full` then `restore` did not go back to the old size (Oct 2026)

`full` used to `SW_RESTORE` the window and *then* `SetWindowPos` it to
the monitor rectangle. That resize happened while the window was in its
normal state, so Windows overwrote the window's normal rectangle with
the borderless fullscreen one. A later `restore` therefore came back to
the fullscreen rectangle (plus the restored frame), and the pre-`full`
size was gone — including the pre-`max` size after `max` → `full`,
which is the behaviour every other Windows app gets right.

Fix: `full` maximizes first and only then positions the window, so the
resize replaces the *maximized* rectangle and the normal rectangle is
left untouched; verification now also requires `IsZoomed` to be true
after `full`, because a borderless window that is not maximized has
already lost its normal rectangle. Nothing is persisted on disk: the
window itself is the storage, which is why the invariant "never resize
a normal window" must not be weakened.

## Known limitations

- **Several windows per process**: every matching window is set; the
  count in the message is the number of windows found, not processes.
- **Elevation**: if the target process runs as administrator and this
  tool does not, UIPI may swallow `ShowWindow`/`SetWindowPos`.
  Verification then fails and the tool exits 1 instead of reporting a
  false success — run the entry elevated in that case.
- **Toolkit apps may repaint the frame**: apps that react to
  `WM_NCCALCSIZE` can flicker briefly in the full state, and an
  application-internal fullscreen (its own F11-style path) may re-add
  its own decorations. The next `max`/`restore` run reconciles the two
  frame bits.
- **`full` covers the whole monitor**: the target rectangle is
  `rcMonitor`, not `rcWork`, so the taskbar is covered too. Only the
  monitor the window currently sits on is used.
- **Activation**: `SW_MAXIMIZE` and `SW_RESTORE` are both documented by
  Win32 as "activates and displays the window", so a window may come to
  the front. The tool never asks for focus itself (no
  `SetForegroundWindow`, `SWP_NOACTIVATE` on the frame change).
- **Minimized window + `max`/`full`**: `IsZoomed` is false for a
  minimized window, so the command maximizes it — it does not first
  restore it.
- Windows-only: there is no `.sh` entry, and no Linux/macOS code path
  beyond the exit-1 guard.

## Invariants to preserve when editing

1. Argument matching stays strict and case-sensitive: the state is
   `max`/`restore`/`full` only, anything else exits 2. Never normalise,
   complete or rewrite the process name either (`LESSONS.md`): the
   caller passes a literal name and that literal is what gets matched.
2. Success is reported only after re-reading **both** `IsZoomed` and
   the frame bits; never trust `ShowWindow`'s or `SetWindowLongPtr`'s
   return value as the success signal.
3. The only style bits ever written are `WS_CAPTION` and
   `WS_THICKFRAME`; everything else is preserved by read-modify-write.
4. Every frame change is followed by a `ShowWindow` of the requested
   show state — never skip it because `IsZoomed` already agrees; the
   maximize rect belongs to the frame style it was computed with.
5. `full` maximizes **before** it positions the window; a borderless
   window that is not maximized fails verification. This is what keeps
   the normal rectangle — and therefore `restore` — working.
6. Absent process = exit 1, and the message goes to stderr as one line.
7. A failure prints a `[FAIL]` headline plus the whole exception; never
   `$_.Exception.Message` alone, never an empty `catch`.
8. No file in this tool may mention a concrete application: it is the
   generic half, and an application-specific wrapper is a separate
   tool. The README guarantees above must be updated in the same edit
   as any change to matching, states, output or exit codes.
9. `set-window-state.cmd` stays CRLF and keeps `%~dp0` quoted paths.

## Manual verification on Windows

```cmd
set-window-state\set-window-state.cmd                     & rem usage screen, exit 2
set-window-state\set-window-state.cmd notepad             & rem usage screen, exit 2
set-window-state\set-window-state.cmd notepad toggle      & rem usage screen, exit 2
set-window-state\set-window-state.cmd notepad max         & rem notepad maximized, title bar visible, exit 0
set-window-state\set-window-state.cmd notepad full        & rem title bar gone, still maximized, exit 0
set-window-state\set-window-state.cmd notepad full        & rem no-op, exit 0
set-window-state\set-window-state.cmd notepad max         & rem title bar back, still maximized, exit 0
set-window-state\set-window-state.cmd notepad full        & rem title bar gone again, geometry still correct
set-window-state\set-window-state.cmd notepad restore     & rem back to the size notepad had before the first max, exit 0
```

Close the process first for the last case: with nothing running the
command must print `[FAIL] no window found for process notepad.` and
exit 1.
