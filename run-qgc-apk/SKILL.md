---
name: run-qgc-apk
description: Run the QGroundControl APK on a 1440x3120 Android virtual device (S24 Plus). Derives the APK path from the current QGC repo (build_android/package/QGroundControl64.apk) and delegates to run-apk-on-avd. Use when asked to run QGC on an emulator, to show QGC on a virtual device, or to launch QGC at a phone-sized resolution.
---

## Commands

```bash
./run-qgc-apk.sh [QGC_REPO_ROOT]
run-qgc-apk.cmd [QGC_REPO_ROOT]     # Windows; drag the QGC repo folder onto it
```

## APK path resolution

Without `--abi`,
`<QGC_ROOT>/build_android/android-build/build/outputs/apk/release/android-build-release-signed.apk`
(arm64) is preferred, then the arm64 dist copy, then the x86_64 build, then
`<QGC_ROOT>/dist/*.apk`, then
`<QGC_ROOT>/build_android/package/QGroundControl64.apk`. With `--abi`, the
ABI's build output is selected first, then its dist copy. Use
`--abi x86_64` for an x86_64 emulator. The QGC root is resolved from the
first positional argument (if a directory), the current git repo root, or the
sibling `qgc` directory next to this tools repo.

## Options

All options after the optional QGC root are forwarded to `run-apk-on-avd`:
`--avd`, `--resolution` (default `1440x3120`), `--timeout`, `--no-boot-wait`,
`--headless`, `--gpu`, `--sdk-root`, `--api`, `--image-tag`, `--abi`, and
`--software-emulation`.

## Exit codes

`0` — APK launched, `1` — QGC root or APK not found, emulator/adb unavailable,
install failed, or boot timed out, `2` — bad usage or no QGC root resolvable.

## Guarantees

- Derives the APK path from the QGC repo; never modifies QGC source or build
  artifacts
- `--abi x86_64|arm64-v8a` selects both the APK and the emulator ABI;
  `--apk PATH` overrides the search
- `--window-size` / `--window-position` move or resize the emulator window
- Delegates to `run-apk-on-avd`, so the emulator opens a visible window at
  the requested resolution and the APK is installed and launched
- Automatically provisions the Android command-line tools, emulator, adb,
  system image, and AVD when they are missing
- Idempotent: re-running re-installs (`-r`) without removing the emulator
