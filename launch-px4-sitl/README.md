# launch-px4-sitl

One command that gets PX4 SITL running: it resolves where your PX4 checkout
lives, clones it if you do not have one yet (latest GitHub release, with
submodules), builds SITL if the binary is missing, and launches the simulator.
The PX4 local path is remembered, so from the second run on it goes straight to
build-or-launch.

## Command Line

Linux/macOS only. The `launch-px4-sitl` name is put on `PATH` by
`init-tools-env`.

```bash
launch-px4-sitl                      # full flow, remembers the PX4 path
launch-px4-sitl --root ~/PX4-Autopilot   # use (and save) an explicit checkout
launch-px4-sitl --print-path        # show the stored PX4 location
launch-px4-sitl --set-path /projects/PX4-Autopilot   # store a path, exit
launch-px4-sitl --sim jmavsim --headless
launch-px4-sitl --help
```

## Options

| Flag/arg       | Default                  | Effect                                  |
| -------------- | ------------------------ | --------------------------------------- |
| `--root`       | stored path, else prompt | PX4 checkout; saved on first use        |
| `--set-path`   | -                        | Store the PX4 location and exit         |
| `--print-path` | -                        | Print the stored PX4 location and exit  |
| `--sim`        | `gz`                     | Simulator: `gz` (Gazebo) or `jmavsim`   |
| `--model`      | `gz_x500`                | Vehicle model, `gz` only                |
| `--world`      | `default`                | Gazebo world, `gz` only                 |
| `--headless`   | off                      | Launch without the simulator GUI        |
| `--branch`     | latest GitHub release    | Branch/tag to clone                     |
| `--rebuild`    | off                      | Build even if the binary already exists |
| `--no-stop`    | off                      | Do not stop a running PX4/Gazebo first  |
| `--help`       | -                        | Print this help and exit                |

Stored path lives in `${XDG_CONFIG_HOME:-~/.config}/launch-px4-sitl/config`
as `PX4_ROOT=<path>` (and `PX4_BRANCH=<tag>` after a clone).

## Exit codes

`0` — success (path printed, stored, or SITL launched); `1` — the location is
not a PX4 checkout, the clone or build failed, or the binary/rootfs is missing;
`2` — bad usage (unknown option or a missing option value).

## Requirements

Bash and Python 3.8+ (the `.sh` is a thin bootstrap that `exec`s the Python
implementation in `internal/px4sitl`), plus `git` and network access to clone.
Launching `gz` needs Gazebo (`gz`) on `PATH`; launching `jmavsim` needs the
jMAVSim jar built by `make`. Building PX4 needs a working C/C++ toolchain —
the tool creates a repo-local `.venv` and installs
`Tools/setup/requirements.txt` before building.

## Guarantees

- First run asks where PX4 should live and remembers the answer; later runs
  reuse it (an explicit `--root` always wins and is saved).
- Never re-clones over an existing PX4 checkout — if the path already is a
  checkout it is reused as-is.
- Builds only when `build/px4_sitl_default/bin/px4` is missing (or `--rebuild`).
- The build is self-contained: it prepares the PX4 python `.venv` before
  `make`, so a clean machine can build without a pre-provisioned environment.
- Deterministic and inspectable: it prints each decision (path, clone branch,
  whether it skipped the build) before acting.

Read `internal/NOTES.md` only if the output looks wrong or you need to change
the script.
