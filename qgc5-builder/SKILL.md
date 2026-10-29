---
name: qgc5-builder
description: Build a QGroundControl 5 (CMake/Qt 6) checkout inside Docker using the checkout's own deploy/docker image. Use when a QGC 5 tree must be compiled without a host Qt/toolchain, when reproducing a CI Docker build, or when an AppImage/APK is needed. Does not modify source files.
---

## Commands

```bash
build-qgc5                                   # Release, ubuntu variant, current checkout
build-qgc5 ~/qgroundcontrol -b Debug -j8     # Debug build with 8 jobs
build-qgc5 --variant android                 # Android APK image
build-qgc5 --clean --rebuild-image           # fresh build directory and image
build-qgc5 --list-variants                   # show the checkout's variants
```

## Options

| Flag                 | Default           | Description                                        |
| -------------------- | ----------------- | -------------------------------------------------- |
| `QGC_ROOT`           | current directory | QGroundControl 5 checkout                          |
| `-b`, `--build-type` | `Release`         | `Release`, `Debug`, `RelWithDebInfo`, `MinSizeRel` |
| `--variant`          | `ubuntu`          | Variant from `deploy/docker/variants.json`         |
| `-j`, `--jobs`       | all cores         | Parallel build jobs                                |
| `--build-dir`        | `<root>/build`    | Output directory                                   |
| `--image`            | variant image     | Docker image tag                                   |
| `--clean`            | off               | Remove the build directory first                   |
| `--rebuild-image`    | off               | Rebuild the image with `--no-cache`                |

## Exit codes

`0` — build succeeded, `1` — Docker/image/build failed, `2` — bad usage or the
root is not a QGroundControl 5 checkout.

## Guarantees

- Uses the checkout's own Dockerfile and variant build arguments, so it matches
  upstream CI; no Qt or toolchain is installed on the host
- Reuses the image and build directory between runs; artifacts are owned by the
  invoking user on Linux
- QGC 4 checkouts are refused with a pointer to `build-qgc`
- Never modifies source files; only `<root>/build` (or `--build-dir`) changes

Read `internal/NOTES.md` only if the output looks wrong or you need to change
the script.
