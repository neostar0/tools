# Run an APK on an Android Virtual Device

Install an APK onto an Android emulator and launch it at a fixed
1440x3120 resolution (Samsung S24 Plus aspect). Use when asked to run an
APK on an emulator or virtual device, to show an app on a virtual
device, or to verify an app at a phone-sized resolution. The tool installs the Android
SDK, emulator and system image automatically, creates the AVD at the
requested resolution, boots the emulator with a visible window, installs
the APK and launches it so the app can be seen.

## Command Line

```bash
./run-apk-on-avd.sh APK_PATH
run-apk-on-avd.cmd APK_PATH              # Windows, or drag the APK onto it
```

## Options

| Flag                   | Default         | Description                                                                |
| ---------------------- | --------------- | -------------------------------------------------------------------------- |
| `APK_PATH`             | (required)      | Path to the APK to install and run                                         |
| `--avd`                | `s24-plus`      | AVD name to create or reuse                                                |
| `--resolution`         | `1440x3120`     | Display resolution passed to the emulator skin                             |
| `--api`                | `35`            | Android API level for the system image                                     |
| `--image-tag`          | `google_apis`   | System-image tag (e.g. `google_apis`, `default`)                           |
| `--abi`                | `x86_64`        | System-image ABI                                                           |
| `--port`               | `5554`          | Emulator console port                                                      |
| `--timeout`            | `600`           | Boot timeout in seconds                                                    |
| `--sdk-root`           | `~/Android/Sdk` | Android SDK root directory                                                 |
| `--emulator`           | auto            | Path to the emulator binary                                                |
| `--no-boot-wait`       | false           | Install once adb connects; do not wait for boot                            |
| `--headless`           | false           | Hide the emulator window (default: visible window)                         |
| `--window-size`        | built-in        | Resize the host emulator window `WxH`                                      |
| `--scale`              | emulator        | Emulator window scale factor `FLOAT`                                       |
| `--window-position`    | built-in        | Move the host emulator window `X,Y`                                        |
| `--gpu`                | `swangle`       | GPU mode: `auto`, `host`, `software`, `swangle`, `swiftshader`, `lavapipe` |
| `--software-emulation` | false           | Allow very slow emulation without hardware virtualization                  |

## Exit codes

`0` — APK installed and launched, `1` — APK missing, SDK/emulator install
failed, AVD creation failed, emulator did not register, boot timed out, or
install/launch failed, `2` — bad arguments.

## Requirements

Nothing pre-installed. The tool downloads the Android command-line tools,
installs the emulator, adb and a system image via `sdkmanager`, creates the
AVD at the requested resolution, boots the emulator with a visible window,
installs the APK and launches it. All artifacts land under `~/Android/Sdk` (override
with `--sdk-root`). `--software-emulation` is needed when `/dev/kvm` is
unavailable. An APK whose only ABI is `arm64-v8a` runs through ARM
translation on an x86_64 emulator; build a native x86_64 APK with
`build-qgc-apk --abi x86_64`. Recent Android emulators (35.2+) reject
arm64 guests on x86_64 hosts, so `--abi arm64-v8a` is only usable on an
arm64 host or a physical device.

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
- Stop the running emulator with `adb -s emulator-<port> emu kill`
