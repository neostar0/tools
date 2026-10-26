---
name: qgc-android-builder
description: Build QGroundControl Android APKs for x86_64 and arm64-v8a with this repo's own Docker image. Use when an emulator needs a native x86_64 APK, when the arm64 device APK must be rebuilt, or when both ABIs are required.
---

## Commands

```bash
build-qgc-apk --abi all
build-qgc-apk --root ~/qgc --abi x86_64
build-qgc-apk --abi arm64-v8a --jobs 8
```

## Options

| Flag              | Default                      | Description                             |
| ----------------- | ---------------------------- | --------------------------------------- |
| `--abi`           | `arm64-v8a`                  | `x86_64`, `arm64-v8a`, or `all`         |
| `--out`           | `<root>/dist`                | Output directory                        |
| `--jobs`          | `4`                          | Parallel make jobs                      |
| `--image`         | `qgc-android-builder:latest` | Docker image                            |
| `--rebuild-image` | off                          | Rebuild the Docker image                |
| `--clean`         | off                          | Remove the ABI build directory          |
| `--x86-video`     | off                          | x86_64 with video (needs PIC GStreamer) |

## Exit codes

`0` — all requested ABIs built, `1` — build failed, `2` — bad usage.

## Guarantees

- Owns its Dockerfile under `docker/`; does not call the checkout's build script
- Reuses the Docker image and per-ABI build directories between runs
- x86_64 defaults to a UI build because the bundled GStreamer x86_64 static
  libraries are not PIC; arm64-v8a keeps video streaming
- arm64-v8a builds in the original `<root>/build_android`; x86_64 uses
  `<root>/build_android_x86_64`
- Leaves the signed APK in the original build directory; `--out` also
  copies it to `<out>/<name>-<abi>[-novideo].apk`
