# build-qgc5 - Developer Notes

## Layout

| File                          | Purpose                                                   |
| ----------------------------- | --------------------------------------------------------- |
| `build-qgc5.sh`               | Linux entry; resolves symlinks, prints usage, runs Python |
| `build-qgc5.cmd`              | Windows entry; forwards to Python or prints usage (CRLF)  |
| `internal/build_qgc5.py`      | All logic: root/variant discovery, docker build and run   |
| `internal/test_build_qgc5.py` | Standard-library unit tests                               |
| `internal/usage.md`           | Usage screen and exit-code meanings                       |

## How to Run Tests

```bash
python3 internal/test_build_qgc5.py
python3 test_repo.py          # repo-wide audit, from the tools root
```

## Detection Rules

- A QGC 5 checkout has `CMakeLists.txt`, `deploy/docker/Dockerfile`, and
  `deploy/docker/variants.json`. Without an explicit root, search the current
  directory and its parents.
- A directory with `qgroundcontrol.pro` and no QGC 5 files is QGC 4; the error
  points at `build-qgc` so the user does not build the wrong tree.
- Variants come from the checkout's own `variants.json`; no variant names are
  hardcoded except the default (`ubuntu`) and the `aarch64` build-directory
  special case.
- The image is reused when `docker image inspect` finds it. `--rebuild-image`
  forces `docker build --no-cache`; the tool never pulls implicitly.

## Algorithm

1. Parse arguments; reject conflicting roots, bad jobs, and unknown flags with
   exit 2.
2. Resolve and validate the checkout, load its variants, and handle
   `--list-variants` without touching Docker.
3. Resolve the image tag, build directory (`build-aarch64` for `aarch64`), and
   jobs (all cores by default).
4. Optionally remove the build directory (`--clean`), then create it.
5. Build the image from the checkout's Dockerfile, target, and build arguments
   when it is missing or `--rebuild-image` is given.
6. Run `docker run --rm` as the host UID/GID with `HOME=/tmp`, `JOBS`, and
   `CLEAN_BUILD`, plus FUSE options for variants that need them.
7. Report the build directory and any generated AppImage/`AppRun` on success,
   or one error line on failure. The `Release/QGroundControl` linker output is
   not deployable on its own.

## Known Limitations

- Requires Docker and Python; the first image build needs network access and can
  take a long time.
- Artifact names depend on the upstream variant; the tool reports the build
  directory rather than guessing an AppImage/APK filename.
- The `--clean` flag deletes the chosen build directory; `--build-dir` is not
  restricted to the checkout, so a typo can remove an unrelated directory.
- Windows runs Python without a mapped UID, so files can be root-owned in the
  bind mount (Docker Desktop usually remaps this).

## Invariants to Preserve

1. **The checkout owns the build recipe** - never copy or fork the upstream
   Dockerfile, targets, or variant build arguments into this tool.
2. **Never modify the source tree** - only the selected build directory and
   Docker images change.
3. **Fail loudly and briefly** - one stderr line, exit 1 for runtime failures
   and 2 for usage/checkout errors; no tracebacks.
4. **Stay in sync with `run_docker.py`** - the run environment (UID, HOME,
   JOBS, CLEAN_BUILD, FUSE options) should match the upstream script.
