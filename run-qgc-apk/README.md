# Run the QGroundControl APK on an Android Virtual Device

Install the QGroundControl APK onto the 1440x3120 Android virtual device
(S24 Plus) and show it in a running emulator window. The APK path is derived from the current
QGC repository — no need to locate the APK manually. The Android SDK,
emulator and system image are installed automatically by
`run-apk-on-avd`. Use when asked to run QGC on an emulator, to test QGC
or to verify QGC on a virtual device at a phone-sized
resolution.

## Command Line

```bash
./run-qgc-apk.sh [QGC_REPO_ROOT]
run-qgc-apk.cmd [QGC_REPO_ROOT]      # Windows, or drag the QGC repo folder onto it
```

## How the APK path is found

With `--abi`, the build output is preferred, then the dist copy:
arm64-v8a uses `<QGC_ROOT>/build_android/.../android-build-release-signed.apk`
and x86_64 uses `<QGC_ROOT>/build_android_x86_64/.../android-build-release-signed.apk`,
then `<QGC_ROOT>/dist/QGroundControl-<abi>[-novideo].apk`.
Without `--abi`, the arm64
`<QGC_ROOT>/build_android/android-build/build/outputs/apk/release/android-build-release-signed.apk`
is preferred, then `<QGC_ROOT>/dist/QGroundControl-arm64-v8a.apk`, then the
x86_64 build (`<QGC_ROOT>/build_android_x86_64/...`, then
`<QGC_ROOT>/dist/QGroundControl-x86_64*.apk`), then any
`<QGC_ROOT>/dist/*.apk`, then
`<QGC_ROOT>/build_android/package/QGroundControl64.apk`. Use
`--abi x86_64` to run the native x86_64 build on an x86_64 emulator. Use `--apk PATH` to
pick a file explicitly.

The default is the arm64 `build_android` APK. On an x86_64 emulator pass
`--abi x86_64` to use the native x86_64 build instead of running the arm64
APK through ARM translation.

The QGC root is resolved from:
1. the first positional argument, if it is a directory
2. `git rev-parse --show-toplevel` from the current working directory
3. the sibling `qgc` directory next to this tools repo

## Options

All options after the optional QGC root are forwarded to
`run-apk-on-avd`.

| Flag                   | Default       | Description                                                                |
| ---------------------- | ------------- | -------------------------------------------------------------------------- |
| `--avd`                | `s24-plus`    | AVD name to create or reuse                                                |
| `--resolution`         | `1440x3120`   | Display resolution passed to the emulator skin                             |
| `--api`                | `35`          | Android API level for the system image                                     |
| `--image-tag`          | `google_apis` | System-image tag                                                           |
| `--abi`                | none          | Select the APK and emulator ABI (`x86_64` or `arm64-v8a`)                  |
| `--apk`                | none          | Use this APK instead of searching                                          |
| `--timeout`            | `600`         | Boot timeout in seconds                                                    |
| `--no-boot-wait`       | false         | Install once adb connects; do not wait for boot                            |
| `--headless`           | false         | Hide the emulator window (default: visible window)                         |
| `--window-size`        | built-in      | Resize the emulator window after launch                                    |
| `--scale`              | emulator      | Emulator window scale factor                                               |
| `--window-position`    | built-in      | Move the emulator window after launch                                      |
| `--gpu`                | `swangle`     | GPU mode: `auto`, `host`, `software`, `swangle`, `swiftshader`, `lavapipe` |
| `--software-emulation` | false         | Allow very slow emulation without hardware virtualization                  |

## Exit codes

`0` — APK installed and launched, `1` — QGC root or APK not found, SDK or
launch failed, `2` — bad usage or no QGC root resolvable.

## Requirements

Nothing pre-installed beyond a QGC build. `run-apk-on-avd` installs the
Android SDK, emulator and system image automatically; all artifacts land
under `~/Android/Sdk` (override with `--sdk-root`). `--software-emulation`
is needed when `/dev/kvm` is unavailable.

## Guarantees

- Derives the APK path from the QGC repo; never modifies QGC source or build
  artifacts
- Delegates to `run-apk-on-avd`, so the SDK, emulator and AVD are set up
  automatically and the emulator is started in a visible window at the requested
  resolution and kept running in the background
- Idempotent: re-running re-installs (`-r`) without removing the emulator
