---
name: run-apk-on-avd
description: Run an APK on an Android virtual device at 1440x3120 (S24 Plus). Installs the Android SDK, emulator and system image automatically, creates the AVD at the requested resolution, boots the emulator with a visible window, installs the APK and launches it so the app can be seen and interacted with. Use when asked to run/test an APK on an emulator or virtual device, to show an app on a virtual device, or to verify an app at a phone-sized resolution.
---

## Commands

```bash
./run-apk-on-avd.sh APK_PATH
run-apk-on-avd.cmd APK_PATH     # Windows; drag the APK onto the .cmd instead
```

## Options

| Flag                   | Default       | Description                                                                |
| ---------------------- | ------------- | -------------------------------------------------------------------------- |
| `--avd`                | `s24-plus`    | AVD name to create or reuse                                                |
| `--resolution`         | `1440x3120`   | Display resolution passed to the emulator skin                             |
| `--api`                | `35`          | Android API level for the system image                                     |
| `--image-tag`          | `google_apis` | System-image tag                                                           |
| `--abi`                | `x86_64`      | System-image ABI                                                           |
| `--timeout`            | `600`         | Boot timeout in seconds                                                    |
| `--no-boot-wait`       | false         | Install once adb connects; do not wait for boot                            |
| `--headless`           | false         | Hide the emulator window (default: visible window)                         |
| `--window-size`        | built-in      | Resize the host emulator window `WxH`                                      |
| `--scale`              | emulator      | Emulator window scale factor `FLOAT`                                       |
| `--window-position`    | built-in      | Move the host emulator window `X,Y`                                        |
| `--gpu`                | `swangle`     | GPU mode: `auto`, `host`, `software`, `swangle`, `swiftshader`, `lavapipe` |
| `--software-emulation` | false         | Allow very slow emulation without hardware virtualization                  |

## Exit codes

`0` — APK installed and launched, `1` — APK missing, SDK/emulator install
failed, AVD creation failed, emulator did not register, boot timed out, or
install/launch failed, `2` — bad arguments.

## Guarantees

- Installs the Android SDK, emulator, system image and AVD automatically;
  re-running reuses what is already installed and only re-installs the APK
- Starts the emulator in a visible window by default at exactly the
  requested resolution and leaves it running so the APK can be seen;
  pass `--headless` for a background run
- Never modifies the APK; the only disk writes are the SDK/AVD artifacts
  the tools themselves create
- Idempotent: re-running with the same APK re-installs (`-r`) without
  removing the emulator
- arm64-only APKs run through ARM translation on x86_64; build a native
  x86_64 APK with `build-qgc-apk --abi x86_64`
- Recent emulators reject arm64 guests on x86_64 hosts, so `--abi arm64-v8a`
  only works on an arm64 host or a physical device
- Stop the running emulator with `adb -s emulator-<port> emu kill`
