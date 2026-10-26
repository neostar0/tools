---
name: android-avd
description: Open, close and position Android Virtual Devices. Provisions the Android SDK, emulator and system image, creates the AVD, waits for boot, and moves/resizes the emulator window. Use when an emulator must be visible, placed at a specific size/position, or stopped.
---

## Commands

```bash
./android-avd.sh open --window-size 900x416 --window-position 40,80
./android-avd.sh geometry --avd s24-plus --window-size 1200x555
./android-avd.sh close --avd s24-plus
./android-avd.sh status
```

## Options

| Flag                | Default     | Description                            |
| ------------------- | ----------- | -------------------------------------- |
| `--avd`             | `s24-plus`  | AVD name; non-x86_64 ABIs get a suffix |
| `--abi`             | `x86_64`    | System-image ABI                       |
| `--resolution`      | `1440x3120` | Guest display resolution               |
| `--window-size`     | built-in    | Host window size `WxH`                 |
| `--scale`           | emulator    | Emulator window scale factor           |
| `--window-position` | built-in    | Host window position `X,Y`             |
| `--headless`        | false       | No visible window                      |
| `--gpu`             | `swangle`   | Emulator GPU mode                      |

## Exit codes

`0` — success, `1` — SDK/AVD/emulator/window operation failed, `2` — bad
usage.

## Guarantees

- Installs the Android SDK, emulator, system image and AVD when missing
- Reuses a running emulator on the same port instead of starting another
- Window geometry uses `wmctrl` on Linux, PowerShell on Windows and AppleScript
  on macOS; it never changes the guest resolution
- `close` stops the emulator via `adb emu kill`
