# launch-px4-sitl — notes

## Layout

`launch-px4-sitl.sh` is a thin bootstrap: it resolves itself through any
symlinks, picks a Python 3 interpreter, and `exec`s
`internal/launch_px4_sitl.py`. All logic lives in the `internal/px4sitl`
package:

| Module                               | Responsibility                                   |
| ------------------------------------ | ------------------------------------------------ |
| `cli.py`                             | argparse setup and the top-level orchestration   |
| `resolve.py`                         | locating / prompting for the PX4 checkout        |
| `gitops.py`                          | latest release tag and `git clone`               |
| `builder.py`                         | `.venv` + requirements + `make px4_sitl_default` |
| `runner.py`                          | stop stale instances and `exec` the SITL binary  |
| `config.py`                          | the persistent `KEY=VALUE` store                 |
| `settings.py`                        | constants and the `Settings` dataclass           |
| `process.py` / `ui.py` / `errors.py` | subprocess, console, exit codes                  |

## Why the `.venv`

A clean PX4 checkout has no Python packages installed for whatever `python3`
happens to be on `PATH`. PX4's `CMakeLists.txt` prefers a repo-local
`.venv/bin/python` when it exists, so the tool creates one (with
`--system-site-packages`, to reuse preinstalled deps and keep the install
fast) and best-effort installs `Tools/setup/requirements.txt` before `make`.
If a single pip requirement fails to build, the tool warns and relies on the
system packages instead of aborting the whole build.

## Clone target

The default branch is the latest **stable** GitHub release (from
`releases/latest`), falling back to the highest `vX.Y` tag reachable via
`git ls-remote` when the API is unavailable. Set `--branch` to override.

## Port expectations after launch

The GCS mavlink instance uses the MAVLink-spec default remote port **14550**
(local bind `18570 + instance`); the offboard/API instance is
`14580 -> 14540`. No `-o`/`-t` override is injected, so remote forwarding is
left to an external `mavlink-router` if you need one.

## Test hook

`LAUNCH_PX4_SITL_RELEASES_JSON=<file>` makes the tag parser read a canned
GitHub `releases/latest` JSON instead of calling the network, so
`internal/test_gitops.py` stays hermetic.
