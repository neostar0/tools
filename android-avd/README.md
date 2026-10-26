# Android AVD Control

Open, close and position Android Virtual Devices without going through Android
Studio. The tool provisions the Android SDK, emulator and system image on
first use, creates the AVD, waits for boot, and can move or resize the emulator
window. Use it when a build or a test needs a visible emulator, or when an
emulator window should be placed at a specific size/position.

## Command Line

```bash
./android-avd.sh open
./android-avd.sh open --avd s24-plus --window-size 900x416 --window-position 40,80
./android-avd.sh geometry --avd s24-plus --window-size 1200x555
./android-avd.sh close --avd s24-plus
./android-avd.sh list
./android-avd.sh status
```

## Options

| Command    | Option                   | Default       | Description                            |
| ---------- | ------------------------ | ------------- | -------------------------------------- |
| `open`     | `--avd`                  | `s24-plus`    | AVD name; non-x86_64 ABIs get a suffix |
| `open`     | `--abi`                  | `x86_64`      | System-image ABI                       |
| `open`     | `--api`                  | `35`          | Android API level                      |
| `open`     | `--image-tag`            | `google_apis` | System-image tag                       |
| `open`     | `--resolution`           | `1440x3120`   | Guest display resolution               |
| `open`     | `--port`                 | `5554`        | Emulator console port                  |
| `open`     | `--gpu`                  | `swangle`     | GPU mode                               |
| `open`     | `--headless`             | false         | No visible window                      |
| `open`     | `--scale`                | emulator      | Emulator window scale factor           |
| `open`     | `--window-size`          | built-in      | Host window size `WxH`                 |
| `open`     | `--window-position`      | built-in      | Host window position `X,Y`             |
| `open`     | `--no-boot-wait`         | false         | Return once adb connects               |
| `geometry` | `--window-size`          | unchanged     | Resize the running window              |
| `geometry` | `--window-position`      | unchanged     | Move the running window                |
| `close`    | `--avd`/`--port`/`--all` | -             | Which emulator to stop                 |

## Exit codes

`0` — success, `1` — SDK/AVD/emulator/window operation failed, `2` — bad
usage.

## Requirements

Linux uses `wmctrl` for window geometry (install it with
`sudo apt install wmctrl`); Windows and macOS use PowerShell and AppleScript.
The Android SDK is installed under `~/Android/Sdk` on first use (override with
`--sdk-root`).
